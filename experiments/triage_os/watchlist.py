"""Distressed watchlist: BDC borrowers with any tranche < 80 (30 Jun 2026), top-15 cap-structure issuers, world situations, SEC distress signals."""
import sqlite3
from datasets import norm
def build(db):
    c = sqlite3.connect(db, timeout=120); w = {}
    def add(name, src, why, url):
        k = norm(name)
        if len(k) >= 4 and k not in w: w[k] = (k, name, src, why, url)
    for b, bor, m, u in c.execute("select bdc,borrower,min(mark),source_url from bdc_marks where period='2026-06-30' and mark>0 and mark<80 group by borrower_key"):
        add(bor, "bdc_marks", f"{b} mark {m}", u)
    for s, i, u in c.execute("select situation,issuer,source_url from cap_structures_top15"): add(i, "cap_structure", s, u)
    for e, t, u in c.execute("select entity,type,url from world_situations"): add(e, "world", t, u)
    for s, e, u in c.execute("select signal,entity,source_url from signals2 where signal in ('covenant_waiver_8k','auditor_change_plus_nt10k','uk_late_accounts','trade_claims_top20')"): add(e, "signal", s, u)
    c.execute("drop table if exists watchlist"); c.execute("create table watchlist(nkey primary key,name,source,reason,source_url)")
    c.executemany("insert into watchlist values(?,?,?,?,?)", w.values()); c.commit(); return len(w)
if __name__ == "__main__": print(build("/workspace/triage_os_data/triage.db"))

def add_ciks_eins(db, workers=8):
    """For SEC-filer watchlist names, pull CIK -> EIN, state of incorporation from the EDGAR submissions API (primary)."""
    import json, re, urllib.request
    from concurrent.futures import ThreadPoolExecutor
    c = sqlite3.connect(db, timeout=120)
    for col in ("cik", "ein", "inc_state"):
        try: c.execute(f"alter table watchlist add column {col}")
        except sqlite3.OperationalError: pass
    rows = [(k, re.search(r"CIK=(\d+)", u or "").group(1)) for k, u in c.execute("select nkey,source_url from watchlist") if re.search(r"CIK=(\d+)", u or "")]
    def one(r):
        try:
            j = json.loads(urllib.request.urlopen(urllib.request.Request(f"https://data.sec.gov/submissions/CIK{int(r[1]):010d}.json", headers={"User-Agent": "TRIAGE-OS research arslane.souici@example.com"}), timeout=30).read())
            return (r[1], j.get("ein"), j.get("stateOfIncorporation"), r[0])
        except Exception: return None
    with ThreadPoolExecutor(workers) as ex: res = [x for x in ex.map(one, rows) if x]
    c.executemany("update watchlist set cik=?, ein=?, inc_state=? where nkey=?", res); c.commit(); return len(res)
