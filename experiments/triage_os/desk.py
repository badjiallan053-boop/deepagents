"""TRIAGE OS: minimal provenance-first special-situations ingestion and triage.

Standard library only. Requires an explicit SEC identity (User-Agent with contact).
CourtListener token is optional (anonymous v4 search works; token raises limits).
Not an automated investment or legal decision engine. Every signal is stored
as 'unverified'.
"""
import argparse
import csv
import datetime as dt
import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DB = Path(os.environ.get("TRIAGE_DB", "triage.db"))
TERMS = {
    "bankruptcy": 18, "chapter 11": 18, "363 sale": 22,
    "sale procedures": 22, "foreclosure": 18, "receivership": 18,
    "going concern": 12, "covenant": 8, "default": 12,
    "liquidation": 15, "restructuring": 8, "credit bid": 18,
    "debtor in possession": 15, "dip financing": 15, "stalking horse": 20,
    "forbearance": 12, "acceleration": 10, "delisting": 10,
}
# Form 8-K item codes indicating distress (points).
SEC_ITEMS = {
    "1.03": 40,  # Bankruptcy or receivership
    "2.04": 30,  # Triggering events accelerating an obligation
    "2.06": 20,  # Material impairments
    "3.01": 20,  # Delisting / failure to satisfy listing rule
    "4.02": 15,  # Non-reliance on prior financials
    "2.05": 10,  # Exit or disposal costs
    "5.02": 5,   # Officer/director departures
    "1.02": 10,  # Termination of a material definitive agreement
}
CHAPTER_POINTS = {7: 15, 11: 20, 15: 10}
SEC_FORMS = {"8-K", "10-K", "10-Q", "6-K", "20-F"}

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def connect(path=DB):
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE IF NOT EXISTS signals (
      id INTEGER PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL,
      title TEXT NOT NULL, url TEXT NOT NULL, event_date TEXT,
      fetched_at TEXT NOT NULL, raw_json TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'unverified',
      UNIQUE(source, external_id))""")
    return con

def score(title):
    """Heuristic keyword prioritization; not an investment score."""
    value = sum(points for term, points in TERMS.items() if term in (title or "").lower())
    return min(100, value)

def score_sec_items(items):
    return sum(SEC_ITEMS.get(str(i).strip(), 0) for i in (items or []))

def score_court_item(item):
    text = " ".join(filter(None, [item.get("caseName"), item.get("cause"),
                                  item.get("suitNature")] +
                    [d.get("description") or d.get("short_description")
                     for d in item.get("recap_documents") or []]))
    value = score(text)
    try:
        value += CHAPTER_POINTS.get(int(item.get("chapter")), 0)
    except (TypeError, ValueError):
        pass
    return value

def signal_score(source, title, raw):
    if source == "sec":
        return min(100, score(title) + score_sec_items(raw.get("items")))
    if source == "courtlistener":
        return min(100, score_court_item(raw))
    return score(title)

def store(con, source, external_id, title, url, event_date, raw):
    if not (source and external_id and title and url.startswith("https://")):
        raise ValueError("Incomplete signal provenance")
    con.execute("""INSERT INTO signals
       (source, external_id, title, url, event_date, fetched_at, raw_json)
       VALUES (?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(source, external_id) DO UPDATE SET
       title=excluded.title, url=excluded.url, event_date=excluded.event_date,
       fetched_at=excluded.fetched_at, raw_json=excluded.raw_json""",
       (source, external_id, title, url, event_date, now(), json.dumps(raw)))
    con.commit()

# --- HTTP with rate limit and retry -------------------------------------
_MIN_INTERVAL = 0.11  # <= ~9 req/s, under SEC's 10 req/s ceiling
_last_call = [0.0]

def get_json(url, headers, retries=4, backoff=1.0, opener=None):
    opener = opener or urllib.request.urlopen
    for attempt in range(retries + 1):
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()
        try:
            req = urllib.request.Request(url, headers=headers)
            with opener(req, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == retries:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            delay = float(retry_after) if retry_after and retry_after.isdigit() else backoff * 2 ** attempt
        except urllib.error.URLError:
            if attempt == retries:
                raise
            delay = backoff * 2 ** attempt
        time.sleep(delay)

# --- SEC ------------------------------------------------------------------
def _sec_headers(user_agent):
    if "@" not in (user_agent or ""):
        raise ValueError("SEC requires a descriptive user-agent with contact information")
    return {"User-Agent": user_agent, "Accept": "application/json"}

def _store_sec_rows(con, cik, name, block):
    columns = ("accessionNumber", "primaryDocument", "form", "filingDate", "items")
    n = len(block.get("accessionNumber", []))
    cols = [block.get(c) or [""] * n for c in columns]
    count = 0
    for accession, document, form, date, items in zip(*cols):
        if form not in SEC_FORMS:
            continue
        acc = accession.replace("-", "")
        filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{urllib.parse.quote(document)}"
        item_list = [i for i in (items or "").split(",") if i]
        title = f"{name} — {form} filed {date}" + (f" (items {', '.join(item_list)})" if item_list else "")
        store(con, "sec", accession, title, filing_url, date,
              {"cik": cik, "entity": name, "form": form, "filing_date": date,
               "document": document, "items": item_list})
        count += 1
    return count

def ingest_sec(con, cik, user_agent, include_history=False, fetch=get_json):
    headers = _sec_headers(user_agent)
    cik = str(int(cik)).zfill(10)
    data = fetch(f"https://data.sec.gov/submissions/CIK{cik}.json", headers)
    name = data.get("name", cik)
    filings = data.get("filings", {})
    count = _store_sec_rows(con, cik, name, filings.get("recent", {}))
    if include_history:
        for f in filings.get("files", []):
            block = fetch(f"https://data.sec.gov/submissions/{f['name']}", headers)
            count += _store_sec_rows(con, cik, name, block)
    return count

def ingest_sec_fulltext(con, query, user_agent, start, end, items=None, max_pages=5, fetch=get_json):
    """EDGAR full-text search for 8-Ks; keeps hits containing any of `items`."""
    headers = _sec_headers(user_agent)
    wanted = set(items or [])
    count = 0
    for page in range(max_pages):
        params = urllib.parse.urlencode({"q": query, "forms": "8-K", "dateRange": "custom",
                                         "startdt": start, "enddt": end, "from": page * 100})
        data = fetch("https://efts.sec.gov/LATEST/search-index?" + params, headers)
        hits = data.get("hits", {}).get("hits", [])
        for hit in hits:
            src = hit.get("_source", {})
            hit_items = src.get("items") or []
            if wanted and not wanted.intersection(hit_items):
                continue
            adsh = src.get("adsh") or hit.get("_id", "").split(":")[0]
            doc = hit.get("_id", ":").split(":", 1)[1]
            ciks = src.get("ciks") or []
            if not (adsh and doc and ciks):
                continue
            cik = int(ciks[0])
            entity = (src.get("display_names") or [str(cik)])[0]
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{urllib.parse.quote(doc)}"
            title = f"{entity} — {src.get('form', '8-K')} filed {src.get('file_date')} (items {', '.join(hit_items)})"
            store(con, "sec", adsh, title, url, src.get("file_date"),
                  {"cik": str(cik).zfill(10), "entity": entity, "form": src.get("form"),
                   "filing_date": src.get("file_date"), "document": doc,
                   "items": hit_items, "query": query})
            count += 1
        if len(hits) < 100:
            break
    return count

# --- CourtListener --------------------------------------------------------
COURT_SEARCH = "https://www.courtlistener.com/api/rest/v4/search/"

def ingest_court(con, query, token=None, filed_after=None, max_pages=5, fetch=get_json):
    params = {"q": query, "type": "r", "order_by": "dateFiled desc"}
    if filed_after:
        params["filed_after"] = filed_after
    url = COURT_SEARCH + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "TRIAGE-OS-research/0.1"}
    if token:
        headers["Authorization"] = "Token " + token
    count = 0
    for _ in range(max_pages):
        data = fetch(url, headers)
        for item in data.get("results", []):
            external_id = str(item.get("docket_id") or item.get("id") or "")
            title = item.get("caseName") or item.get("case_name") or item.get("description") or ""
            path = item.get("docket_absolute_url") or item.get("absolute_url") or ""
            item_url = urllib.parse.urljoin("https://www.courtlistener.com", path)
            if external_id and title and path and item_url.startswith("https://"):
                item = dict(item, query=query)
                store(con, "courtlistener", external_id, title, item_url,
                      item.get("dateFiled") or item.get("date_filed"), item)
                count += 1
        url = data.get("next")
        if not url:
            break
    return count

# --- Ranking / export -------------------------------------------------------
def _signal_type(source, raw):
    if source == "sec":
        hits = [i for i in raw.get("items", []) if i in SEC_ITEMS]
        return f"8-K items {','.join(hits)}" if hits else raw.get("form", "filing")
    if source == "courtlistener":
        ch = raw.get("chapter")
        return f"chapter {ch} docket" if ch else f"docket ({raw.get('query', 'search')})"
    return source

def rank(con, limit=25):
    rows = con.execute("""SELECT source, title, url, event_date, fetched_at, status, raw_json
                          FROM signals""").fetchall()
    out = []
    for r in rows:
        raw = json.loads(r[6])
        out.append({"priority": signal_score(r[0], r[1], raw), "source": r[0], "title": r[1],
                    "entity": raw.get("entity") or raw.get("caseName") or r[1],
                    "signal_type": _signal_type(r[0], raw),
                    "url": r[2], "event_date": r[3], "fetched_at": r[4], "status": r[5]})
    out.sort(key=lambda x: (x["priority"], x["event_date"] or ""), reverse=True)
    return out[:limit]

def export_csv(con, path, limit=20):
    rows = rank(con, limit)
    fields = ["priority", "source", "entity", "event_date", "signal_type", "url", "status"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return len(rows)

def main():
    parser = argparse.ArgumentParser(description="TRIAGE OS provenance-first MVP")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sec = sub.add_parser("ingest-sec")
    sec.add_argument("--cik", required=True)
    sec.add_argument("--user-agent", required=True)
    sec.add_argument("--history", action="store_true")
    ft = sub.add_parser("ingest-sec-fulltext")
    ft.add_argument("--query", required=True)
    ft.add_argument("--user-agent", required=True)
    ft.add_argument("--start", required=True)
    ft.add_argument("--end", required=True)
    ft.add_argument("--items", default="1.03,2.04,2.06,3.01")
    court = sub.add_parser("ingest-court")
    court.add_argument("--query", required=True)
    court.add_argument("--filed-after")
    court.add_argument("--max-pages", type=int, default=5)
    rank_cmd = sub.add_parser("rank")
    rank_cmd.add_argument("--limit", type=int, default=25)
    exp = sub.add_parser("export")
    exp.add_argument("--out", required=True)
    exp.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    with connect() as con:
        if args.command == "init":
            print(f"Initialized {DB}")
        elif args.command == "ingest-sec":
            print(f"Stored {ingest_sec(con, args.cik, args.user_agent, args.history)} SEC filings")
        elif args.command == "ingest-sec-fulltext":
            n = ingest_sec_fulltext(con, args.query, args.user_agent, args.start, args.end,
                                    [i for i in args.items.split(",") if i])
            print(f"Stored {n} SEC 8-K hits")
        elif args.command == "ingest-court":
            n = ingest_court(con, args.query, os.getenv("COURTLISTENER_TOKEN"),
                             args.filed_after, args.max_pages)
            print(f"Stored {n} court records")
        elif args.command == "export":
            print(f"Exported {export_csv(con, args.out, args.limit)} rows to {args.out}")
        else:
            print(json.dumps(rank(con, args.limit), indent=2))

if __name__ == "__main__":
    main()
