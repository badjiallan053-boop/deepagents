"""2019-2026 backtests on public SEC data (all results UNVERIFIED, research only).

A. Pre-filing watchlist: 8-K item 2.04 (acceleration), 3.01 (delisting notice) vs later item 1.03 (bankruptcy) by the same CIK.
B. BDC mark-cliff: par-weighted borrower mark falls >=15pts QoQ from >=80 vs later mark <60 (same BDC, next 4 quarters).
"""
import argparse, datetime as dt, json, sqlite3, statistics
from collections import defaultdict

D = dt.date.fromisoformat

def load_8k(path):
    ev = defaultdict(lambda: defaultdict(set))  # cik -> item -> {dates}
    names = {}
    for line in open(path):
        r = json.loads(line)
        if not r.get("cik") or not r.get("date"): continue
        for it in ("1.03", "2.04", "3.01"):
            if it in r["items"]: ev[r["cik"]][it].add(r["date"])
        names[r["cik"]] = r["name"]
    return ev, names

def prefiling(ev, start="2019-01-01", end="2025-04-30", horizon=540, lookback=730, data_end="2026-10-21"):
    out = {}
    defs = {"2.04 acceleration": lambda e: e["2.04"], "3.01 delisting": lambda e: e["3.01"],
            "2.04 + 3.01 within 180d": lambda e: {a for a in e["2.04"] for b in e["3.01"] if abs((D(a) - D(b)).days) <= 180}}
    for label, fn in defs.items():
        n = tp = 0; leads = []
        for cik, e in ev.items():
            bk = sorted(D(x) for x in e["1.03"])
            flags = sorted(D(x) for x in fn(e) if start <= x <= end)
            # drop flags that come within 365d AFTER a bankruptcy (post-petition noise)
            flags = [f for f in flags if not any(0 <= (f - b).days <= 365 for b in bk)]
            if not flags: continue
            f = flags[0]; n += 1
            hit = [b for b in bk if 0 < (b - f).days <= horizon]
            if hit: tp += 1; leads.append((hit[0] - f).days)
        out[label] = {"flagged_issuers": n, "filed_ch11_within_540d": tp, "precision": round(tp / n, 3) if n else None,
                      "median_lead_days": statistics.median(leads) if leads else None,
                      "p25_lead_days": statistics.quantiles(leads, n=4)[0] if len(leads) >= 4 else None}
    # recall: bankruptcies 2019-07..data_end with any prior flag within lookback
    bks = flagged = 0; leads = []
    for cik, e in ev.items():
        for b in sorted(e["1.03"])[:1]:
            if not ("2019-07-01" <= b <= data_end): continue
            bks += 1
            prior = [D(x) for x in e["2.04"] | e["3.01"] if 0 < (D(b) - D(x)).days <= lookback]
            if prior: flagged += 1; leads.append((D(b) - min(prior)).days)
    out["recall"] = {"ch11_8k_filers": bks, "flagged_before": flagged, "hit_rate": round(flagged / bks, 3) if bks else None,
                     "median_lead_days": statistics.median(leads) if leads else None}
    return out

def quarter_marks(con, tables=("bdc_marks_hist", "bdc_marks")):
    m = defaultdict(dict)
    for t in tables:
        try:
            rows = con.execute(f"select bdc, borrower_key, period, sum(par), sum(fv) from {t} where par>0 and borrower_key!='' group by 1,2,3").fetchall()
        except sqlite3.OperationalError: continue
        for b, k, p, par, fv in rows:
            if par >= 1e6: m[(b, k)][p] = 100 * fv / par
    return m

def mark_cliff(m, drop=15, from_=80, bad=60, horizon_q=4):
    n = tp = 0; leads = []; base_n = base_tp = 0; ever_bad = preceded = 0
    for key, s in m.items():
        ps = sorted(s)
        for i in range(1, len(ps)):
            prev, cur = s[ps[i - 1]], s[ps[i]]
            fut = [s[p] for p in ps[i + 1:i + 1 + horizon_q]]
            if prev < from_ or not fut: continue
            if prev - cur >= drop and cur >= bad:
                n += 1
                j = next((k for k, v in enumerate(fut) if v < bad), None)
                if j is not None: tp += 1; leads.append((j + 1) * 91)
            elif prev - cur < drop:
                base_n += 1; base_tp += any(v < bad for v in fut)
        # hit rate: positions that fell from >=80 to <60, was there an earlier cliff (still >=60)?
        for i in range(1, len(ps)):
            if s[ps[i]] < bad and max(s[p] for p in ps[:i]) >= from_:
                ever_bad += 1
                preceded += any(s[ps[k - 1]] - s[ps[k]] >= drop and s[ps[k]] >= bad for k in range(1, i))
                break
    return {"cliff_events": n, "fell_below_60_within_4q": tp, "precision": round(tp / n, 3) if n else None,
            "base_rate_no_cliff": round(base_tp / base_n, 3) if base_n else None,
            "lift": round((tp / n) / (base_tp / base_n), 1) if n and base_tp else None,
            "median_lead_days": statistics.median(leads) if leads else None,
            "positions_that_broke_below_60": ever_bad, "preceded_by_cliff": preceded,
            "hit_rate": round(preceded / ever_bad, 3) if ever_bad else None,
            "quarters": sorted({p for s in m.values() for p in s})}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); ap.add_argument("--items", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ev, _ = load_8k(a.items); res = {"prefiling": prefiling(ev), "mark_cliff": mark_cliff(quarter_marks(sqlite3.connect(a.db)))}
    json.dump(res, open(a.out, "w"), indent=1, default=str); print(json.dumps(res, indent=1, default=str))
