"""TRIAGE paper portfolio: combine the KEPT edges into one beta-hedged book and validate it honestly.
Sleeves (rules fixed before the OOS look; thresholds were picked on the full sample in earlier passes, which the deflated Sharpe penalises):
  BNF JP (TOPIX large/mid, kairi<=-25%, 5d), BNF HK (kairi<=-20%, 5d), NEW: BNF TW / KR / AU (kairi<=-20%, 5d),
  PEAD short (bottom-decile SUE, 60d), late-filer (NT 10-K) short overlay (120d).
Each position earns stock return minus its local index ETF return (= beta hedge with an index future proxy), daily.
Sleeve return = sum of active positions / max(n_active, 5) (per-name cap 20% of a sleeve). Each sleeve is scaled to 10% annual vol with a
trailing 60-day vol (lagged one day = vol targeting, which also gives inverse-vol weights); the book is the average of the sleeves, rescaled to 10% vol.
Costs: spread + square-root impact per round trip, borrow on shorts (PEAD 3%/yr general collateral proxy, late filers 20%/yr hard-to-borrow).
Survivorship: all universes are CURRENT members (Yahoo / today's SEC list); LSE has no delisted stocks (checked: every catalog stock ticks in 2026), so it cannot fix this.
IS < 2021-01-01 <= OOS. Deflated Sharpe (Bailey & Lopez de Prado 2014) with N = number of variants tried across the lab. Block bootstrap CI.
"""
import json, os, math, random, statistics as st, collections, datetime, subprocess, concurrent.futures as cf
import numpy as np
import bnf_cis as B, edge_lab as L
OUT = "/workspace/triage_os_data/portfolio.json"; OOS = "2021-01-01"
KR = "005930 000660 035420 005380 051910 006400 035720 068270 207940 000270 012330 105560 055550 003550 017670 015760 034730 096770 066570 028260 032830 086790 010950 009150 018260 011170 033780 036570 251270 352820 003670 047050 010130 000810 024110 316140 030200 090430 009540 011200".split()
AU = "BHP CBA CSL NAB WBC ANZ WES MQG WDS TLS RIO FMG GMG TCL WOW ALL STO REA COL QBE SUN ORG S32 MIN PLS IGO LYC NST EVN XRO WTC CPU AMC RMD SHL TWE QAN ASX BXB COH FLT SEK CAR JBH HVN".split()
def tw_list(k=120):
    j = json.loads(subprocess.run(["curl", "-s", "-m", "40", "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"], capture_output=True, text=True).stdout)
    j = [r for r in j if r["Code"].isdigit() and len(r["Code"]) == 4 and not r["Code"].startswith("00")]
    j.sort(key=lambda r: -float(r["TradeValue"] or 0)); return [r["Code"] + ".TW" for r in j[:k]]
def daily(P, Bm, e, x, sgn):
    """per-day excess returns of a position entered at close e, exited at close x"""
    out = []
    for d in range(e + 1, x + 1):
        b0, b1 = Bm.get(P[d - 1][0]), Bm.get(P[d][0])
        if not b0 or not b1 or P[d - 1][1] <= 0: continue
        out.append((P[d][0], sgn * ((P[d][1] / P[d - 1][1] - 1) - (b1 / b0 - 1))))
    return out
def impact_bp(adv_usd, pos_usd=250_000): return 10 * math.sqrt(min(1.0, pos_usd / max(adv_usd, 1)))*10  # sqrt law, 100bp at 100% of ADV
def bnf_trades(tickers, bench, thr, h, spread_bp, fx=1.0):
    Bm = {r[0]: r[1] for r in B.pxv(bench)}; T = []
    for t in tickers:
        P = B.pxv(t)
        if len(P) < 60: continue
        c = [r[1] for r in P]; last = -99
        for i in range(25, len(P) - h - 1):
            if c[i] / (sum(c[i - 24:i + 1]) / 25) - 1 <= -thr and i - last > 10:
                adv = st.mean(r[1] * r[2] for r in P[max(0, i - 20):i + 1]) / fx
                if adv < 2e6: last = i; continue                      # liquidity screen: >= $2m ADV
                T.append(dict(t=t, d=P[i + 1][0], days=daily(P, Bm, i + 1, i + 1 + h, 1), cost=(spread_bp + impact_bp(adv)) / 1e4, borrow=0, adv=adv)); last = i
    return T
def us_trades(events, h, sgn, spread_bp, borrow_yr, bench="IWM"):
    Bm = dict(L.px(bench)); T = []; last = {}
    import bisect
    for t, d in sorted(events, key=lambda e: e[1]):
        p = f"{L.PXD}/{t}.json"
        if not os.path.exists(p): continue
        P = json.load(open(p))
        if len(P) < 30: continue
        ks = [r[0] for r in P]; i = bisect.bisect_right(ks, d)
        if i >= len(P) - h or (t in last and i - last[t] < h) or P[i][1] <= 0: continue
        last[t] = i; T.append(dict(t=t, d=P[i][0], days=daily(P, Bm, i, i + h, sgn), cost=spread_bp / 1e4, borrow=borrow_yr, adv=None))
    return T
def sleeve(T, net=True):
    acc = collections.defaultdict(float); n = collections.Counter()
    for tr in T:
        for k, (d, r) in enumerate(tr["days"]):
            x = r
            if net:
                if k == 0: x -= tr["cost"]
                x -= tr["borrow"] / 252
            x = max(x, -1.0); acc[d] += x; n[d] += 1
    return {d: acc[d] / max(n[d], 5) for d in acc}
def voltarget(s, dates, tgt=0.10):
    r = np.array([s.get(d, 0.0) for d in dates]); out = np.zeros_like(r)
    for i in range(61, len(r)):
        v = r[i - 61:i - 1].std() * math.sqrt(252)
        out[i] = r[i] * min(tgt / v, 5) if v > 1e-6 else 0
    return out
def stats(r):
    r = np.asarray(r); r = r[r != 0] if (r != 0).sum() > 50 else r
    if len(r) < 30 or r.std() == 0: return dict(n_days=len(r))
    sr = r.mean() / r.std() * math.sqrt(252); eq = np.cumprod(1 + r); dd = (eq / np.maximum.accumulate(eq) - 1).min()
    return dict(n_days=len(r), ann_ret=round(100 * r.mean() * 252, 2), ann_vol=round(100 * r.std() * math.sqrt(252), 2), sharpe=round(sr, 2), max_dd=round(100 * dd, 1),
                skew=round(float(((r - r.mean()) ** 3).mean() / r.std() ** 3), 2), kurt=round(float(((r - r.mean()) ** 4).mean() / r.std() ** 4), 2))
def dsr(r, n_trials, sr_var_ann=0.5 ** 2):
    from statistics import NormalDist as N
    r = np.asarray(r); T = len(r); sr = r.mean() / r.std(); g = 0.5772156649
    v = sr_var_ann / 252; e = math.e
    sr0 = math.sqrt(v) * ((1 - g) * N().inv_cdf(1 - 1 / n_trials) + g * N().inv_cdf(1 - 1 / (n_trials * e)))
    sk = ((r - r.mean()) ** 3).mean() / r.std() ** 3; ku = ((r - r.mean()) ** 4).mean() / r.std() ** 4
    z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(max(1e-9, 1 - sk * sr + (ku - 1) / 4 * sr ** 2))
    return dict(dsr_prob=round(N().cdf(z), 3), sr0_ann=round(sr0 * math.sqrt(252), 2), n_trials=n_trials)
def boot(r, reps=2000, blk=20):
    r = np.asarray(r); n = len(r); rng = np.random.default_rng(7); S = []
    for _ in range(reps):
        idx = np.concatenate([np.arange(s, s + blk) % n for s in rng.integers(0, n, n // blk + 1)])[:n]; x = r[idx]
        S.append(x.mean() / x.std() * math.sqrt(252) if x.std() > 0 else 0)
    return [round(float(np.percentile(S, 2.5)), 2), round(float(np.percentile(S, 97.5)), 2)]
def run():
    big, _ = B.universe(); tw = tw_list(); kr = [c + ".KS" for c in KR]; au = [c + ".AX" for c in AU]
    with cf.ThreadPoolExecutor(8) as ex: list(ex.map(B.pxv, tw + kr + au + ["0050.TW", "069500.KS", "STW.AX"]))
    import pead
    top, bot, _ = pead.events()
    nt = [(t, d) for t, d, co in L.first_per_cik({"NT 10-K"})]
    SL = {"BNF JP (TOPIX L/M, -25%, 5d)": bnf_trades(big, "1306.T", 0.25, 5, 20, fx=150),
          "BNF HK (-20%, 5d)": bnf_trades(B.HK, "2800.HK", 0.20, 5, 25, fx=7.8),
          "BNF TW (top-120 by value, -20%, 5d) NEW": bnf_trades(tw, "0050.TW", 0.20, 5, 45, fx=32),   # incl. 0.3% sell tax
          "BNF KR (40 large, -20%, 5d) NEW": bnf_trades(kr, "069500.KS", 0.20, 5, 35, fx=1350),      # incl. ~0.18% sell tax
          "BNF AU (44 large, -20%, 5d) NEW": bnf_trades(au, "STW.AX", 0.20, 5, 15, fx=1.5),
          "PEAD short (bottom decile, 60d)": us_trades([(t, d) for t, d, _ in bot], 60, -1, 30, 0.03),
          "Late-filer short overlay (120d)": us_trades(nt, 120, -1, 150, 0.20)}
    dates = sorted({d for T in SL.values() for tr in T for d, _ in tr["days"]}); dates = [d for d in dates if d >= "2012-01-01"]
    res = dict(asof="2026-10-23", method=__doc__, sleeves={}, book={})
    G, N_ = {}, {}
    for k, T in SL.items():
        g = voltarget(sleeve(T, False), dates); n = voltarget(sleeve(T, True), dates); G[k], N_[k] = g, n
        oi = [i for i, d in enumerate(dates) if d >= OOS]; ii = [i for i, d in enumerate(dates) if d < OOS]
        res["sleeves"][k] = dict(trades=len(T), IS_net=stats(n[ii]), OOS_gross=stats(g[oi]), OOS_net=stats(n[oi]),
                                 median_adv_musd=round(st.median([t["adv"] for t in T if t["adv"]]) / 1e6, 1) if any(t["adv"] for t in T) else None)
    names = list(SL); M = np.array([N_[k] for k in names]); oi = np.array([d >= OOS for d in dates])
    C = np.corrcoef(M[:, oi]); res["oos_corr"] = {names[i][:22]: [round(float(x), 2) for x in C[i]] for i in range(len(names))}
    def combo(sel, src):
        X = np.array([src[k] for k in sel]).mean(0); v = X[: (~oi).sum()].std() * math.sqrt(252)
        return X * (0.10 / v if v > 0 else 1)
    core = names[:2] + names[5:7]; full = names
    for lab, sel in (("Core (KEPT edges: BNF JP, BNF HK, PEAD short, late-filer short)", core), ("Core + new markets (TW, KR, AU)", full)):
        g, n = combo(sel, G), combo(sel, N_)
        wf = {str(y): stats(n[[i for i, d in enumerate(dates) if d[:4] == str(y)]]).get("sharpe") for y in range(2013, 2027)}
        res["book"][lab] = dict(sleeves=sel, IS_net=stats(n[~oi]), OOS_gross=stats(g[oi]), OOS_net=stats(n[oi]), walk_forward_net_sharpe_by_year=wf,
                                bootstrap95_oos_net_sharpe=boot(n[oi]), deflated=dsr(n[oi][n[oi] != 0], n_trials=60))
        res["book"][lab]["series"] = [[d, round(float(x), 6)] for d, x in zip(dates[::5], np.cumprod(1 + n)[::5])]
    # capacity: BNF sleeves trade at <=5% of ADV, ~5 names, 5-day holds
    adv = [t["adv"] for k in names[:5] for t in SL[k] if t["adv"]]
    res["capacity"] = dict(median_bnf_adv_musd=round(st.median(adv) / 1e6, 1), est_book_usd_m=round(0.05 * st.median(adv) * 5 / 1e6, 1),
                           note="5% of median ADV per name x ~5 concurrent names per BNF sleeve; PEAD/late-filer shorts are micro-cap heavy, borrow-limited, likely < $5m.")
    json.dump(res, open(OUT, "w"), indent=1)
    for k, v in res["sleeves"].items(): print(k, v["trades"], "IS", v["IS_net"].get("sharpe"), "OOS g/n", v["OOS_gross"].get("sharpe"), v["OOS_net"].get("sharpe"))
    for k, v in res["book"].items(): print(k, "IS", v["IS_net"].get("sharpe"), "OOS g", v["OOS_gross"], "OOS n", v["OOS_net"], v["bootstrap95_oos_net_sharpe"], v["deflated"])
    print(res["capacity"]); print(res["oos_corr"])
if __name__ == "__main__": run()
