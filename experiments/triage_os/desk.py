"""TRIAGE OS: minimal provenance-first special-situations ingestion and triage.

Standard library only. Requires an explicit SEC identity (User-Agent with contact).
CourtListener token is optional (anonymous v4 search works; token raises limits).
Not an automated investment or legal decision engine. Every signal is stored
as 'unverified'.
"""
import argparse
import csv
import importlib.util
import datetime as dt
import json
import os
import re
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
    cols = {r[1] for r in con.execute("PRAGMA table_info(signals)")}
    if "entity_key" not in cols:
        con.execute("ALTER TABLE signals ADD COLUMN entity_key TEXT")
    con.execute("""CREATE TABLE IF NOT EXISTS entities (
      entity_key TEXT PRIMARY KEY, name TEXT NOT NULL, cik TEXT,
      first_seen TEXT NOT NULL)""")
    con.execute("CREATE INDEX IF NOT EXISTS entities_cik ON entities(cik)")
    return con

_SUFFIXES = {"inc", "incorporated", "corp", "corporation", "co", "company", "llc",
             "lp", "llp", "ltd", "limited", "plc", "holdings", "holding", "group",
             "the", "sa", "ag", "nv", "de", "debtor", "debtors", "et", "al"}

def clean_entity_name(name):
    """Strip EDGAR display decorations: 'Acme, Inc.  (ACME)  (CIK 0000001)' -> 'Acme, Inc.'"""
    return re.sub(r"\s*\([^)]*\)", "", name or "").strip()

def normalize_name(name):
    words = re.sub(r"[^a-z0-9 ]+", " ", clean_entity_name(name).lower()).split()
    core = [w for w in words if w not in _SUFFIXES]
    return " ".join(core or words)

def resolve_entity(con, name, cik=None):
    """Entity key shared across forms and sources: CIK when known, else normalized
    name; a CIK-less record whose normalized name matches a known CIK entity merges into it."""
    norm = normalize_name(name)
    if cik:
        cik = str(int(cik))
        key = "cik:" + cik
        row = con.execute("SELECT entity_key FROM entities WHERE entity_key=?", (key,)).fetchone()
        if not row:
            con.execute("INSERT INTO entities VALUES (?,?,?,?)", (key, clean_entity_name(name), cik, now()))
            # absorb earlier name-only records for the same entity
            con.execute("UPDATE signals SET entity_key=? WHERE entity_key=?", (key, "name:" + norm))
            con.execute("DELETE FROM entities WHERE entity_key=?", ("name:" + norm,))
        return key
    for (key, other) in con.execute("SELECT entity_key, name FROM entities WHERE cik IS NOT NULL"):
        if normalize_name(other) == norm:
            return key
    key = "name:" + norm
    con.execute("INSERT OR IGNORE INTO entities VALUES (?,?,?,?)", (key, clean_entity_name(name), None, now()))
    return key

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
    ent_name = raw.get("entity") or raw.get("caseName") or title
    entity_key = resolve_entity(con, ent_name, raw.get("cik"))
    con.execute("""INSERT INTO signals
       (source, external_id, title, url, event_date, fetched_at, raw_json)
       VALUES (?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(source, external_id) DO UPDATE SET
       title=excluded.title, url=excluded.url, event_date=excluded.event_date,
       fetched_at=excluded.fetched_at, raw_json=excluded.raw_json""",
       (source, external_id, title, url, event_date, now(), json.dumps(raw)))
    con.execute("UPDATE signals SET entity_key=? WHERE source=? AND external_id=?",
                (entity_key, source, external_id))
    con.commit()

# --- HTTP with rate limit and retry -------------------------------------
_MIN_INTERVAL = 0.11  # <= ~9 req/s, under SEC's 10 req/s ceiling
_last_call = [0.0]

def get_json(url, headers, retries=4, backoff=1.0, opener=None, timeout=60):
    opener = opener or urllib.request.urlopen
    for attempt in range(retries + 1):
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()
        try:
            req = urllib.request.Request(url, headers=headers)
            with opener(req, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == retries:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            delay = min(float(retry_after), 600.0) if retry_after and retry_after.isdigit() else backoff * 2 ** attempt
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

def confirmed_items(cik, accession, headers, fetch, cache):
    """Item codes for one filing from the submissions JSON (authoritative metadata)."""
    cik = str(int(cik)).zfill(10)
    if cik not in cache:
        data = fetch(f"https://data.sec.gov/submissions/CIK{cik}.json", headers)
        recent = data.get("filings", {}).get("recent", {})
        cache[cik] = {a: [i for i in (it or "").split(",") if i]
                      for a, it in zip(recent.get("accessionNumber", []), recent.get("items", []))}
    return cache[cik].get(accession)

def ingest_sec_fulltext(con, query, user_agent, start, end, items=None, max_pages=5,
                        fetch=get_json, confirm=True, cache=None):
    """EDGAR full-text search for 8-Ks. With `confirm`, keeps only filings whose
    submissions-JSON `items` actually contain a wanted item (drops text-only mentions)."""
    headers = _sec_headers(user_agent)
    wanted = set(items or [])
    cache = {} if cache is None else cache
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
            if confirm and wanted:
                real = confirmed_items(cik, adsh, headers, fetch, cache)
                if real is None or not wanted.intersection(real):
                    continue
                hit_items = real
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
    token = token or os.getenv("COURTLISTENER_TOKEN")
    if token:
        headers["Authorization"] = "Token " + token
    count = 0
    for page in range(max_pages):
        try:
            data = fetch(url, headers)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if page == 0:
                raise
            # throttled mid-pagination: keep what is already stored
            print(f"courtlistener: stopped after page {page} ({exc}); partial results kept")
            break
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

def rank(con, limit=25, dedupe=False, only_entities=None):
    rows = con.execute("""SELECT source, title, url, event_date, fetched_at, status, raw_json,
                          entity_key FROM signals""").fetchall()
    out = []
    for r in rows:
        raw = json.loads(r[6])
        if only_entities is not None and r[7] not in only_entities:
            continue
        out.append({"priority": signal_score(r[0], r[1], raw), "source": r[0], "title": r[1],
                    "entity": clean_entity_name(raw.get("entity") or raw.get("caseName") or r[1]),
                    "entity_key": r[7], "signal_type": _signal_type(r[0], raw),
                    "url": r[2], "event_date": r[3], "fetched_at": r[4], "status": r[5]})
    out.sort(key=lambda x: (x["priority"], x["event_date"] or ""), reverse=True)
    if dedupe:
        merged = {}
        for s in out:  # highest priority first
            m = merged.get(s["entity_key"])
            if m is None:
                merged[s["entity_key"]] = dict(s, signal_count=1, sources=s["source"],
                                               all_urls=s["url"], signal_types=s["signal_type"])
            else:
                m["signal_count"] += 1
                m["all_urls"] += " | " + s["url"]
                if s["source"] not in m["sources"].split(","):
                    m["sources"] += "," + s["source"]
                if s["signal_type"] not in m["signal_types"].split(" ; "):
                    m["signal_types"] += " ; " + s["signal_type"]
        out = list(merged.values())
    return out[:limit]

def export_csv(con, path, limit=20, dedupe=True, only_entities=None):
    rows = rank(con, limit, dedupe=dedupe, only_entities=only_entities)
    fields = ["priority", "source", "entity", "event_date", "signal_type", "url", "status"]
    if dedupe:
        fields += ["entity_key", "signal_count", "sources", "signal_types", "all_urls"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return len(rows)

def backfill_entities(con):
    """Assign entity keys to signals stored before entity resolution existed."""
    rows = con.execute("SELECT source, external_id, title, raw_json FROM signals WHERE entity_key IS NULL "
                       "ORDER BY source DESC").fetchall()  # sec first so CIKs anchor names
    for source, ext, title, raw_json in rows:
        raw = json.loads(raw_json)
        key = resolve_entity(con, raw.get("entity") or raw.get("caseName") or title, raw.get("cik"))
        con.execute("UPDATE signals SET entity_key=? WHERE source=? AND external_id=?", (key, source, ext))
    con.commit()
    return len(rows)

SEC_ITEM_QUERIES = {"1.03": '"Item 1.03"', "2.04": '"Item 2.04"',
                    "2.06": '"Item 2.06"', "3.01": '"Item 3.01"'}
COURT_QUERIES = ['"363 sale"', '"chapter 11"', "receivership", '"credit bid"', '"DIP financing"']

def daily_hunt(out_dir, days, user_agent, court_pages=2, sec_pages=2,
               sec_fetch=get_json, court_fetch=get_json, today=None):
    """Whole SEC + CourtListener hunt. Each query fails independently (partial results kept).
    Writes signals_top.csv (deduped) and signals_new.csv (only entities first seen in this run)."""
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    today = today or dt.date.today()
    start = (today - dt.timedelta(days=days)).isoformat()
    report = {"start": start, "end": today.isoformat(), "queries": {}, "errors": {}}
    with connect(out / "triage.db") as con:
        report["backfilled"] = backfill_entities(con)
        before = {r[0] for r in con.execute("SELECT entity_key FROM entities")}
        cache = {}
        for item, q in SEC_ITEM_QUERIES.items():
            try:
                report["queries"]["sec " + q] = ingest_sec_fulltext(
                    con, q, user_agent, start, today.isoformat(), [item], sec_pages,
                    fetch=sec_fetch, cache=cache)
            except Exception as exc:  # keep going; stored rows are committed
                report["errors"]["sec " + q] = repr(exc)
        for q in COURT_QUERIES:
            try:
                report["queries"]["court " + q] = ingest_court(
                    con, q, None, start, court_pages, fetch=court_fetch)
            except Exception as exc:
                report["errors"]["court " + q] = repr(exc)
        after = {r[0] for r in con.execute("SELECT entity_key FROM entities")}
        new = after - before
        con.execute("DELETE FROM entities WHERE entity_key NOT IN (SELECT DISTINCT entity_key FROM signals WHERE entity_key IS NOT NULL)")
        report["top_rows"] = export_csv(con, out / "signals_top.csv", 20)
        report["new_entities"] = export_csv(con, out / "signals_new.csv", 10**6, only_entities=new)
    return report

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
    hunt = sub.add_parser("daily-hunt")
    hunt.add_argument("--days", type=int, default=2)
    hunt.add_argument("--out", required=True)
    hunt.add_argument("--user-agent", default=os.getenv("SEC_USER_AGENT",
                      "TRIAGE-OS research badjiallan053@gmail.com"))
    hunt.add_argument("--court-pages", type=int, default=2)
    hunt.add_argument("--sec-pages", type=int, default=2)
    bt = sub.add_parser("backtest")
    bt.add_argument("--out", required=True)
    bt.add_argument("--db", default=str(DB))
    bt.add_argument("--user-agent", default=os.getenv("SEC_USER_AGENT",
                    "TRIAGE-OS research badjiallan053@gmail.com"))
    bt.add_argument("--gt-after", default=(dt.date.today() - dt.timedelta(days=730)).isoformat())
    bt.add_argument("--gt-before", default=dt.date.today().isoformat())
    bt.add_argument("--fp-start", default=(dt.date.today() - dt.timedelta(days=730)).isoformat())
    bt.add_argument("--fp-end", default=(dt.date.today() - dt.timedelta(days=545)).isoformat())
    bt.add_argument("--no-sec-replay", action="store_true")
    exp = sub.add_parser("export")
    exp.add_argument("--out", required=True)
    exp.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if args.command == "backtest":
        spec = importlib.util.spec_from_file_location("backtest", Path(__file__).with_name("backtest.py"))
        bt_mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(bt_mod)
        print(json.dumps(bt_mod.run(args.db, args.out, args.user_agent, args.gt_after, args.gt_before,
                                    args.fp_start, args.fp_end, sec_replay=not args.no_sec_replay),
                         indent=2, default=str))
        return
    if args.command == "daily-hunt":
        print(json.dumps(daily_hunt(args.out, args.days, args.user_agent,
                                    args.court_pages, args.sec_pages), indent=2))
        return
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
