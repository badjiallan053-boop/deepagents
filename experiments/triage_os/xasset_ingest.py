"""Cross-asset ingest (free public data only, read-only). Writes /workspace/triage_os_data/xasset/*.csv|json and xasset_counts.json.
Patterns reimplemented (not run) from public repos: CFTC COT zip parsing (NDelventhal/cot_reports, MIT), DefiLlama stablecoin
endpoints (DefiLlama/defillama-server, MIT), Binance public futures REST paging (binance/binance-connector-python, MIT)."""
import os, io, json, time, zipfile, csv, urllib.request, urllib.parse, datetime
O = "/workspace/triage_os_data/xasset"; os.makedirs(O, exist_ok=True)
UA = {"User-Agent": "TRIAGE-OS research arslane.souici@example.com"}
def get(u, t=90, tries=3):
    for i in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read()
        except Exception as e:
            err = e; time.sleep(3 * (i + 1))
    raise err
counts = {}
def log(k, n, src): counts[k] = dict(rows=n, source=src, fetched=datetime.datetime.now().isoformat(timespec="seconds")); print(k, n, flush=True)

FRED = {"BAMLH0A0HYM2": "US HY OAS", "BAMLC0A0CM": "US IG OAS", "DGS10": "UST 10y", "DGS2": "UST 2y", "T10Y2Y": "2s10s", "VIXCLS": "VIX", "DTWEXBGS": "Broad USD",
        "WCESTUS1": "US crude stocks ex-SPR (weekly)", "DCOILWTICO": "WTI spot", "DFII10": "10y real yield", "IRLTLT01JPM156N": "Japan 10y (monthly)", "BAMLEMHBHYCRPIOAS": "EM HY corp OAS"}
def fred():
    for sid, lab in FRED.items():
        try:
            t = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}").decode()
            rows = [l.split(",") for l in t.strip().splitlines()[1:]]
            rows = [(d, float(v)) for d, v in rows if v not in (".", "")]
            with open(f"{O}/fred_{sid}.csv", "w") as f: f.write("date,value\n" + "\n".join(f"{d},{v}" for d, v in rows))
            log(f"fred:{sid}", len(rows), f"https://fred.stlouisfed.org/series/{sid}")
        except Exception as e: log(f"fred:{sid}", f"ERR {e}", sid)

YAHOO = ["GC=F", "SI=F", "HG=F", "CL=F", "NG=F", "ZC=F", "ZS=F", "ZW=F", "PL=F", "BTC-USD", "ETH-USD", "SOL-USD", "^GSPC", "SPY", "REMX", "MP", "LIT", "URA", "TLT", "HYG", "JNK", "EEM", "^N225", "^HSI", "^STOXX50E", "GLD", "COPX", "SIL", "LYC.AX", "600111.SS", "^TNX", "DX-Y.NYB", "1306.T", "2800.HK", "IEF"]
def yahoo(tickers=YAHOO, tag="px"):
    for t in tickers:
        try:
            j = json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(t)}?period1=946684800&period2={int(time.time())}&interval=1d"))
            r = j["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]; adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or q["close"]
            rows = [(datetime.datetime.utcfromtimestamp(a).date().isoformat(), c) for a, c in zip(ts, adj) if c is not None]
            with open(f"{O}/{tag}_{t.replace('^','I_').replace('=','_')}.csv", "w") as f: f.write("date,close\n" + "\n".join(f"{d},{c}" for d, c in rows))
            log(f"{tag}:{t}", len(rows), "query1.finance.yahoo.com chart (public)")
        except Exception as e: log(f"{tag}:{t}", f"ERR {e}", t)
        time.sleep(0.3)

COT_MKTS = {"GOLD - COMMODITY EXCHANGE INC.": "GC=F", "SILVER - COMMODITY EXCHANGE INC.": "SI=F", "COPPER- #1 - COMMODITY EXCHANGE INC.": "HG=F", "COPPER #1 - COMMODITY EXCHANGE INC.": "HG=F",
            "WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE": "CL=F", "CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE": "CL=F", "NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE": "NG=F",
            "NATURAL GAS - NEW YORK MERCANTILE EXCHANGE": "NG=F", "CORN - CHICAGO BOARD OF TRADE": "ZC=F", "SOYBEANS - CHICAGO BOARD OF TRADE": "ZS=F", "WHEAT-SRW - CHICAGO BOARD OF TRADE": "ZW=F",
            "WHEAT - CHICAGO BOARD OF TRADE": "ZW=F", "PLATINUM - NEW YORK MERCANTILE EXCHANGE": "PL=F"}
def cot():
    urls = ["https://www.cftc.gov/files/dea/history/fut_disagg_txt_hist_2006_2016.zip"] + [f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{y}.zip" for y in range(2017, 2027)]
    out = []; raw = 0
    for u in urls:
        try:
            z = zipfile.ZipFile(io.BytesIO(get(u, 180)))
            for n in z.namelist():
                rd = csv.DictReader(io.TextIOWrapper(z.open(n), encoding="latin-1"))
                for r in rd:
                    raw += 1; m = r["Market_and_Exchange_Names"].strip()
                    if m in COT_MKTS:
                        d = r.get("Report_Date_as_YYYY-MM-DD") or r.get("Report_Date_as_MM_DD_YYYY")
                        out.append((d[:10], COT_MKTS[m], int(r["M_Money_Positions_Long_All"]), int(r["M_Money_Positions_Short_All"]), int(r["Open_Interest_All"])))
        except Exception as e: print("cot ERR", u, e)
    out = sorted(set(out))
    with open(f"{O}/cot_mm.csv", "w") as f: f.write("date,asset,mm_long,mm_short,oi\n" + "\n".join(",".join(map(str, r)) for r in out))
    log("cftc:disagg_raw_rows", raw, "https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm"); log("cftc:mm_rows_kept", len(out), "derived")

def stables():
    j = json.loads(get("https://stablecoins.llama.fi/stablecoincharts/all"))
    rows = [(datetime.datetime.utcfromtimestamp(int(r["date"])).date().isoformat(), r["totalCirculatingUSD"].get("peggedUSD", 0)) for r in j]
    with open(f"{O}/stablecoin_total.csv", "w") as f: f.write("date,usd\n" + "\n".join(f"{d},{v}" for d, v in rows))
    log("defillama:stablecoin_total", len(rows), "https://stablecoins.llama.fi/stablecoincharts/all")
    try:
        p = json.loads(get("https://yields.llama.fi/pools")); log("defillama:yield_pools_snapshot", len(p.get("data", [])), "https://yields.llama.fi/pools")
    except Exception as e: print(e)

def funding():
    """Bybit public v5 REST, paged backwards by endTime (pattern reimplemented from public connector docs)."""
    for sym in ["BTCUSDT", "ETHUSDT"]:
        rows = []; end = int(time.time() * 1000)
        while True:
            j = json.loads(get(f"https://api.bybit.com/v5/market/funding/history?category=linear&symbol={sym}&limit=200&endTime={end}"))["result"]["list"]
            if not j: break
            rows += [(int(x["fundingRateTimestamp"]), float(x["fundingRate"])) for x in j]; end = int(j[-1]["fundingRateTimestamp"]) - 1
            if len(j) < 200: break
            time.sleep(0.15)
        rows.sort()
        with open(f"{O}/funding_{sym}.csv", "w") as f: f.write("ts,rate\n" + "\n".join(f"{a},{b}" for a, b in rows))
        log(f"bybit:funding:{sym}", len(rows), "https://api.bybit.com/v5/market/funding/history")
        oi = []; end = int(time.time() * 1000)
        for _ in range(15):
            j = json.loads(get(f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={sym}&intervalTime=1d&limit=200&endTime={end}"))["result"]["list"]
            if not j: break
            oi += [(int(x["timestamp"]), float(x["openInterest"])) for x in j]; end = int(j[-1]["timestamp"]) - 1
            time.sleep(0.15)
        oi.sort()
        with open(f"{O}/oi_{sym}.csv", "w") as f: f.write("ts,oi\n" + "\n".join(f"{a},{b}" for a, b in oi))
        log(f"bybit:oi_daily:{sym}", len(oi), "https://api.bybit.com/v5/market/open-interest")

def auctions():
    rows = []; page = 1
    while True:
        u = f"https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query?filter=security_term:eq:10-Year,security_type:eq:Note&fields=auction_date,cusip,bid_to_cover_ratio,high_yield,offering_amt,primary_dealer_accepted,indirect_bidder_accepted,total_accepted&page[number]={page}&page[size]=500&sort=auction_date"
        j = json.loads(get(u.replace("[", "%5B").replace("]", "%5D"))); rows += j["data"]
        if page >= j["meta"]["total-pages"]: break
        page += 1
    json.dump(rows, open(f"{O}/ust10_auctions.json", "w")); log("treasury:10y_auctions", len(rows), "https://api.fiscaldata.treasury.gov auctions_query")

def sp500_changes():
    t = get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies").decode()
    open(f"{O}/sp500_wiki.html", "w").write(t); log("wikipedia:sp500_page_bytes", len(t), "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")

def usgs():
    b = get("https://pubs.usgs.gov/periodicals/mcs2026/mcs2026.pdf", 300); open(f"{O}/mcs2026.pdf", "wb").write(b); log("usgs:mcs2026_bytes", len(b), "https://pubs.usgs.gov/periodicals/mcs2026/mcs2026.pdf")

if __name__ == "__main__":
    import sys
    for step in (sys.argv[1:] or ["fred", "yahoo", "cot", "stables", "funding", "auctions", "sp500_changes", "usgs"]):
        try: globals()[step]()
        except Exception as e: print("STEP ERR", step, e)
    p = f"{O}/xasset_counts.json"; old = json.load(open(p)) if os.path.exists(p) else {}
    old.update(counts); json.dump(old, open(p, "w"), indent=1)
