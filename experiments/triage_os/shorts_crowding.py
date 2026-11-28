"""S24 short-position crowding (France AMF + Netherlands AFM public registers of net short positions >=0.5%).
Mechanism: when disclosed shorts in one issuer pile up, any good news forces buy-ins (squeeze), or the crowd is right.
Direction tested honestly: event = aggregate disclosed short first crosses 5% of share capital (month-end sample);
forward excess return vs the country ETF (EWQ for FR, EWN for NL) at 20 and 60 trading days, 30bp round-trip cost.
OOS from 2019-01-01. Tickers resolved by ISIN via Yahoo search; unresolved issuers are listed, not dropped silently.
Survivorship note: registers include delisted issuers, but Yahoo may lack their prices → listed as unresolved."""
import csv, json, os, datetime, collections, subprocess, statistics as st, math, time
V = "/workspace/triage_os_data/xasset/v4"
def curl(u):
    r = subprocess.run(["curl", "-sSL", "-m", "30", "-A", "Mozilla/5.0", u], capture_output=True); return r.stdout if r.returncode == 0 else b""
def positions():
    P = []
    for r in csv.DictReader(open(f"{V}/amf_shorts.csv", encoding="utf-8", errors="ignore"), delimiter=";"):
        try: P.append((r["Emetteur / issuer"], r["code ISIN"], r["Detenteur de la position courte nette"], float(r["Ratio"]), r["Date de debut position"], r["Date de fin de publication position"] or "2099-01-01", "FR"))
        except Exception: pass
    rows = collections.defaultdict(list)
    for r in csv.DictReader(open(f"{V}/afm_history.csv", encoding="utf-8", errors="ignore"), delimiter=";"):
        try: rows[(r["ISIN"], r["Positie houder"])].append((r["Positiedatum"][:10], float(r["Netto Shortpositie"].replace(",", ".")), r["Naam van de emittent"]))
        except Exception: pass
    for (isin, h), lst in rows.items():
        lst.sort()
        for i, (d, v, nm) in enumerate(lst):
            end = lst[i + 1][0] if i + 1 < len(lst) else "2099-01-01"
            if v >= 0.5: P.append((nm, isin, h, v, d, end, "NL"))
    return P
def month_ends():
    out = []; y, m = 2013, 1
    while True:
        nxt = datetime.date(y + (m == 12), m % 12 + 1, 1); d = nxt - datetime.timedelta(days=1)
        if d >= datetime.date.today(): break
        out.append(d.isoformat()); y, m = nxt.year, nxt.month
    return out
def run():
    P = positions(); by = collections.defaultdict(list)
    for p in P: by[p[1]].append(p)
    ME = month_ends(); agg = {}
    for isin, ps in by.items():
        s = {}
        for m in ME:
            cur = {}
            for nm, _, h, v, a, b, c in sorted(ps, key=lambda z: z[4]):
                if a <= m < b: cur[h] = v
            s[m] = sum(cur.values())
        agg[isin] = dict(name=ps[0][0], country=ps[0][6], series=s)
    events = []
    for isin, a in agg.items():
        prev = 0
        for m in ME:
            v = a["series"][m]
            if v >= 5 and prev < 5: events.append((isin, a["name"], a["country"], m, round(v, 2)))
            prev = v
    cache_f = f"{V}/isin_tickers.json"; cache = json.load(open(cache_f)) if os.path.exists(cache_f) else {}
    for isin in sorted(set(e[0] for e in events)):
        if isin in cache: continue
        try:
            j = json.loads(curl(f"https://query2.finance.yahoo.com/v1/finance/search?q={isin}&quotesCount=3&newsCount=0") or b"{}")
            q = [x["symbol"] for x in j.get("quotes", []) if x.get("symbol", "").endswith((".PA", ".AS", ".BR"))]
            cache[isin] = q[0] if q else None
        except Exception: cache[isin] = None
        time.sleep(0.3)
    json.dump(cache, open(cache_f, "w"))
    def px(t):
        f = f"{V}/px_{t}.json"
        if not os.path.exists(f): open(f, "wb").write(curl(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=15y&interval=1d")); time.sleep(0.3)
        try:
            r = json.load(open(f))["chart"]["result"][0]; c = r["indicators"]["adjclose"][0]["adjclose"]
            return {datetime.date.fromtimestamp(a).isoformat(): b for a, b in zip(r["timestamp"], c) if b}
        except Exception: return {}
    bm = {"FR": px("EWQ"), "NL": px("EWN")}; res = []; unresolved = []
    for isin, nm, c, m, v in events:
        t = cache.get(isin)
        if not t: unresolved.append(nm); continue
        p = px(t); b = bm[c]; ks = sorted(k for k in p if k > m); kb = sorted(k for k in b if k > m)
        row = dict(isin=isin, name=nm, ticker=t, month=m, short_pct=v)
        for h in (20, 60):
            if len(ks) > h and len(kb) > h:
                row[f"x{h}"] = round(100 * ((p[ks[h]] / p[ks[0]] - 1) - (b[kb[h]] / b[kb[0]] - 1)) - 0.3, 2)
        res.append(row)
    def agg_(rs, k):
        xs = [r[k] for r in rs if r.get(k) is not None]
        if not xs: return dict(n=0)
        return dict(n=len(xs), pct_up=round(100 * sum(x > 0 for x in xs) / len(xs)), mean=round(st.mean(xs), 2), median=round(st.median(xs), 2),
                    t=round(st.mean(xs) / (st.stdev(xs) / math.sqrt(len(xs))), 2) if len(xs) > 2 else None)
    IS = [r for r in res if r["month"] < "2019-01-01"]; OS = [r for r in res if r["month"] >= "2019-01-01"]
    out = dict(events=res, unresolved=unresolved, n_issuers=len(agg), positions=len(P),
               stats={f"{w}_{k}": agg_(rs, k) for w, rs in (("IS", IS), ("OOS", OS)) for k in ("x20", "x60")})
    last = ME[-1]; live = sorted([(a["series"][last], a["name"], a["country"]) for a in agg.values() if a["series"][last] >= 3], reverse=True)[:15]
    out["live_crowded"] = [dict(name=n, country=c, short_pct=round(v, 2), asof=last) for v, n, c in live]
    json.dump(out, open("/workspace/triage_os_data/shorts_crowding.json", "w"), indent=1); print(json.dumps(out["stats"]), len(res), "unresolved", len(unresolved)); print(out["live_crowded"][:8])
if __name__ == "__main__": run()
