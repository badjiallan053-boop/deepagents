"""Systemic bulk ingest: FDIC call reports (all banks), FRED/H.8/SLOOS series, EDGAR filings. Read-only public data."""
import csv, io, json, os, sqlite3, time, urllib.request
OUT = "/workspace/triage_os_data/systemic"; DB = os.environ.get("TRIAGE_DB", "/workspace/triage_os_data/triage.db")
UA = {"User-Agent": "TRIAGE-OS research arslane.souici@example.com"}
def get(u, t=60):
    for i in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read()
        except Exception as e: err = e; time.sleep(2)
    raise err
F = "CERT,NAME,CITY,STALP,ASSET,DEP,LNLSNET,LNRECONS,LNREMULT,LNRENROT,LNRENROW,LNRENRES,RBC,RBCT1J,EQ,NCLNLS,NALNLS,P9LNLS,BRO,SCAF,SCAA,SCHA,SCHF,REPDTE"
def fdic(rep):
    rows, off = [], 0
    while True:
        j = json.loads(get(f"https://api.fdic.gov/banks/financials?filters=REPDTE:{rep}&fields={F}&limit=10000&offset={off}&format=json"))
        rows += [d["data"] for d in j["data"]]; off += 10000
        if off >= j["meta"]["total"]: break
    return rows
FRED = {"TOTBKCR": "H.8 bank credit, all commercial banks", "CREACBW027SBOG": "H.8 CRE loans, all commercial banks",
        "CRELCBW027SBOG": "H.8 CRE loans, large domestic banks", "CRESCBW027SBOG": "H.8 CRE loans, small domestic banks",
        "CREFCBW027SBOG": "H.8 CRE loans, foreign-related institutions",
        "DRTSCILM": "SLOOS: net % tightening C&I, large/mid firms", "SUBLPDRCSC": "SLOOS: net % tightening CRE construction",
        "SUBLPDRCSN": "SLOOS: net % tightening CRE nonfarm nonresidential", "SUBLPDRCSM": "SLOOS: net % tightening CRE multifamily",
        "DRCRELEXFACBS": "Delinquency rate, CRE excl. farmland, all banks", "CORCREXFACBS": "Charge-off rate, CRE excl. farmland, all banks",
        "BAMLH0A0HYM2": "ICE BofA US HY OAS", "BAMLC0A4CBBB": "ICE BofA BBB OAS"}
def fred(sid):
    t = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}").decode()
    return [r for r in csv.reader(io.StringIO(t))][1:]
if __name__ == "__main__":
    con = sqlite3.connect(DB); log = {}
    for rep in ("20260630", "20250630"):
        rows = fdic(rep)
        con.execute(f"drop table if exists fdic_call_{rep}")
        con.execute(f"create table fdic_call_{rep} ({','.join(F.split(','))})")
        con.executemany(f"insert into fdic_call_{rep} values ({','.join('?'*len(F.split(',')))})", [[r.get(k) for k in F.split(",")] for r in rows])
        log[f"fdic_call_{rep}"] = len(rows); print(rep, len(rows), flush=True)
    con.execute("create table if not exists fred_series (sid, label, date, value)"); con.execute("delete from fred_series")
    for sid, lab in FRED.items():
        try:
            r = fred(sid); con.executemany("insert into fred_series values (?,?,?,?)", [(sid, lab, d, v) for d, v in r]); log[f"fred:{sid}"] = len(r)
        except Exception as e: log[f"fred:{sid}"] = f"ERR {e}"
        print(sid, log[f"fred:{sid}"], flush=True)
    con.commit(); json.dump(log, open(f"{OUT}/ingest_log.json", "w"), indent=1)
