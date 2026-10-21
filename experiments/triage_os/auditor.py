"""TRIAGE OS - auditor-change (8-K Item 4.01) and going-concern signals from SEC EDGAR
full-text search. Read-only; public filings; every row keeps its filing URL; unverified.

Why: an auditor resignation, a dismissal right after a going-concern paragraph, or a
first-time 'substantial doubt' disclosure in a 10-Q usually precedes a default,
restructuring or delisting by months.
"""
import json, re, sqlite3, time, urllib.parse, urllib.request

EFTS = "https://efts.sec.gov/LATEST/search-index?"

def _get(url, ua, timeout=60):
    time.sleep(0.15)
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")

def search(query, forms, start, end, ua, fetch=None, max_pages=10):
    fetch = fetch or (lambda u: _get(u, ua))
    hits = []
    for p in range(max_pages):
        d = json.loads(fetch(EFTS + urllib.parse.urlencode({"q": query, "forms": forms,
            "dateRange": "custom", "startdt": start, "enddt": end, "from": p * 100})))
        page = d["hits"]["hits"]
        hits += page
        if len(page) < 100:
            break
    return hits

def filing_url(hit):
    adsh, doc = hit["_id"].split(":", 1)
    cik = str(int(hit["_source"]["ciks"][0]))
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{doc}"

NEG = re.compile(r"\b(no|not|none|neither|nor|without|any)\b")

def _affirmed(t, term):
    """True if some occurrence of term is not negated / hypothetical in the preceding 120 chars."""
    for m in re.finditer(term, t):
        if not NEG.search(t[max(0, m.start() - 120):m.start()]):
            return True
    return False

def classify_401(text):
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).lower()
    flags = []
    if re.search(r"\bresign|declin\w* to stand", t):
        flags.append("auditor_resigned")
    if re.search(r"\bdismiss", t):
        flags.append("auditor_dismissed")
    if "going concern" in t:
        flags.append("going_concern_in_prior_reports")
    if _affirmed(t, "disagreement"):
        flags.append("disagreement_mentioned")
    if re.search(r"material weakness", t):
        flags.append("material_weakness")
    if _affirmed(t, "reportable event"):
        flags.append("reportable_event")
    return flags

SCORE = {"auditor_resigned": 40, "auditor_dismissed": 15, "going_concern_in_prior_reports": 25,
         "disagreement_mentioned": 25, "material_weakness": 10, "reportable_event": 15,
         "going_concern_10q": 30}

def score(flags):
    return min(100, sum(SCORE.get(f, 0) for f in flags))

def store(con, rows):
    con.execute("""CREATE TABLE IF NOT EXISTS auditor_flags(entity text, cik text, form text,
        file_date text, kind text, flags text, score int, source_url text,
        status text default 'unverified', primary key(source_url, kind))""")
    con.executemany("INSERT OR REPLACE INTO auditor_flags VALUES (?,?,?,?,?,?,?,?,'unverified')",
        [(r["entity"], r["cik"], r["form"], r["file_date"], r["kind"], ",".join(r["flags"]),
          score(r["flags"]), r["url"]) for r in rows])
    con.commit()

def row(hit, kind, flags):
    s = hit["_source"]
    return {"entity": re.sub(r"\s*\(CIK.*", "", s["display_names"][0]).strip(),
            "cik": s["ciks"][0], "form": s["form"], "file_date": s["file_date"],
            "kind": kind, "flags": flags, "url": filing_url(hit)}

def hunt(con, start, end, ua):
    rows = []
    for h in search('"certifying accountant"', "8-K", start, end, ua):
        if "4.01" not in (h["_source"].get("items") or []):
            continue
        try:
            flags = classify_401(_get(filing_url(h), ua))
        except Exception:
            flags = ["unread"]
        rows.append(row(h, "auditor_change", flags))
    seen = set()
    for h in search('"substantial doubt" "going concern"', "10-Q", start, end, ua):
        cik = h["_source"]["ciks"][0]
        if cik in seen:
            continue
        seen.add(cik)
        rows.append(row(h, "going_concern_10q", ["going_concern_10q"]))
    store(con, rows)
    return rows
