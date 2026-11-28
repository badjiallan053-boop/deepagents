"""Pass-4 public ingests (read-only): ALFRED weekly vintages (point-in-time) for WALCL/RRP/STLFSI4, SHFE weekly
warehouse stocks + warrants, AFM (NL) and AMF (FR, data.gouv) net short positions, EIA-930 balance (Jul–Dec 2026),
UN Comtrade public preview (China critical-mineral exports, monthly). Blocked/key-only sources are logged as gaps."""
import os, sys, json, csv, io, re, time, datetime, urllib.request, urllib.parse, concurrent.futures as cf
X = "/workspace/triage_os_data/xasset"; V = f"{X}/v4"; os.makedirs(V, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (TRIAGE-OS research)"}
def get(u, t=90, tries=3):
    """curl (urllib hangs on some of these hosts)."""
    import subprocess
    for i in range(tries):
        r = subprocess.run(["curl", "-sSL", "--fail", "-m", str(t), "-A", "Mozilla/5.0", u], capture_output=True)
        if r.returncode == 0: return r.stdout
        err = RuntimeError(r.stderr.decode()[-200:]); time.sleep(2 + 3 * i)
    raise err
LOG = f"{V}/log.json"
def log(k, n, src, note=""):
    L = json.load(open(LOG)) if os.path.exists(LOG) else {}
    L[k] = dict(rows=n, src=src, note=note, fetched=datetime.datetime.now().isoformat(timespec="seconds")); json.dump(L, open(LOG, "w"), indent=1); print(k, n, note, flush=True)
def alfred():
    """Four-weekly vintages (every 4th Friday) 2015→today (weekly was ~10s/request, too slow for 2k calls): the value of each series *as published on that date*."""
    for sid in ["WALCL", "STLFSI4", "RRPONTSYD"]:
        d0 = datetime.date(2015, 1, 2); dates = []
        while d0 <= datetime.date.today(): dates.append(d0.isoformat()); d0 += datetime.timedelta(days=28)
        fp = f"{V}/alfred_{sid}.json"; out = json.load(open(fp)) if os.path.exists(fp) else {}
        fails = 0
        for vd in dates:  # polite + resumable: sequential, 6 s apart, skips vintages already held, stops after 5 straight failures (host throttles bursts)
            if out.get(vd): continue
            try:
                t = get(f"https://alfred.stlouisfed.org/graph/alfredgraph.csv?id={sid}&vintage_date={vd}", 120, 1).decode().splitlines()
                out[vd] = [l.split(",") for l in t[1:] if "," in l and l.split(",")[1] not in ("", ".")][-30:]; fails = 0
            except Exception: out[vd] = None; fails += 1
            json.dump(out, open(fp, "w")); time.sleep(6)
            if fails >= 5: break
        json.dump(out, open(f"{V}/alfred_{sid}.json", "w")); log(f"alfred:{sid} 4-weekly vintages", sum(1 for v in out.values() if v), "https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=..&vintage_date=..", f"{sum(1 for v in out.values() if not v)} vintages failed")
def shfe():
    d = datetime.date.today(); fr = []
    while d.weekday() != 4: d -= datetime.timedelta(days=1)
    for i in range(260): fr.append(d - datetime.timedelta(weeks=i))
    M = ["铜", "铝", "锌", "铅", "镍", "锡"]; EN = dict(zip(M, ["copper", "aluminium", "zinc", "lead", "nickel", "tin"]))
    def one(day):
        u = f"https://www.shfe.com.cn/data/tradedata/future/stockdata/weeklystock_{day:%Y%m%d}/ZH/all.html"
        try: t = get(u, 40, 1).decode("utf-8", "ignore")
        except Exception: return day, None
        x = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", t)); res = {}
        heads = [(m.start(), m.group(1)) for m in re.finditer(r"(铜|铝|锌|铅|镍|锡)\s+单位", x)]
        for j, (pos, m) in enumerate(heads):
            seg = x[pos: heads[j + 1][0] if j + 1 < len(heads) else pos + 20000]
            tots = re.findall(r"总计 ([-\d ]+?) (?=地区|完税|厂库|$|[^\d -])", seg + " 地区")
            if tots:
                nums = [int(v) for v in tots[-1].split()]
                if len(nums) >= 4 and m not in res: res[EN[m]] = dict(stock=nums[2], warrants=nums[3])
        return day, res or None
    out = {}
    with cf.ThreadPoolExecutor(4) as ex:
        for day, r in ex.map(one, fr):
            if r: out[day.isoformat()] = r
    json.dump(dict(sorted(out.items())), open(f"{V}/shfe_weekly.json", "w")); log("shfe:weekly warehouse stocks+warrants (6 metals)", len(out), "https://www.shfe.com.cn/data/tradedata/future/stockdata/weeklystock_<date>/ZH/all.html")
def shorts():
    for k, u in [("afm_current", "https://www.afm.nl/export.aspx?type=8a46a4ef-f196-4467-a7ab-1ae1cb58f0e7&format=csv"), ("afm_history", "https://www.afm.nl/export.aspx?type=3ca31b3d-23d9-4fa2-b846-29c7e3f0e5ff&format=csv")]:
        try:
            t = get(u, 120).decode("utf-8", "ignore"); open(f"{V}/{k}.csv", "w").write(t); log(f"shorts:{k} (NL)", t.count("\n") - 1, u)
        except Exception as e: log(f"shorts:{k}", 0, u, f"ERR {e}")
    try:
        j = json.loads(get("https://www.data.gouv.fr/api/1/datasets/?q=positions%20courtes%20nettes%20AMF&page_size=10"))
        for d in j["data"]:
            if "courtes" in d["title"].lower():
                for r in d["resources"]:
                    if r.get("format", "").lower() in ("csv", "xlsx", "xls") or r["url"].endswith((".csv", ".xlsx")):
                        b = get(r["url"], 120); ext = r["url"].rsplit(".", 1)[-1][:4]; open(f"{V}/amf_shorts.{ext}", "wb").write(b)
                        log("shorts:amf (FR, data.gouv)", len(b.splitlines()) - 1 if ext == "csv" else len(b), r["url"], d["title"][:80]); return
        log("shorts:amf", 0, "data.gouv.fr", "no CSV resource found")
    except Exception as e: log("shorts:amf", 0, "data.gouv.fr", f"ERR {e}")
def eia930():
    u = "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/EIA930_BALANCE_2026_Jul_Dec.csv"
    t = get(u, 300).decode("utf-8", "ignore"); r = csv.reader(io.StringIO(t)); h = next(r)
    iD = h.index("Data Date") if "Data Date" in h else 1; iBA = h.index("Balancing Authority"); iDem = [i for i, c in enumerate(h) if c.startswith("Demand (MW)")][0]
    agg = {}
    for row in r:
        try: v = float(row[iDem].replace(",", "")) if row[iDem] else None
        except Exception: v = None
        if v is None: continue
        key = (row[iD], row[iBA]); agg[key] = agg.get(key, 0) + v
    out = {}
    for (d, ba), v in agg.items(): out.setdefault(ba, {})[d] = round(v)
    json.dump(out, open(f"{V}/eia930_daily_demand_by_ba.json", "w")); log("eia930:daily demand MWh by balancing authority (Jul–Dec 2026)", sum(len(v) for v in out.values()), u)
def comtrade():
    cmds = {"811292": "Ga/Ge/In/Nb/Re unwrought & powders", "8110": "antimony", "2846": "rare-earth compounds", "280530": "rare-earth metals", "250410": "natural graphite powder/flakes", "810194": "tungsten unwrought"}
    rows = []
    pers = [f"{y}{m:02d}" for y in range(2022, 2027) for m in range(1, 13) if f"{y}{m:02d}" <= datetime.date.today().strftime("%Y%m")]
    for per in pers:  # preview endpoint returns nothing for multi-period requests -> one month per call
        for c in cmds:
            u = "https://comtradeapi.un.org/public/v1/preview/C/M/HS?" + urllib.parse.urlencode({"reporterCode": 156, "period": per, "cmdCode": c, "flowCode": "X", "partnerCode": 0})
            try:
                j = json.loads(get(u, 60, 2))
                for d in j.get("data", []): rows.append(dict(period=d["period"], cmd=c, desc=cmds[c], kg=d.get("netWgt"), usd=d.get("primaryValue")))
            except Exception as e: print("comtrade err", per, c, e)
            time.sleep(0.5)
    json.dump(rows, open(f"{V}/comtrade_china_exports.json", "w")); log("comtrade:China exports, 6 critical-mineral HS codes, monthly 2022+", len(rows), "https://comtradeapi.un.org/public/v1/preview/C/M/HS (no key, preview)")
if __name__ == "__main__":
    for s in (sys.argv[1:] or ["shorts", "shfe", "comtrade", "eia930", "alfred"]):
        try: globals()[s]()
        except Exception as e: print("STEP ERR", s, repr(e)); log(f"ERR:{s}", 0, "", repr(e))
