"""Read-only 363 sale calendar ingestion from public claims-agent pages and notices.

Parses dates out of plain text (Stretto/Kroll/Epiq/Omni notices, press releases).
No auth, no form posts. Stores rows with source URL and retrieval date.
"""
import csv
import re
import sqlite3
from datetime import datetime, timezone

AGENTS = {"stretto": "cases.stretto.com", "kroll": "restructuring.ra.kroll.com",
          "epiq": "dm.epiq11.com", "omni": "omniagentsolutions.com"}
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE = rf"((?:{MONTHS})\s+\d{{1,2}},\s+\d{{4}})"
FIELDS = {
    "bid_deadline": rf"(?<!preliminary )bid deadline(?: is| was|:)?[^.]{{0,40}}?{DATE}",
    "auction": rf"auction(?: date)?(?: \(if (?:needed|any|necessary)\))?(?: is| on|:)?[^.]{{0,30}}?{DATE}",
    "sale_hearing": rf"sale hearing(?: is| on|:)?[^.]{{0,30}}?{DATE}",
    "objection_deadline": rf"(?:sale )?objection deadline(?: is|:)?[^.]{{0,30}}?{DATE}",
}
COLS = ["case_name", "court", "case_no", "agent", "bid_deadline", "auction", "sale_hearing",
        "objection_deadline", "stalking_horse", "price_usd_m", "status", "source_url", "retrieved_at"]


def agent_for(url):
    for name, host in AGENTS.items():
        if host in (url or ""):
            return name
    return ""


def iso(d):
    return datetime.strptime(re.sub(r"\s+", " ", d), "%B %d, %Y").date().isoformat()


def extract_dates(text):
    t = re.sub(r"\s+", " ", text or "")
    out = {}
    for k, pat in FIELDS.items():
        m = re.search(pat, t, re.I)
        if m:
            out[k] = iso(m.group(1))
    return out


def connect(path):
    con = sqlite3.connect(path)
    con.execute("create table if not exists calendar_363 (" + ",".join(c + " text" for c in COLS) +
                ", primary key(case_no, source_url))")
    return con


def upsert(con, row):
    row = {c: row.get(c, "") or "" for c in COLS}
    if not row["source_url"]:
        raise ValueError("source_url required (provenance)")
    row["agent"] = row["agent"] or agent_for(row["source_url"])
    row["retrieved_at"] = row["retrieved_at"] or datetime.now(timezone.utc).date().isoformat()
    con.execute(f"insert or replace into calendar_363 values ({','.join('?' * len(COLS))})", [row[c] for c in COLS])
    return row


def export(con, path, today=None):
    rows = [dict(zip(COLS, r)) for r in con.execute("select * from calendar_363")]
    key = lambda r: (r["bid_deadline"] or r["sale_hearing"] or "9999")
    rows.sort(key=key)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(rows)
    return rows
