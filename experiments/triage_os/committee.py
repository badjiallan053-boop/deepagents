"""TRIAGE Alpha Committee — structured multi-agent debate adapted from
Zhao, Lyu, Jones, Garber, Pasquali, Mehta (BlackRock), "AlphaAgents: Large Language Model based Multi-Agents for
Equity Portfolio Constructions", arXiv:2508.11152v1 (2025), https://arxiv.org/html/2508.11152v1.

Protocol mirrored from the paper (§2.2.4, §2.3, §3.2):
  1. independent analysis — each role agent sees only its own data/tool (paper Table 1: per-agent data access);
  2. round-robin debate — every agent receives peers' views and must speak at least twice;
     no agent may decide for the group; terminate only after all agents were invoked;
  3. consensus — BUY/SELL agreed by all non-abstaining agents, else after MAX_ROUNDS a majority with the
     risk-profile tie-break (risk-averse ⇒ no position);
  4. risk tolerance — the same agents run as 'risk_neutral' or 'risk_averse' profiles (paper §2.3);
  5. evaluation — equal-weight portfolios from committee vs single agents vs equal-weight benchmark,
     cumulative return and Sharpe (paper §3.2 / §4.3), with full debate logs kept.
DIFFERENCE (stated honestly): the agents here are deterministic, tool-based rule agents — no LLM is called,
so the backtest is reproducible and free of look-ahead from model training data. The paper's role prompts are
kept verbatim in PROMPTS (adapted roles appended) so an LLM backend can be swapped in later; a backtest of an
LLM committee would be contaminated by the model's knowledge of the test period, which is why we do not run one.
PAPER-ONLY: no trades, no advice to third parties."""
import os, csv, json, math, hashlib, datetime, statistics as st
X = "/workspace/triage_os_data/xasset"; OUT = "/workspace/triage_os_data/committee"; os.makedirs(OUT, exist_ok=True)
PAPER = "arXiv:2508.11152v1 (AlphaAgents, BlackRock, 2025)"
PROMPTS = {  # paper prompts verbatim (§2.2.2, §2.2.4) + TRIAGE role prompts written in the same pattern
 "paper_valuation": "As a valuation equity analyst, your primary responsibility is to analyze the valuation trends of a given asset or portfolio over an extended time horizon. ...",
 "paper_coordinator_debate": "You are a helpful assistant skilled at coordinating a group of other agents to solve a task. You make sure that every agent in the group chat has a chance to speak at least twice. Each agent can not decide for the whole group. They are tasked with coming to a consensus. You must invoke all agents before deciding to Terminate. Reply \"TERMINATE\" at the end when everything is done.",
 "signal": "As a signal/radar analyst, your primary responsibility is to read the cross-asset radar (trend and flow signals) for the asset and state whether the signal supports owning it.",
 "valuation": "As a valuation analyst, your primary responsibility is to analyze the return and volatility of the asset over an extended horizon (annualised return and volatility tools) and judge whether it is reasonably priced for the investor's risk tolerance.",
 "contrarian": "As a contrarian analyst, your primary responsibility is to identify crowded or exhausted moves and argue against the consensus when positioning or recent returns are extreme.",
 "forced_seller": "As a forced-seller analyst, your primary responsibility is to identify holders that must sell (credit spread shocks, redemptions, covenant or rating triggers) and whether the asset is on the receiving end.",
 "lme": "As a commodities-positioning analyst (LME/CFTC), your primary responsibility is to analyse managed-money positioning and say whether it is stretched.",
 "macro": "As a macro analyst using a Dalio-style regime (real rates, credit spreads, debasement), your primary responsibility is to say whether the regime favours the asset class.",
}
ROLES = ["signal", "valuation", "contrarian", "forced_seller", "lme", "macro"]
CLASS = {"SPY": "eq", "I_GSPC": "eq", "I_HSI": "eq", "I_N225": "eq", "I_STOXX50E": "eq", "EEM": "eq", "2800.HK": "eq", "1306.T": "eq", "COPX": "eq", "LIT": "eq", "REMX": "eq", "SIL": "eq", "URA": "eq", "MP": "eq", "LYC.AX": "eq",
         "HYG": "credit", "JNK": "credit", "TLT": "rates", "IEF": "rates", "GLD": "gold", "GC_F": "gold", "BTC-USD": "crypto", "ETH-USD": "crypto",
         "CL_F": "cmdty", "HG_F": "cmdty", "SI_F": "cmdty", "NG_F": "cmdty", "PL_F": "cmdty", "ZC_F": "cmdty", "ZS_F": "cmdty", "ZW_F": "cmdty"}
COT = {"CL_F": "CL=F", "GC_F": "GC=F", "HG_F": "HG=F", "SI_F": "SI=F", "NG_F": "NG=F", "PL_F": "PL=F", "ZC_F": "ZC=F", "ZS_F": "ZS=F", "ZW_F": "ZW=F", "GLD": "GC=F"}
UNIVERSE = ["SPY", "EEM", "I_HSI", "I_N225", "I_STOXX50E", "COPX", "SIL", "URA", "REMX", "HYG", "JNK", "TLT", "IEF", "GLD", "BTC-USD", "CL_F", "HG_F", "SI_F", "NG_F", "ZC_F", "ZS_F", "ZW_F"]
def load(fn, col=1):
    p = f"{X}/{fn}"; d = {}
    if os.path.exists(p):
        for r in list(csv.reader(open(p)))[1:]:
            try: d[r[0][:10]] = float(r[col])
            except Exception: pass
    return d
PX = {t: load(f"px_{t}.csv") for t in UNIVERSE}
HY = load("fred_BAMLH0A0HYM2.csv"); RR = load("fred_DFII10.csv")
cot = {}
for r in list(csv.reader(open(f"{X}/cot_mm.csv")))[1:]:
    try: cot.setdefault(r[1], {})[r[0]] = (float(r[2]) - float(r[3])) / float(r[4])
    except Exception: pass
def upto(s, d):
    ks = [k for k in s if k <= d]; return sorted(ks)
def hist(s, d, n):
    ks = upto(s, d); return [s[k] for k in ks[-n:]]
def r_(s, d, n):
    h = hist(s, d, n + 1); return h[-1] / h[0] - 1 if len(h) == n + 1 and h[0] > 0 else None
def vol(s, d, n=63):
    h = hist(s, d, n + 1)
    if len(h) < n + 1: return None
    rs = [h[i + 1] / h[i] - 1 for i in range(n) if h[i] > 0]; return st.pstdev(rs) * math.sqrt(252)
def lvl(s, d, back=0):
    ks = upto(s, d)
    if not ks: return None
    if back: tgt = (datetime.date.fromisoformat(d) - datetime.timedelta(days=back)).isoformat(); ks = [k for k in ks if k <= tgt]
    return s[ks[-1]] if ks else None
# ---------- independent analysis: each agent uses only its own data (paper Table 1 discipline) ----------
def a_signal(t, d, prof):
    m = r_(PX[t], d, 63); m12 = r_(PX[t], d, 252)
    if m is None or m12 is None: return ("ABSTAIN", 0, "no history")
    v = "BUY" if m > 0 and m12 > 0 else "SELL" if m < 0 and m12 < 0 else "ABSTAIN"
    return (v, min(1, abs(m) * 5), f"3m {m:+.1%}, 12m {m12:+.1%}")
def a_valuation(t, d, prof):
    r = r_(PX[t], d, 252); v = vol(PX[t], d)
    if r is None or not v: return ("ABSTAIN", 0, "no history")
    ann = (1 + r) ** (252 / 252) - 1; sh = ann / v  # paper §2.2.3: annualised return / volatility tools
    cap = 0.30 if prof == "risk_averse" else 9
    if v > cap: return ("SELL", 0.6, f"vol {v:.0%} above risk-averse cap")
    return ("BUY" if sh > 0.5 else "SELL" if sh < -0.25 else "ABSTAIN", min(1, abs(sh) / 2), f"ann ret {ann:+.1%}, vol {v:.0%}, ratio {sh:.2f}")
def a_contrarian(t, d, prof):
    m1 = r_(PX[t], d, 21); v = vol(PX[t], d)
    if m1 is None or not v: return ("ABSTAIN", 0, "no history")
    z = m1 / (v / math.sqrt(12))
    return ("SELL" if z > 2 else "BUY" if z < -2 else "ABSTAIN", min(1, abs(z) / 3), f"1m move z={z:+.1f}")
def a_forced(t, d, prof):
    a, b = lvl(HY, d), lvl(HY, d, 30)
    if a is None or b is None: return ("ABSTAIN", 0, "no HY")
    w = a - b; c = CLASS[t]
    if w > 0.5:  # spread shock ⇒ credit/EM/equity holders forced to de-risk; havens receive flows
        return ("SELL" if c in ("eq", "credit", "crypto") else "BUY" if c in ("rates", "gold") else "ABSTAIN", min(1, w), f"HY OAS +{w:.2f}pp in 30d")
    if w < -0.5 and a > 5: return ("BUY" if c in ("credit", "eq") else "ABSTAIN", 0.5, f"HY OAS {w:+.2f}pp from {b:.1f}% — forced selling exhausting")
    return ("ABSTAIN", 0, f"HY OAS {w:+.2f}pp 30d")
def a_lme(t, d, prof):
    k = COT.get(t)
    if not k or k not in cot: return ("ABSTAIN", 0, "not a positioned commodity")
    s = cot[k]; ks = [x for x in s if x <= d]
    if len(ks) < 156: return ("ABSTAIN", 0, "short COT history")
    h = [s[x] for x in sorted(ks)[-156:]]; p = sum(1 for x in h if x <= h[-1]) / len(h)
    return ("SELL" if p > 0.9 else "BUY" if p < 0.1 else "ABSTAIN", abs(p - 0.5) * 2, f"MM net/OI pctile {p:.0%} (3y)")
def a_macro(t, d, prof):
    rr, rr0, hy, hy0 = lvl(RR, d), lvl(RR, d, 90), lvl(HY, d), lvl(HY, d, 90)
    if None in (rr, rr0, hy, hy0): return ("ABSTAIN", 0, "no macro")
    c = CLASS[t]; tight = rr - rr0 > 0.25; stress = hy - hy0 > 0.5
    if tight and stress: v = "SELL" if c in ("eq", "credit", "crypto", "cmdty") else "BUY" if c == "rates" else "ABSTAIN"
    elif rr - rr0 < -0.25: v = "BUY" if c in ("gold", "eq", "crypto") else "ABSTAIN"
    else: v = "ABSTAIN"
    return (v, 0.5 if v != "ABSTAIN" else 0, f"real 10y {rr:.2f}% ({rr-rr0:+.2f} 90d), HY {hy:.2f}% ({hy-hy0:+.2f})")
AG = dict(signal=a_signal, valuation=a_valuation, contrarian=a_contrarian, forced_seller=a_forced, lme=a_lme, macro=a_macro)
MAX_ROUNDS = 3
def debate(t, d, prof="risk_neutral"):
    """Round robin: every agent speaks in round 0 (independent) and round 1+ (rebuttal), i.e. at least twice.
    Rebuttal rule (deterministic stand-in for the LLM exchange): an agent whose confidence is below the
    confidence-weighted mean of peers who disagree concedes to ABSTAIN; agents never adopt a view they have no
    evidence for (they may only hold or withdraw), mirroring 'each agent can not decide for the whole group'."""
    view = {k: AG[k](t, d, prof) for k in ROLES}; log = [dict(round=0, **{k: list(v) for k, v in view.items()})]
    for rnd in range(1, MAX_ROUNDS + 1):
        new = {}
        for k in ROLES:
            v, c, why = view[k]
            if v == "ABSTAIN": new[k] = view[k]; continue
            opp = [view[j][1] for j in ROLES if j != k and view[j][0] not in ("ABSTAIN", v)]
            new[k] = ("ABSTAIN", 0, why + f" | conceded r{rnd}") if opp and c < st.mean(opp) else view[k]
        log.append(dict(round=rnd, **{k: list(v) for k, v in new.items()})); stable = new == view; view = new
        votes = [v[0] for v in view.values() if v[0] != "ABSTAIN"]
        if rnd >= 1 and votes and len(set(votes)) == 1: return votes[0], "consensus", rnd, log
        if stable: break
    votes = [v[0] for v in view.values() if v[0] != "ABSTAIN"]
    b, s = votes.count("BUY"), votes.count("SELL")
    if prof == "risk_averse" and (s or not b): return "NO POSITION", "risk-averse tie-break", rnd, log
    return ("BUY" if b > s else "SELL" if s > b else "NO POSITION"), "majority after max rounds", rnd, log
# ---------- backtest (paper §3.2: equal weights, compare committee vs single agents vs benchmark) ----------
def month_ends(a="2012-01-01", b=None):
    ks = sorted(PX["SPY"]); out = []
    for i, k in enumerate(ks[:-1]):
        if k >= a and k[:7] != ks[i + 1][:7]: out.append(k)
    return out
def fwd(t, d0, d1):
    a, b = lvl(PX[t], d0), lvl(PX[t], d1); return b / a - 1 if a and b else None
def stats(rets):
    if not rets: return {}
    eq = 1; peak = 1; mdd = 0
    for r in rets: eq *= 1 + r; peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
    yrs = len(rets) / 12; cagr = eq ** (1 / yrs) - 1; v = st.pstdev(rets) * math.sqrt(12)
    return dict(months=len(rets), cagr=round(100 * cagr, 1), vol=round(100 * v, 1), sharpe=round(cagr / v, 2) if v else None, maxdd=round(100 * mdd, 1))
def backtest():
    me = month_ends(); res = {}
    for prof in ("risk_neutral", "risk_averse"):
        P = {k: [] for k in ["committee", "equal_weight"] + ROLES}; P["dates"] = []; calls = 0; hits = 0
        for i in range(len(me) - 1):
            d0, d1 = me[i], me[i + 1]; live = [t for t in UNIVERSE if fwd(t, d0, d1) is not None and r_(PX[t], d0, 252) is not None]
            if not live: continue
            R = {t: fwd(t, d0, d1) for t in live}; P["dates"].append(d1)
            P["equal_weight"].append(st.mean(R.values()))
            def book(picks):  # long BUYs equal-weight; cash (0) if none — paper uses long-only selection
                return st.mean([R[t] for t in picks]) if picks else 0.0
            for k in ROLES: P[k].append(book([t for t in live if AG[k](t, d0, prof)[0] == "BUY"]))
            cm = [t for t in live if debate(t, d0, prof)[0] == "BUY"]; P["committee"].append(book(cm))
            for t in cm: calls += 1; hits += R[t] > st.mean(R.values())
        split = next(i for i, d in enumerate(P["dates"]) if d >= "2021-01-01")
        res[prof] = dict(full={k: stats(P[k]) for k in P if k != "dates"}, oos_2021={k: stats(P[k][split:]) for k in P if k != "dates"},
                         committee_calls=calls, committee_beat_ew_pct=round(100 * hits / max(1, calls)), start=P["dates"][0], end=P["dates"][-1])
    return res
# ---------- PAPER-ONLY hash-chained track record ----------
LEDGER = f"{OUT}/track_record.jsonl"
def append(rec):
    prev = "0" * 64
    if os.path.exists(LEDGER):
        lines = [l for l in open(LEDGER) if l.strip()]
        if lines: prev = json.loads(lines[-1])["hash"]
    rec = dict(rec, prev_hash=prev, logged_at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds"), paper_only=True)
    rec["hash"] = hashlib.sha256(json.dumps(rec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    open(LEDGER, "a").write(json.dumps(rec, ensure_ascii=False) + "\n"); return rec
def verify():
    prev = "0" * 64; n = 0
    for l in open(LEDGER):
        r = json.loads(l); h = r.pop("hash")
        if r["prev_hash"] != prev or hashlib.sha256(json.dumps(r, sort_keys=True, ensure_ascii=False).encode()).hexdigest() != h: return False, n
        prev = h; n += 1
    return True, n
def live_calls(prof="risk_neutral"):
    d = max(PX["SPY"]); out = []
    for t in UNIVERSE:
        if r_(PX[t], d, 252) is None: continue
        v, how, rnd, log = debate(t, d, prof)
        if v in ("BUY", "SELL"):
            r0 = log[0]; thesis = "; ".join(f"{k}: {r0[k][0]} ({r0[k][2]})" for k in ROLES if r0[k][0] != "ABSTAIN")
            out.append(dict(kind="cross-asset", instrument=t, call=v, entry_date=lvl_date(PX[t], d), entry=lvl(PX[t], d), thesis=thesis, consensus=how, rounds=rnd,
                            catalyst="next monthly committee", exit_rule="close at the next month-end committee or if the committee flips; -10% stop", benchmark="equal-weight 22-asset universe",
                            profile=prof, method=PAPER))
    return out, log
def lvl_date(s, d): return upto(s, d)[-1]
def credit_calls():
    W = json.load(open("/workspace/triage_os_data/world.json")); out = []
    for s in W["situations"]:
        if not s.get("price"): continue
        g = s.get("gap"); call = "WATCH"
        thesis = f"{s['stage'][:140]}"
        if g is not None: call = "BUY (recovery > price)" if g > 0 else "AVOID (price > recovery)"
        out.append(dict(kind="credit-situation", instrument=f"{s['entity']} — {s['price']['instrument']}", call=call, entry_date=s["price"]["date"], entry=s["price"]["value"],
                        entry_kind=s["price"]["kind"], thesis=thesis, catalyst=f"{s['date']}: {s['basis'][:120]}", exit_rule="mark at catalyst date + 5 trading days; close at outcome",
                        benchmark="Bloomberg pan-European HY proxy not public → JNK (USD HY ETF) as stand-in", gap_pp=g, method=PAPER))
    return out
if __name__ == "__main__":
    import sys
    bt = backtest(); json.dump(bt, open(f"{OUT}/backtest.json", "w"), indent=1)
    if "--log" in sys.argv:
        calls, sample = live_calls()
        for c in calls + credit_calls(): append(c)
        json.dump(sample, open(f"{OUT}/sample_debate.json", "w"), indent=1)
    print(json.dumps({p: {k: v for k, v in bt[p]["oos_2021"].items() if k in ("committee", "equal_weight", "signal", "valuation", "macro")} for p in bt}, indent=0)[:1500])
    print(verify() if os.path.exists(LEDGER) else "no ledger")
