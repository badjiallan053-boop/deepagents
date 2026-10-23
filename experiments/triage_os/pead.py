"""Free PEAD substitute: SEC XBRL frames (us-gaap EarningsPerShareBasic, quarterly CY frames), surprise = seasonal random walk.
SUE = (EPS_q - EPS_q-4) / stdev(last 8 seasonal diffs, min 4). Filing date from 10-Q accession via form.idx (point-in-time).
Long top decile SUE, short bottom decile, 60 trading days, excess vs IWM, 20bp. Q4 omitted (10-K frames are annual).
Bias: tickers from current company_tickers.json, so dead firms are missing (long leg biased up, short leg down).
"""
import os, json, subprocess, time, collections, statistics as st, random
import edge_lab as L
D = f"{L.E_}/frames"; os.makedirs(D, exist_ok=True)
def frame(y, q):
    p = f"{D}/CY{y}Q{q}.json"
    if not os.path.exists(p):
        time.sleep(0.2); t = subprocess.run(["curl", "-s", "-m", "60", "-A", "TRIAGE research badjiallan053@gmail.com", f"https://data.sec.gov/api/xbrl/frames/us-gaap/EarningsPerShareBasic/USD-per-shares/CY{y}Q{q}.json"], capture_output=True, text=True).stdout
        open(p, "w").write(t)
    try: return json.load(open(p))["data"]
    except Exception: return []
def events():
    acc = {}
    for ft, co, cik, d, path in L.idx_rows({"10-Q"}): acc[path.split("/")[-1].replace(".txt", "")] = d
    eps = collections.defaultdict(dict); fd = {}
    for y in range(2010, 2027):
        for q in (1, 2, 3):
            for r in frame(y, q):
                k = (y, q); eps[str(r["cik"])][k] = r["val"]
                if r["accn"] in acc: fd[(str(r["cik"]), k)] = acc[r["accn"]]
    ev = []
    for cik, s in eps.items():
        t = L.CT.get(cik)
        if not t: continue
        diffs = []
        for y in range(2011, 2027):
            for q in (1, 2, 3):
                if (y, q) in s and (y - 1, q) in s:
                    dlt = s[(y, q)] - s[(y - 1, q)]
                    if len(diffs) >= 4 and (cik, (y, q)) in fd:
                        sd = st.stdev(diffs[-8:])
                        if sd > 0: ev.append((t, fd[(cik, (y, q))], dlt / sd))
                    diffs.append(dlt)
    ev.sort(key=lambda e: e[1]); by = collections.defaultdict(list)
    for e in ev: by[e[1][:7]].append(e)   # decile within filing month (point-in-time cross-section)
    top, bot = [], []
    for m, es in by.items():
        if len(es) < 20: continue
        es.sort(key=lambda e: e[2]); k = len(es) // 10; bot += es[:k]; top += es[-k:]
    return top, bot, ev
def run():
    top, bot, ev = events()
    random.seed(7); top = random.sample(top, min(900, len(top))); bot = random.sample(bot, min(900, len(bot)))
    L.prefetch([e[0] for e in top + bot])
    res = dict(n_surprises=len(ev), long_top_decile=L.study([(t, d) for t, d, _ in top], 60, 20), short_bottom_decile=L.study([(t, d) for t, d, _ in bot], 60, 20, direction=-1))
    json.dump(res, open("/workspace/triage_os_data/pead.json", "w"), indent=1)
    for k in ("long_top_decile", "short_bottom_decile"): r = res[k]; print(k, r["status"], r["coverage"], r["IS"], r["OOS"])
if __name__ == "__main__": run()
