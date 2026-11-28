"""TRIAGE OS backtest + precision labelling. Real public data only.

1. Ground truth: 363 sale orders entered on CourtListener/RECAP dockets in a
   window (document search, type=rd), grouped per docket.
2. Replay: would our scoring have flagged the debtor before the sale order?
   - CourtListener channel: the docket itself (petition date, chapter score).
   - SEC channel: 8-Ks of a filer whose name matches the debtor, scored by items.
   Lead time = sale order date - first flag date.
3. False-positive rate: historical flagged 8-Ks (1.03/2.04) in an older window,
   checked for a sale order on CourtListener within the follow-up horizon.
4. Precision: label stored signals true_distress / false_positive / unclear
   (item_check on filing text for SEC; debtor-type and chapter rules for courts).
Coverage limits (RECAP is partial; most debtors are private) are reported, not hidden.
"""
import datetime as dt
import html
import importlib.util
import json
import re
import statistics
import urllib.parse
from pathlib import Path

def _load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

desk = _load("desk")
item_check = _load("item_check")

CL = "https://www.courtlistener.com/api/rest/v4/search/"
EFTS = "https://efts.sec.gov/LATEST/search-index"
CL_HEADERS = {"User-Agent": "TRIAGE-OS-research/0.1"}
SALE_ORDER_QUERIES = ['description:"order approving the sale" AND description:363',
                      'description:"order authorizing the sale" AND description:363',
                      'description:"sale order" AND description:363']
ORDER_RE = re.compile(r"^\s*(agreed |final |amended )?order\b[^.]{0,200}?\b(approving|authorizing)\b[^.]{0,120}?\bsale\b", re.I)
NOT_ORDER_RE = re.compile(r"^\s*(objection|motion|notice|transmittal|application|response|reply|declaration|certificate|stipulation)", re.I)
SEC_FLAG = 20      # score_sec_items threshold (1.03=40, 2.04=30, 2.06/3.01=20)
COURT_FLAG = 20    # score_court_item threshold (chapter 11 alone = 20)

def days(a, b):
    return (dt.date.fromisoformat(b[:10]) - dt.date.fromisoformat(a[:10])).days

# --- 1. ground truth ------------------------------------------------------------
def is_sale_order(description):
    d = description or ""
    return bool(ORDER_RE.search(d)) and not NOT_ORDER_RE.search(d)

def group_sale_orders(results):
    """rd search results -> {docket_id: {sale_order_date, sale_order_url, description}} (earliest order)."""
    out = {}
    for r in results:
        if not is_sale_order(r.get("description")) or not r.get("entry_date_filed"):
            continue
        k = str(r["docket_id"])
        if k not in out or r["entry_date_filed"] < out[k]["sale_order_date"]:
            out[k] = {"docket_id": k, "sale_order_date": r["entry_date_filed"],
                      "sale_order_url": urllib.parse.urljoin("https://www.courtlistener.com", r.get("absolute_url") or ""),
                      "description": (r.get("description") or "")[:300]}
    return out

def collect_sale_orders(after, before, fetch=desk.get_json, max_pages=10):
    results = []
    for q in SALE_ORDER_QUERIES:
        url = CL + "?" + urllib.parse.urlencode({"type": "rd", "q": q, "entry_date_filed_after": after,
                                                 "entry_date_filed_before": before,
                                                 "order_by": "entry_date_filed desc"})
        for _ in range(max_pages):
            try:
                data = fetch(url, CL_HEADERS)
            except Exception:
                break
            results += data.get("results", [])
            url = data.get("next")
            if not url:
                break
    cases = group_sale_orders(results)
    metas = docket_meta_batch(list(cases), fetch)
    for k, c in cases.items():
        m = metas.get(k, {})
        c.update({"case_name": m.get("caseName"), "petition_date": m.get("dateFiled"),
                  "chapter": m.get("chapter"), "court_id": m.get("court_id"),
                  "docket_url": urllib.parse.urljoin("https://www.courtlistener.com", m.get("docket_absolute_url") or ""),
                  "docket_meta": {x: m.get(x) for x in ("caseName", "chapter", "cause", "suitNature")}})
    return [c for c in cases.values() if c.get("case_name") and c.get("petition_date")]

def docket_meta_batch(docket_ids, fetch, batch=20):
    """Docket metadata for many dockets in few calls (anonymous CourtListener limits are tight)."""
    out = {}
    for i in range(0, len(docket_ids), batch):
        chunk = docket_ids[i:i + batch]
        url = CL + "?" + urllib.parse.urlencode({"type": "r", "q": "docket_id:(" + " OR ".join(map(str, chunk)) + ")"})
        while url:
            try:
                data = fetch(url, CL_HEADERS)
            except Exception:
                break
            for m in data.get("results", []):
                out[str(m.get("docket_id"))] = m
            url = data.get("next") if len(out) < len(docket_ids) else None
    return out

# --- 2. replay --------------------------------------------------------------------
def sec_first_flag(case_name, before, fetch, user_agent, lookback_days=730):
    """First 8-K by a filer whose normalized name equals the debtor's, with item score >= SEC_FLAG."""
    norm = desk.normalize_name(case_name)
    if not norm or len(norm) < 3:
        return None
    start = (dt.date.fromisoformat(before) - dt.timedelta(days=lookback_days)).isoformat()
    url = EFTS + "?" + urllib.parse.urlencode({"q": f'"{desk.clean_entity_name(case_name)}"', "forms": "8-K",
                                               "dateRange": "custom", "startdt": start, "enddt": before})
    try:
        data = fetch(url, desk._sec_headers(user_agent))
    except Exception:
        return None
    best = None
    for h in data.get("hits", {}).get("hits", []):
        s = h.get("_source", {})
        names = [desk.normalize_name(n) for n in s.get("display_names") or []]
        if norm not in names:
            continue
        if desk.score_sec_items(s.get("items")) >= SEC_FLAG and s.get("file_date") <= before:
            if best is None or s["file_date"] < best["date"]:
                best = {"date": s["file_date"], "items": s.get("items"), "adsh": s.get("adsh")}
    return best

def replay(cases, sec_lookup=None):
    """Annotate each ground-truth case with first flag per channel and lead times."""
    rows = []
    for c in cases:
        court_score = desk.score_court_item(dict(c.get("docket_meta") or {}, caseName=c["case_name"],
                                                 chapter=c.get("chapter")))
        court_flag = c["petition_date"] if court_score >= COURT_FLAG and c["petition_date"] <= c["sale_order_date"] else None
        sec = sec_lookup(c) if sec_lookup else None
        sec_flag = sec["date"] if sec else None
        first = min([d for d in (court_flag, sec_flag) if d], default=None)
        rows.append(dict(c, court_score=court_score, court_flag=court_flag, sec_flag=sec_flag,
                         sec_items=(sec or {}).get("items"), first_flag=first,
                         lead_days=days(first, c["sale_order_date"]) if first else None,
                         sec_lead_days=days(sec_flag, c["sale_order_date"]) if sec_flag else None))
    return rows

def summarize(rows):
    n = len(rows)
    flagged = [r for r in rows if r["first_flag"]]
    sec = [r for r in rows if r["sec_flag"]]
    leads = [r["lead_days"] for r in flagged]
    return {"n_sale_orders": n,
            "hit_rate_any": round(len(flagged) / n, 3) if n else None,
            "hit_rate_court": round(sum(1 for r in rows if r["court_flag"]) / n, 3) if n else None,
            "hit_rate_sec": round(len(sec) / n, 3) if n else None,
            "n_sec_hits": len(sec),
            "median_lead_days_any": statistics.median(leads) if leads else None,
            "median_lead_days_sec": statistics.median([r["sec_lead_days"] for r in sec]) if sec else None,
            "lead_days_p25_p75": (statistics.quantiles(leads, n=4)[0], statistics.quantiles(leads, n=4)[2]) if len(leads) >= 4 else None}

# --- 3. false positives -----------------------------------------------------------
def has_sale_order(case_name, after, before, fetch):
    name = desk.clean_entity_name(case_name).replace('"', "")
    q = f'caseName:"{name}" AND (description:"approving the sale" OR description:"authorizing the sale" OR description:"sale order")'
    url = CL + "?" + urllib.parse.urlencode({"type": "rd", "q": q, "entry_date_filed_after": after,
                                             "entry_date_filed_before": before})
    data = fetch(url, CL_HEADERS)
    return any(is_sale_order(r.get("description")) for r in data.get("results", []))

def sale_order_names(names, after, before, fetch, batch=15, max_pages=5):
    """Batched: normalized debtor names (among `names`) with a 363 sale order entered in [after, before].
    Returns (found_set, checked_set); names in failed batches are not 'checked'."""
    found, checked = set(), set()
    for i in range(0, len(names), batch):
        chunk = names[i:i + batch]
        ors = " OR ".join(f'caseName:"{desk.clean_entity_name(n).replace(chr(34), "")}"' for n in chunk)
        q = f'({ors}) AND (description:"approving the sale" OR description:"authorizing the sale" OR description:"sale order")'
        url = CL + "?" + urllib.parse.urlencode({"type": "rd", "q": q, "entry_date_filed_after": after,
                                                 "entry_date_filed_before": before})
        ids, ok = set(), True
        for _ in range(max_pages):
            try:
                data = fetch(url, CL_HEADERS)
            except Exception:
                ok = False
                break
            ids |= {str(r["docket_id"]) for r in data.get("results", []) if is_sale_order(r.get("description"))}
            url = data.get("next")
            if not url:
                break
        if not ok:
            continue
        metas = docket_meta_batch(sorted(ids), fetch) if ids else {}
        meta_names = {desk.normalize_name(m.get("caseName")) for m in metas.values()}
        for n in chunk:
            checked.add(desk.normalize_name(n))
            if desk.normalize_name(n) in meta_names:
                found.add(desk.normalize_name(n))
    return found, checked

def false_positive_rate(flags, fetch, horizon_days=540):
    """flags: [{entity, date}] from an older window. FP = no 363 sale order found within horizon
    (horizon counted from the latest flag date in the sample)."""
    if not flags:
        return [], {"n_flags": 0, "n_checked": 0, "fp_rate_no_363": None}
    after = min(f["date"] for f in flags)
    before = (dt.date.fromisoformat(max(f["date"] for f in flags)) + dt.timedelta(days=horizon_days)).isoformat()
    found, checked = sale_order_names([f["entity"] for f in flags], after, before, fetch)
    out = []
    for f in flags:
        n = desk.normalize_name(f["entity"])
        out.append(dict(f, sale_order_found=(n in found) if n in checked else None))
    checked = [o for o in out if o["sale_order_found"] is not None]
    fp = sum(1 for o in checked if not o["sale_order_found"])
    return out, {"n_flags": len(flags), "n_checked": len(checked),
                 "fp_rate_no_363": round(fp / len(checked), 3) if checked else None}

# --- 4. precision labels ------------------------------------------------------------
BUSINESS = re.compile(r"\b(inc|llc|l\.l\.c|corp|co|company|lp|llp|ltd|holdings?|group|partners|trust|bank|fund|"
                      r"associates|enterprises|industries|properties|realty|capital|partnership|church|hospital|"
                      r"services|systems|communications|technologies|international|ventures|management)\b", re.I)
DISTRESS_TEXT = re.compile(r"chapter 11|chapter 7|bankruptcy|going concern|event of default|forbearance|"
                           r"accelerat(ed|ion) of (the |all )?(obligations|indebtedness|loans?|notes|amounts outstanding)|receivership|restructuring support|insolven|wind[- ]down", re.I)
BENIGN_301 = re.compile(r"transfer (its|the) listing|voluntar(il)?y (to )?delist|in connection with the (merger|closing)|"
                        r"upon (the )?(consummation|closing) of the merger|regained compliance", re.I)
WEAK_301 = re.compile(r"minimum bid price|bid price requirement|market value of (listed|publicly held)|"
                      r"stockholders.? equity requirement|late filing|periodic (report|filing)", re.I)

def html_to_text(raw):
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw or "")
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t))

def label_sec(items, text):
    items = set(items or [])
    if not text:
        return "unclear", "filing text unavailable"
    if items & {"1.03", "2.04"}:
        status, why = item_check.check_items(items, text)
        if status == "false_positive":
            return "false_positive", why
        return "true_distress", f"item_check {status}: {why}"
    if DISTRESS_TEXT.search(text):
        return "true_distress", "text: " + DISTRESS_TEXT.search(text).group(0)
    if "3.01" in items and BENIGN_301.search(text):
        return "false_positive", "3.01 benign: " + BENIGN_301.search(text).group(0)
    if "3.01" in items and WEAK_301.search(text):
        return "unclear", "3.01 listing deficiency only: " + WEAK_301.search(text).group(0)
    return "unclear", "no distress language found"

def label_court(raw):
    name = raw.get("caseName") or ""
    ch = str(raw.get("chapter") or "")
    if ch == "13":
        return "false_positive", "chapter 13 individual"
    if ch in ("11", "7", "15") or "chapter 11" in (raw.get("query") or ""):
        if not ch:
            return "unclear", "no chapter in metadata"
        if not BUSINESS.search(name) and len(name.split()) <= 4:
            return "false_positive", f"chapter {ch}, individual debtor (not a desk target)"
        return "true_distress", f"chapter {ch} business debtor"
    if ch == "13":
        return "false_positive", "chapter 13 individual"
    if "receiv" in (name + json.dumps(raw.get("recap_documents") or [])).lower():
        return "true_distress", "receivership in docket"
    return "unclear", "no chapter / non-bankruptcy docket"

def signal_kind(source, raw):
    if source == "sec":
        it = set(raw.get("items") or [])
        for k in ("1.03", "2.04", "2.06", "3.01"):
            if k in it:
                return "sec_" + k
        return "sec_other"
    ch = raw.get("chapter")
    return f"court_ch{ch}" if ch else "court_unknown"

def ensure_labels(con):
    con.execute("""CREATE TABLE IF NOT EXISTS labels (source TEXT, external_id TEXT, label TEXT NOT NULL,
        reason TEXT, signal_kind TEXT, method TEXT, labeled_at TEXT,
        PRIMARY KEY (source, external_id))""")

def label_all(con, fetch_text, user_agent=None):
    ensure_labels(con)
    # scope: SEC + CourtListener connectors only (other feeds have their own QA)
    rows = con.execute("SELECT source, external_id, url, raw_json FROM signals "
                       "WHERE source IN ('sec', 'courtlistener')").fetchall()
    con.execute("DELETE FROM labels WHERE source NOT IN ('sec', 'courtlistener')")
    for source, ext, url, raw_json in rows:
        raw = json.loads(raw_json)
        if source == "sec":
            try:
                text = html_to_text(fetch_text(url))
            except Exception:
                text = ""
            label, reason = label_sec(raw.get("items"), text)
            method = "item_check+filing_text"
        else:
            label, reason = label_court(raw)
            method = "docket_metadata_rules"
        con.execute("INSERT OR REPLACE INTO labels VALUES (?,?,?,?,?,?,?)",
                    (source, ext, label, reason[:300], signal_kind(source, raw), method, desk.now()))
    con.commit()
    return precision(con)

def precision(con):
    out = {}
    for kind, label, n in con.execute("SELECT signal_kind, label, count(*) FROM labels GROUP BY 1, 2"):
        out.setdefault(kind, {"true_distress": 0, "false_positive": 0, "unclear": 0})[label] = n
    total = {"true_distress": 0, "false_positive": 0, "unclear": 0}
    for v in out.values():
        for k in total:
            total[k] += v[k]
    out["ALL"] = total
    for v in out.values():
        decided = v["true_distress"] + v["false_positive"]
        v["n"] = decided + v["unclear"]
        v["precision_decided"] = round(v["true_distress"] / decided, 3) if decided else None
        v["precision_strict"] = round(v["true_distress"] / v["n"], 3) if v["n"] else None
    return out

# --- orchestration -----------------------------------------------------------------
def fetch_text_factory(user_agent, opener=None):
    import time, urllib.request
    def fetch_text(url):
        time.sleep(0.12)  # stay under SEC 10 req/s
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with (opener or urllib.request.urlopen)(req, timeout=60) as r:
            return r.read().decode("utf-8", "replace")
    return fetch_text

def fp_flags_from_efts(start, end, user_agent, fetch=desk.get_json, max_pages=3):
    """Historical 8-K flags with items 1.03 or 2.04 (metadata) in [start, end]."""
    flags, seen = [], set()
    for q in ('"Item 1.03"', '"Item 2.04"'):
        for page in range(max_pages):
            url = EFTS + "?" + urllib.parse.urlencode({"q": q, "forms": "8-K", "dateRange": "custom",
                                                       "startdt": start, "enddt": end, "from": page * 100})
            try:
                hits = fetch(url, desk._sec_headers(user_agent)).get("hits", {}).get("hits", [])
            except Exception:
                break
            for h in hits:
                s = h.get("_source", {})
                cik = (s.get("ciks") or [None])[0]
                if cik and cik not in seen and set(s.get("items") or []) & {"1.03", "2.04"}:
                    seen.add(cik)
                    flags.append({"entity": (s.get("display_names") or [""])[0], "cik": cik,
                                  "date": s.get("file_date"), "items": s.get("items")})
            if len(hits) < 100:
                break
    return flags

def run(db_path, out_dir, user_agent, gt_after, gt_before, fp_start, fp_end,
        cl_fetch=desk.get_json, sec_fetch=desk.get_json, fetch_text=None, sec_replay=True):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    cases = collect_sale_orders(gt_after, gt_before, fetch=cl_fetch)
    lookup = (lambda c: sec_first_flag(c["case_name"], c["sale_order_date"], sec_fetch, user_agent)) if sec_replay else None
    rows = replay(cases, lookup)
    flags = fp_flags_from_efts(fp_start, fp_end, user_agent, fetch=sec_fetch)
    fp_rows, fp = false_positive_rate(flags, cl_fetch)
    with desk.connect(db_path) as con:
        prec = label_all(con, fetch_text or fetch_text_factory(user_agent))
        con.execute("""CREATE TABLE IF NOT EXISTS backtest_cases (docket_id TEXT PRIMARY KEY, case_name TEXT,
            court_id TEXT, chapter TEXT, petition_date TEXT, sale_order_date TEXT, sale_order_url TEXT,
            court_flag TEXT, sec_flag TEXT, sec_items TEXT, lead_days INTEGER, run_at TEXT)""")
        for r in rows:
            con.execute("INSERT OR REPLACE INTO backtest_cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (r["docket_id"], r["case_name"], r["court_id"], r["chapter"], r["petition_date"],
                         r["sale_order_date"], r["sale_order_url"], r["court_flag"], r["sec_flag"],
                         json.dumps(r["sec_items"]), r["lead_days"], desk.now()))
        con.commit()
    result = {"ground_truth_window": [gt_after, gt_before], "replay": summarize(rows),
              "fp_window": [fp_start, fp_end], "false_positives": fp, "precision": prec}
    (out / "backtest_cases.json").write_text(json.dumps(rows, indent=1, default=str))
    (out / "backtest_fp.json").write_text(json.dumps(fp_rows, indent=1))
    (out / "backtest_metrics.json").write_text(json.dumps(result, indent=1))
    return result
