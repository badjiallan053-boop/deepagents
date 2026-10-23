"""Pass-3 public ingests (read-only): BLM hub dated claims (Created), EIA weekly crude + NG storage, NASA FIRMS VIIRS 7-day
public CSV (no key), Treasury auctions (fiscaldata), FRED sovereign yields, extra Yahoo prices."""
import os, json, csv, io, time, urllib.request, urllib.parse, datetime, sys
X = "/workspace/triage_os_data/xasset"; V = f"{X}/v3"; os.makedirs(V, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (TRIAGE-OS research)"}
def get(u, t=90):
    for i in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read()
        except Exception as e: err = e; time.sleep(2 + 3 * i)
    raise err
LOG = f"{V}/log.json"; L = json.load(open(LOG)) if os.path.exists(LOG) else {}
def log(k, n, src): L[k] = dict(rows=n, src=src, fetched=datetime.datetime.now().isoformat(timespec="seconds")); json.dump(L, open(LOG, "w"), indent=1); print(k, n, flush=True)
HUB = {"open": "https://nlsdbpubgis.blm.gov/arcgishub/rest/services/HUB/BLM_Natl_MLRS_Mining_Claims_Not_Closed/FeatureServer/0",
       "closed": "https://nlsdbpubgis.blm.gov/arcgishub/rest/services/HUB/BLM_Natl_MLRS_Mining_Claims_Closed/FeatureServer/0"}
SITES = {"Mountain Pass": (-115.53, 35.48, "MP"), "Thacker Pass": (-118.05, 41.71, "LAC"), "Stibnite": (-115.33, 44.91, "PPTA"),
         "Bear Lodge": (-104.45, 44.48, "RER.V"), "Rhyolite Ridge": (-117.98, 37.97, "INR.AX")}
def blm():
    out = {}
    for name, (x, y, tk) in SITES.items():
        recs = []
        for lay, u in HUB.items():
            off = 0
            while True:
                q = urllib.parse.urlencode({"where": "1=1", "geometry": f"{x-.15},{y-.15},{x+.15},{y+.15}", "geometryType": "esriGeometryEnvelope", "inSR": 4326,
                     "spatialRel": "esriSpatialRelIntersects", "outFields": "CSE_NR,LEG_CSE_NR,CSE_DISP,Created,Modified", "returnGeometry": "false", "resultOffset": off, "resultRecordCount": 2000, "f": "json"})
                j = json.loads(get(f"{u}/query?{q}")); fs = j.get("features", [])
                recs += [dict(f["attributes"], layer=lay) for f in fs]; off += len(fs)
                if not fs or not j.get("exceededTransferLimit"): break
        out[name] = dict(ticker=tk, records=recs); log(f"blm_hub:{name}", len(recs), HUB["open"])
    json.dump(out, open(f"{V}/blm_hub_sites.json", "w"))
    # national monthly new-claim counts (records with no legacy serial), via outStatistics on Created would need SQL expr; page counts by month instead
    nat = {}
    d = datetime.date(2021, 1, 1)
    while d < datetime.date.today():
        e = (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        n = 0
        for u in HUB.values():
            q = urllib.parse.urlencode({"where": f"Created >= TIMESTAMP '{d} 00:00:00' AND Created < TIMESTAMP '{e} 00:00:00' AND (LEG_CSE_NR IS NULL OR LEG_CSE_NR = '')", "returnCountOnly": "true", "f": "json"})
            try: n += json.loads(get(f"{u}/query?{q}")).get("count", 0)
            except Exception as ex: print("nat err", d, ex)
        nat[str(d)[:7]] = n; d = e
    json.dump(nat, open(f"{V}/blm_national_new_by_month.json", "w")); log("blm_hub:national_monthly", len(nat), HUB["open"])
def eia():
    import subprocess
    open(f"{V}/WCESTUS1w.xls", "wb").write(get("https://www.eia.gov/dnav/pet/hist_xls/WCESTUS1w.xls"))
    try:
        import xlrd
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--break-system-packages", "xlrd"], check=False); import xlrd
    b = xlrd.open_workbook(f"{V}/WCESTUS1w.xls"); sh = b.sheet_by_name("Data 1"); rows = []
    for r in range(3, sh.nrows):
        try: rows.append((xlrd.xldate_as_datetime(sh.cell_value(r, 0), b.datemode).date().isoformat(), float(sh.cell_value(r, 1))))
        except Exception: pass
    open(f"{V}/eia_crude_stocks.csv", "w").write("date,value\n" + "\n".join(f"{a},{v}" for a, v in rows)); log("eia:WCESTUS1 weekly crude ex-SPR", len(rows), "https://www.eia.gov/dnav/pet/hist_xls/WCESTUS1w.xls")
    open(f"{V}/NW2_EPG0_SWO_R48_BCFw.xls", "wb").write(get("https://www.eia.gov/dnav/ng/hist_xls/NW2_EPG0_SWO_R48_BCFw.xls"))
    b = xlrd.open_workbook(f"{V}/NW2_EPG0_SWO_R48_BCFw.xls"); sh = b.sheet_by_name("Data 1"); rows = []
    for r in range(3, sh.nrows):
        try: rows.append((xlrd.xldate_as_datetime(sh.cell_value(r, 0), b.datemode).date().isoformat(), float(sh.cell_value(r, 1))))
        except Exception: pass
    open(f"{V}/eia_ng_storage.csv", "w").write("date,value\n" + "\n".join(f"{a},{v}" for a, v in rows)); log("eia:NG storage L48 weekly", len(rows), "https://www.eia.gov/dnav/ng/hist_xls/NW2_EPG0_SWO_R48_BCFw.xls")
def firms():
    t = get("https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Global_7d.csv", 180).decode()
    rows = list(csv.DictReader(io.StringIO(t))); hits = {}
    SITES2 = dict(SITES, **{"Bayan Obo (CN)": (109.97, 41.78, ""), "Mount Weld (AU)": (122.55, -28.86, ""), "Kolwezi (DRC)": (25.47, -10.72, ""), "Escondida (CL)": (-69.07, -24.27, ""), "Norilsk (RU)": (88.2, 69.35, "")})
    for n, (x, y, _) in SITES2.items():
        hits[n] = [r for r in rows if abs(float(r["longitude"]) - x) < .15 and abs(float(r["latitude"]) - y) < .15]
    json.dump(dict(total=len(rows), hits=hits), open(f"{V}/firms_viirs_7d_sites.json", "w")); log("firms:VIIRS NOAA-20 7d global (no key)", len(rows), "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Global_7d.csv")
def auctions():
    rows = []; page = 1
    while True:
        u = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query?" + urllib.parse.urlencode({"filter": "security_type:in:(Note,Bond),auction_date:gte:2006-01-01", "fields": "auction_date,security_term,security_type,bid_to_cover_ratio,high_yield,indirect_bidder_accepted,offering_amt,reopening", "page[size]": 1000, "page[number]": page})
        j = json.loads(get(u)); rows += j["data"]
        if page >= j["meta"]["total-pages"]: break
        page += 1
    json.dump(rows, open(f"{V}/ust_auctions.json", "w")); log("fiscaldata:auctions notes+bonds 2006+", len(rows), "https://api.fiscaldata.treasury.gov/.../auctions_query")
def fred():
    for s in ["IRLTLT01ITM156N", "IRLTLT01DEM156N", "IRLTLT01GBM156N", "IRLTLT01FRM156N", "WALCL", "RRPONTSYD", "STLFSI4", "DEXJPUS"]:
        try:
            t = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}", 60).decode().splitlines()
            open(f"{X}/fred_{s}.csv", "w").write("date,value\n" + "\n".join(l for l in t[1:] if not l.endswith(","))); log(f"fred:{s}", len(t) - 1, f"https://fred.stlouisfed.org/series/{s}")
        except Exception as e: print("fred err", s, e)
def yahoo():
    for t in ["GDXJ", "LAC", "INR.AX", "RER.V", "USO", "UNG", "KRE", "XLE", "IBIT", "EWI", "EWJ", "FXI", "GDX", "UUP"]:
        try:
            r = json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(t)}?range=25y&interval=1d"))["chart"]["result"][0]
            c = r["indicators"]["adjclose"][0]["adjclose"] if "adjclose" in r["indicators"] else r["indicators"]["quote"][0]["close"]
            rows = [(datetime.date.fromtimestamp(a).isoformat(), b) for a, b in zip(r["timestamp"], c) if b]
            open(f"{X}/px_{t}.csv", "w").write("date,close\n" + "\n".join(f"{a},{b}" for a, b in rows)); log(f"yahoo:{t}", len(rows), "query1.finance.yahoo.com/v8/finance/chart")
        except Exception as e: print("yahoo err", t, e)
        time.sleep(0.3)
if __name__ == "__main__":
    for s in (sys.argv[1:] or ["yahoo", "fred", "eia", "auctions", "firms", "blm"]):
        try: globals()[s]()
        except Exception as e: print("STEP ERR", s, repr(e))
