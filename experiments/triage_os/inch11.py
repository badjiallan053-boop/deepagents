"""TRIAGE OS - is a watchlist name already in Chapter 11?

A pre-filing watchlist must drop companies that have already filed. Three public,
read-only checks per CIK (SEC EDGAR):
  1. submissions: any 8-K with item 1.03 (bankruptcy/receivership) in the lookback;
  2. XBRL companyfacts: LiabilitiesSubjectToCompromise (ASC 852) reported > 0;
  3. XBRL companyfacts: debtor-in-possession financing concepts reported > 0.
Every hit keeps its source URL. A fetch error leaves the name 'unknown', never 'clear'.
"""
import datetime as dt

LSTC = ("LiabilitiesSubjectToCompromise",)
DIP = ("DebtorInPossessionFinancingAmountArranged", "DebtorInPossessionFinancingBorrowingsOutstanding",
       "ProceedsFromDebtorInPossessionFinancing", "DebtorInPossessionFinancingAmountOutstanding")

def _recent(date, since):
    return (date or "") >= since

def check(cik, fetch, headers, lookback_days=730, today=None):
    cik10 = str(int(cik)).zfill(10)
    since = ((today or dt.date.today()) - dt.timedelta(days=lookback_days)).isoformat()
    out = {"cik": str(int(cik)), "in_ch11": False, "evidence": [], "status": "clear"}
    try:
        sub = fetch(f"https://data.sec.gov/submissions/CIK{cik10}.json", headers)
        r = sub.get("filings", {}).get("recent", {})
        for form, date, items, acc, doc in zip(r.get("form", []), r.get("filingDate", []), r.get("items", []),
                                               r.get("accessionNumber", []), r.get("primaryDocument", [])):
            if form.startswith("8-K") and "1.03" in (items or "") and _recent(date, since):
                out["evidence"].append(("8-K 1.03", date, f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"))
    except Exception as exc:
        out["status"] = f"unknown: submissions {exc}"
    try:
        facts = fetch(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json", headers).get("facts", {}).get("us-gaap", {})
        for tag, label in [(t, "XBRL LiabilitiesSubjectToCompromise") for t in LSTC] + [(t, "XBRL DIP " + t) for t in DIP]:
            for unit in facts.get(tag, {}).get("units", {}).values():
                hits = [u for u in unit if (u.get("val") or 0) > 0 and _recent(u.get("end") or u.get("filed"), since)]
                if hits:
                    h = max(hits, key=lambda u: u.get("end", ""))
                    out["evidence"].append((label, h.get("end"), f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{h.get('accn', '').replace('-', '')}/"))
                    break
    except Exception as exc:
        if out["status"] == "clear":
            out["status"] = f"unknown: companyfacts {exc}"
    if out["evidence"]:
        out["in_ch11"], out["status"] = True, "in_ch11"
    return out

def filter_watchlist(rows, fetch, headers, n=50, today=None, log=None):
    """rows: prefiling.build() output. Marks filed names and returns the first n clear ones."""
    kept = []
    for e in rows:
        if e.get("filed"):
            continue
        if e["key"].startswith("cik:"):
            res = check(e["key"][4:], fetch, headers, today=today)
            if log is not None:
                log.append((e["name"], res))
            if res["in_ch11"]:
                e["filed"] = True
                e["filed_evidence"] = res["evidence"]
                continue
        kept.append(e)
        if len(kept) >= n:
            break
    return kept
