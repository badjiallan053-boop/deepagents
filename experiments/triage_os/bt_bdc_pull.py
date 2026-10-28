"""Historical BDC schedule-of-investments marks (Inline XBRL era, 2022Q3+) into bdc_marks_hist."""
import json, re, sqlite3, sys, time, urllib.request, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("bdc", Path(__file__).with_name("bdc.py")); bdc = importlib.util.module_from_spec(spec); spec.loader.exec_module(bdc)
UA = {"User-Agent": "TRIAGE-OS research arslane.souici@example.com", "Accept-Encoding": "identity"}
def get(u):
    for i in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read().decode("utf-8", "replace")
        except Exception as e: time.sleep(3); err = e
    raise err
db = sys.argv[1]; con = sqlite3.connect(db, timeout=120)
con.execute("create table if not exists bdc_marks_hist (bdc, borrower, borrower_key, identifier, period, par, cost, fv, mark, source_url, primary key(bdc, identifier, period))")
ciks = dict(con.execute("select bdc, substr(source_url, 41, instr(substr(source_url,41),'/')-1) from bdc_marks group by bdc").fetchall())
for t in sys.argv[2].split(","):
    cik = ciks[t]; sub = json.loads(get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"))["filings"]["recent"]
    for form, date, acc, doc, rep in zip(sub["form"], sub["filingDate"], sub["accessionNumber"], sub["primaryDocument"], sub["reportDate"]):
        if form not in ("10-Q", "10-K") or not ("2022-09-01" <= rep <= "2025-12-31"): continue
        if con.execute("select 1 from bdc_marks_hist where bdc=? and period=? limit 1", (t, rep)).fetchone(): continue
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{doc}"
        try: rows = bdc.parse(get(url), period=rep)
        except Exception as e: print(t, rep, "ERR", e, flush=True); continue
        con.executemany("insert or replace into bdc_marks_hist values (?,?,?,?,?,?,?,?,?,?)",
            [(t, r["borrower"], r["borrower_key"], r["identifier"], r["period"], r.get("par"), r.get("cost"), r["fv"], r["mark"], url) for r in rows])
        con.commit(); print(t, rep, len(rows), flush=True); time.sleep(0.3)
