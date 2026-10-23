"""Own WARN readers for TX, NJ, IL, FL (patterns informed by biglocalnews/warn-scraper; no code copied).
Each parser returns rows: state, company, city, notice_date (ISO), effective_date, employees, reason, source_url."""
import datetime as dt, re, sqlite3, json

URLS = {
    "NJ": "https://www.nj.gov/labor/assets/PDFs/WARN/WARN_Notice_Archive.xlsx",
    "IL": "https://apps.illinoisworknet.com/iebs/api/public/export?statuses=4&memberType=1",
    "FL": "https://reactwarn.floridajobs.org/WarnList/Records?year={year}&page={page}",
    "TX": "https://www.twc.texas.gov/data-reports/warn-notice",  # links to warn-act-listings-YYYY-twc.xlsx
}
MONTHS = {m: i for i, m in enumerate(["january","february","march","april","may","june","july","august","september","october","november","december"], 1)}

def _iso(v):
    if isinstance(v, (dt.datetime, dt.date)): return v.strftime("%Y-%m-%d")
    if not v: return None
    s = str(v).strip()
    for f in ("%m/%d/%Y", "%m/%d/%y", "%m-%d-%y", "%m-%d-%Y", "%Y-%m-%d"):
        try: return dt.datetime.strptime(s.split()[0], f).strftime("%Y-%m-%d")
        except ValueError: pass
    return None

def _int(v):
    try: return int(re.sub(r"[^\d]", "", str(v)) or 0)
    except Exception: return None

def _rows_xlsx(path):
    import openpyxl
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    it = ws.iter_rows(values_only=True); hdr = [str(h).strip() if h else "" for h in next(it)]
    return [dict(zip(hdr, r)) for r in it if any(r)]

def parse_nj(path, year=2026):
    out = []
    for r in _rows_xlsx(path):
        eff = r.get("Effective Date"); m = MONTHS.get(str(r.get("Month Posted") or "").strip().lower())
        out.append(dict(state="NJ", company=r.get("Company"), city=r.get("City"),
                        notice_date=f"{year}-{m:02d}-01" if m else None,
                        effective_date=_iso(eff) or (str(eff) if eff else None), employees=_int(r.get("Workforce Affected")),
                        reason=None, source_url=URLS["NJ"]))
    return out

def parse_il(path):
    return [dict(state="IL", company=r.get("Location Name"), city=r.get("Location City"),
                 notice_date=_iso(r.get("Initial Date Reported")), effective_date=_iso(r.get("Impact Date")),
                 employees=_int(r.get("Revised Layoff") or r.get("Expected Layoff")),
                 reason=" / ".join(x for x in [r.get("Causes"), r.get("Reason")] if x), source_url=URLS["IL"]) for r in _rows_xlsx(path)]

def parse_tx(path):
    out = []
    for r in _rows_xlsx(path):
        k = {key.upper(): v for key, v in r.items()}
        out.append(dict(state="TX", company=k.get("JOB_SITE_NAME") or k.get("COMPANY"), city=k.get("CITY_NAME") or k.get("CITY"),
                        notice_date=_iso(k.get("NOTICE_DATE")), effective_date=_iso(k.get("LAYOFF_DATE")),
                        employees=_int(k.get("TOTAL_LAYOFF_NUMBER")), reason=None, source_url=URLS["TX"]))
    return out

FL_ROW = re.compile(r"^\|\s*\*\*(?P<co>.+?)\*\*(?P<addr>.*?)\|\s*(?P<nd>\d\d-\d\d-\d\d)\s*\|\s*(?P<ld>\d\d-\d\d-\d\d)?.*?\|\s*(?P<n>\d+)\s*\|\s*(?P<ind>[^|]*)\|", re.M)
def parse_fl_markdown(md, year=2026):
    out = []
    for m in FL_ROW.finditer(md):
        city = re.findall(r"<br>\s*([A-Z .'-]+),\s*FL", m.group("addr"))
        out.append(dict(state="FL", company=m.group("co").strip(), city=city[-1].strip().title() if city else None,
                        notice_date=_iso(m.group("nd")), effective_date=_iso(m.group("ld")), employees=int(m.group("n")),
                        reason=m.group("ind").strip(), source_url=URLS["FL"].format(year=year, page=1)))
    return out

def ingest(rows, db):
    c = sqlite3.connect(db, timeout=120)
    c.execute("create table if not exists warn_state_notices(state,company,city,notice_date,effective_date,employees integer,reason,source_url,fetched_at, unique(state,company,city,notice_date,employees))")
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    n0 = c.execute("select count(*) from warn_state_notices").fetchone()[0]
    c.executemany("insert or ignore into warn_state_notices values(?,?,?,?,?,?,?,?,?)",
                  [(r["state"], r["company"], r["city"], r["notice_date"], r["effective_date"], r["employees"], r["reason"], r["source_url"], now) for r in rows if r["company"]])
    c.commit(); return c.execute("select count(*) from warn_state_notices").fetchone()[0] - n0
