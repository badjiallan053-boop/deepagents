"""TRIAGE OS: minimal provenance-first special-situations ingestion and triage.

Standard library only. Requires explicit SEC identity and CourtListener token.
Not an automated investment or legal decision engine.
"""
import argparse
import datetime as dt
import json
import os
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path

DB = Path(os.environ.get("TRIAGE_DB", "triage.db"))
TERMS = {
    "bankruptcy": 18, "chapter 11": 18, "363 sale": 22,
    "sale procedures": 22, "foreclosure": 18, "receivership": 18,
    "going concern": 12, "covenant": 8, "default": 12,
    "liquidation": 15, "restructuring": 8, "credit bid": 18,
}

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
    value = sum(points for term, points in TERMS.items() if term in title.lower())
    return min(100, value)

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

def get_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)

def ingest_sec(con, cik, user_agent):
    if "@" not in user_agent:
        raise ValueError("SEC requires a descriptive user-agent with contact information")
    cik = str(int(cik)).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    data = get_json(url, {"User-Agent": user_agent, "Accept": "application/json"})
    recent = data.get("filings", {}).get("recent", {})
    columns = ("accessionNumber", "primaryDocument", "form", "filingDate")
    count = 0
    for accession, document, form, date in zip(*(recent.get(c, []) for c in columns)):
        if form not in {"8-K", "10-K", "10-Q", "6-K", "20-F"}:
            continue
        acc = accession.replace("-", "")
        filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{urllib.parse.quote(document)}"
        title = f"{data.get('name', cik)} — {form} filed {date}"
        store(con, "sec", accession, title, filing_url, date,
              {"cik": cik, "form": form, "filing_date": date, "document": document})
        count += 1
    return count

def ingest_court(con, query, token):
    if not token:
        raise ValueError("COURTLISTENER_TOKEN is required")
    params = urllib.parse.urlencode({"q": query, "type": "r"})
    url = "https://www.courtlistener.com/api/rest/v3/search/?" + params
    data = get_json(url, {"Authorization": "Token " + token,
                          "User-Agent": "TRIAGE-OS-research/0.1"})
    count = 0
    for item in data.get("results", []):
        external_id = str(item.get("id") or item.get("docket_id") or "")
        title = item.get("caseName") or item.get("case_name") or item.get("description") or ""
        path = item.get("absolute_url") or item.get("absoluteUrl") or ""
        item_url = urllib.parse.urljoin("https://www.courtlistener.com", path)
        if external_id and title and path and item_url.startswith("https://"):
            store(con, "courtlistener", external_id, title, item_url,
                  item.get("dateFiled") or item.get("date_filed"), item)
            count += 1
    return count

def rank(con, limit=25):
    rows = con.execute("""SELECT source, title, url, event_date, fetched_at, status
                          FROM signals ORDER BY fetched_at DESC""").fetchall()
    return sorted(({"priority": score(r[1]), "source": r[0], "title": r[1],
                    "url": r[2], "event_date": r[3], "fetched_at": r[4],
                    "status": r[5]} for r in rows),
                  key=lambda x: x["priority"], reverse=True)[:limit]

def main():
    parser = argparse.ArgumentParser(description="TRIAGE OS provenance-first MVP")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sec = sub.add_parser("ingest-sec")
    sec.add_argument("--cik", required=True)
    sec.add_argument("--user-agent", required=True)
    court = sub.add_parser("ingest-court")
    court.add_argument("--query", required=True)
    rank_cmd = sub.add_parser("rank")
    rank_cmd.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    with connect() as con:
        if args.command == "init":
            print(f"Initialized {DB}")
        elif args.command == "ingest-sec":
            print(f"Stored {ingest_sec(con, args.cik, args.user_agent)} SEC filings")
        elif args.command == "ingest-court":
            print(f"Stored {ingest_court(con, args.query, os.getenv('COURTLISTENER_TOKEN'))} court records")
        else:
            print(json.dumps(rank(con, args.limit), indent=2))

if __name__ == "__main__":
    main()
