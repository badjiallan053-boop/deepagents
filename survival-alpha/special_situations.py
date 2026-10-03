"""
Special situations scanner: SEC odd-lot tender offers (PAPER ONLY).

What it does
------------
* Polls the free SEC EDGAR full-text search index for recent tender-offer
  filings (SC TO-I, SC TO-T, their /A amendments, SC 13E4 and similar).
* Downloads each filing's full submission text (only for subject companies
  that have an exchange ticker in SEC's company_tickers.json; non-traded
  funds/BDCs are recorded as SKIPPED_NO_TICKER and never fetched).
* Parses offer terms with deterministic regexes: fixed price or modified
  Dutch auction range, expiration date, odd-lot priority clause (holders of
  fewer than 100 shares who tender all are bought before proration, incl. a
  record-date requirement if present), explicit conditions, extensions, and
  final results / termination in amendments.
* Computes a PAPER expected value per tender for an odd-lot position
  (<= 99 shares): p_complete * ((offer - market) * shares - fees).
  If no market price is available the EV is marked UNPRICED. Prices are
  never fabricated.
* Records a paper entry snapshot and, when final results are filed, a paper
  outcome, building a forward track record.

What it does NOT do
-------------------
No broker integration, no order placement, no live execution of any kind.
Everything here is research/paper bookkeeping.

Configuration (env)
-------------------
SPECIAL_SITUATIONS_ENABLED   default "false" - background poller off unless true
SEC_USER_AGENT               required by SEC fair-access policy ("Name email")
SPECIAL_POLL_SECONDS         default 1800
SPECIAL_LOOKBACK_DAYS        default 45
SPECIAL_SEC_MAX_RPS          default 5 (hard-capped at 9, SEC limit is 10/s)
SPECIAL_PRICE_SOURCE         "none" (default, EV unpriced) | "yahoo_chart"
                             (unofficial public endpoint, opt-in, labeled)
SPECIAL_ODD_LOT_SHARES       default 99 (capped at 99)
SPECIAL_BUY_COMMISSION_USD   default 0   (set to YOUR broker's real fees)
SPECIAL_TENDER_FEE_USD       default 0   (many brokers charge a tender/reorg fee)
SPECIAL_P_BASE               default 0.95 heuristic prior, completion probability
SPECIAL_HAIRCUT_FINANCING    default 0.85 multiplier if financing condition
SPECIAL_HAIRCUT_MINIMUM      default 0.90 multiplier if minimum-tender condition
SPECIAL_HAIRCUT_APPROVAL     default 0.90 multiplier if holder/regulatory approval
SPECIAL_HAIRCUT_UNKNOWN      default 0.95 multiplier per condition that could
                             not be determined from the text
"""
from __future__ import annotations

import asyncio
import gzip
import hmac
import html
import json
import logging
import os
import re
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import quote

import httpx
from sqlalchemy import text

log = logging.getLogger("special_situations")

TENDER_FORMS = [
    "SC TO-I", "SC TO-I/A",
    "SC TO-T", "SC TO-T/A",
    "SC 13E4", "SC 13E4/A",
    "SC14D1F", "SC14D1F/A",
]
ORIGINAL_FORMS = {"SC TO-I", "SC TO-T", "SC 13E4", "SC14D1F"}
# EDGAR full-text search matches amendments via root_forms; passing "/A" variants
# in the forms filter returns an inconsistent subset, so query root forms only.
FTS_ROOT_FORMS = ["SC TO-I", "SC TO-T", "SC 13E4", "SC14D1F"]
FTS_URL = "https://efts.sec.gov/LATEST/search-index"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/{acc}.txt"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1d&interval=1d"
MAX_SUBMISSION_BYTES = 12_000_000
MAX_TEXT_CHARS = 1_500_000
SKIP_DOC_TYPES = ("GRAPHIC", "ZIP", "PDF", "EXCEL", "XML", "JSON")

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}
_DATE = r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\.?\s+\d{1,2},?\s+\d{4})"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except ValueError:
        return default


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


def parse_month_date(s: str) -> Optional[str]:
    m = re.match(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", (s or "").strip())
    if not m:
        return None
    mon = MONTHS.get(m.group(1).lower())
    if not mon:
        return None
    try:
        return date(int(m.group(3)), mon, int(m.group(2))).isoformat()
    except ValueError:
        return None


def _num(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Submission (.txt) parsing
# ---------------------------------------------------------------------------

def html_to_text(raw: str) -> str:
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\s*\n\s*", " ", s)
    return s.strip()


def parse_header(raw: str) -> dict[str, Any]:
    head = raw.split("<DOCUMENT>", 1)[0][:200_000]

    def first(pat: str, src: str = head) -> Optional[str]:
        m = re.search(pat, src)
        return m.group(1).strip() if m else None

    subjects = []
    for block in re.split(r"\n(?=SUBJECT COMPANY:|FILED BY:|FILER:)", head):
        kind = block.split(":", 1)[0].strip()
        if kind not in {"SUBJECT COMPANY", "FILED BY", "FILER"}:
            continue
        subjects.append({
            "role": kind,
            "name": first(r"COMPANY CONFORMED NAME:\s*(.+)", block),
            "cik": (first(r"CENTRAL INDEX KEY:\s*(\d+)", block) or "").lstrip("0") or None,
            "form_type": first(r"FORM TYPE:\s*(.+)", block),
            "file_number": first(r"SEC FILE NUMBER:\s*(.+)", block),
        })
    filed = first(r"FILED AS OF DATE:\s*(\d{8})")
    return {
        "accession": first(r"ACCESSION NUMBER:\s*([\d-]+)"),
        "form": first(r"CONFORMED SUBMISSION TYPE:\s*(.+)"),
        "filed_date": f"{filed[:4]}-{filed[4:6]}-{filed[6:]}" if filed else None,
        "parties": subjects,
        "subject": next((p for p in subjects if p["role"] == "SUBJECT COMPANY"), None),
        "all_form_types": sorted({p["form_type"] for p in subjects if p.get("form_type")}),
    }


def extract_documents(raw: str) -> list[dict[str, str]]:
    out = []
    for m in re.finditer(r"(?s)<DOCUMENT>(.*?)</DOCUMENT>", raw):
        body = m.group(1)
        typ = (re.search(r"<TYPE>([^\n<]+)", body) or [None, ""])[1].strip()
        fn = (re.search(r"<FILENAME>([^\n<]+)", body) or [None, ""])[1].strip()
        if typ.upper().startswith(SKIP_DOC_TYPES) or fn.lower().endswith(
                (".jpg", ".jpeg", ".gif", ".png", ".pdf", ".zip", ".xlsx", ".xml", ".json")):
            continue
        tm = re.search(r"(?s)<TEXT>(.*?)(?:</TEXT>|$)", body)
        txt = html_to_text(tm.group(1) if tm else body)
        out.append({"type": typ, "filename": fn, "text": txt})
    return out


def submission_text(raw: str) -> str:
    docs = extract_documents(raw)
    return "\n\n".join(f"[[{d['type']} {d['filename']}]] {d['text']}" for d in docs)[:MAX_TEXT_CHARS]


# ---------------------------------------------------------------------------
# Term extraction (deterministic regexes; fragile by nature - see limitations)
# ---------------------------------------------------------------------------

_MONEY = r"(?:U\.?S\.?)?\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)"


def _snippet(t: str, start: int, end: int, pad: int = 160, cap: int = 700) -> str:
    a = max(0, start - pad)
    b = min(len(t), end + pad)
    return t[a:b].strip()[:cap]


def _mode(vals: list) -> Any:
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return Counter(vals).most_common(1)[0][0]


def extract_prices(t: str) -> dict[str, Any]:
    dutch_words = bool(re.search(r"dutch\s+auction", t, re.I))
    ranges = []
    for m in re.finditer(
        r"not\s+(?:less|greater|more)\s+than\s+" + _MONEY + r"(?:\s+per\s+(?:share|unit))?,?\s+"
        r"(?:and|nor)\s+not\s+(?:more|greater|less)\s+than\s+" + _MONEY, t, re.I):
        lo, hi = sorted([_num(m.group(1)), _num(m.group(2))])
        if lo and hi and lo > 0:
            ranges.append((lo, hi))
    for m in re.finditer(
        r"price\s+range\s+(?:of|from)\s+" + _MONEY + r"(?:\s+per\s+(?:share|unit))?\s+to\s+" + _MONEY, t, re.I):
        lo, hi = sorted([_num(m.group(1)), _num(m.group(2))])
        if lo and hi and lo > 0:
            ranges.append((lo, hi))
    fixed = []
    for m in re.finditer(
        r"(?:at\s+a\s+(?:cash\s+)?(?:purchase\s+|offer\s+)?price\s+of|purchase\s+price\s+of|offer\s+price\s+of|"
        r"price\s+per\s+share\s+of|for\s+cash\s+at)\s+" + _MONEY + r"\s+(?:in\s+cash\s+)?per\s+(?:share|unit)",
        t, re.I):
        v = _num(m.group(1))
        if v and v >= 0.01:
            fixed.append(v)
    # standard third-party (SC TO-T) wording: "for $10.50 per Share, net to the seller in cash"
    for m in re.finditer(r"\bfor\s+" + _MONEY + r"\s+per\s+(?:share|unit),?\s+net\s+to\s+the\s+(?:seller|holder)",
                         t, re.I):
        v = _num(m.group(1))
        if v and v >= 0.01:
            fixed.append(v)
    rng = _mode(ranges)
    nav = re.search(r"(\d{2,3}(?:\.\d+)?)\s*(?:%|percent)\s+of\s+(?:the\s+)?(?:its\s+|their\s+|the\s+Fund.s\s+)?"
                    r"(?:per[\s-]+share\s+)?net\s+asset\s+value", t, re.I) or \
        re.search(r"price\s+(?:per\s+share\s+)?equal\s+to\s+(?:the\s+)?(?:its\s+|the\s+Fund.s\s+)?(?:per[\s-]+share\s+)?"
                  r"net\s+asset\s+value", t, re.I)
    if nav and not rng:
        pct = _num(nav.group(1)) if nav.groups() else 100.0
        return {"offer_type": "NAV_BASED", "price_fixed": None, "price_low": None, "price_high": None,
                "currency": "USD", "nav_pct": pct,
                "nav_snippet": _snippet(t, nav.start(), nav.end(), pad=160, cap=400)}
    currency = "USD"
    if re.search(r"\bC(?:DN|AD)?\$\s?\d", t) and not re.search(r"U\.?S\.?\$|\$\s?\d", t):
        currency = "CAD"
    if rng and (dutch_words or not fixed):
        return {"offer_type": "DUTCH_AUCTION", "price_fixed": None,
                "price_low": rng[0], "price_high": rng[1], "currency": currency}
    if fixed:
        return {"offer_type": "FIXED_PRICE", "price_fixed": _mode(fixed),
                "price_low": None, "price_high": None, "currency": currency}
    return {"offer_type": "DUTCH_AUCTION" if dutch_words else "UNKNOWN", "price_fixed": None,
            "price_low": None, "price_high": None, "currency": currency}


def extract_expiration(t: str, amendment: bool = False) -> dict[str, Any]:
    def not_waiting_period(m: re.Match) -> bool:
        # "The waiting period under the HSR Act ... is scheduled to expire at 11:59 p.m. on ..." is NOT the offer
        return not re.search(r"waiting\s+period|HSR|Hart-Scott|antitrust|warrants?\b|options?\s+expire",
                             re.split(r"\.\s", t[max(0, m.start() - 220): m.start()])[-1], re.I)

    cands = [parse_month_date(m.group(1)) for m in re.finditer(
        r"expire[sd]?\s+at\s+.{0,170}?\bon\s+(?:[A-Za-z]+day,?\s+)?" + _DATE, t, re.I) if not_waiting_period(m)]
    cands += [parse_month_date(m.group(1)) for m in re.finditer(
        r"Expiration\s+(?:Date|Time)\W{0,20}(?:means|is|shall\s+mean)\s+.{0,170}?\bon\s+(?:[A-Za-z]+day,?\s+)?" + _DATE,
        t, re.I)]
    ext = []
    for m in re.finditer(
        r"extend\w*\s+(?:the\s+)?(?:expiration\s+(?:date|time)\s+(?:of\s+the\s+(?:tender\s+)?offer\s+)?|"
        r"(?:tender\s+)?offer\s+)?.{0,120}?(?:until|to)\s+.{0,90}?\bon\s+(?:[A-Za-z]+day,?\s+)?" + _DATE,
        t, re.I):
        d = parse_month_date(m.group(1))
        if d and not_waiting_period(m):
            ext.append(d)
    exp = _mode(cands)
    extended_to = max(ext) if (amendment and ext) else None
    if extended_to and (exp is None or extended_to > exp):
        exp = extended_to
    return {"expiration_date": exp, "extended": bool(extended_to), "expiration_candidates": sorted(set(c for c in cands if c))[:10]}


def extract_odd_lot(t: str) -> dict[str, Any]:
    mentions = [m for m in re.finditer(r"odd[\s\-\u2010-\u2014]*lot", t, re.I)]
    fewer = [m for m in re.finditer(r"fewer\s+than\s+100\s+(?:shares|units|common\s+shares)", t, re.I)]
    priority = False
    snippet = None
    record_date = None
    for fm in fewer:
        win = t[max(0, fm.start() - 1500): fm.end() + 1500]
        near_odd = bool(re.search(r"odd[\s\-\u2010-\u2014]*lot", win, re.I))
        prio = re.search(
            r"(?:not\s+(?:be\s+)?subject\s+to\s+(?:any\s+)?proration|priority|"
            r"before\s+(?:any\s+)?proration|prior\s+to\s+(?:any\s+)?proration|"
            r"without\s+(?:any\s+)?proration|will\s+not\s+be\s+prorated|first,?\s+(?:all|from))",
            win, re.I)
        if near_odd and prio:
            priority = True
            if snippet is None:
                snippet = _snippet(t, fm.start(), fm.end(), pad=260)
            before = t[max(0, fm.start() - 400): fm.start()]
            rd = re.search(r"as\s+of\s+the\s+close\s+of\s+business\s+on\s+" + _DATE, before, re.I) or \
                re.search(r"(?:of\s+record|record\s+date)\s+(?:as\s+of|on)\s+" + _DATE, before, re.I)
            if rd and record_date is None:
                record_date = parse_month_date(rd.group(1))
    return {
        "odd_lot_mentioned": bool(mentions),
        "odd_lot_priority": priority,
        "odd_lot_record_date": record_date,
        "odd_lot_snippet": snippet,
    }


def _cond(t: str, neg: list[str], pos: list[str]) -> dict[str, Any]:
    for p in neg:
        m = re.search(p, t, re.I)
        if m:
            return {"present": False, "evidence": _snippet(t, m.start(), m.end(), pad=80, cap=360)}
    for p in pos:
        cs = p.startswith("CS:")
        m = re.search(p[3:] if cs else p, t, 0 if cs else re.I)
        if m:
            return {"present": True, "evidence": _snippet(t, m.start(), m.end(), pad=80, cap=360)}
    return {"present": None, "evidence": None}


_NOT_COND = r"not\s+(?:be\s+)?(?:subject\s+to|conditioned\s+(?:up)?on|conditional\s+(?:up)?on|contingent\s+(?:up)?on)\s+"


def extract_conditions(t: str) -> dict[str, Any]:
    financing = _cond(t, [
        _NOT_COND + r"(?:any\s+|a\s+)?(?:minimum[^.]{0,120}?\s+or\s+)?(?:any\s+|a\s+)?(?:receipt\s+of\s+|obtaining\s+)?(?:any\s+)?financing",
        r"no\s+financing\s+condition",
        r"(?:is|are)\s+not\s+subject\s+to\s+(?:a|any)\s+financing\s+condition",
    ], [
        r"CS:Financing\s+Condition",
        r"conditioned\s+(?:up)?on\s+[^.]{0,160}financing",
    ])
    minimum = _cond(t, [
        _NOT_COND + r"(?:any\s+|the\s+|a\s+)?minimum\s+(?:number|amount|tender|of|condition)",
        r"no\s+minimum\s+(?:number|tender|condition)",
    ], [
        r"CS:Minimum\s+(?:Tender\s+)?Condition",
        r"conditioned\s+(?:up)?on\s+[^.]{0,120}minimum\s+(?:number|amount)",
    ])
    approval = _cond(t, [], [
        r"condition\w*\s+[^.]{0,200}(?:stockholder|shareholder|unitholder)\s+approval",
        r"condition\w*\s+[^.]{0,200}(?:HSR\s+Act|Hart-Scott-Rodino|regulatory\s+approval|antitrust)",
    ])
    other = _cond(t, [], [
        r"subject\s+to\s+(?:certain\s+|a\s+number\s+of\s+)?(?:other\s+)?conditions",
        r"Conditions\s+of\s+the\s+(?:Tender\s+)?Offer",
    ])
    delisting = _cond(t, [], [
        r"condition\w*\s+[^.]{0,240}(?:delist|deregist|cease\s+to\s+be\s+listed|Rule\s+13e-3)",
    ])
    return {
        "financing": financing,
        "minimum_tender": minimum,
        "holder_or_regulatory_approval": approval,
        "delisting_or_listing_related": delisting,
        "general_conditions": other,
    }


def extract_final_results(t: str, form: str) -> dict[str, Any]:
    """Final results / termination signals. Only meaningful for amendments."""
    out: dict[str, Any] = {"final": False, "preliminary": False, "terminated": False}
    if not (form or "").endswith("/A"):
        return out
    final_box = bool(re.search(
        r"final\s+amendment\s+reporting\s+the\s+results\s+of\s+the\s+tender\s+offer\W{0,10}\[\s*[xX\u2612\u2611]\s*\]", t))
    out["final_amendment_box_checked"] = final_box
    if re.search(r"announc\w*\s+(?:the\s+)?preliminary\s+results", t, re.I):
        out["preliminary"] = True
    final_words = bool(re.search(r"final\s+results", t, re.I))
    acc = None
    for m in re.finditer(
        r"(?:accepted\s+for\s+(?:purchase|payment)|taken\s+up\s+and\s+accepted\s+for\s+purchase|"
        r"has\s+taken\s+up|accepted|purchased)\s+(?:a\s+total\s+of\s+|an\s+aggregate\s+of\s+|approximately\s+)?"
        r"(\d{1,3}(?:,\d{3})+|\d{4,})\s+(?:shares|units|common\s+shares|of\s+its)", t, re.I):
        win = t[m.start(): m.end() + 400]
        pm = re.search(r"(?:at\s+(?:a|the)\s+(?:final\s+)?(?:purchase\s+)?price\s+of\s+|at\s+)" + _MONEY
                       + r"\s+per\s+(?:share|unit)", win, re.I)
        acc = (_num(m.group(1)), _num(pm.group(1)) if pm else None, _snippet(t, m.start(), m.end(), pad=120))
        if pm:
            break
    if acc:
        out["shares_accepted"] = acc[0]
        out["final_price"] = acc[1]
        out["results_snippet"] = acc[2]
    pr = re.search(r"approximately\s+(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)\s+of\s+(?:their|the|such)\s+(?:validly\s+)?tendered", t, re.I) or \
        re.search(r"proration\s+factor\s+(?:of|was|is)\s+(?:approximately\s+)?(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)", t, re.I)
    if pr:
        out["proration_pct"] = _num(pr.group(1))
    term = re.search(
        r"\b(?:has|have)\s+(?:been\s+)?terminated\s+(?:the\s+)?(?:tender\s+)?offer|"
        r"(?:tender\s+)?offer\s+(?:has|was)\s+(?:been\s+)?(?:terminated|withdrawn)|"
        r"announc\w+\s+(?:the\s+)?termination\s+of\s+(?:the|its)\s+(?:tender\s+)?offer|"
        r"withdr[ae]w\w*\s+(?:the|its)\s+(?:tender\s+)?offer", t, re.I)
    if term:
        out["terminated"] = True
        out["termination_snippet"] = _snippet(t, term.start(), term.end(), pad=160)
    out["final"] = bool((final_box or final_words) and acc and acc[1] is not None and not out["terminated"])
    if out["final"] and out["preliminary"] and not (final_box or re.search(r"announces?\s+final\s+results", t, re.I)):
        out["final"] = False
    return out


def extract_terms(raw: str) -> dict[str, Any]:
    hdr = parse_header(raw)
    t = submission_text(raw)
    form = hdr.get("form") or ""
    amendment = form.endswith("/A")
    terms: dict[str, Any] = {"header": hdr}
    terms.update(extract_prices(t))
    terms.update(extract_expiration(t, amendment=amendment))
    terms.update(extract_odd_lot(t))
    terms["conditions"] = extract_conditions(t)
    terms["results"] = extract_final_results(t, form)
    terms["going_private"] = bool("SC 13E3" in hdr.get("all_form_types", []) or form.startswith("SC 13E3")
                                  or re.search(r"\[\s*[xX]\s*\]\s*going-private\s+transaction", t))
    terms["text_chars"] = len(t)
    return terms


# ---------------------------------------------------------------------------
# Paper EV / outcome
# ---------------------------------------------------------------------------

def ev_assumptions() -> dict[str, Any]:
    return {
        "shares": max(1, min(99, env_int("SPECIAL_ODD_LOT_SHARES", 99))),
        "buy_commission_usd": env_float("SPECIAL_BUY_COMMISSION_USD", 0.0),
        "tender_fee_usd": env_float("SPECIAL_TENDER_FEE_USD", 0.0),
        "p_base": env_float("SPECIAL_P_BASE", 0.95),
        "haircut_financing": env_float("SPECIAL_HAIRCUT_FINANCING", 0.85),
        "haircut_minimum": env_float("SPECIAL_HAIRCUT_MINIMUM", 0.90),
        "haircut_approval": env_float("SPECIAL_HAIRCUT_APPROVAL", 0.90),
        "haircut_unknown": env_float("SPECIAL_HAIRCUT_UNKNOWN", 0.95),
        "note": ("heuristic priors, not estimated from data; fees default to 0 and must be set "
                 "to the user's actual broker commission + tender/reorg fee"),
    }


def completion_probability(conditions: dict[str, Any], a: dict[str, Any]) -> tuple[float, list[str]]:
    p = a["p_base"]
    applied = [f"base {a['p_base']}"]
    for key, hk in (("financing", "haircut_financing"), ("minimum_tender", "haircut_minimum"),
                    ("holder_or_regulatory_approval", "haircut_approval")):
        present = (conditions.get(key) or {}).get("present")
        if present is True:
            p *= a[hk]
            applied.append(f"{key} present x{a[hk]}")
        elif present is None and key != "holder_or_regulatory_approval":
            p *= a["haircut_unknown"]
            applied.append(f"{key} undetermined x{a['haircut_unknown']}")
    return round(max(0.0, min(1.0, p)), 4), applied


def compute_ev(tender: dict[str, Any], market_price: Optional[float], today: Optional[date] = None,
               assumptions: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    a = assumptions or ev_assumptions()
    today = today or utc_now().date()
    conditions = tender.get("conditions") or {}
    if isinstance(conditions, str):
        conditions = json.loads(conditions or "{}")
    p, applied = completion_probability(conditions, a)
    offer_lo = tender.get("price_fixed") if tender.get("price_fixed") is not None else tender.get("price_low")
    offer_hi = tender.get("price_fixed") if tender.get("price_fixed") is not None else tender.get("price_high")
    fees = a["buy_commission_usd"] + a["tender_fee_usd"]
    out: dict[str, Any] = {
        "model": "p_complete * ((offer - market) * shares - fees); Dutch uses range low (conservative)",
        "assumptions": a,
        "p_complete": p,
        "p_adjustments": applied,
        "offer_price_used": offer_lo,
        "offer_price_high": offer_hi,
        "market_price": market_price,
        "fees_usd": fees,
        "shares": a["shares"],
        "blockers": [],
    }
    if not tender.get("odd_lot_priority"):
        out["blockers"].append("no odd-lot priority clause detected: small lots would be prorated")
    rd = tender.get("odd_lot_record_date")
    if rd and rd < today.isoformat():
        out["blockers"].append(
            f"odd-lot priority requires ownership as of {rd}: shares bought now likely do NOT qualify")
    exp = tender.get("expiration_date")
    if exp and exp < today.isoformat():
        out["blockers"].append(f"offer expired {exp}")
    if (tender.get("currency") or "USD") != "USD":
        out["blockers"].append(f"non-USD offer ({tender.get('currency')}); not modeled")
    if tender.get("offer_type") == "NAV_BASED":
        out["status"] = "NAV_BASED_UNMODELED"
        out["ev_usd"] = None
        out["blockers"].append("offer priced off NAV at expiration; final price unknown until then")
        return out
    if offer_lo is None:
        out["status"] = "UNPARSED_PRICE"
        out["ev_usd"] = None
        return out
    if market_price is None or market_price <= 0:
        out["status"] = "UNPRICED"
        out["ev_usd"] = None
        return out
    gross = (offer_lo - market_price) * a["shares"]
    out["gross_spread_usd"] = round(gross, 4)
    out["ev_usd"] = round(p * gross - fees, 4)
    out["ev_usd_if_offer_high"] = round(p * (offer_hi - market_price) * a["shares"] - fees, 4) if offer_hi else None
    out["capital_usd"] = round(market_price * a["shares"] + a["buy_commission_usd"], 2)
    out["status"] = "PRICED"
    # NB: fees are paid even if the deal fails; the failure branch's P&L
    # depends on the post-failure price, which is unknown -> not modeled.
    return out


def paper_outcome(entry_price: float, shares: int, final_price: Optional[float], terminated: bool,
                  fees_usd: float, exit_price_if_terminated: Optional[float] = None) -> dict[str, Any]:
    if terminated:
        if exit_price_if_terminated is None:
            return {"result": "TERMINATED_UNPRICED", "pnl_usd": None,
                    "note": "offer terminated; no post-termination market price recorded"}
        pnl = (exit_price_if_terminated - entry_price) * shares - fees_usd
        return {"result": "TERMINATED", "exit_price": exit_price_if_terminated,
                "pnl_usd": round(pnl, 4)}
    if final_price is None:
        return {"result": "PENDING", "pnl_usd": None}
    pnl = (final_price - entry_price) * shares - fees_usd
    return {"result": "COMPLETED", "exit_price": final_price, "pnl_usd": round(pnl, 4),
            "assumes": "odd-lot tender of all shares accepted in full at the final price (purchase-price tender)"}


# ---------------------------------------------------------------------------
# Auth helper (read token or admin). Kept here so it does not collide with
# the require_reader() helper proposed in PR #1; switch once that merges.
# ---------------------------------------------------------------------------

def check_read_or_admin(token: Optional[str]) -> tuple[int, str]:
    """Return (http_status, detail). 200 means authorized."""
    admin = os.getenv("PAPER_ADMIN_TOKEN", "")
    reader = os.getenv("PAPER_READ_TOKEN", "")
    if not admin and not reader:
        return 503, "PAPER_ADMIN_TOKEN is not configured"
    if token:
        for expected in (admin, reader):
            if expected and hmac.compare_digest(token.encode(), expected.encode()):
                return 200, "ok"
    return 401, "unauthorized"


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def ensure_special_tables(engine) -> None:
    """Each statement runs in its own transaction (Postgres aborts a whole
    transaction on one failed statement; see the markout migration fix)."""
    sqlite = str(engine.url).startswith("sqlite")
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if sqlite else "BIGSERIAL PRIMARY KEY"
    stmts = [
        f"""
        CREATE TABLE IF NOT EXISTS special_filing (
            id {pk},
            accession TEXT NOT NULL UNIQUE,
            form TEXT NOT NULL,
            filed_date TEXT,
            subject_cik TEXT,
            subject_name TEXT,
            ticker TEXT,
            file_number TEXT,
            status TEXT NOT NULL,
            tender_id BIGINT,
            terms_json TEXT,
            error TEXT,
            source_url TEXT,
            discovered_at_utc TEXT NOT NULL,
            parsed_at_utc TEXT
        )""",
        f"""
        CREATE TABLE IF NOT EXISTS special_tender (
            id {pk},
            tender_key TEXT NOT NULL UNIQUE,
            subject_cik TEXT NOT NULL,
            subject_name TEXT,
            ticker TEXT,
            file_number TEXT,
            root_form TEXT,
            first_accession TEXT NOT NULL,
            first_filed_date TEXT,
            last_accession TEXT,
            last_filed_date TEXT,
            amendments INTEGER NOT NULL DEFAULT 0,
            offer_type TEXT,
            price_fixed DOUBLE PRECISION,
            price_low DOUBLE PRECISION,
            price_high DOUBLE PRECISION,
            currency TEXT,
            expiration_date TEXT,
            odd_lot_priority INTEGER NOT NULL DEFAULT 0,
            odd_lot_record_date TEXT,
            odd_lot_snippet TEXT,
            conditions_json TEXT,
            going_private INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            final_accession TEXT,
            final_price DOUBLE PRECISION,
            shares_accepted DOUBLE PRECISION,
            proration_pct DOUBLE PRECISION,
            market_price DOUBLE PRECISION,
            price_source TEXT,
            price_as_of_utc TEXT,
            ev_json TEXT,
            ev_usd DOUBLE PRECISION,
            paper_entry_price DOUBLE PRECISION,
            paper_entry_at_utc TEXT,
            paper_shares INTEGER,
            paper_would_trade INTEGER,
            paper_entry_ev_json TEXT,
            paper_outcome_json TEXT,
            paper_pnl_usd DOUBLE PRECISION,
            outcome_recorded_at_utc TEXT,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS ix_special_filing_subject ON special_filing (subject_cik, file_number)",
        "CREATE INDEX IF NOT EXISTS ix_special_tender_status ON special_tender (status)",
    ]
    for s in stmts:
        with engine.begin() as cx:
            cx.execute(text(s))
    # Future column additions go here, one ALTER per transaction, e.g.:
    # _add_column(engine, "special_tender", "new_col", "TEXT")


def _add_column(engine, table: str, column: str, ddl: str) -> None:
    try:
        with engine.begin() as cx:
            cx.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# HTTP client with SEC fair-access throttle
# ---------------------------------------------------------------------------

class SecClient:
    def __init__(self, user_agent: str, max_rps: float = 5.0, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.user_agent = user_agent
        self.min_interval = 1.0 / max(0.5, min(9.0, max_rps))
        self._lock = asyncio.Lock()
        self._last = 0.0
        self.requests = 0
        self.errors = 0
        self._client = httpx.AsyncClient(
            timeout=30.0, transport=transport, follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})

    async def close(self) -> None:
        await self._client.aclose()

    async def _throttle(self) -> None:
        async with self._lock:
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()

    async def get(self, url: str, max_bytes: int = MAX_SUBMISSION_BYTES, sec: bool = True) -> bytes:
        delay = 2.0
        for attempt in range(4):
            if sec:
                await self._throttle()
            self.requests += 1
            try:
                async with self._client.stream("GET", url) as r:
                    if r.status_code in (429, 503) or r.status_code >= 500:
                        self.errors += 1
                        if attempt < 3:
                            ra = r.headers.get("Retry-After")
                            await asyncio.sleep(min(60.0, float(ra)) if ra and ra.isdigit() else delay)
                            delay *= 2
                            continue
                    r.raise_for_status()
                    buf = bytearray()
                    async for chunk in r.aiter_bytes():
                        buf.extend(chunk)
                        if len(buf) >= max_bytes:
                            break
                    return bytes(buf)
            except (httpx.TransportError,) as e:
                self.errors += 1
                if attempt >= 3:
                    raise
                log.warning("SEC GET retry %s: %s", url, e)
                await asyncio.sleep(delay)
                delay *= 2
        raise RuntimeError(f"GET failed after retries: {url}")

    async def get_json(self, url: str, sec: bool = True) -> Any:
        return json.loads(await self.get(url, max_bytes=50_000_000, sec=sec))


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def _acc_nodash(acc: str) -> str:
    return acc.replace("-", "")


class SpecialSituationsScanner:
    def __init__(self, engine, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.engine = engine
        self.transport = transport
        ensure_special_tables(engine)
        self._task: Optional[asyncio.Task] = None
        self._tickers: dict[str, str] = {}
        self._tickers_at = 0.0
        self.last_scan: dict[str, Any] = {}
        self.last_error: Optional[str] = None
        self.scans = 0

    # -- config ------------------------------------------------------------
    @staticmethod
    def enabled() -> bool:
        return env_bool("SPECIAL_SITUATIONS_ENABLED", False)

    @staticmethod
    def user_agent() -> str:
        return os.getenv("SEC_USER_AGENT", "").strip()

    @staticmethod
    def price_source() -> str:
        return (os.getenv("SPECIAL_PRICE_SOURCE", "none") or "none").strip().lower()

    def idle_reasons(self) -> list[str]:
        r = []
        if not self.enabled():
            r.append("SPECIAL_SITUATIONS_ENABLED is not true (scanner feature flag off)")
        ua = self.user_agent()
        if not ua:
            r.append("SEC_USER_AGENT is not set (SEC requires a declared User-Agent with contact email)")
        elif "@" not in ua:
            r.append("SEC_USER_AGENT should include a contact email per SEC fair-access policy")
        return r

    # -- lifecycle -----------------------------------------------------------
    async def start(self) -> None:
        if self.idle_reasons() and not (self.enabled() and self.user_agent()):
            log.info("special situations scanner idle: %s", self.idle_reasons())
            return
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await self.scan_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # keep the poller alive
                self.last_error = f"{type(e).__name__}: {e}"[:500]
                log.exception("special situations scan failed")
            await asyncio.sleep(max(300, env_int("SPECIAL_POLL_SECONDS", 1800)))

    # -- discovery -------------------------------------------------------------
    async def _ticker_map(self, client: SecClient) -> dict[str, str]:
        if self._tickers and time.time() - self._tickers_at < 86400:
            return self._tickers
        data = await client.get_json(TICKERS_URL)
        m: dict[str, str] = {}
        for row in (data.values() if isinstance(data, dict) else data):
            cik = str(row.get("cik_str", "")).lstrip("0")
            if cik and cik not in m:
                m[cik] = str(row.get("ticker", "")).upper()
        self._tickers, self._tickers_at = m, time.time()
        return m

    async def discover(self, client: SecClient, start: date, end: date, max_hits: int = 2000) -> list[dict[str, Any]]:
        forms = ",".join(FTS_ROOT_FORMS)
        seen: dict[str, dict[str, Any]] = {}
        frm = 0
        while frm < max_hits:
            url = (f"{FTS_URL}?forms={quote(forms, safe=',')}&dateRange=custom"
                   f"&startdt={start.isoformat()}&enddt={end.isoformat()}&from={frm}")
            data = await client.get_json(url)
            hits = (data.get("hits") or {}).get("hits") or []
            for h in hits:
                src = h.get("_source") or {}
                adsh = src.get("adsh") or str(h.get("_id", "")).split(":")[0]
                if not adsh or adsh in seen:
                    continue
                seen[adsh] = {
                    "accession": adsh,
                    "form": src.get("form") or (src.get("root_forms") or [""])[0],
                    "filed_date": src.get("file_date"),
                    "ciks": [str(c).lstrip("0") for c in (src.get("ciks") or [])],
                    "display_names": src.get("display_names") or [],
                    "file_num": src.get("file_num") or [],
                }
            total = ((data.get("hits") or {}).get("total") or {}).get("value", 0)
            frm += len(hits)
            if not hits or frm >= total:
                break
        return sorted(seen.values(), key=lambda r: (r["filed_date"] or "", r["accession"]))

    # -- per-filing processing -----------------------------------------------
    def _known(self, accession: str) -> Optional[str]:
        with self.engine.begin() as cx:
            return cx.execute(text("SELECT status FROM special_filing WHERE accession=:a"),
                              {"a": accession}).scalar()

    def _record_filing(self, row: dict[str, Any]) -> None:
        with self.engine.begin() as cx:
            exists = cx.execute(text("SELECT id FROM special_filing WHERE accession=:accession"),
                                row).scalar()
            if exists:
                cx.execute(text("""
                    UPDATE special_filing SET form=:form, filed_date=:filed_date, subject_cik=:subject_cik,
                        subject_name=:subject_name, ticker=:ticker, file_number=:file_number, status=:status,
                        tender_id=:tender_id, terms_json=:terms_json, error=:error, source_url=:source_url,
                        parsed_at_utc=:parsed_at_utc
                    WHERE accession=:accession"""), row)
            else:
                cx.execute(text("""
                    INSERT INTO special_filing (accession, form, filed_date, subject_cik, subject_name, ticker,
                        file_number, status, tender_id, terms_json, error, source_url, discovered_at_utc, parsed_at_utc)
                    VALUES (:accession, :form, :filed_date, :subject_cik, :subject_name, :ticker, :file_number,
                        :status, :tender_id, :terms_json, :error, :source_url, :discovered_at_utc, :parsed_at_utc)"""),
                           row)

    def ingest_parsed(self, hit: dict[str, Any], terms: dict[str, Any], ticker: Optional[str],
                      source_url: Optional[str] = None, today: Optional[date] = None) -> Optional[int]:
        """Link a parsed filing to a tender (create or update). Returns tender id."""
        hdr = terms.get("header") or {}
        subj = hdr.get("subject") or {}
        form = hdr.get("form") or hit.get("form") or ""
        filed = hdr.get("filed_date") or hit.get("filed_date")
        cik = subj.get("cik") or (hit.get("ciks") or [None])[0]
        file_number = subj.get("file_number")
        acc = hdr.get("accession") or hit["accession"]
        root = form.replace("/A", "")
        now = utc_now_iso()
        tender_id = None
        with self.engine.begin() as cx:
            existing = None
            if form.endswith("/A"):
                q = """SELECT * FROM special_tender WHERE subject_cik=:cik AND root_form=:root
                       AND (first_filed_date IS NULL OR first_filed_date <= :filed)"""
                params: dict[str, Any] = {"cik": cik, "root": root, "filed": filed or "9999"}
                if file_number:
                    q += " AND (file_number=:fn OR file_number IS NULL)"
                    params["fn"] = file_number
                q += " ORDER BY first_filed_date DESC, id DESC LIMIT 1"
                existing = cx.execute(text(q), params).mappings().first()
            else:
                existing = cx.execute(text("SELECT * FROM special_tender WHERE first_accession=:a"),
                                      {"a": acc}).mappings().first()
            res = terms.get("results") or {}
            if existing is None:
                status = "OPEN"
                row = {
                    "tender_key": f"{cik}:{file_number or '-'}:{acc}",
                    "subject_cik": cik, "subject_name": subj.get("name"), "ticker": ticker,
                    "file_number": file_number, "root_form": root, "first_accession": acc,
                    "first_filed_date": filed, "last_accession": acc, "last_filed_date": filed,
                    "amendments": 1 if form.endswith("/A") else 0,
                    "offer_type": terms.get("offer_type"), "price_fixed": terms.get("price_fixed"),
                    "price_low": terms.get("price_low"), "price_high": terms.get("price_high"),
                    "currency": terms.get("currency"), "expiration_date": terms.get("expiration_date"),
                    "odd_lot_priority": 1 if terms.get("odd_lot_priority") else 0,
                    "odd_lot_record_date": terms.get("odd_lot_record_date"),
                    "odd_lot_snippet": terms.get("odd_lot_snippet"),
                    "conditions_json": json.dumps(terms.get("conditions") or {}),
                    "going_private": 1 if terms.get("going_private") else 0,
                    "status": status, "created": now, "updated": now,
                }
                cx.execute(text("""
                    INSERT INTO special_tender (tender_key, subject_cik, subject_name, ticker, file_number, root_form,
                        first_accession, first_filed_date, last_accession, last_filed_date, amendments, offer_type,
                        price_fixed, price_low, price_high, currency, expiration_date, odd_lot_priority,
                        odd_lot_record_date, odd_lot_snippet, conditions_json, going_private, status,
                        created_at_utc, updated_at_utc)
                    VALUES (:tender_key, :subject_cik, :subject_name, :ticker, :file_number, :root_form,
                        :first_accession, :first_filed_date, :last_accession, :last_filed_date, :amendments,
                        :offer_type, :price_fixed, :price_low, :price_high, :currency, :expiration_date,
                        :odd_lot_priority, :odd_lot_record_date, :odd_lot_snippet, :conditions_json,
                        :going_private, :status, :created, :updated)"""), row)
                tender_id = cx.execute(text("SELECT id FROM special_tender WHERE tender_key=:k"),
                                       {"k": row["tender_key"]}).scalar_one()
                existing = cx.execute(text("SELECT * FROM special_tender WHERE id=:i"), {"i": tender_id}).mappings().first()
            else:
                tender_id = existing["id"]
                upd: dict[str, Any] = {"id": tender_id, "updated": now}
                sets = ["updated_at_utc=:updated"]
                if form.endswith("/A") and (existing["last_filed_date"] or "") <= (filed or ""):
                    sets += ["last_accession=:la", "last_filed_date=:lf", "amendments=amendments+1"]
                    upd.update(la=acc, lf=filed)
                    # amendments may change price/expiration; only overwrite with parsed values
                    # amendments restate the current expiration; a later date means an extension
                    if terms.get("expiration_date") and (terms.get("extended") or (
                            existing["expiration_date"] and terms["expiration_date"] > existing["expiration_date"])):
                        sets.append("expiration_date=:exp")
                        upd["exp"] = terms["expiration_date"]
                    for k in ("price_fixed", "price_low", "price_high"):
                        if terms.get(k) is not None and existing[k] is not None and terms[k] != existing[k] \
                                and terms.get("offer_type") == existing["offer_type"] and not res.get("final"):
                            sets.append(f"{k}=:{k}")
                            upd[k] = terms[k]
                    if not existing["odd_lot_priority"] and terms.get("odd_lot_priority"):
                        sets += ["odd_lot_priority=1", "odd_lot_snippet=:ols", "odd_lot_record_date=:olr"]
                        upd.update(ols=terms.get("odd_lot_snippet"), olr=terms.get("odd_lot_record_date"))
                cx.execute(text(f"UPDATE special_tender SET {', '.join(sets)} WHERE id=:id"), upd)
            # results
            if form.endswith("/A") and existing["status"] not in ("COMPLETED", "TERMINATED"):
                if res.get("terminated"):
                    cx.execute(text("""UPDATE special_tender SET status='TERMINATED', final_accession=:a,
                                       updated_at_utc=:u WHERE id=:id"""), {"a": acc, "u": now, "id": tender_id})
                elif res.get("final"):
                    cx.execute(text("""UPDATE special_tender SET status='COMPLETED', final_accession=:a,
                                       final_price=:p, shares_accepted=:s, proration_pct=:pr, updated_at_utc=:u
                                       WHERE id=:id"""),
                               {"a": acc, "p": res.get("final_price"), "s": res.get("shares_accepted"),
                                "pr": res.get("proration_pct"), "u": now, "id": tender_id})
        self._record_filing({
            "accession": acc, "form": form, "filed_date": filed, "subject_cik": cik,
            "subject_name": subj.get("name"), "ticker": ticker, "file_number": file_number,
            "status": "PARSED", "tender_id": tender_id,
            "terms_json": json.dumps(terms, default=str)[:400_000], "error": None,
            "source_url": source_url, "discovered_at_utc": now, "parsed_at_utc": now,
        })
        self.refresh_status(tender_id, today)
        return tender_id

    def refresh_status(self, tender_id: int, today: Optional[date] = None) -> None:
        today = today or utc_now().date()
        with self.engine.begin() as cx:
            t = cx.execute(text("SELECT status, expiration_date FROM special_tender WHERE id=:i"),
                           {"i": tender_id}).mappings().first()
            if t and t["status"] == "OPEN" and t["expiration_date"] and t["expiration_date"] < today.isoformat():
                cx.execute(text("UPDATE special_tender SET status='EXPIRED_AWAITING_RESULTS' WHERE id=:i"),
                           {"i": tender_id})
            elif (t and t["status"] == "EXPIRED_AWAITING_RESULTS" and t["expiration_date"]
                  and t["expiration_date"] >= today.isoformat()):
                # an amendment extended the offer
                cx.execute(text("UPDATE special_tender SET status='OPEN' WHERE id=:i"), {"i": tender_id})

    # -- pricing / EV / paper book ------------------------------------------------
    async def fetch_price(self, client: SecClient, ticker: str) -> Optional[dict[str, Any]]:
        if self.price_source() != "yahoo_chart" or not ticker:
            return None
        try:
            data = json.loads(await client.get(YAHOO_CHART_URL.format(ticker=quote(ticker)), max_bytes=2_000_000, sec=False))
            meta = data["chart"]["result"][0]["meta"]
            px = meta.get("regularMarketPrice")
            ts = meta.get("regularMarketTime")
            if px is None or float(px) <= 0 or (meta.get("currency") or "USD") != "USD":
                return None
            return {"price": float(px), "source": "yahoo_chart (unofficial, possibly delayed)",
                    "as_of_utc": datetime.fromtimestamp(int(ts), timezone.utc).isoformat() if ts else None}
        except Exception as e:
            log.info("price fetch failed for %s: %s", ticker, e)
            return None

    def apply_price_and_ev(self, tender_id: int, price: Optional[dict[str, Any]],
                           today: Optional[date] = None) -> dict[str, Any]:
        today = today or utc_now().date()
        now = utc_now_iso()
        with self.engine.begin() as cx:
            t = dict(cx.execute(text("SELECT * FROM special_tender WHERE id=:i"), {"i": tender_id}).mappings().one())
            t["conditions"] = json.loads(t.get("conditions_json") or "{}")
            mp = price["price"] if price else None
            ev = compute_ev(t, mp, today=today)
            cx.execute(text("""UPDATE special_tender SET market_price=:mp, price_source=:src, price_as_of_utc=:asof,
                               ev_json=:ev, ev_usd=:evu, updated_at_utc=:u WHERE id=:i"""),
                       {"mp": mp, "src": price["source"] if price else None,
                        "asof": price.get("as_of_utc") if price else None,
                        "ev": json.dumps(ev), "evu": ev.get("ev_usd"), "u": now, "i": tender_id})
            # paper entry: first priced observation of an open odd-lot tender
            if (t["paper_entry_at_utc"] is None and t["status"] == "OPEN" and ev.get("status") == "PRICED"
                    and t["odd_lot_priority"]):
                would = bool(ev["ev_usd"] is not None and ev["ev_usd"] > 0 and not ev["blockers"])
                cx.execute(text("""UPDATE special_tender SET paper_entry_price=:p, paper_entry_at_utc=:at,
                                   paper_shares=:s, paper_would_trade=:w, paper_entry_ev_json=:ev WHERE id=:i"""),
                           {"p": mp, "at": now, "s": ev["shares"], "w": 1 if would else 0,
                            "ev": json.dumps(ev), "i": tender_id})
        return ev

    def record_outcomes(self, exit_prices: Optional[dict[int, float]] = None) -> int:
        exit_prices = exit_prices or {}
        n = 0
        a = ev_assumptions()
        with self.engine.begin() as cx:
            rows = cx.execute(text("""SELECT * FROM special_tender WHERE paper_entry_at_utc IS NOT NULL
                                      AND outcome_recorded_at_utc IS NULL
                                      AND status IN ('COMPLETED','TERMINATED')""")).mappings().all()
            for t in rows:
                out = paper_outcome(t["paper_entry_price"], int(t["paper_shares"] or 0), t["final_price"],
                                    t["status"] == "TERMINATED", a["buy_commission_usd"] + a["tender_fee_usd"],
                                    exit_prices.get(int(t["id"])))
                out["would_trade_at_entry"] = bool(t["paper_would_trade"])
                out["proration_pct_reported"] = t["proration_pct"]
                cx.execute(text("""UPDATE special_tender SET paper_outcome_json=:o, paper_pnl_usd=:p,
                                   outcome_recorded_at_utc=:u WHERE id=:i"""),
                           {"o": json.dumps(out), "p": out.get("pnl_usd"), "u": utc_now_iso(), "i": t["id"]})
                n += 1
        return n

    # -- main scan ------------------------------------------------------------------
    async def scan_once(self, lookback_days: Optional[int] = None, today: Optional[date] = None) -> dict[str, Any]:
        ua = self.user_agent()
        if not ua:
            raise RuntimeError("SEC_USER_AGENT is not set")
        today = today or utc_now().date()
        lookback = lookback_days or env_int("SPECIAL_LOOKBACK_DAYS", 45)
        client = SecClient(ua, env_float("SPECIAL_SEC_MAX_RPS", 5.0), transport=self.transport)
        summary: dict[str, Any] = {"started_at_utc": utc_now_iso(), "discovered": 0, "new": 0, "parsed": 0,
                                   "skipped_no_ticker": 0, "errors": 0, "priced": 0}
        try:
            tickers = await self._ticker_map(client)
            hits = await self.discover(client, today - timedelta(days=lookback), today)
            summary["discovered"] = len(hits)
            for hit in hits:
                if self._known(hit["accession"]) in ("PARSED", "SKIPPED_NO_TICKER"):
                    continue
                summary["new"] += 1
                tick = next((tickers[c] for c in hit["ciks"] if c in tickers), None)
                if not tick:
                    self._record_filing({
                        "accession": hit["accession"], "form": hit["form"], "filed_date": hit["filed_date"],
                        "subject_cik": (hit["ciks"] or [None])[0],
                        "subject_name": (hit["display_names"] or [None])[0], "ticker": None,
                        "file_number": None, "status": "SKIPPED_NO_TICKER", "tender_id": None, "terms_json": None,
                        "error": None, "source_url": None, "discovered_at_utc": utc_now_iso(), "parsed_at_utc": None})
                    summary["skipped_no_ticker"] += 1
                    continue
                cik = next(c for c in hit["ciks"] if c in tickers)
                url = ARCHIVE_URL.format(cik=cik, acc_nodash=_acc_nodash(hit["accession"]), acc=hit["accession"])
                try:
                    raw = (await client.get(url)).decode("utf-8", errors="replace")
                    terms = extract_terms(raw)
                    subj = (terms.get("header") or {}).get("subject") or {}
                    # ticker must belong to the SUBJECT company, never the bidder/filer
                    tick = tickers.get(subj.get("cik") or "") if subj.get("cik") else tick
                    self.ingest_parsed(hit, terms, tick, source_url=url, today=today)
                    summary["parsed"] += 1
                except Exception as e:
                    summary["errors"] += 1
                    self._record_filing({
                        "accession": hit["accession"], "form": hit["form"], "filed_date": hit["filed_date"],
                        "subject_cik": cik, "subject_name": (hit["display_names"] or [None])[0], "ticker": tick,
                        "file_number": None, "status": "ERROR", "tender_id": None, "terms_json": None,
                        "error": f"{type(e).__name__}: {e}"[:500], "source_url": url,
                        "discovered_at_utc": utc_now_iso(), "parsed_at_utc": None})
            # refresh statuses, prices and EV for open tenders
            with self.engine.begin() as cx:
                open_rows = cx.execute(text("""SELECT id, ticker FROM special_tender
                                               WHERE status IN ('OPEN','EXPIRED_AWAITING_RESULTS')""")).mappings().all()
            for r in open_rows:
                self.refresh_status(int(r["id"]), today)
                price = await self.fetch_price(client, r["ticker"]) if r["ticker"] else None
                if price:
                    summary["priced"] += 1
                self.apply_price_and_ev(int(r["id"]), price, today)
            summary["outcomes_recorded"] = self.record_outcomes()
        finally:
            summary["sec_requests"] = client.requests
            summary["http_errors"] = client.errors
            await client.close()
        summary["finished_at_utc"] = utc_now_iso()
        self.last_scan = summary
        self.last_error = None
        self.scans += 1
        return summary

    # -- read API --------------------------------------------------------------------
    @staticmethod
    def _tender_out(r: dict[str, Any]) -> dict[str, Any]:
        d = dict(r)
        for k in ("conditions_json", "ev_json", "paper_entry_ev_json", "paper_outcome_json"):
            v = d.pop(k, None)
            d[k[:-5]] = json.loads(v) if v else None
        d["odd_lot_priority"] = bool(d.get("odd_lot_priority"))
        d["going_private"] = bool(d.get("going_private"))
        if d.get("paper_would_trade") is not None:
            d["paper_would_trade"] = bool(d["paper_would_trade"])
        d["paper_only"] = True
        return d

    def list_tenders(self, status: Optional[str] = None, odd_lot_only: bool = False,
                     limit: int = 200) -> list[dict[str, Any]]:
        limit = min(max(int(limit), 1), 1000)
        q = "SELECT * FROM special_tender WHERE 1=1"
        p: dict[str, Any] = {"limit": limit}
        if status:
            q += " AND status=:status"
            p["status"] = status.upper()
        if odd_lot_only:
            q += " AND odd_lot_priority=1"
        q += " ORDER BY COALESCE(expiration_date, first_filed_date) DESC, id DESC LIMIT :limit"
        with self.engine.begin() as cx:
            rows = cx.execute(text(q), p).mappings().all()
        return [self._tender_out(r) for r in rows]

    def get_tender(self, accession: str) -> Optional[dict[str, Any]]:
        with self.engine.begin() as cx:
            t = cx.execute(text("SELECT * FROM special_tender WHERE first_accession=:a OR last_accession=:a "
                                "OR final_accession=:a"), {"a": accession}).mappings().first()
            if t is None:
                tid = cx.execute(text("SELECT tender_id FROM special_filing WHERE accession=:a"),
                                 {"a": accession}).scalar()
                if tid:
                    t = cx.execute(text("SELECT * FROM special_tender WHERE id=:i"), {"i": tid}).mappings().first()
            if t is None:
                return None
            filings = cx.execute(text("""SELECT accession, form, filed_date, status, source_url, error, terms_json
                                         FROM special_filing WHERE tender_id=:i ORDER BY filed_date, id"""),
                                 {"i": t["id"]}).mappings().all()
        out = self._tender_out(t)
        fl = []
        for f in filings:
            d = dict(f)
            terms = json.loads(d.pop("terms_json") or "{}")
            d["results"] = terms.get("results")
            d["expiration_date_parsed"] = terms.get("expiration_date")
            fl.append(d)
        out["filings"] = fl
        return out

    def status(self) -> dict[str, Any]:
        with self.engine.begin() as cx:
            by_status = {str(r["status"]): int(r["n"]) for r in cx.execute(text(
                "SELECT status, COUNT(*) AS n FROM special_tender GROUP BY status")).mappings().all()}
            filings = {str(r["status"]): int(r["n"]) for r in cx.execute(text(
                "SELECT status, COUNT(*) AS n FROM special_filing GROUP BY status")).mappings().all()}
            odd = cx.execute(text("SELECT COUNT(*) FROM special_tender WHERE odd_lot_priority=1")).scalar_one()
            book = cx.execute(text("""SELECT COUNT(*) AS entries,
                    SUM(CASE WHEN paper_would_trade=1 THEN 1 ELSE 0 END) AS would_trade,
                    SUM(CASE WHEN outcome_recorded_at_utc IS NOT NULL THEN 1 ELSE 0 END) AS outcomes,
                    SUM(CASE WHEN outcome_recorded_at_utc IS NOT NULL AND paper_would_trade=1
                             THEN paper_pnl_usd ELSE 0 END) AS pnl_would_trade
                    FROM special_tender WHERE paper_entry_at_utc IS NOT NULL""")).mappings().one()
        return {
            "mode": "paper-only",
            "live_execution_available": False,
            "broker_integration": False,
            "enabled": self.enabled(),
            "running": bool(self._task and not self._task.done()),
            "idle_reasons": self.idle_reasons(),
            "sec_user_agent_set": bool(self.user_agent()),
            "price_source": self.price_source(),
            "price_note": ("none: EV is UNPRICED (no fabricated prices)" if self.price_source() == "none"
                           else "unofficial public quote endpoint; may be delayed; labeled per tender"),
            "forms": TENDER_FORMS,
            "tenders_by_status": by_status,
            "filings_by_status": filings,
            "odd_lot_priority_tenders": int(odd or 0),
            "paper_book": {k: (float(v) if k == "pnl_would_trade" and v is not None else int(v or 0))
                           for k, v in dict(book).items()},
            "ev_assumptions": ev_assumptions(),
            "scans": self.scans,
            "last_scan": self.last_scan,
            "last_error": self.last_error,
        }


def load_fixture(path: str) -> str:
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:
        return f.read()
