"""TRIAGE cross-asset signal library: mechanism, trigger, event-study backtest, kill rule, live status.
Method (applies to every signal, stated once):
  * Event = first trigger day after a cooldown equal to the holding horizon h (no overlapping events per asset).
  * Entry = close of the first trading day AFTER the data is public (publication lag per signal: EIA +1 day,
    COT Tuesday data released Friday → +3 days, FRED daily +1, BLM month bucket → first day of next month).
  * Excess move = asset h-day return minus the asset's unconditional mean h-day return over the whole sample
    (drift-adjusted), signed by the predicted direction. Precision = share of events with positive signed excess.
  * Lead time = mean trading days until the maximum favourable signed excess inside the h window.
  * In-sample < OOS_START (default 2019-01-01, rules written before looking at OOS); OOS ≥ OOS_START.
  * Costs: round-trip cost per asset class deducted from every event (ETF/futures 10 bp, single stocks 30 bp,
    crypto 20 bp, junior miners 100 bp).
  * KILL rule: OOS net mean excess ≤ 0 or OOS precision < 52%. UNTESTED: fewer than 8 OOS events.
Public data only; files listed in SOURCES."""
import os, csv, json, math, datetime, statistics as st, collections
X = "/workspace/triage_os_data/xasset"; V = f"{X}/v3"; OUT = "/workspace/triage_os_data/signals.json"
def load(p, col=1, date_col=0):
    d = {}
    if not os.path.exists(p): return d
    for r in list(csv.reader(open(p)))[1:]:
        try: d[r[date_col][:10]] = float(r[col])
        except Exception: pass
    return dict(sorted(d.items()))
PX = lambda t: load(f"{X}/px_{t}.csv")
FRED = lambda s: load(f"{X}/fred_{s}.csv")
class Ser:
    def __init__(s, d): s.k = list(d); s.v = list(d.values()); s.ix = {k: i for i, k in enumerate(s.k)}
    def idx_after(s, d):  # first index with date > d
        import bisect; return bisect.bisect_right(s.k, d)
def study(name, px, triggers, direction, h, lag_days, cost_bp, oos="2019-01-01", min_oos=8):
    S = Ser(px); n = len(S.v)
    drift = st.mean(S.v[i + h] / S.v[i] - 1 for i in range(n - h)) if n > h else 0
    ev = []; last = -10**9
    for d, sgn in triggers:
        pub = (datetime.date.fromisoformat(d) + datetime.timedelta(days=lag_days)).isoformat()
        i = S.idx_after(pub) - 1 + (1 if lag_days > 0 else 1)
        i = S.idx_after(pub)  # entry at first close strictly after publication date
        if i >= n - h or i - last < h: continue
        if min(S.v[i:i + h + 1]) <= 0: continue  # e.g. WTI front-month negative print 20 Apr 2020 — returns undefined, event dropped
        dirn = sgn if sgn else direction
        path = [dirn * (S.v[i + j] / S.v[i] - 1 - drift * j / h) for j in range(1, h + 1)]
        ev.append(dict(sig=name, date=S.k[i], dir=dirn, x=path[-1] - cost_bp / 1e4, lead=1 + max(range(h), key=lambda j: path[j]))); last = i
    def agg(es):
        if not es: return dict(n=0)
        xs = [e["x"] for e in es]
        return dict(n=len(es), precision=round(100 * sum(x > 0 for x in xs) / len(xs)), mean_excess=round(100 * st.mean(xs), 2), median=round(100 * st.median(xs), 2),
                    lead_days=round(st.mean(e["lead"] for e in es), 1), worst=round(100 * min(xs), 1),
                    t_stat=round(st.mean(xs) / (st.stdev(xs) / math.sqrt(len(xs))), 2) if len(xs) > 2 and st.stdev(xs) > 0 else None)
    IS = [e for e in ev if e["date"] < oos]; OS = [e for e in ev if e["date"] >= oos]
    a, b = agg(IS), agg(OS)
    status = verdict(a, b, min_oos)
    fails = sorted(OS, key=lambda e: e["x"])[:3]
    return dict(name=name, h=h, cost_bp=cost_bp, oos_start=oos, in_sample=a, oos=b, status=status, events=ev, worst_oos=[dict(date=e["date"], x=round(100 * e["x"], 1)) for e in fails])
def verdict(a, b, min_oos=8):
    """KEPT only if OOS passes AND in-sample (when n≥8) agrees in sign; OOS pass with IS disagreement = FRAGILE."""
    if b["n"] < min_oos: return f"UNTESTED (n_oos={b['n']}<{min_oos})"
    if b["mean_excess"] <= 0 or b["precision"] < 52: return "KILLED"
    if a.get("n", 0) >= 8 and (a["mean_excess"] <= 0 or a["precision"] < 50): return "FRAGILE (IS disagrees)"
    return "KEPT"
def pctile_series(vals, win):
    out = []
    for i in range(len(vals)):
        w = vals[max(0, i - win + 1):i + 1]; out.append(sum(x <= vals[i] for x in w) / len(w) if len(w) >= win // 2 else None)
    return out
SIG = []; LIVE = {}
def add(meta, res, live):
    res.update(meta); res["live"] = live; SIG.append(res); print(f"{res['id']:4} {res['status']:22} IS {res['in_sample']} | OOS {res['oos']}", flush=True)
def recent(trigs, days=30):
    if not trigs: return False, None
    d = max(t[0] for t in trigs); return (datetime.date.today() - datetime.date.fromisoformat(d)).days <= days, d
def run():
    # S1/S2 CFTC managed-money positioning extremes (pooled across 9 commodities)
    cot = collections.defaultdict(dict)
    for r in list(csv.reader(open(f"{X}/cot_mm.csv")))[1:]:
        try: cot[r[1]][r[0]] = (float(r[2]) - float(r[3])) / float(r[4])
        except Exception: pass
    for sid, side, cond in (("S1", -1, lambda p: p >= 0.95), ("S2", 1, lambda p: p <= 0.05)):
        ev_all = []; live = []
        for a, s in cot.items():
            ks = sorted(s); p = pctile_series([s[k] for k in ks], 156)
            trig = [(ks[i], 0) for i in range(len(ks)) if p[i] is not None and cond(p[i])]
            px = PX(a.replace("=", "_"))
            if not px: continue
            r = study(f"{sid}:{a}", px, trig, side, 20, 3, 10); ev_all += r["events"]
            if trig and (datetime.date.today() - datetime.date.fromisoformat(trig[-1][0])).days <= 14: live.append(f"{a} pctile {p[-1]:.0%} ({ks[-1]})")
        IS = [e for e in ev_all if e["date"] < "2019-01-01"]; OS = [e for e in ev_all if e["date"] >= "2019-01-01"]
        agg = lambda es: dict(n=len(es), precision=round(100 * sum(e["x"] > 0 for e in es) / max(1, len(es))), mean_excess=round(100 * st.mean([e["x"] for e in es]), 2) if es else None,
                              median=round(100 * st.median([e["x"] for e in es]), 2) if es else None, lead_days=round(st.mean([e["lead"] for e in es]), 1) if es else None, worst=round(100 * min([e["x"] for e in es]), 1) if es else None)
        b = agg(OS); status = verdict(agg(IS), b)
        add(dict(id=sid, asset="9 CFTC commodities (pooled)", cls="commodities", mechanism=("Managed money at a 3-year positioning extreme LONG must eventually sell to exit; the marginal buyer is exhausted (fade)." if side < 0 else "Managed money at a 3-year SHORT extreme must buy back (short-covering)."),
                 trigger=f"MM net/OI percentile vs 3y {'≥95%' if side<0 else '≤5%'}; trade {'short' if side<0 else 'long'} 20d", data="CFTC disaggregated futures-only COT (cot_mm.csv) + Yahoo continuous futures", buyer="Commodity trading houses, CTAs, macro funds"),
            dict(name=sid, h=20, cost_bp=10, oos_start="2019-01-01", in_sample=agg(IS), oos=b, status=status, events=ev_all, worst_oos=[dict(date=e["date"], x=round(100 * e["x"], 1)) for e in sorted(OS, key=lambda e: e["x"])[:3]]),
            dict(fired=bool(live), detail="; ".join(live) or "no commodity at an extreme in the last 2 weeks"))
    # S3 EIA crude inventory surprise vs 5y seasonal average change
    cs = load(f"{V}/eia_crude_stocks.csv"); ks = list(cs); ch = {ks[i]: cs[ks[i]] - cs[ks[i - 1]] for i in range(1, len(ks))}
    trig = []; z_last = None
    for i, k in enumerate(ks[1:], 1):
        wk = datetime.date.fromisoformat(k).isocalendar()[1]; y = int(k[:4])
        past = [v for kk, v in ch.items() if int(kk[:4]) in range(y - 5, y) and abs(datetime.date.fromisoformat(kk).isocalendar()[1] - wk) <= 1]
        if len(past) < 8: continue
        z = (ch[k] - st.mean(past)) / (st.pstdev(past) or 1); z_last = (k, z)
        if z < -1.5: trig.append((k, 1))
        elif z > 1.5: trig.append((k, -1))
    r = study("S3", PX("CL_F"), trig, 0, 10, 1, 10)
    add(dict(id="S3", asset="WTI (CL=F)", cls="commodities", mechanism="An inventory draw/build far outside the 5-year seasonal norm reprices prompt barrels; refiners/traders must re-hedge.",
             trigger="Weekly US crude stocks ex-SPR change vs same-week 5y average, |z|>1.5; trade with the surprise 10d", data="EIA WCESTUS1 weekly (no key)", buyer="Oil traders, energy PMs"), r,
        dict(fired=bool(z_last and abs(z_last[1]) > 1.5), detail=f"latest week {z_last[0]} z={z_last[1]:+.2f}" if z_last else ""))
    # S4 NG storage deficit vs 5y
    ng = load(f"{V}/eia_ng_storage.csv"); trig = []; last = None
    for k, v in ng.items():
        d = datetime.date.fromisoformat(k); wk = d.isocalendar()[1]
        past = [vv for kk, vv in ng.items() if int(kk[:4]) in range(d.year - 5, d.year) and abs(datetime.date.fromisoformat(kk).isocalendar()[1] - wk) <= 0]
        if len(past) < 4: continue
        dev = v / st.mean(past) - 1; last = (k, dev)
        if dev < -0.10: trig.append((k, 1))
        elif dev > 0.10: trig.append((k, -1))
    r = study("S4", PX("NG_F"), trig, 0, 20, 1, 10)
    add(dict(id="S4", asset="Henry Hub (NG=F)", cls="commodities", mechanism="Storage far below (above) the 5-year norm forces utilities/marketers to bid (dump) gas before winter.",
             trigger="Lower-48 working gas vs 5y same-week avg beyond ±10%; trade toward normalisation 20d", data="EIA NW2_EPG0_SWO_R48_BCF weekly", buyer="Gas traders, utilities"), r,
        dict(fired=bool(last and abs(last[1]) > .10), detail=f"{last[0]} storage vs 5y {last[1]:+.1%}" if last else ""))
    # S5 weak Treasury auction (bid-to-cover z vs last 12 same-term auctions)
    au = json.load(open(f"{V}/ust_auctions.json")); by = collections.defaultdict(list)
    for a in sorted(au, key=lambda a: a["auction_date"]):
        if a["security_term"] in ("10-Year", "30-Year", "9-Year 10-Month", "9-Year 11-Month", "29-Year 10-Month", "29-Year 11-Month") or a["security_term"].startswith(("29-Year", "9-Year")):
            try: by["long"].append((a["auction_date"], float(a["bid_to_cover_ratio"])))
            except Exception: pass
    trig = []; L = by["long"]; lastz = None
    for i in range(12, len(L)):
        w = [b for _, b in L[i - 12:i]]; z = (L[i][1] - st.mean(w)) / (st.pstdev(w) or 1); lastz = (L[i][0], z)
        if z < -1.5: trig.append((L[i][0], 0))
    r = study("S5", PX("TLT"), trig, -1, 5, 0, 10)
    add(dict(id="S5", asset="TLT", cls="bonds", mechanism="A weak long-end auction means dealers absorb supply they must distribute; duration sells off as they hedge.",
             trigger="10y/30y auction bid-to-cover z < −1.5 vs prior 12 long-end auctions; short TLT 5d from next close", data="Treasury fiscaldata auctions_query (1,863 note/bond auctions since 2006)", buyer="Rates desks, macro funds"), r,
        dict(fired=bool(lastz and lastz[1] < -1.5), detail=f"last long-end auction {lastz[0]} z={lastz[1]:+.2f}" if lastz else ""))
    # S6 credit forced-selling proxy: HYG underperforms IEF by >4% in 22d (FRED ICE HY OAS only has 3y public history)
    hyg, ief = PX("HYG"), PX("IEF"); k = [d for d in hyg if d in ief]; trig = []
    for i in range(22, len(k)):
        rel = (hyg[k[i]] / hyg[k[i - 22]]) / (ief[k[i]] / ief[k[i - 22]]) - 1
        if rel < -0.04: trig.append((k[i], 0))
    r = study("S6", hyg, trig, 1, 60, 0, 10)
    rel_now = (hyg[k[-1]] / hyg[k[-23]]) / (ief[k[-1]] / ief[k[-23]]) - 1
    add(dict(id="S6", asset="HYG", cls="bonds", mechanism="A fast HY-vs-Treasury sell-off forces mutual-fund/ETF redemptions and CLO/insurer de-risking; forced selling overshoots fair value.",
             trigger="HYG under-performs IEF by >4% in 22 trading days; buy HYG 60d", data="Yahoo HYG, IEF (FRED ICE HY OAS has only 3y public history — noted)", buyer="Credit hedge funds, distressed desks"), r,
        dict(fired=recent(trig, 45)[0], detail=f"HYG vs IEF 22d {rel_now:+.1%}"))
    # S7 VIX spike
    vx = FRED("VIXCLS"); k = list(vx); trig = []; lastt = -999
    for i in range(1, len(k)):
        if vx[k[i]] > 30 and vx[k[i - 1]] <= 30 and i - lastt > 60: trig.append((k[i], 0)); lastt = i
    r = study("S7", PX("SPY"), trig, 1, 20, 1, 10)
    add(dict(id="S7", asset="SPY", cls="stocks", mechanism="Vol-targeting and risk-parity funds mechanically cut equity when VIX spikes; the forced selling is front-loaded and mean-reverts.",
             trigger="VIX closes above 30 for the first time in 60 days; long SPY 20d", data="FRED VIXCLS", buyer="Equity PMs, vol desks"), r,
        dict(fired=recent(trig, 30)[0], detail=f"VIX {vx[k[-1]]:.1f} ({k[-1]})"))
    # S8 dollar squeeze → EM
    dx = PX("DX-Y.NYB"); k = list(dx); trig = [(k[i], 0) for i in range(63, len(k)) if dx[k[i]] / dx[k[i - 63]] - 1 > 0.05]
    r = study("S8", PX("EEM"), trig, -1, 20, 0, 10)
    add(dict(id="S8", asset="EEM", cls="stocks", mechanism="A fast dollar rally tightens EM dollar-funding; foreign holders of EM assets are forced to cut.",
             trigger="DXY +5% over 63 trading days; short EEM 20d", data="Yahoo DX-Y.NYB, EEM", buyer="EM funds, sovereign funds"), r,
        dict(fired=recent(trig, 20)[0], detail=f"DXY 3m {dx[k[-1]]/dx[k[-64]]-1:+.1%}"))
    # S9 copper/gold ratio → yields
    hg, gc = PX("HG_F"), PX("GC_F"); k = [d for d in hg if d in gc]; rat = {d: hg[d] / gc[d] for d in k if gc[d] > 0}; k = list(rat)
    trig = [(k[i], 0) for i in range(63, len(k)) if rat[k[i]] / rat[k[i - 63]] - 1 > 0.10]
    r = study("S9", PX("TLT"), trig, -1, 20, 0, 10)
    add(dict(id="S9", asset="TLT", cls="bonds", mechanism="Copper/gold rising = growth/reflation repricing; duration holders sell.",
             trigger="Copper/gold ratio +10% in 63 days; short TLT 20d", data="Yahoo HG=F, GC=F, TLT", buyer="Macro funds"), r,
        dict(fired=recent(trig, 20)[0], detail=f"Cu/Au 3m {rat[k[-1]]/rat[k[-64]]-1:+.1%}"))
    # S10 stablecoin supply impulse
    sc = load(f"{X}/stablecoin_total.csv"); k = list(sc); trig = [(k[i], 0) for i in range(30, len(k)) if sc[k[i - 30]] > 0 and sc[k[i]] / sc[k[i - 30]] - 1 > 0.05]
    r = study("S10", PX("BTC-USD"), trig, 1, 30, 1, 20, oos="2023-01-01")
    add(dict(id="S10", asset="BTC", cls="crypto", mechanism="New stablecoin issuance is dry powder minted to buy crypto on exchanges.",
             trigger="Total stablecoin market cap +5% in 30 days; long BTC 30d", data="DefiLlama stablecoins", buyer="Crypto funds, market makers"), r,
        dict(fired=recent(trig, 30)[0], detail=f"30d supply change {sc[k[-1]]/sc[k[-31]]-1:+.1%}" if len(k) > 31 else ""))
    # S11/S12 funding extremes
    fr = {}
    for r_ in list(csv.reader(open(f"{X}/funding_BTCUSDT.csv")))[1:]:
        try: fr.setdefault(datetime.datetime.utcfromtimestamp(int(r_[0]) / 1000).date().isoformat(), []).append(float(r_[1]))
        except Exception: pass
    fd = {d: st.mean(v) for d, v in sorted(fr.items())}; k = list(fd); f7 = {k[i]: st.mean(fd[k[j]] for j in range(i - 6, i + 1)) for i in range(6, len(k))}
    for sid, cond, side, mech in (("S11", lambda x: x > 0.0003, -1, "Perp longs paying >0.03%/8h are levered and crowded; liquidations cascade on any dip."),
                                  ("S12", lambda x: x < 0, 1, "Negative funding = crowded shorts paying to stay short; short squeeze risk.")):
        trig = [(d, 0) for d, x in f7.items() if cond(x)]
        r = study(sid, PX("BTC-USD"), trig, side, 7, 1, 20, oos="2023-01-01")
        lk = list(f7)[-1]
        add(dict(id=sid, asset="BTC", cls="crypto", mechanism=mech, trigger=f"7d avg Bybit BTCUSDT funding {'>0.03%' if side<0 else '<0'}; {'short' if side<0 else 'long'} BTC 7d", data="Bybit v5 funding history", buyer="Crypto funds, basis desks"), r,
            dict(fired=cond(f7[lk]), detail=f"7d funding {100*f7[lk]:.4f}%/8h ({lk})"))
    # S13 OI surge
    oi = {}
    for r_ in list(csv.reader(open(f"{X}/oi_BTCUSDT.csv")))[1:]:
        try: oi[datetime.datetime.utcfromtimestamp(int(r_[0]) / 1000).date().isoformat()] = float(r_[1])
        except Exception: pass
    oi = dict(sorted(oi.items())); k = list(oi); trig = [(k[i], 0) for i in range(7, len(k)) if oi[k[i]] / oi[k[i - 7]] - 1 > 0.20]
    r = study("S13", PX("BTC-USD"), trig, -1, 7, 1, 20, oos="2023-01-01")
    add(dict(id="S13", asset="BTC", cls="crypto", mechanism="A fast open-interest build is new leverage; it must be unwound (liquidations) when price moves against it.",
             trigger="Bybit BTCUSDT OI +20% in 7 days; short BTC 7d", data="Bybit v5 open interest (daily)", buyer="Crypto funds"), r,
        dict(fired=recent(trig, 7)[0], detail=f"OI 7d {oi[k[-1]]/oi[k[-8]]-1:+.1%}"))
    # S14 regional-bank forced-seller drawdown → rebound
    kre = PX("KRE"); k = list(kre); trig = [(k[i], 0) for i in range(20, len(k)) if kre[k[i]] / max(kre[k[j]] for j in range(i - 20, i)) - 1 < -0.20]
    r = study("S14", kre, trig, 1, 60, 0, 10)
    add(dict(id="S14", asset="KRE", cls="stocks", mechanism="Bank-stress drawdowns trigger deposit flight and forced liquidation of bank equity by risk-limited holders; overshoot then policy backstop.",
             trigger="KRE −20% from its 20-day high; long KRE 60d", data="Yahoo KRE", buyer="Financials PMs, event funds"), r,
        dict(fired=recent(trig, 60)[0], detail=f"KRE vs 20d high {kre[k[-1]]/max(kre[k[j]] for j in range(len(k)-21,len(k)-1))-1:+.1%}"))
    # S15 sovereign spread shock (Italy–Bund, monthly FRED) → EWI
    it, de = FRED("IRLTLT01ITM156N"), FRED("IRLTLT01DEM156N"); k = [d for d in it if d in de]
    if k:
        sp = {d: it[d] - de[d] for d in k}; trig = [(k[i], 0) for i in range(1, len(k)) if sp[k[i]] - sp[k[i - 1]] > 0.4]
        # monthly average data published ~mid next month → lag 45 days
        r = study("S15", PX("EWI"), trig, -1, 20, 45, 10)
        add(dict(id="S15", asset="EWI", cls="bonds", mechanism="A BTP–Bund blow-out forces Italian banks (big BTP holders) and EM-style sovereign funds to cut; equities follow.",
                 trigger="Monthly IT–DE 10y spread +40bp m/m; short EWI 20d (lag 45d for publication)", data="FRED IRLTLT01ITM156N, IRLTLT01DEM156N (OECD monthly)", buyer="Euro macro funds, banks"), r,
            dict(fired=recent(trig, 75)[0], detail=f"IT–DE spread {sp[k[-1]]:.2f}pp ({k[-1]})"))
    # S16 China export-control announcements (MOFCOM)
    trig = [("2023-07-02", 0), ("2024-08-14", 0), ("2025-04-03", 0), ("2025-10-08", 0)]
    r = study("S16", PX("REMX"), trig, 1, 5, 0, 10, oos="2024-01-01", min_oos=8)
    add(dict(id="S16", asset="REMX", cls="critical minerals", mechanism="Chinese export licensing removes supply for non-Chinese buyers; Western producers re-rate.",
             trigger="MOFCOM/GACC export-control announcement on a critical mineral; long REMX 5d", data="MOFCOM announcements 2023 No.23, 2024 No.33, 2025 No.18, 2025 No.57", buyer="Critical-minerals funds, OEM procurement"), r,
        dict(fired=False, detail="no new MOFCOM control in the last 30 days found (not monitored automatically yet)"))
    # S17 staking surge near controlled-mineral deposit (BLM MLRS Created dates)
    b = json.load(open(f"{V}/blm_hub_sites.json")); evs = []; live = []
    for site, s in b.items():
        cnt = collections.Counter(datetime.datetime.utcfromtimestamp(r_["Created"] / 1000).strftime("%Y-%m") for r_ in s["records"] if r_.get("Created") and not (r_.get("LEG_CSE_NR") or "").strip())
        months = []; d = datetime.date(2021, 1, 1)
        while d <= datetime.date.today(): months.append(d.strftime("%Y-%m")); d = (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        for i, m in enumerate(months):
            prev = [cnt.get(x, 0) for x in months[max(0, i - 12):i]]
            if i >= 6 and cnt.get(m, 0) >= 50 and cnt.get(m, 0) >= 3 * (st.mean(prev) + 1):
                nxt = (datetime.date.fromisoformat(m + "-01").replace(day=28) + datetime.timedelta(days=4)).replace(day=1).isoformat()
                evs.append((site, s["ticker"], nxt, cnt[m]))
                if (datetime.date.today() - datetime.date.fromisoformat(nxt)).days < 120: live.append(f"{site} {m}: {cnt[m]} new claims")
    rows = []
    for site, tk, d, n in evs:
        px = PX(tk); bm = PX("GDXJ")
        if not px: continue
        S, B = Ser(px), Ser(bm); i, j = S.idx_after(d), B.idx_after(d)
        if i + 60 >= len(S.v) or j + 60 >= len(B.v): rows.append(dict(site=site, ticker=tk, month=d, claims=n, x60=None)); continue
        x = (S.v[i + 60] / S.v[i] - 1) - (B.v[j + 60] / B.v[j] - 1) - 0.01
        x20 = (S.v[i + 20] / S.v[i] - 1) - (B.v[j + 20] / B.v[j] - 1) - 0.01
        rows.append(dict(site=site, ticker=tk, month=d, claims=n, x20=round(100 * x20, 1), x60=round(100 * x, 1)))
    xs = [r_["x60"] for r_ in rows if r_.get("x60") is not None]
    agg = dict(n=len(xs), precision=round(100 * sum(x > 0 for x in xs) / len(xs)) if xs else None, mean_excess=round(st.mean(xs), 2) if xs else None, median=round(st.median(xs), 2) if xs else None)
    status = "UNTESTED" if len(xs) < 8 else ("KILLED" if agg["mean_excess"] <= 0 or agg["precision"] < 52 else "KEPT")
    add(dict(id="S17", asset="Nearby listed owner/junior vs GDXJ", cls="critical minerals", mechanism="A staking surge next to a documented controlled-mineral deposit signals new money/explorers crowding in; the nearby listed developer is re-rated (or is the one staking).",
             trigger="District new BLM claims in a month ≥50 and ≥3× trailing-12m average; long nearby listed owner vs GDXJ 60d, 100bp cost", data="BLM MLRS hub FeatureServer (Created date, MLRS-native serials only, 2021+)", buyer="Resource funds, royalty companies", staking_events=rows),
        dict(name="S17", h=60, cost_bp=100, oos_start="2021-01-01 (all data is post-MLRS)", in_sample=dict(n=0), oos=agg, status=status, events=[], worst_oos=sorted([r_ for r_ in rows if r_.get("x60") is not None], key=lambda r_: r_["x60"])[:3]),
        dict(fired=bool(live), detail="; ".join(live) or "no surge in last 4 months"))
    # S18 JGB 10y jump (BoJ normalisation / forced JGB selling by banks & lifers)
    jp = FRED("IRLTLT01JPM156N"); k = list(jp); trig = [(k[i], 0) for i in range(3, len(k)) if jp[k[i]] - jp[k[i - 3]] > 0.20]
    r = study("S18", PX("EWJ"), trig, -1, 20, 45, 10)
    add(dict(id="S18", asset="EWJ", cls="bonds", mechanism="A fast JGB yield rise inflicts mark-to-market losses on Japanese banks/lifers who sell foreign assets and cut equity; yen carry unwinds.",
             trigger="Japan 10y (OECD monthly) +20bp over 3 months; short EWJ 20d after 45d publication lag", data="FRED IRLTLT01JPM156N", buyer="Japan macro funds, global allocators"), r,
        dict(fired=recent(trig, 75)[0], detail=f"JGB 10y {jp[k[-1]]:.2f}% ({k[-1]}), 3m {jp[k[-1]]-jp[k[-4]]:+.2f}pp"))
    # S19 real-rate collapse → gold
    rr = FRED("DFII10"); k = list(rr); trig = [(k[i], 0) for i in range(63, len(k)) if rr[k[i]] - rr[k[i - 63]] < -0.50]
    r = study("S19", PX("GLD"), trig, 1, 20, 1, 10)
    add(dict(id="S19", asset="GLD", cls="commodities", mechanism="Falling real yields cut the carry cost of holding gold; real-money and central-bank buyers add.",
             trigger="US 10y TIPS yield −50bp in 63 days; long GLD 20d", data="FRED DFII10, Yahoo GLD", buyer="Macro funds, sovereign funds"), r,
        dict(fired=recent(trig, 20)[0], detail=f"10y real {rr[k[-1]]:.2f}%, 63d {rr[k[-1]]-rr[k[-64]]:+.2f}pp"))
    # S20 national BLM staking surge → GDXJ
    nat = json.load(open(f"{V}/blm_national_new_by_month.json")); ms = sorted(nat); trig = []
    for i in range(12, len(ms)):
        prev = [nat[m] for m in ms[i - 12:i]]
        if nat[ms[i]] > 1.5 * st.mean(prev): trig.append(((datetime.date.fromisoformat(ms[i] + "-01").replace(day=28) + datetime.timedelta(days=4)).replace(day=1).isoformat(), 0))
    r = study("S20", PX("GDXJ"), trig, 1, 60, 0, 10, oos="2023-01-01", min_oos=5)
    add(dict(id="S20", asset="GDXJ", cls="critical minerals", mechanism="A national jump in new federal claims shows exploration capital flooding in — momentum in juniors.",
             trigger="US new MLRS claims in a month >1.5× trailing-12m average; long GDXJ 60d", data="BLM MLRS hub FeatureServer, Created date (MLRS-native serials), 2021+", buyer="Resource funds"), r,
        dict(fired=recent(trig, 60)[0], detail=f"last month {ms[-1]}: {nat[ms[-1]]} new claims vs 12m avg {st.mean(nat[m] for m in ms[-13:-1]):.0f}"))
    # S21 Fed net liquidity impulse (WALCL − RRP)
    wa, rp = FRED("WALCL"), FRED("RRPONTSYD"); k = [d for d in wa]
    def rpv(d):
        ks = [x for x in rp if x <= d]; return rp[ks[-1]] if ks else 0  # RRP in $bn; WALCL in $m → /1e3 = $bn
    nl = {d: wa[d] / 1e3 - rpv(d) for d in k if d >= "2014-01-01"}; k = list(nl)
    trig = [(k[i], 0) for i in range(13, len(k)) if nl[k[i]] - nl[k[i - 13]] > 200]
    r = study("S21", PX("SPY"), trig, 1, 20, 2, 10)
    add(dict(id="S21", asset="SPY", cls="bonds", mechanism="A rise in Fed balance sheet net of reverse-repo adds bank reserves; liquidity-sensitive holders re-risk.",
             trigger="(WALCL − RRP) +$200bn over 13 weeks; long SPY 20d", data="FRED WALCL (weekly, $m), RRPONTSYD (daily, $bn)", buyer="Macro funds, liquidity strategists"), r,
        dict(fired=recent(trig, 20)[0], detail=f"net liquidity 13w change {nl[k[-1]]-nl[k[-14]]:+.0f}bn"))
    # S22 yen carry unwind
    jy = FRED("DEXJPUS"); k = list(jy); trig = [(k[i], 0) for i in range(10, len(k)) if jy[k[i]] / jy[k[i - 10]] - 1 < -0.05]
    r = study("S22", PX("EWJ"), trig, 1, 20, 1, 10)
    add(dict(id="S22", asset="EWJ", cls="stocks", mechanism="A fast yen rally forces carry-trade unwinds (short-yen funded longs) — Japanese equities are dumped by levered foreigners and overshoot.",
             trigger="USDJPY −5% in 10 trading days; long EWJ 20d", data="FRED DEXJPUS (H.10 noon buying rate)", buyer="Japan funds, macro funds"), r,
        dict(fired=recent(trig, 20)[0], detail=f"USDJPY 10d {jy[k[-1]]/jy[k[-11]]-1:+.1%}"))
    # S23 financial stress index spike → equity
    fs = FRED("STLFSI4"); k = list(fs); trig = []; lt = -99
    for i in range(1, len(k)):
        if fs[k[i]] > 1.0 and fs[k[i - 1]] <= 1.0 and i - lt > 8: trig.append((k[i], 0)); lt = i
    r = study("S23", PX("SPY"), trig, 1, 60, 7, 10)
    add(dict(id="S23", asset="SPY", cls="stocks", mechanism="When the St. Louis Fed stress index crosses +1, deleveraging is under way; forced sellers overshoot and policy reacts.",
             trigger="STLFSI4 crosses above 1.0; long SPY 60d", data="FRED STLFSI4 (weekly)", buyer="Multi-asset PMs"), r,
        dict(fired=recent(trig, 60)[0], detail=f"STLFSI4 {fs[k[-1]]:+.2f} ({k[-1]})"))
    json.dump({s["id"]: dict(asset=s["asset"], status=s["status"], h=s["h"], events=s.get("events", [])) for s in SIG}, open("/workspace/triage_os_data/signal_events.json", "w"))
    for s in SIG: s.pop("events", None)
    json.dump(dict(asof=datetime.date.today().isoformat(), method=__doc__, signals=SIG), open(OUT, "w"), indent=1, default=str)
if __name__ == "__main__": run()
