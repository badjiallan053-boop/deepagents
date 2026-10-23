"""BNF (kairi-ritsu mean reversion) and CIS (new-high breakout on volume) rebuilt and tested.
Universe: TSE Prime TOPIX Core30/Large70/Mid400 (BNF) + Small1 (CIS) from the JPX listed-issues file (CURRENT members: survivorship bias, upward).
Prices: Yahoo daily adjusted close + volume since 2010. Signal on close t, entry at close t+1 (no same-day fill assumed), costs per round trip.
IS < 2021-01-01 <= OOS. Kill rule as elsewhere (OOS mean>0, precision>=52%, IS agrees, n_oos>=8). Benchmark: 1306.T (TOPIX ETF) / local index ETF.
"""
import json, os, subprocess, datetime, statistics as st, math, concurrent.futures as cf, bisect
import pandas as pd
D = "/workspace/triage_os_data/edge/pxv"; os.makedirs(D, exist_ok=True); OUT = "/workspace/triage_os_data/bnf_cis.json"; OOS = "2021-01-01"
def pxv(t, rng="max"):
    p = f"{D}/{t}.json"
    if os.path.exists(p): return [r for r in json.load(open(p)) if isinstance(r[1], (int, float)) and math.isfinite(r[1]) and r[1] > 0]
    rows = []
    try:
        r = json.loads(subprocess.run(["curl", "-s", "-m", "40", "-A", "Mozilla/5.0", f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?period1=1262304000&period2=1792800000&interval=1d"], capture_output=True, text=True).stdout)["chart"]["result"][0]
        q = r["indicators"]["quote"][0]; a = r["indicators"]["adjclose"][0]["adjclose"]
        rows = [[datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date().isoformat(), c, v or 0] for ts, c, v in zip(r["timestamp"], a, q["volume"]) if c]
    except Exception: pass
    json.dump(rows, open(p, "w")); return [r for r in rows if isinstance(r[1], (int, float)) and math.isfinite(r[1]) and r[1] > 0]
def universe():
    d = pd.read_excel("/workspace/triage_os_data/edge/jpx.xlsx")
    big = d[d["規模区分"].isin(["TOPIX Core30", "TOPIX Large70", "TOPIX Mid400"])]["コード"].astype(str).tolist()
    sm = d[d["規模区分"] == "TOPIX Small 1"]["コード"].astype(str).tolist()
    return [c + ".T" for c in big], [c + ".T" for c in sm]
US = ["AAPL","MSFT","AMZN","GOOGL","META","NVDA","TSLA","JPM","BAC","WFC","C","GS","MS","XOM","CVX","PFE","MRK","JNJ","INTC","AMD","MU","BA","GE","F","GM","DIS","NFLX","T","VZ","KO","PEP","WMT","TGT","COST","HD","LOW","NKE","SBUX","MCD","CAT","DE","MMM","UPS","FDX","AAL","DAL","UAL","CCL","RCL","NCLH","OXY","SLB","HAL","DVN","APA","MRO","FCX","AA","X","CLF","PYPL","SQ","SHOP","UBER","LYFT","SNAP","PINS","ROKU","ZM","DOCU","PTON","BABA","JD","PDD","NIO","BIDU","WBA","CVS","MO","PM","BMY","ABBV","GILD","BIIB","VRTX","REGN","MRNA","BNTX","LUV","EXPE","BKNG","MAR","HLT","WYNN","LVS","MGM","KSS","M"]
EU = ["ASML.AS","SAP.DE","SIE.DE","ALV.DE","BAS.DE","BAYN.DE","BMW.DE","MBG.DE","VOW3.DE","DBK.DE","CBK.DE","LHA.DE","ADS.DE","IFX.DE","MC.PA","OR.PA","TTE.PA","BNP.PA","GLE.PA","ACA.PA","AIR.PA","SAN.PA","KER.PA","RNO.PA","STLAM.MI","ENI.MI","ISP.MI","UCG.MI","SAN.MC","BBVA.MC","ITX.MC","IBE.MC","NOVO-B.CO","NESN.SW","UBSG.SW","ROG.SW","NOKIA.HE","ERIC-B.ST","VOLV-B.ST","HM-B.ST","PHIA.AS","INGA.AS","ADYEN.AS","PRX.AS","AD.AS","HEIA.AS","ABI.BR","KBC.BR","CS.PA","ORA.PA"]
HK = ["0700.HK","9988.HK","3690.HK","1810.HK","0005.HK","0939.HK","1398.HK","2318.HK","0941.HK","0883.HK","0388.HK","1299.HK","0016.HK","0001.HK","0002.HK","0003.HK","0011.HK","0027.HK","1928.HK","2020.HK","2331.HK","9618.HK","9999.HK","1211.HK","2382.HK","0981.HK","1093.HK","2269.HK","0688.HK","1109.HK","0960.HK","2007.HK","3333.HK","1918.HK","0175.HK","2015.HK","9868.HK","0268.HK","6098.HK","0291.HK"]
BENCH = dict(JP="1306.T", US="SPY", EU="EZU", HK="2800.HK", DIST="IWM")
def agg(xs):
    if not xs: return dict(n=0)
    return dict(n=len(xs), precision=round(100 * sum(x > 0 for x in xs) / len(xs)), mean=round(100 * st.mean(xs), 2), median=round(100 * st.median(xs), 2),
                t=round(st.mean(xs) / (st.stdev(xs) / math.sqrt(len(xs))), 2) if len(xs) > 2 and st.stdev(xs) > 0 else None)
def verdict(a, b):
    if b["n"] < 8: return f"UNTESTED (n_oos={b['n']})"
    if b["mean"] <= 0 or b["precision"] < 52: return "KILLED"
    if a.get("n", 0) >= 8 and (a["mean"] <= 0 or a["precision"] < 50): return "FRAGILE (IS disagrees)"
    return "KEPT"
def bnf(tickers, bench, thr, h, cost_bp, use_px=None):
    B = {r[0]: r[1] for r in pxv(bench)}; ev = []
    for t in tickers:
        P = use_px(t) if use_px else pxv(t)
        if len(P) < 60: continue
        c = [r[1] for r in P]; last = -99
        for i in range(25, len(P) - h - 1):
            ma = sum(c[i - 24:i + 1]) / 25
            if c[i] / ma - 1 <= -thr and i - last > 10:
                e, x = i + 1, i + 1 + h
                b0, b1 = B.get(P[e][0]), B.get(P[x][0])
                if not b0 or not b1: continue
                ev.append((P[e][0], (c[x] / c[e] - 1) - (b1 / b0 - 1) - cost_bp / 1e4, t)); last = i
    IS = agg([x for d, x, t in ev if d < OOS]); OS = agg([x for d, x, t in ev if d >= OOS])
    return dict(thr=thr, h=h, cost_bp=cost_bp, IS=IS, OOS=OS, status=verdict(IS, OS), names=len(tickers))
def cis(tickers, bench, cost_bp, stop=0.07, maxh=60):
    B = {r[0]: r[1] for r in pxv(bench)}; ev = []
    for t in tickers:
        P = pxv(t)
        if len(P) < 300: continue
        c = [r[1] for r in P]; v = [r[2] for r in P]; i = 250
        while i < len(P) - 2:
            av = sum(v[i - 50:i]) / 50
            if c[i] >= max(c[i - 250:i]) and av > 0 and v[i] > 2 * av:
                e = i + 1; hi = c[e]; x = e
                for j in range(e + 1, min(len(P), e + maxh + 1)):
                    x = j; hi = max(hi, c[j])
                    if c[j] <= hi * (1 - stop): break
                b0, b1 = B.get(P[e][0]), B.get(P[x][0])
                if b0 and b1: ev.append((P[e][0], (c[x] / c[e] - 1) - (b1 / b0 - 1) - cost_bp / 1e4, t))
                i = x + 1
            else: i += 1
    IS = agg([x for d, x, t in ev if d < OOS]); OS = agg([x for d, x, t in ev if d >= OOS])
    return dict(stop=stop, maxh=maxh, cost_bp=cost_bp, IS=IS, OOS=OS, status=verdict(IS, OS), names=len(tickers))
def live(tickers, region):
    out = []
    for t in tickers:
        P = pxv(t)
        if len(P) < 260 or P[-1][0] < "2026-10-15": continue
        c = [r[1] for r in P]; v = [r[2] for r in P]; ma = sum(c[-25:]) / 25; k = c[-1] / ma - 1
        if k <= -0.20: out.append(dict(t=t, region=region, kind="BNF", kairi=round(100 * k, 1), px=c[-1], d=P[-1][0]))
        av = sum(v[-51:-1]) / 50
        if c[-1] >= max(c[-251:-1]) and av > 0 and v[-1] > 2 * av: out.append(dict(t=t, region=region, kind="CIS", vol_x=round(v[-1] / av, 1), px=c[-1], d=P[-1][0]))
    return out
def run():
    big, sm = universe()
    import edge_lab as L
    dist = sorted({f[:-5] for f in os.listdir(L.PXD)} - {"IWM", "SPY"})[:1500]
    allt = big + sm + US + EU + HK + list(BENCH.values())
    with cf.ThreadPoolExecutor(8) as ex: list(ex.map(pxv, allt))
    R = {}
    for thr in (0.20, 0.25, 0.30):
        for h in (1, 3, 5): R[f"BNF JP large/mid kairi<=-{int(thr*100)}% hold {h}d"] = bnf(big, BENCH["JP"], thr, h, 25)
    for nm, tk, bm, cst in (("US large", US, "SPY", 10), ("EU large", EU, "EZU", 20), ("HK large", HK, "2800.HK", 30)):
        for h in (3, 5): R[f"BNF {nm} kairi<=-20% hold {h}d"] = bnf(tk, bm, 0.20, h, cst)
    for h in (3, 5): R[f"BNF distressed/event universe (US small) kairi<=-20% hold {h}d"] = bnf(dist, "IWM", 0.20, h, 75, use_px=lambda t: [[a, b, 0] for a, b in L.px(t)])
    R["CIS JP large/mid breakout on 2x volume, 7% trailing stop"] = cis(big, BENCH["JP"], 25)
    R["CIS JP small1 breakout on 2x volume, 7% trailing stop"] = cis(sm, BENCH["JP"], 40)
    R["CIS US large breakout on 2x volume, 7% trailing stop"] = cis(US, "SPY", 10)
    LV = live(big + sm, "JP") + live(US, "US") + live(EU, "EU") + live(HK, "HK")
    json.dump(dict(asof="2026-10-23", method=__doc__, results=R, live=LV, universe=dict(jp_big=len(big), jp_small1=len(sm), us=len(US), eu=len(EU), hk=len(HK), dist=len(dist))), open(OUT, "w"), indent=1)
    for k, v in R.items(): print(k, "|", v["status"], "| IS", v["IS"], "| OOS", v["OOS"])
    print("live", len(LV))
if __name__ == "__main__": run()
