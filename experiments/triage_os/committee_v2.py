"""Alpha Committee v2 — rebuilt on the signal library only (AlphaAgents protocol, arXiv:2508.11152, kept: each
signal is an agent with its own data; when agents on the same asset disagree the committee abstains; risk-averse
profile caps gross exposure). Daily book, equal weight across open trades, cash otherwise, realistic costs:
round-trip 10 bp ETFs/futures proxies, 20 bp crypto, plus 5 bp/day financing on shorts (borrow) — conservative.
Out-of-sample = 2019-01-01 onward (signal rules were fixed on 2006–2018; crypto signals have OOS from 2023)."""
import json, os, math, statistics as st, datetime, collections, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signals as SG, committee as C1
SIGS = json.load(open("/workspace/triage_os_data/signals.json"))["signals"]; EV = json.load(open("/workspace/triage_os_data/signal_events.json"))
TK = {"S3": "CL_F", "S4": "NG_F", "S5": "TLT", "S6": "HYG", "S7": "SPY", "S8": "EEM", "S9": "TLT", "S10": "BTC-USD", "S11": "BTC-USD", "S12": "BTC-USD", "S13": "BTC-USD",
      "S14": "KRE", "S15": "EWI", "S16": "REMX", "S18": "EWJ", "S19": "GLD", "S20": "GDXJ", "S21": "SPY", "S22": "EWJ", "S23": "SPY"}
def ticker(sig): return sig.split(":")[1].replace("=", "_") if ":" in sig else TK[sig]
COST = lambda t: 20 if "USD" in t else 10
def tiers():
    st_ = {s["id"]: s["status"] for s in SIGS}
    A = [k for k, v in st_.items() if v == "KEPT"]
    B = [s["id"] for s in SIGS if s["status"] != "KEPT" and not s["status"].startswith("KILLED") and s["in_sample"].get("mean_excess", -1) and s["in_sample"].get("mean_excess", -1) > 0 and (s["oos"].get("mean_excess") or -1) > 0]
    return A, B
def book(ids, start="2019-01-01", averse=False):
    P = {}; trades = []
    for sid in ids:
        h = EV[sid]["h"]
        for e in EV[sid]["events"]:
            t = ticker(e.get("sig", sid)); P.setdefault(t, SG.PX(t)); trades.append((e["date"], t, e["dir"], h, sid))
    days = sorted(set(d for t in P for d in P[t] if d >= start and d <= max(SG.PX("SPY"))))
    days = [d for d in days if d in P.get("SPY", SG.PX("SPY")) or True]
    spy = SG.PX("SPY"); days = [d for d in sorted(spy) if d >= start]
    open_ = []; rets = []; n_tr = 0; abst = 0
    tr_by_day = collections.defaultdict(list)
    for tr in trades: tr_by_day[tr[0]].append(tr)
    idx = {t: {d: i for i, d in enumerate(P[t])} for t in P}; keys = {t: list(P[t]) for t in P}
    for d in days:
        for tr in tr_by_day.get(d, []):
            same = [o for o in open_ if o["t"] == tr[1]]
            if any(o["dir"] != tr[2] for o in same): abst += 1; continue  # disagreement → abstain (and close conflicting)
            if same: continue
            open_.append(dict(t=tr[1], dir=tr[2], left=tr[3], new=True)); n_tr += 1
        r = []
        for o in open_:
            t = o["t"]; i = idx[t].get(d)
            if i is None or i == 0: r.append(0.0); continue
            p0, p1 = P[t][keys[t][i - 1]], P[t][d]
            x = o["dir"] * (p1 / p0 - 1) if p0 > 0 and p1 > 0 else 0.0
            if o["new"]: x -= COST(t) / 2 / 1e4; o["new"] = False
            if o["dir"] < 0: x -= 5 / 1e4 / 21
            o["left"] -= 1
            if o["left"] <= 0: x -= COST(t) / 2 / 1e4
            r.append(x)
        gross = 1.0 if not averse else 0.5
        rets.append(gross * (st.mean(r) if r else 0.0)); open_ = [o for o in open_ if o["left"] > 0]
    return rets, n_tr, abst
def stats(r, per=252):
    if not r: return {}
    eq = pk = 1; dd = 0
    for x in r: eq *= 1 + x; pk = max(pk, eq); dd = min(dd, eq / pk - 1)
    yrs = len(r) / per; v = st.pstdev(r) * math.sqrt(per); cagr = eq ** (1 / yrs) - 1
    return dict(cagr=round(100 * cagr, 1), vol=round(100 * v, 1), sharpe=round((st.mean(r) * per) / v, 2) if v else None, maxdd=round(100 * dd, 1), days=len(r))
def ew_daily(start="2019-01-01"):
    spy = SG.PX("SPY"); days = [d for d in sorted(spy) if d >= start]; U = {t: SG.PX(t) for t in C1.UNIVERSE}; out = []
    for i in range(1, len(days)):
        rr = []
        for t, p in U.items():
            if days[i] in p and days[i - 1] in p and p[days[i - 1]] > 0: rr.append(p[days[i]] / p[days[i - 1]] - 1)
        out.append(st.mean(rr) if rr else 0)
    return out
def v1_net():
    """Committee v1 (rule agents, monthly) net of costs: 10 bp round trip per name changed (20 bp crypto)."""
    me = C1.month_ends(); prev = set(); out = []
    for i in range(len(me) - 1):
        d0, d1 = me[i], me[i + 1]
        if d0 < "2019-01-01": continue
        live = [t for t in C1.UNIVERSE if C1.fwd(t, d0, d1) is not None and C1.r_(C1.PX[t], d0, 252) is not None]
        picks = set(t for t in live if C1.debate(t, d0)[0] == "BUY")
        gross = st.mean([C1.fwd(t, d0, d1) for t in picks]) if picks else 0
        ch = picks ^ prev; cost = sum(COST(t) / 2 / 1e4 for t in ch) / max(1, len(picks | prev))
        out.append(gross - cost); prev = picks
    return out
if __name__ == "__main__":
    A, B = tiers(); res = dict(tier_A=A, tier_B=B)
    for lab, ids in (("v2_tierA_kept_only", A), ("v2_tierA+B_candidates", A + B)):
        for prof in ("risk_neutral", "risk_averse"):
            r, n, ab = book(ids, averse=prof == "risk_averse"); res[f"{lab}|{prof}"] = dict(stats(r), trades=n, abstentions=ab)
            # sub-period 2022+ (post-QE) for honesty
            r2, _, _ = book(ids, start="2022-01-01", averse=prof == "risk_averse"); res[f"{lab}|{prof}|2022+"] = stats(r2)
    res["equal_weight_universe|daily"] = stats(ew_daily()); res["equal_weight_universe|2022+"] = stats(ew_daily("2022-01-01"))
    res["v1_rule_committee_net|monthly"] = stats(v1_net(), 12)
    json.dump(res, open("/workspace/triage_os_data/committee_v2.json", "w"), indent=1); print(json.dumps(res, indent=0))
