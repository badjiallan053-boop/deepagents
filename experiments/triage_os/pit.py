"""Point-in-time (PIT) rebuild of the macro signals S21 (Fed net liquidity) and S23 (financial stress) from ALFRED vintages.

Each trigger is evaluated only with data *as published on the vintage date* (ALFRED alfredgraph.csv?vintage_date=D),
sampled every 4th Friday from 2015 (data/limit: ~10 s per request). The same backtest engine (signals.study) is used.
Three runs per signal, so the effect of revisions is separated from the effect of coarser sampling:
  final_daily   = the original signals.py result (final revised data, every observation)
  final_sampled = final revised data, sampled on the same vintage dates
  pit           = vintage data on the vintage dates (the honest number)
Output: /workspace/triage_os_data/pit.json with a 'summary'.
"""
import json, os, datetime
import signals as S
V4 = "/workspace/triage_os_data/xasset/v4"; OUT = "/workspace/triage_os_data/pit.json"
def vint(sid):
    p = f"{V4}/alfred_{sid}.json"
    if not os.path.exists(p): return {}
    d = json.load(open(p)); out = {}
    for vd, rows in sorted(d.items()):
        if not rows: continue
        try: out[vd] = [(r[0][:10], float(r[1])) for r in rows]
        except Exception: pass
    return out
def asof(series, d):
    ks = [k for k in series if k <= d]; return series[ks[-1]] if ks else None
def s21():
    wa, rp = vint("WALCL"), vint("RRPONTSYD"); vds = sorted(set(wa) & set(rp)); vds = [v for v in vds if len(wa[v]) >= 14]
    pit, fs = [], []
    WA, RP = S.FRED("WALCL"), S.FRED("RRPONTSYD"); wk = list(WA)
    for i, vd in enumerate(vds):
        if i < 3: continue
        w = wa[vd]; now = w[-1][1] / 1e3 - rp[vd][-1][1]; back = w[-14][1] / 1e3 - rp[vds[i - 3]][-1][1]
        if now - back > 200: pit.append((vd, 0))
        ks = [k for k in wk if k <= vd]
        if len(ks) > 13:
            f_now = WA[ks[-1]] / 1e3 - (asof(RP, ks[-1]) or 0); f_back = WA[ks[-14]] / 1e3 - (asof(RP, ks[-14]) or 0)
            if f_now - f_back > 200: fs.append((vd, 0))
    return len(vds), [S.study("S21", S.PX("SPY"), t, 1, 20, 0, 10) for t in (fs, pit)]
def s23():
    fsv = vint("STLFSI4"); vds = sorted(fsv); pit, fsm = [], []; F = S.FRED("STLFSI4"); fk = list(F); last_p = last_f = None
    for vd in vds:
        r = fsv[vd][-5:]
        if any(r[j][1] > 1 and r[j - 1][1] <= 1 for j in range(1, len(r))): pit.append((vd, 0))
        ks = [k for k in fk if k <= vd][-5:]
        if any(F[ks[j]] > 1 and F[ks[j - 1]] <= 1 for j in range(1, len(ks))): fsm.append((vd, 0))
    return len(vds), [S.study("S23", S.PX("SPY"), t, 1, 60, 0, 10) for t in (fsm, pit)]
def main():
    base = {s["id"]: s for s in json.load(open(S.OUT))["signals"]}; res = {}
    for sid, fn in (("S21", s21), ("S23", s23)):
        nv, (fsamp, p) = fn()
        strip = lambda r: {k: r[k] for k in ("status", "in_sample", "oos", "oos_start", "worst_oos")}
        b = base.get(sid, {})
        res[sid] = dict(vintages=nv, final_daily={k: b.get(k) for k in ("status", "in_sample", "oos")}, final_sampled=strip(fsamp), pit=strip(p),
                        pit_events=[dict(date=e["date"], x=round(100 * e["x"], 2)) for e in p["events"]])
    lines = []
    for sid, r in res.items():
        o = r["pit"]["oos"]
        lines.append(f"{sid}: final data {r['final_daily']['status']} -> point-in-time {r['pit']['status']} (PIT OOS n={o.get('n')}, mean {o.get('mean_excess')}%, precision {o.get('precision')}%; {r['vintages']} vintages)")
    if not any(r["vintages"] for r in res.values()):
        lines = ["PENDING: ALFRED throttled this box (HTTP/2 INTERNAL_ERROR / timeouts on every request after a 12-thread burst); a polite sequential resumable fetch is queued. Until it lands, S21's KEPT status is on final revised data and is NOT point-in-time; the Quant Validation gate therefore vetoes it."]
    summ = "; ".join(lines)
    json.dump(dict(asof=datetime.date.today().isoformat(), method=__doc__, summary=summ, signals=res), open(OUT, "w"), indent=1)
    print(summ); return res
if __name__ == "__main__": main()
