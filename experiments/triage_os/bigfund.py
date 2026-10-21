"""Big-fund intel layer (read-only): people flow, digital exhaust, holders, advisors, litigation.

Every row carries source + source_url + signal_date + retrieved_at. Pure transforms are testable offline;
fetching happens in the desk scripts (Crustdata/Apollo/Clay/Context/X/EDGAR/CourtListener/Apify).
"""
import re
import sqlite3

TABLES = ["people_signals", "digital_signals", "holder_signals", "advisor_signals", "litigation_signals"]
COLS = ["entity", "signal_type", "detail", "value", "source", "source_url", "signal_date", "retrieved_at"]
KEY_ROLE = re.compile(r"chief financial|\bCFO\b|treasurer|general counsel|chief legal|chief restructuring|"
                      r"restructuring officer|turnaround|chief executive officer|^CEO\b|\bCEO$|president and CEO", re.I)
NOT_KEY = re.compile(r"chief of staff|chief revenue|\bVP\b", re.I)
CRO_ROLE = re.compile(r"restructuring|turnaround|interim", re.I)
FUNDS = ["Apollo", "Oaktree", "Elliott", "Silver Point", "Monarch", "King Street", "Davidson Kempner",
         "Owl Creek", "Sculptor", "Centerbridge", "Anchorage", "Redwood"]
ADVISORS = ["Kirkland", "PJT", "Houlihan", "Evercore", "Lazard", "Moelis", "Alvarez", "Gibson Dunn",
            "Paul Weiss", "Guggenheim", "Ducera", "Perella", "FTI", "AlixPartners"]


def init(db):
    for t in TABLES:
        db.execute(f"CREATE TABLE IF NOT EXISTS {t} ({', '.join(c + ' TEXT' for c in COLS)}, "
                   f"UNIQUE(entity, signal_type, detail, source_url))")


def insert(db, table, rows):
    assert table in TABLES
    db.executemany(f"INSERT OR IGNORE INTO {table} VALUES ({','.join('?' * len(COLS))})",
                   [[r.get(c, "") for c in COLS] for r in rows])
    return len(rows)


def _months_between(a, b):
    ya, ma = int(a[:4]), int(a[5:7])
    yb, mb = int(b[:4]), int(b[5:7])
    return (yb - ya) * 12 + (mb - ma)


def people_from_crust(rec, asof, url, retrieved, window_m=12, drop_pct=-15.0):
    """rec = {n, hc, hcg:{six_months,yoy}, cx:[[name,title,start]]} -> people_signals rows."""
    out = []
    for name, title, start in rec.get("cx") or []:
        if not (title and start and KEY_ROLE.search(title)) or NOT_KEY.search(title):
            continue
        if 0 <= _months_between(start[:7], asof[:7]) <= window_m:
            kind = "cro_or_interim" if CRO_ROLE.search(title) else "key_exec_new"
            out.append(dict(entity=rec["n"], signal_type=kind, detail=f"{name} — {title}",
                            value=start, source="crustdata", source_url=url, signal_date=start, retrieved_at=retrieved))
    g = rec.get("hcg") or {}
    for k in ("six_months", "yoy"):
        v = g.get(k)
        if v is not None and v <= drop_pct:
            out.append(dict(entity=rec["n"], signal_type=f"headcount_drop_{k}", detail=f"{rec.get('hc')} employees",
                            value=f"{v:.1f}%", source="crustdata", source_url=url, signal_date=asof, retrieved_at=retrieved))
    return out


def digital_from_crust(rec, asof, url, retrieved, collapse=-0.5, min_base=0):
    """Job-postings collapse: openings_growth_percent.yoy is a fraction (-0.8 = -80%)."""
    jg = rec.get("jg") or {}
    yoy = jg.get("yoy")
    if yoy is None or yoy > collapse:
        return []
    return [dict(entity=rec["n"], signal_type="job_postings_collapse_yoy",
                 detail=f"{rec.get('jobs')} open roles now; qoq {round((jg.get('qoq') or 0) * 100)}%",
                 value=f"{round(yoy * 100)}%", source="crustdata", source_url=url, signal_date=asof, retrieved_at=retrieved)]


def holder_rows(hits, retrieved, watch=()):
    """hits from EDGAR FTS (13D/13G) -> holder_signals; flags subjects matching watch names."""
    out = []
    w = [x.lower() for x in watch]
    for h in hits:
        subject = re.sub(r"\s*\(CIK \d+\)", "", h["names"][0]).strip()
        initial = not h["form"].endswith("/A")
        hit = any(x and x in subject.lower() for x in w)
        out.append(dict(entity=subject, signal_type=("new_" if initial else "amend_") + h["form"].replace("SCHEDULE ", "").replace(" ", "").replace("/A", ""),
                        detail=f"{h['fund']}{' | WATCHLIST' if hit else ''}", value=h["form"], source="sec_edgar_fts",
                        source_url=h["url"], signal_date=h["date"], retrieved_at=retrieved))
    return out


def advisor_mentions(text):
    return [a for a in ADVISORS if re.search(r"\b" + re.escape(a), text or "", re.I)]


def classify_litigation(case_name, nos, entity):
    """Defendant-side contract suits = supplier/landlord stress; own bankruptcy dockets flagged."""
    c = (case_name or "").lower()
    e = entity.lower().split()[0]
    if " v. " not in c and e in c:
        return "own_bankruptcy_or_petition"
    if " v. " in c and e in c.split(" v. ", 1)[1]:
        n = (nos or "").lower()
        if "contract" in n or "lease" in n or "real property" in n or n.startswith("190"):
            return "supplier_or_landlord_suit"
        if "fair standards" in n or "e.r.i.s.a" in n or "labor" in n:
            return "wage_or_benefits_suit"
        return "defendant_other"
    return "plaintiff_or_unrelated"


def multi_source(db):
    """Entities with signals in >=2 big-fund tables, ranked by count of distinct tables then rows."""
    q = " UNION ALL ".join(f"SELECT entity, '{t}' t FROM {t}" for t in TABLES)
    return db.execute(f"SELECT entity, COUNT(DISTINCT t) nt, COUNT(*) n, GROUP_CONCAT(DISTINCT t) FROM ({q}) "
                      f"GROUP BY lower(entity) HAVING nt >= 2 ORDER BY nt DESC, n DESC").fetchall()
