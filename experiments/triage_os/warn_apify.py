"""TRIAGE OS - normalize WARN rows from Apify actors into warn_notices (company-level only).
Two actor shapes are supported (snake_case aggregator; camelCase scraper). Rows keep source_url."""
import datetime as dt

def normalize(item):
    loc = item.get("location") or {}
    return {
        "state": item.get("state") or item.get("source_state") or loc.get("state") or "",
        "county": item.get("county") or loc.get("county") or "",
        "notice_date": (item.get("notice_date") or item.get("noticeDate") or "")[:10],
        "effective_date": (item.get("effective_date") or item.get("layoffDate") or "")[:10],
        "company": (item.get("employer_name") or item.get("companyName") or "").strip(),
        "kind": item.get("layoff_type") or item.get("warnNoticeType") or "",
        "employees": item.get("affected_workers") or item.get("employeesAffected") or 0,
        "address": item.get("employer_address") or loc.get("address") or "",
        "industry": item.get("industry") or "",
        "source_url": item.get("source_url") or item.get("sourceUrl") or "",
    }

def store(con, items, retrieved_at=None):
    retrieved_at = retrieved_at or dt.datetime.now(dt.timezone.utc).isoformat()
    con.execute("""CREATE TABLE IF NOT EXISTS warn_notices(state text, county text, notice_date text, effective_date text,
                   company text, kind text, employees int, address text, industry text, source_url text, retrieved_at text)""")
    rows = [normalize(i) for i in items]
    rows = [r for r in rows if r["company"]]
    existing = {(c, d, a) for c, d, a in con.execute("SELECT company, notice_date, address FROM warn_notices")}
    new = [r for r in rows if (r["company"], r["notice_date"], r["address"]) not in existing]
    con.executemany("INSERT INTO warn_notices VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    [(r["state"], r["county"], r["notice_date"], r["effective_date"], r["company"], r["kind"],
                      r["employees"], r["address"], r["industry"], r["source_url"], retrieved_at) for r in new])
    return len(new)
