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
SPECIAL_LOOKBACK_DAYS        default 45 (full-text search window for new filings; 1..365)
SPECIAL_BACKFILL_DAYS        default 365 - when an amendment arrives whose original
                             filing is not in the DB, look back this far for the
                             original (catches older offers still open)
SPECIAL_UNKNOWN_EXPIRY_STALE_DAYS default 60 - a tender whose expiration could not
                             be parsed is UNKNOWN_EXPIRY; after this many days
                             with no new filing it becomes STALE_UNKNOWN
SPECIAL_PRORATION_FILL_FLOOR default 0.0 - assumed fill fraction for a prorated
                             offer (no odd-lot priority) when the offer size vs
                             shares outstanding cannot be parsed
SPECIAL_PRICE_USER_AGENT     generic UA for price requests (never the SEC UA)
SPECIAL_SEC_MAX_RPS          default 5 (hard-capped at 9, SEC limit is 10/s)
SPECIAL_PRICE_SOURCE         "none" (default, EV unpriced) | "yahoo_chart"
                             (unofficial public endpoint, opt-in, labeled)
SPECIAL_ODD_LOT_SHARES       default 99 (capped at 99)
SPECIAL_BUY_COMMISSION_USD   default 0   (set to YOUR broker's real fees)
SPECIAL_TENDER_FEE_USD       default 25  (broker voluntary-reorg / tender fee; a
                             conservative ASSUMPTION, set to your broker's fee)
SPECIAL_ENTRY_HALF_SPREAD_BPS default 100 - when only a last trade is available,
                             entry = last * (1 + this); an ask is used when known
SPECIAL_EXIT_HALF_SPREAD_BPS default 100 - exit after a terminated deal is
                             booked at last * (1 - this)
SPECIAL_MAX_PRICE_AGE_HOURS  default 96 - older quotes are treated as unpriced
                             (covers a weekend; tighten for intraday use)
SPECIAL_TERMINATED_LOSS_PCT  default 0.15 - placeholder loss vs entry for a
                             terminated deal with no post-termination price
                             (flagged PLACEHOLDER; it still counts in n)
SPECIAL_UNRESOLVED_AFTER_DAYS default 10 - EXPIRED_AWAITING_RESULTS older than
                             this (days past expiry) is reported UNRESOLVED
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
from sqlalchemy import bindparam, text

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
# Price requests go through a SEPARATE client with a generic UA. The SEC
# User-Agent carries a contact e-mail and must only ever be sent to sec.gov.
DEFAULT_PRICE_USER_AGENT = "Mozilla/5.0 (compatible; paper-research)"
OPEN_LIKE_STATUSES = ("OPEN", "EXPIRED_AWAITING_RESULTS", "UNKNOWN_EXPIRY")
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
    # Canadian take-over bids (Schedule 14D-1F): "will remain open for acceptance until 5:00 p.m. (Mountain Time) on ..."
    cands += [parse_month_date(m.group(1)) for m in re.finditer(
        r"open\s+for\s+acceptance\s+until\s+.{0,80}?\bon\s+(?:[A-Za-z]+day,?\s+)?" + _DATE, t, re.I)]
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
    record_dates: set[str] = set()
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
        if near_odd:
            # every odd-lot definition / certification (Offer to Purchase, Letter of
            # Transmittal, Notice of Guaranteed Delivery...) may state its own date
            before = t[max(0, fm.start() - 400): fm.start()]
            for rd in re.finditer(r"as\s+of\s+the\s+close\s+of\s+business\s+on\s+" + _DATE, before, re.I):
                d = parse_month_date(rd.group(1))
                if d:
                    record_dates.add(d)
            for rd in re.finditer(r"(?:of\s+record|record\s+date)\s+(?:as\s+of|on)\s+" + _DATE, before, re.I):
                d = parse_month_date(rd.group(1))
                if d:
                    record_dates.add(d)
    dates = sorted(record_dates) if priority else []
    return {
        "odd_lot_mentioned": bool(mentions),
        "odd_lot_priority": priority,
        # strictest (earliest) date governs eligibility; all dates are kept
        "odd_lot_record_date": dates[0] if dates else None,
        "odd_lot_record_dates": dates,
        "odd_lot_record_date_conflict": len(dates) > 1,
        "odd_lot_snippet": snippet,
    }


_PREF_TICKER = re.compile(r"-P[A-Z]?$|\.PR[A-Z]?$|\^")
_OTHER_TICKER = re.compile(r"(?:-WT|-W|-U|-R|-RT|\.WS|\.U)$")


def extract_security(t: str) -> dict[str, Any]:
    """Which class is being tendered, and is it traded at all?"""
    title = None
    m = re.search(r"([^()\[\]]{3,220}?)\s*\(\s*Title\s+of\s+Class(?:es)?\s+of\s+Securities\s*\)", t[:200_000], re.I)
    if m:
        title = re.sub(r"[_\-=*]{2,}", " ", m.group(1))
        title = re.sub(r"\s+", " ", title).strip(" ,;:")[-200:] or None
    tl = (title or "").lower()
    if re.search(r"\boptions?\b", tl):
        cls = "OPTIONS"
    elif "warrant" in tl:
        cls = "WARRANTS"
    elif re.search(r"\bnotes?\b|debentures?|bonds?\b", tl):
        cls = "DEBT"
    elif "preferred" in tl or "preference" in tl:
        cls = "PREFERRED"
    elif re.search(r"common|ordinary|beneficial\s+interest|\bshares\b|\bunits\b|stock", tl):
        cls = "COMMON"
    else:
        cls = "UNKNOWN"
    untraded = bool(re.search(
        r"no\s+established\s+(?:public\s+)?trading\s+market|"
        r"not\s+(?:currently\s+)?(?:listed\s+or\s+)?traded\s+on\s+(?:an?\s+)?(?:established\s+)?(?:public\s+)?(?:trading\s+market|(?:securities\s+)?exchange)|"
        r"(?:there\s+is\s+(?:otherwise\s+)?)?no\s+(?:current\s+)?public\s+(?:trading\s+)?market\s+for\s+(?:the|its|our)\s+Shares|"
        r"since\s+there\s+is\s+no\s+current\s+public\s+market",
        t[:400_000], re.I))
    return {"security_title": title, "security_class": cls, "untraded": untraded}


def select_ticker(candidates: list[str], security_class: Optional[str], untraded: bool = False) -> Optional[str]:
    """Pick the exchange ticker for the class actually tendered.

    SEC's company_tickers.json lists every class under one CIK (e.g. a fund's
    preferred series). We only price COMMON tenders off a common ticker; a
    preferred tender cannot be mapped to a specific series reliably, so it is
    left unpriced rather than priced off the wrong security."""
    if untraded or not candidates:
        return None
    if security_class not in ("COMMON", "UNKNOWN", None):
        return None
    common = [c for c in candidates if not _PREF_TICKER.search(c) and not _OTHER_TICKER.search(c)]
    return common[0] if common else None


def extract_offer_kind(t: str) -> dict[str, Any]:
    """CASH tender vs securities exchange vs employee option exchange."""
    head = t[:60_000]
    if re.search(r"\bexchange\b.{0,80}?\b(?:certain\s+)?(?:outstanding\s+|eligible\s+|unexercised\s+)*"
                 r"(?:stock\s+)?options\s+(?:to\s+purchase|for\s+new|granted)", head, re.I | re.S) or \
            re.search(r"Offer\s+to\s+Exchange\s+(?:Certain\s+)?(?:Outstanding\s+|Eligible\s+)*(?:Stock\s+)?Options", head, re.I):
        return {"offer_kind": "OPTION_EXCHANGE"}
    mixed = re.search(r"\d+(?:\.\d+)?\s+of\s+an?\s+[^.]{0,80}?share[^.]{0,200}?(?:U\.?S\.?)?\$\s?\d+(?:\.\d+)?\s+in\s+cash",
                      t[:400_000], re.I)
    if mixed:
        return {"offer_kind": "CASH_AND_STOCK", "offer_kind_snippet": _snippet(t, mixed.start(), mixed.end(), pad=80, cap=400)}
    # "a tender or exchange offer for the shares" is boilerplate in cash-offer conditions, so only
    # an offer *to exchange* or the capitalised defined term counts
    exch = re.search(r"\b(?:offer|offering)\s+(?:by\s+[^.]{0,80}?\s+)?to\s+exchange\b", head, re.I) or \
        re.search(r"[(“\"]\s*the\s+[“\"]?\s*Exchange\s+Offer\s*[”\"]|\bOFFER\s+TO\s+EXCHANGE\b|\bOffer\s+to\s+Exchange\b", head)
    if exch:
        return {"offer_kind": "SECURITIES_EXCHANGE", "offer_kind_snippet": _snippet(t, exch.start(), exch.end(), pad=80, cap=400)}
    return {"offer_kind": "CASH"}


def extract_offer_size(t: str) -> dict[str, Any]:
    """Offer size relative to shares outstanding -> worst-case pro-rata fill."""
    any_and_all = bool(re.search(
        r"(?:acquire|purchase)\s+(?:any\s+and\s+)?all\s+(?:of\s+)?(?:the\s+)?(?:issued\s+and\s+)?outstanding\s+"
        r"(?:shares|common|ordinary|units)", t[:200_000], re.I))
    pcts = []
    for pat in (
        r"up\s+to\s+(\d{1,2}(?:\.\d+)?)\s*(?:%|percent)\s+of\s+(?:its|the|our|the\s+Fund.s|the\s+Trust.s)\s+"
        r"(?:currently\s+)?(?:issued\s+and\s+)?outstanding",
        r"(?:purchase|repurchase|acquire)\s+(?:for\s+cash\s+)?up\s+to\s+[\d,]{4,}\s+[^.]{0,120}?\(\s*(?:or\s+)?approximately\s+"
        r"(\d{1,2}(?:\.\d+)?)\s*%",
        r"Offer\s+(?:is|would\s+be)\s+for\s+(?:a\s+maximum\s+of\s+[\d,]+\s+Shares,?\s+)?(?:constituting\s+)?approximately\s+"
        r"(\d{1,2}(?:\.\d+)?)\s*%",
        r"constituting\s+approximately\s+(\d{1,2}(?:\.\d+)?)\s*%\s+of\s+the\s+(?:total\s+)?(?:issued\s+and\s+)?"
        r"(?:outstanding|Shares\s+outstanding|shares\s+outstanding)",
    ):
        for m in re.finditer(pat, t, re.I):
            # "may purchase additional Shares representing up to 2% ... (Rule 13e-4(f))" is not the offer size
            if re.search(r"additional|without\s+amending|without\s+extending", t[max(0, m.start() - 120): m.start()], re.I):
                continue
            pcts.append(_num(m.group(1)))
    pct = _mode([x for x in pcts if x and 0 < x < 100])
    max_shares = _mode([_num(m.group(1)) for m in re.finditer(
        r"(?:to\s+purchase|repurchase|to\s+acquire|offering\s+to\s+purchase|Offer\s+to\s+Purchase)\s+(?:for\s+cash\s+)?"
        r"up\s+to\s+(?:a\s+maximum\s+of\s+|an\s+aggregate\s+of\s+)?(\d{1,3}(?:,\d{3})+)\s+(?:outstanding\s+|of\s+(?:its|the)\s+"
        r"(?:issued\s+and\s+)?outstanding\s+)?(?:shares|Shares|common)", t, re.I)])
    outstanding = _mode([_num(m.group(1)) for m in re.finditer(
        r"there\s+were\s+(\d{1,3}(?:,\d{3})+)\s+(?:Shares|shares)[^.]{0,60}?(?:issued\s+and\s+)?outstanding", t, re.I)])
    min_fill = None
    if pct:
        min_fill = pct / 100.0
    elif max_shares and outstanding and outstanding > max_shares:
        min_fill = max_shares / outstanding
    return {"any_and_all": any_and_all and not pct and not max_shares, "offer_max_pct": pct,
            "offer_max_shares": max_shares, "shares_outstanding_parsed": outstanding,
            "min_fill_if_all_tender": round(min_fill, 6) if min_fill else None}


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
    expired_done = re.search(
        r"(?:Offer|withdrawal\s+rights)\s+expired\s+(?:as\s+scheduled\s+)?at\s+[^.]{0,160}", t, re.I)
    accepted_all = re.search(
        r"(?:has|have)\s+(?:irrevocably\s+)?accepted\s+(?:for\s+(?:payment|purchase)\s+)?(?:\(?irrevocably\)?\s+)?all\s+"
        r"(?:such\s+)?(?:Shares|shares|Units|units)\s+(?:that\s+were\s+)?validly\s+tendered|"
        r"(?:effected|completed|consummated)\s+the\s+Merger", t, re.I)
    if expired_done:
        out["expired_reported"] = True
    if expired_done and accepted_all and not out["terminated"]:
        out["completed_all_accepted"] = True
        out["results_snippet"] = out.get("results_snippet") or _snippet(t, expired_done.start(), expired_done.end(), pad=60)
    out["final"] = bool((final_box or final_words) and acc and acc[1] is not None and not out["terminated"])
    if out.get("completed_all_accepted"):
        out["final"] = True
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
    terms.update(extract_security(t))
    terms.update(extract_offer_kind(t))
    terms.update(extract_offer_size(t))
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
        "tender_fee_usd": env_float("SPECIAL_TENDER_FEE_USD", 25.0),
        "entry_half_spread_bps": max(0.0, env_float("SPECIAL_ENTRY_HALF_SPREAD_BPS", 100.0)),
        "exit_half_spread_bps": max(0.0, env_float("SPECIAL_EXIT_HALF_SPREAD_BPS", 100.0)),
        "max_price_age_hours": env_float("SPECIAL_MAX_PRICE_AGE_HOURS", 96.0),
        "terminated_loss_pct": max(0.0, min(1.0, env_float("SPECIAL_TERMINATED_LOSS_PCT", 0.15))),
        "unresolved_after_days": max(1, env_int("SPECIAL_UNRESOLVED_AFTER_DAYS", 10)),
        "p_base": env_float("SPECIAL_P_BASE", 0.95),
        "haircut_financing": env_float("SPECIAL_HAIRCUT_FINANCING", 0.85),
        "haircut_minimum": env_float("SPECIAL_HAIRCUT_MINIMUM", 0.90),
        "haircut_approval": env_float("SPECIAL_HAIRCUT_APPROVAL", 0.90),
        "haircut_unknown": env_float("SPECIAL_HAIRCUT_UNKNOWN", 0.95),
        "note": ("heuristic priors, not estimated from data; the $25 tender fee, the spread "
                 "haircuts and the terminated-deal placeholder are conservative assumptions, "
                 "not sourced figures; set them to the user's actual broker costs"),
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


def _json_list(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    try:
        out = json.loads(v)
        return out if isinstance(out, list) else []
    except (TypeError, ValueError):
        return []


def entry_price_from_quote(market_price: Optional[float], a: dict[str, Any],
                           ask: Optional[float] = None) -> tuple[Optional[float], str]:
    """Executable entry estimate. Never the bare last trade: use the ask when
    known, otherwise last * (1 + SPECIAL_ENTRY_HALF_SPREAD_BPS)."""
    if ask is not None and ask > 0:
        return float(ask), "ask"
    if market_price is None or market_price <= 0:
        return None, "unpriced"
    hc = float(a.get("entry_half_spread_bps", 100.0))
    return round(float(market_price) * (1.0 + hc / 10_000.0), 6), f"last + {hc:g} bps half-spread haircut"


def exit_price_from_quote(market_price: Optional[float], a: dict[str, Any],
                          bid: Optional[float] = None) -> Optional[float]:
    if bid is not None and bid > 0:
        return float(bid)
    if market_price is None or market_price <= 0:
        return None
    return round(float(market_price) * (1.0 - float(a.get("exit_half_spread_bps", 100.0)) / 10_000.0), 6)


def compute_ev(tender: dict[str, Any], market_price: Optional[float], today: Optional[date] = None,
               assumptions: Optional[dict[str, Any]] = None, ask: Optional[float] = None) -> dict[str, Any]:
    """Paper EV for an odd-lot position.

    Hard blockers (record-date trap, expired, non-USD, non-cash consideration,
    untraded security) make the offer ineligible: no EV is produced at all.
    Prorated offers (no odd-lot priority, not any-and-all) get a conservative
    EV that assumes only the worst-case pro-rata fill (offer size / shares
    outstanding, i.e. every holder tenders) or SPECIAL_PRORATION_FILL_FLOOR
    when the size cannot be parsed. Fees are charged in full regardless."""
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
        "model": ("p_complete * ((offer - market) * shares * fill) - fees; Dutch uses range low; "
                  "fill=1 with odd-lot priority or any-and-all, else worst-case pro-rata fill"),
        "assumptions": a,
        "p_complete": p,
        "p_adjustments": applied,
        "offer_price_used": offer_lo,
        "offer_price_high": offer_hi,
        "market_price": market_price,
        "fees_usd": fees,
        "shares": a["shares"],
        "blockers": [],
        "flags": [],
    }
    status = None
    kind = tender.get("offer_kind") or "CASH"
    if kind == "OPTION_EXCHANGE":
        out["blockers"].append("employee option exchange: not a tradable tender")
        status = status or "NOT_TRADABLE"
    elif kind in ("SECURITIES_EXCHANGE", "CASH_AND_STOCK"):
        out["blockers"].append(f"{kind.lower()}: consideration is (partly) securities; cash EV not modeled")
        status = status or "EXCHANGE_UNMODELED"
    if tender.get("untraded"):
        out["blockers"].append("tendered class has no established trading market")
        status = status or "UNTRADED"
    rds = sorted(set(_json_list(tender.get("odd_lot_record_dates")) + (
        [tender["odd_lot_record_date"]] if tender.get("odd_lot_record_date") else [])))
    if len(rds) > 1:
        out["flags"].append(f"conflicting odd-lot record dates in filing: {', '.join(rds)} (strictest used)")
    out["odd_lot_record_dates"] = rds
    if rds and rds[0] < today.isoformat():
        out["blockers"].append(
            f"odd-lot priority requires ownership as of {rds[0]}: shares bought now do NOT qualify")
        status = status or "INELIGIBLE_RECORD_DATE"
    exp = tender.get("expiration_date")
    if exp and exp < today.isoformat():
        out["blockers"].append(f"offer expired {exp}")
        status = status or "EXPIRED"
    if (tender.get("currency") or "USD") != "USD":
        out["blockers"].append(f"non-USD offer ({tender.get('currency')}); not modeled")
        status = status or "BLOCKED_NON_USD"
    # proration
    odd_lot = bool(tender.get("odd_lot_priority"))
    any_all = bool(tender.get("any_and_all"))
    if odd_lot or any_all:
        fill, fill_basis = 1.0, ("odd-lot priority" if odd_lot else "any-and-all offer")
    else:
        out["flags"].append("prorated: no odd-lot priority clause; small lots are cut back like everyone else")
        mf = tender.get("min_fill_if_all_tender") if tender.get("min_fill_if_all_tender") is not None \
            else tender.get("min_fill")
        if mf:
            fill, fill_basis = float(mf), "worst case: offer size / shares outstanding (all holders tender)"
        else:
            fill = max(0.0, min(1.0, env_float("SPECIAL_PRORATION_FILL_FLOOR", 0.0)))
            fill_basis = "offer size unparsed: SPECIAL_PRORATION_FILL_FLOOR"
    out.update(prorated=not (odd_lot or any_all), fill_assumed=round(fill, 6), fill_basis=fill_basis)
    if status:
        out["status"] = status
        out["ev_usd"] = None
        return out
    if tender.get("offer_type") == "NAV_BASED":
        out["status"] = "NAV_BASED_UNMODELED"
        out["ev_usd"] = None
        out["flags"].append("offer priced off NAV at expiration; final price unknown until then")
        return out
    if offer_lo is None:
        out["status"] = "UNPARSED_PRICE"
        out["ev_usd"] = None
        return out
    if market_price is None or market_price <= 0:
        out["status"] = "UNPRICED"
        out["ev_usd"] = None
        return out
    entry, entry_basis = entry_price_from_quote(market_price, a, ask)
    out["entry_price_used"] = entry
    out["entry_price_basis"] = entry_basis
    gross = (offer_lo - entry) * a["shares"]
    out["gross_spread_usd"] = round(gross, 4)
    out["ev_usd"] = round(p * gross * fill - fees, 4)
    out["ev_usd_full_fill"] = round(p * gross - fees, 4)
    out["ev_usd_if_offer_high"] = round(p * (offer_hi - entry) * a["shares"] * fill - fees, 4) if offer_hi else None
    out["capital_usd"] = round(entry * a["shares"] + a["buy_commission_usd"], 2)
    out["status"] = "PRICED_PRORATED" if out["prorated"] else "PRICED"
    # NB: fees are paid even if the deal fails; the failure branch's P&L and the
    # market value of prorated (returned) shares depend on post-offer prices,
    # which are unknown -> not modeled.
    return out


def paper_outcome(entry_price: float, shares: int, final_price: Optional[float], terminated: bool,
                  fees_usd: float, exit_price_if_terminated: Optional[float] = None,
                  terminated_loss_pct: Optional[float] = None) -> dict[str, Any]:
    """Every terminated/withdrawn deal gets a P&L, so failures stay in the
    track record (no survivorship). With a post-termination quote it is booked
    at that (bid-side) price; without one, at a flagged conservative
    placeholder of entry * (1 - terminated_loss_pct). Fees are charged in
    full on every branch (conservative: brokers often bill the reorg fee on
    the tender instruction, whether or not the deal closes)."""
    if terminated:
        if exit_price_if_terminated is None:
            loss_pct = 0.15 if terminated_loss_pct is None else float(terminated_loss_pct)
            exit_px = round(entry_price * (1.0 - loss_pct), 6)
            pnl = (exit_px - entry_price) * shares - fees_usd
            return {"result": "TERMINATED", "exit_price": exit_px, "pnl_usd": round(pnl, 4),
                    "pnl_basis": "PLACEHOLDER",
                    "note": (f"offer terminated/withdrawn; no post-termination price, booked at a "
                             f"conservative placeholder loss of {loss_pct:.0%} vs entry")}
        pnl = (exit_price_if_terminated - entry_price) * shares - fees_usd
        return {"result": "TERMINATED", "exit_price": exit_price_if_terminated,
                "pnl_usd": round(pnl, 4), "pnl_basis": "MARKET"}
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
            odd_lot_record_dates TEXT,
            odd_lot_snippet TEXT,
            offer_kind TEXT,
            security_class TEXT,
            untraded INTEGER NOT NULL DEFAULT 0,
            any_and_all INTEGER NOT NULL DEFAULT 0,
            min_fill DOUBLE PRECISION,
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
    # Column additions for tables created by earlier versions (one ALTER per transaction).
    for col, ddl in (("odd_lot_record_dates", "TEXT"), ("offer_kind", "TEXT"), ("security_class", "TEXT"),
                     ("untraded", "INTEGER NOT NULL DEFAULT 0"), ("any_and_all", "INTEGER NOT NULL DEFAULT 0"),
                     ("min_fill", "DOUBLE PRECISION")):
        _add_column(engine, "special_tender", col, ddl)


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
    async def _ticker_map(self, client: SecClient) -> dict[str, list[str]]:
        """CIK -> ALL tickers SEC lists for it (common, preferred series, warrants...)."""
        if self._tickers and time.time() - self._tickers_at < 86400:
            return self._tickers
        data = await client.get_json(TICKERS_URL)
        m: dict[str, list[str]] = {}
        for row in (data.values() if isinstance(data, dict) else data):
            cik = str(row.get("cik_str", "")).lstrip("0")
            tk = str(row.get("ticker", "")).upper().strip()
            if cik and tk and tk not in m.setdefault(cik, []):
                m[cik].append(tk)
        self._tickers, self._tickers_at = m, time.time()
        return m

    async def discover(self, client: SecClient, start: date, end: date, max_hits: int = 2000,
                       ciks: Optional[list[str]] = None) -> list[dict[str, Any]]:
        forms = ",".join(FTS_ROOT_FORMS)
        seen: dict[str, dict[str, Any]] = {}
        frm = 0
        cik_q = ("&ciks=" + ",".join(f"{int(c):010d}" for c in ciks)) if ciks else ""
        while frm < max_hits:
            url = (f"{FTS_URL}?forms={quote(forms, safe=',')}{cik_q}&dateRange=custom"
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
                # a tender whose expiration could not be parsed is UNKNOWN, never OPEN forever
                status = "OPEN" if terms.get("expiration_date") else "UNKNOWN_EXPIRY"
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
                    "odd_lot_record_dates": json.dumps(terms.get("odd_lot_record_dates") or []),
                    "offer_kind": terms.get("offer_kind") or "CASH",
                    "security_class": terms.get("security_class"),
                    "untraded": 1 if terms.get("untraded") else 0,
                    "any_and_all": 1 if terms.get("any_and_all") else 0,
                    "min_fill": terms.get("min_fill_if_all_tender"),
                    "conditions_json": json.dumps(terms.get("conditions") or {}),
                    "going_private": 1 if terms.get("going_private") else 0,
                    "status": status, "created": now, "updated": now,
                }
                cx.execute(text("""
                    INSERT INTO special_tender (tender_key, subject_cik, subject_name, ticker, file_number, root_form,
                        first_accession, first_filed_date, last_accession, last_filed_date, amendments, offer_type,
                        price_fixed, price_low, price_high, currency, expiration_date, odd_lot_priority,
                        odd_lot_record_date, odd_lot_snippet, odd_lot_record_dates, offer_kind, security_class,
                        untraded, any_and_all, min_fill, conditions_json, going_private, status,
                        created_at_utc, updated_at_utc)
                    VALUES (:tender_key, :subject_cik, :subject_name, :ticker, :file_number, :root_form,
                        :first_accession, :first_filed_date, :last_accession, :last_filed_date, :amendments,
                        :offer_type, :price_fixed, :price_low, :price_high, :currency, :expiration_date,
                        :odd_lot_priority, :odd_lot_record_date, :odd_lot_snippet, :odd_lot_record_dates,
                        :offer_kind, :security_class, :untraded, :any_and_all, :min_fill, :conditions_json,
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
                    if terms.get("expiration_date") and (terms.get("extended") or not existing["expiration_date"] or (
                            terms["expiration_date"] > existing["expiration_date"])):
                        sets.append("expiration_date=:exp")
                        upd["exp"] = terms["expiration_date"]
                    for k in ("price_fixed", "price_low", "price_high"):
                        if terms.get(k) is not None and existing[k] is not None and terms[k] != existing[k] \
                                and terms.get("offer_type") == existing["offer_type"] and not res.get("final"):
                            sets.append(f"{k}=:{k}")
                            upd[k] = terms[k]
                    if not existing["odd_lot_priority"] and terms.get("odd_lot_priority"):
                        sets += ["odd_lot_priority=1", "odd_lot_snippet=:ols"]
                        upd.update(ols=terms.get("odd_lot_snippet"))
                    # union of record dates across filings; strictest (earliest) governs
                    rds = sorted(set(_json_list(existing.get("odd_lot_record_dates"))
                                     + ([existing["odd_lot_record_date"]] if existing.get("odd_lot_record_date") else [])
                                     + list(terms.get("odd_lot_record_dates") or [])))
                    if rds:
                        sets += ["odd_lot_record_dates=:olrs", "odd_lot_record_date=:olr"]
                        upd.update(olrs=json.dumps(rds), olr=rds[0])
                    # an exchange / option-exchange classification is sticky; amendments are often terse
                    if terms.get("offer_kind") not in (None, "CASH") and (existing.get("offer_kind") or "CASH") == "CASH":
                        sets.append("offer_kind=:ok")
                        upd["ok"] = terms["offer_kind"]
                    if terms.get("untraded") and not existing.get("untraded"):
                        sets.append("untraded=1")
                cx.execute(text(f"UPDATE special_tender SET {', '.join(sets)} WHERE id=:id"), upd)
            # results
            if form.endswith("/A") and existing["status"] not in ("COMPLETED", "TERMINATED"):
                if res.get("terminated"):
                    cx.execute(text("""UPDATE special_tender SET status='TERMINATED', final_accession=:a,
                                       updated_at_utc=:u WHERE id=:id"""), {"a": acc, "u": now, "id": tender_id})
                elif res.get("final"):
                    fp = res.get("final_price")
                    if fp is None and res.get("completed_all_accepted") and existing["offer_type"] == "FIXED_PRICE":
                        fp = existing["price_fixed"]  # any-and-all fixed-price offer: paid the offer price
                    cx.execute(text("""UPDATE special_tender SET status='COMPLETED', final_accession=:a,
                                       final_price=:p, shares_accepted=:s, proration_pct=:pr, updated_at_utc=:u
                                       WHERE id=:id"""),
                               {"a": acc, "p": fp, "s": res.get("shares_accepted"),
                                "pr": res.get("proration_pct"), "u": now, "id": tender_id})
                elif res.get("expired_reported"):
                    cx.execute(text("""UPDATE special_tender SET status='EXPIRED_AWAITING_RESULTS', updated_at_utc=:u
                                       WHERE id=:id AND status IN ('OPEN','UNKNOWN_EXPIRY')"""),
                               {"u": now, "id": tender_id})
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
        iso = today.isoformat()
        stale_days = max(1, env_int("SPECIAL_UNKNOWN_EXPIRY_STALE_DAYS", 60))
        with self.engine.begin() as cx:
            t = cx.execute(text("SELECT status, expiration_date, last_filed_date FROM special_tender WHERE id=:i"),
                           {"i": tender_id}).mappings().first()
            if not t:
                return
            st, exp = t["status"], t["expiration_date"]
            new = st
            if st in ("OPEN", "UNKNOWN_EXPIRY", "STALE_UNKNOWN") and exp:
                new = "EXPIRED_AWAITING_RESULTS" if exp < iso else "OPEN"
            elif st == "EXPIRED_AWAITING_RESULTS" and exp and exp >= iso:
                new = "OPEN"  # an amendment extended the offer
            elif st == "OPEN" and not exp:
                new = "UNKNOWN_EXPIRY"
            if new == "UNKNOWN_EXPIRY" or (st == "UNKNOWN_EXPIRY" and new == st):
                last = t["last_filed_date"]
                if last and last < (today - timedelta(days=stale_days)).isoformat():
                    new = "STALE_UNKNOWN"
            if new != st:
                cx.execute(text("UPDATE special_tender SET status=:s WHERE id=:i"), {"s": new, "i": tender_id})

    # -- pricing / EV / paper book ------------------------------------------------
    def _price_client(self) -> httpx.AsyncClient:
        """Separate client for third-party quote endpoints. It deliberately does
        NOT share headers with SecClient so the SEC contact e-mail never leaves
        for a non-SEC host."""
        ua = (os.getenv("SPECIAL_PRICE_USER_AGENT", "") or DEFAULT_PRICE_USER_AGENT).strip()
        if "@" in ua or ua == self.user_agent():
            ua = DEFAULT_PRICE_USER_AGENT
        return httpx.AsyncClient(timeout=20.0, transport=self.transport, follow_redirects=True,
                                 headers={"User-Agent": ua, "Accept": "application/json"})

    async def fetch_price(self, client: httpx.AsyncClient, ticker: str) -> Optional[dict[str, Any]]:
        if self.price_source() != "yahoo_chart" or not ticker:
            return None
        if isinstance(client, SecClient):  # defensive: never send the SEC UA to a quote vendor
            raise TypeError("fetch_price must use the price client, not SecClient")
        try:
            r = await client.get(YAHOO_CHART_URL.format(ticker=quote(ticker)))
            r.raise_for_status()
            data = r.json()
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
            a = ev_assumptions()
            mp = price["price"] if price else None
            stale_note = None
            if price and price.get("as_of_utc"):
                try:
                    as_of = datetime.fromisoformat(str(price["as_of_utc"]).replace("Z", "+00:00"))
                    if as_of.tzinfo is None:
                        as_of = as_of.replace(tzinfo=timezone.utc)
                    age_h = (utc_now() - as_of).total_seconds() / 3600.0
                    if age_h > a["max_price_age_hours"]:
                        stale_note = f"quote is {age_h:.0f}h old (> {a['max_price_age_hours']:g}h): treated as unpriced"
                        mp = None
                except ValueError:
                    pass
            ev = compute_ev(t, mp, today=today, assumptions=a, ask=(price or {}).get("ask") if mp else None)
            if stale_note:
                ev["flags"].append(stale_note)
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
                           {"p": ev.get("entry_price_used") or mp, "at": now, "s": ev["shares"], "w": 1 if would else 0,
                            "ev": json.dumps(ev), "i": tender_id})
        return ev

    def record_outcomes(self, exit_prices: Optional[dict[int, float]] = None,
                        today: Optional[date] = None) -> int:
        """Book an outcome for every paper entry whose deal resolved, including
        terminated/withdrawn deals (no survivorship). exit_prices are LAST
        trades after termination (keyed by tender id); a bid-side haircut is
        applied. Entries stuck in EXPIRED_AWAITING_RESULTS / STALE_UNKNOWN past
        SPECIAL_UNRESOLVED_AFTER_DAYS are reported UNRESOLVED (shown in the
        ledger, re-evaluated when results arrive)."""
        exit_prices = exit_prices or {}
        today = today or utc_now().date()
        n = 0
        a = ev_assumptions()
        fees = a["buy_commission_usd"] + a["tender_fee_usd"]
        cutoff = (today - timedelta(days=a["unresolved_after_days"])).isoformat()
        with self.engine.begin() as cx:
            rows = cx.execute(text("""SELECT * FROM special_tender WHERE paper_entry_at_utc IS NOT NULL
                                      AND outcome_recorded_at_utc IS NULL
                                      AND status IN ('COMPLETED','TERMINATED',
                                                     'EXPIRED_AWAITING_RESULTS','STALE_UNKNOWN')""")).mappings().all()
            for t in rows:
                if t["status"] in ("EXPIRED_AWAITING_RESULTS", "STALE_UNKNOWN"):
                    exp = t["expiration_date"]
                    if t["status"] == "EXPIRED_AWAITING_RESULTS" and exp and exp > cutoff:
                        continue
                    out = {"result": "UNRESOLVED", "pnl_usd": None,
                           "note": (f"no final results parsed {a['unresolved_after_days']}+ days after expiry "
                                    f"({t['status']}); counted as unresolved, not dropped"),
                           "would_trade_at_entry": bool(t["paper_would_trade"])}
                    cx.execute(text("UPDATE special_tender SET paper_outcome_json=:o WHERE id=:i"),
                               {"o": json.dumps(out), "i": t["id"]})
                    n += 1
                    continue
                terminated = t["status"] == "TERMINATED"
                exit_px = exit_price_from_quote(exit_prices.get(int(t["id"])), a) if terminated else None
                out = paper_outcome(t["paper_entry_price"], int(t["paper_shares"] or 0), t["final_price"],
                                    terminated, fees, exit_px, a["terminated_loss_pct"])
                if out["result"] == "PENDING":
                    continue  # COMPLETED without a parsed final price: wait, stays visible as an entry
                out["would_trade_at_entry"] = bool(t["paper_would_trade"])
                out["proration_pct_reported"] = t["proration_pct"]
                out["fees_usd"] = fees
                cx.execute(text("""UPDATE special_tender SET paper_outcome_json=:o, paper_pnl_usd=:p,
                                   outcome_recorded_at_utc=:u WHERE id=:i"""),
                           {"o": json.dumps(out), "p": out.get("pnl_usd"), "u": utc_now_iso(), "i": t["id"]})
                n += 1
        return n

    def outcome_ledger(self) -> dict[str, Any]:
        """Every paper entry by outcome, failures included. n_resolved counts
        unique tenders with a booked P&L (completed AND terminated)."""
        with self.engine.begin() as cx:
            rows = cx.execute(text("""SELECT status, paper_outcome_json, paper_pnl_usd, paper_would_trade,
                                             outcome_recorded_at_utc
                                      FROM special_tender WHERE paper_entry_at_utc IS NOT NULL""")).mappings().all()
        by_result: dict[str, int] = {}
        pnl = []
        placeholders = 0
        for r in rows:
            o = json.loads(r["paper_outcome_json"]) if r["paper_outcome_json"] else {}
            res = o.get("result") or "OPEN_OR_PENDING"
            by_result[res] = by_result.get(res, 0) + 1
            if r["outcome_recorded_at_utc"] is not None and r["paper_pnl_usd"] is not None:
                pnl.append(float(r["paper_pnl_usd"]))
                placeholders += 1 if o.get("pnl_basis") == "PLACEHOLDER" else 0
        return {"entries": len(rows), "by_result": by_result, "n_resolved": len(pnl),
                "n_placeholder_pnl": placeholders,
                "pnl_usd_total": round(sum(pnl), 4) if pnl else None,
                "note": "terminated/withdrawn deals are booked (placeholder if unpriced), never dropped"}

    # -- main scan ------------------------------------------------------------------
    async def scan_once(self, lookback_days: Optional[int] = None, today: Optional[date] = None) -> dict[str, Any]:
        ua = self.user_agent()
        if not ua:
            raise RuntimeError("SEC_USER_AGENT is not set")
        today = today or utc_now().date()
        lookback = max(1, min(365, int(lookback_days or env_int("SPECIAL_LOOKBACK_DAYS", 45))))
        backfill = max(lookback, min(730, env_int("SPECIAL_BACKFILL_DAYS", 365)))
        client = SecClient(ua, env_float("SPECIAL_SEC_MAX_RPS", 5.0), transport=self.transport)
        price_client = self._price_client()
        summary: dict[str, Any] = {"started_at_utc": utc_now_iso(), "lookback_days": lookback,
                                   "backfill_days": backfill, "discovered": 0, "backfilled_originals": 0,
                                   "new": 0, "parsed": 0, "skipped_no_ticker": 0, "errors": 0, "priced": 0}
        try:
            tickers = await self._ticker_map(client)
            hits = await self.discover(client, today - timedelta(days=lookback), today)
            summary["discovered"] = len(hits)
            hits = await self._backfill_originals(client, hits, tickers, today, backfill, summary)
            for hit in hits:
                if self._known(hit["accession"]) in ("PARSED", "SKIPPED_NO_TICKER"):
                    continue
                summary["new"] += 1
                tick = next((tickers[c][0] for c in hit["ciks"] if tickers.get(c)), None)
                if not tick:
                    self._record_filing({
                        "accession": hit["accession"], "form": hit["form"], "filed_date": hit["filed_date"],
                        "subject_cik": (hit["ciks"] or [None])[0],
                        "subject_name": (hit["display_names"] or [None])[0], "ticker": None,
                        "file_number": None, "status": "SKIPPED_NO_TICKER", "tender_id": None, "terms_json": None,
                        "error": None, "source_url": None, "discovered_at_utc": utc_now_iso(), "parsed_at_utc": None})
                    summary["skipped_no_ticker"] += 1
                    continue
                cik = next(c for c in hit["ciks"] if tickers.get(c))
                url = ARCHIVE_URL.format(cik=cik, acc_nodash=_acc_nodash(hit["accession"]), acc=hit["accession"])
                try:
                    raw = (await client.get(url)).decode("utf-8", errors="replace")
                    terms = extract_terms(raw)
                    subj = (terms.get("header") or {}).get("subject") or {}
                    # ticker must belong to the SUBJECT company (never the bidder/filer) AND to the
                    # class actually tendered; untraded classes get no ticker at all
                    cands = tickers.get(subj.get("cik") or "", []) if subj.get("cik") else tickers.get(cik, [])
                    tick = select_ticker(cands, terms.get("security_class"), bool(terms.get("untraded")))
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
                open_rows = cx.execute(text("""SELECT id, ticker, untraded, offer_kind FROM special_tender
                                               WHERE status IN ('OPEN','EXPIRED_AWAITING_RESULTS','UNKNOWN_EXPIRY')""")).mappings().all()
            for r in open_rows:
                self.refresh_status(int(r["id"]), today)
                priceable = r["ticker"] and not r["untraded"] and (r["offer_kind"] or "CASH") not in ("OPTION_EXCHANGE",)
                price = await self.fetch_price(price_client, r["ticker"]) if priceable else None
                if price:
                    summary["priced"] += 1
                self.apply_price_and_ev(int(r["id"]), price, today)
            # Terminated deals with a paper entry: fetch a post-termination
            # price so the failure is booked at market (placeholder otherwise).
            with self.engine.begin() as cx:
                term_rows = cx.execute(text("""SELECT id, ticker FROM special_tender
                                               WHERE status='TERMINATED' AND paper_entry_at_utc IS NOT NULL
                                                 AND outcome_recorded_at_utc IS NULL""")).mappings().all()
            exit_prices: dict[int, float] = {}
            for r in term_rows:
                px = await self.fetch_price(price_client, r["ticker"]) if r["ticker"] else None
                if px:
                    exit_prices[int(r["id"])] = px["price"]
            summary["outcomes_recorded"] = self.record_outcomes(exit_prices, today)
        finally:
            summary["sec_requests"] = client.requests
            summary["http_errors"] = client.errors
            await client.close()
            await price_client.aclose()
        summary["finished_at_utc"] = utc_now_iso()
        self.last_scan = summary
        self.last_error = None
        self.scans += 1
        return summary

    async def _backfill_originals(self, client: SecClient, hits: list[dict[str, Any]], tickers: dict[str, list[str]],
                                  today: date, backfill_days: int, summary: dict[str, Any]) -> list[dict[str, Any]]:
        """An amendment inside the lookback window whose original filing is older than
        the window (and not already in the DB) means an older offer may still be open:
        fetch the original so terms (price, odd-lot clause, record dates) are known."""
        have = {h["accession"] for h in hits}
        originals_in_window = {(c, (h["form"] or "").replace("/A", "")) for h in hits
                               if not (h["form"] or "").endswith("/A") for c in h["ciks"]}
        extra: list[dict[str, Any]] = []
        asked: set[str] = set()
        for h in hits:
            if not (h["form"] or "").endswith("/A"):
                continue
            root = h["form"].replace("/A", "")
            ciks = [c for c in h["ciks"] if tickers.get(c)]
            if not ciks or any((c, root) in originals_in_window for c in ciks):
                continue
            with self.engine.begin() as cx:
                known = cx.execute(text("SELECT 1 FROM special_tender WHERE subject_cik IN :c AND root_form=:r"
                                        ).bindparams(bindparam("c", expanding=True)),
                                   {"c": ciks, "r": root}).first()
            if known or ciks[0] in asked:
                continue
            asked.add(ciks[0])
            try:
                found = await self.discover(client, today - timedelta(days=backfill_days),
                                            date.fromisoformat(h["filed_date"]) if h.get("filed_date") else today,
                                            max_hits=200, ciks=[ciks[0]])
            except Exception as e:  # backfill is best-effort
                log.info("backfill failed for %s: %s", ciks[0], e)
                continue
            for f in found:
                if f["form"] in ORIGINAL_FORMS and f["accession"] not in have and \
                        f["form"] == root and (f["filed_date"] or "") <= (h["filed_date"] or "9999"):
                    have.add(f["accession"])
                    extra.append(f)
        summary["backfilled_originals"] = len(extra)
        return sorted(hits + extra, key=lambda r: (r["filed_date"] or "", r["accession"]))

    # -- read API --------------------------------------------------------------------
    @staticmethod
    def _tender_out(r: dict[str, Any]) -> dict[str, Any]:
        d = dict(r)
        for k in ("conditions_json", "ev_json", "paper_entry_ev_json", "paper_outcome_json"):
            v = d.pop(k, None)
            d[k[:-5]] = json.loads(v) if v else None
        d["odd_lot_priority"] = bool(d.get("odd_lot_priority"))
        d["going_private"] = bool(d.get("going_private"))
        d["untraded"] = bool(d.get("untraded"))
        d["any_and_all"] = bool(d.get("any_and_all"))
        d["odd_lot_record_dates"] = _json_list(d.get("odd_lot_record_dates"))
        d["odd_lot_record_date_conflict"] = len(d["odd_lot_record_dates"]) > 1
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
            "outcome_ledger": self.outcome_ledger(),
            "scans": self.scans,
            "last_scan": self.last_scan,
            "last_error": self.last_error,
        }


def load_fixture(path: str) -> str:
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:
        return f.read()
