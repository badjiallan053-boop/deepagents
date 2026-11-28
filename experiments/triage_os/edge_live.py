"""Edge Lab live layer (today's candidates) + the three 'overlooked' implementations.
O1 lockup-expiry calendar (IPO 424B4 + first trade -> day-180 expiry in the next 75 days)
O2 late-filer deadline watch (NT 10-K / NT 10-Q filed in the last 60 days)
O3 convergence: open-market insider cluster buying (Form 4 code P, >=3 insiders, 21 days) x activist 13D in the last 120 days
All from EDGAR form.idx + filings; filing date is the point-in-time stamp.
"""
import os, re, json, glob, datetime, subprocess, collections, time, concurrent.futures as cf
import edge_lab as L
UA = "TRIAGE research badjiallan053@gmail.com"; TODAY = datetime.date(2026, 10, 23); OUT = "/workspace/triage_os_data/edge_live.json"
def recent(forms, days):
    lo = (TODAY - datetime.timedelta(days=days)).isoformat()
    return [r for r in L.idx_rows(forms) if r[3] >= lo]
def get(path):
    c = f"/workspace/triage_os_data/edge/f4cache/{path.replace('/', '_')}"
    if os.path.exists(c): return open(c, encoding="utf-8", errors="ignore").read()
    os.makedirs(os.path.dirname(c), exist_ok=True); time.sleep(0.15)
    t = subprocess.run(["curl", "-s", "-m", "40", "-A", UA, f"https://www.sec.gov/Archives/{path}"], capture_output=True, text=True).stdout
    open(c, "w").write(t); return t
def lockups():
    out = []
    for f, co, cik, d, p in recent({"424B4"}, 200):
        t = L.CT.get(cik.lstrip("0")) or L.CT.get(cik)
        if not t or "ACQUISITION" in co.upper() or re.search(r"(U|-UN|W|R)$", t) and len(t) >= 5: continue  # drop SPAC units/warrants/rights
        P = L.px(t.replace(".", "-"))
        if not P: continue
        first = datetime.date.fromisoformat(P[0][0])
        if abs((first - datetime.date.fromisoformat(d)).days) > 10: continue
        exp = first + datetime.timedelta(days=180)
        if TODAY <= exp <= TODAY + datetime.timedelta(days=75):
            out.append(dict(ticker=t, company=co, ipo=P[0][0], lockup_expiry_est=exp.isoformat(), ret_since_ipo=round(100 * (P[-1][1] / P[0][1] - 1)), src=f"https://www.sec.gov/Archives/{p}"))
    return sorted({o["ticker"]: o for o in out}.values(), key=lambda o: o["lockup_expiry_est"])
def late_filers():
    out = {}
    for f, co, cik, d, p in recent({"NT 10-K", "NT 10-Q"}, 60):
        t = L.CT.get(cik.lstrip("0"))
        if t: out[t] = dict(ticker=t, company=co, form=f, filed=d, deadline_note=("15 calendar-day extension (Rule 12b-25) ends " + (datetime.date.fromisoformat(d) + datetime.timedelta(days=15 if f == "NT 10-K" else 5)).isoformat()), src=f"https://www.sec.gov/Archives/{p}")
    return sorted(out.values(), key=lambda o: o["filed"], reverse=True)
def insider_live():
    by = collections.defaultdict(set)
    for f, co, cik, d, p in recent({"4"}, 21):
        if cik.lstrip("0") in L.CT: by[cik.lstrip("0")].add(p)
    cand = {c: ps for c, ps in by.items() if 3 <= len(ps) <= 15}
    paths = [p for ps in cand.values() for p in ps]
    with cf.ThreadPoolExecutor(6) as ex: docs = dict(zip(paths, ex.map(get, paths)))
    res = []
    for c, ps in cand.items():
        buyers = set(); val = 0; srcs = []
        for p in ps:
            x = docs.get(p, "")
            for blk in re.findall(r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>", x, re.S):
                if re.search(r"<transactionCode>\s*P\s*</transactionCode>", blk) and re.search(r"<transactionAcquiredDisposedCode>\s*<value>\s*A", blk):
                    o = re.search(r"<rptOwnerCik>\s*(\d+)", x); sh = re.search(r"<transactionShares>\s*<value>\s*([\d.]+)", blk); pr = re.search(r"<transactionPricePerShare>\s*<value>\s*([\d.]+)", blk)
                    if o: buyers.add(o.group(1)); srcs.append(f"https://www.sec.gov/Archives/{p}")
                    if sh and pr: val += float(sh.group(1)) * float(pr.group(1))
        if len(buyers) >= 3 and val >= 100_000:
            res.append(dict(ticker=L.CT[c], cik=c, insiders=len(buyers), value_usd=round(val), src=sorted(set(srcs))[:3]))
    return sorted(res, key=lambda r: -r["value_usd"])
def activists():
    acc = collections.defaultdict(list)
    for f, co, cik, d, p in recent({"SC 13D", "SCHEDULE 13D"}, 120): acc[p].append((cik.lstrip("0"), co, d))
    out = {}
    for p, rows in acc.items():
        for c, co, d in rows:
            if c in L.CT: out[L.CT[c]] = dict(ticker=L.CT[c], company=co, filed=d, filers=[r[1] for r in rows if r[0] != c][:2], src=f"https://www.sec.gov/Archives/{p}"); break
    return out
def spinoffs():
    out = {}
    for f, co, cik, d, p in recent({"10-12B", "10-12B/A"}, 150):
        out.setdefault(cik, dict(company=co, first_filed=d, ticker=L.CT.get(cik.lstrip("0")), src=f"https://www.sec.gov/Archives/{p}"))
    return list(out.values())
def ledger(lf):
    import committee as K
    have = {(r.get("ticker"), r.get("asof")) for r in map(json.loads, open(K.LEDGER)) if r.get("kind") == "edge_lab"}
    picks = []
    for r in lf:
        if r["form"] != "NT 10-K": continue
        P = L.px(r["ticker"].replace(".", "-"))
        if not P or P[-1][0] < "2026-10-15": continue
        r["last_px"], r["px_date"] = P[-1][1], P[-1][0]
        r["window_end"] = (datetime.date.fromisoformat(r["filed"]) + datetime.timedelta(days=174)).isoformat()
        r["kill"] = "Company files the 10-K within the 12b-25 extension AND the stock beats IWM by >20% within 60 days of the NT filing"
        picks.append(r)
    for r in picks[:12]:
        if (r["ticker"], TODAY.isoformat()) in have: continue
        K.append(dict(kind="edge_lab", asof=TODAY.isoformat(), mechanism="M5 NT 10-K late filer", ticker=r["ticker"], call="AVOID / paper SHORT-WATCH", px=r["last_px"], catalyst=r["deadline_note"], window_end=r["window_end"], kill=r["kill"], src=r["src"], note="paper only; borrow likely unavailable or costly; not advice"))
    return picks[:12], K.verify()
def run():
    ins = insider_live(); act = activists(); lk = lockups(); lf = late_filers()
    conv = [dict(i, activist=act[i["ticker"]]) for i in ins if i["ticker"] in act]
    live, ok = ledger(lf); sp = spinoffs()
    json.dump(dict(asof=TODAY.isoformat(), method=__doc__, insider_clusters=ins, activist_13d_recent=len(act), convergence=conv, lockups=lk, late_filers=lf[:60], live=live, ledger_ok=ok, spinoffs=sp, activists=list(act.values())[:40]), open(OUT, "w"), indent=1)
    print("insider clusters", len(ins), "convergence", len(conv), "lockups", len(lk), "late filers", len(lf), "live", len(live), ok, "spinoffs", len(sp))
if __name__ == "__main__": run()
