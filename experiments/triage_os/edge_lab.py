"""TRIAGE Edge Lab: rebuild documented event-driven mechanisms from free SEC data and test them honestly.

Point-in-time: every event is dated by its SEC *filing date* (when the public could know); entry at the first close strictly after it.
Excess = stock return - IWM return over the same window, minus round-trip cost. One event per ticker per holding window.
In-sample < 2022-01-01, out-of-sample >= 2022-01-01. Kill rule as signals.py: KEPT needs OOS mean>0, OOS precision>=52%, IS agrees, n_oos>=8.
Survivorship: prices come from Yahoo, which drops many delisted tickers; coverage (events priced / events) is reported per mechanism.
Bias direction: missing delisted names are disproportionately failures, so long-side results are biased UP and short-side results DOWN.
"""
import os, io, csv, json, zipfile, glob, random, datetime, subprocess, statistics as st, math, collections, concurrent.futures as cf
E_ = "/workspace/triage_os_data/edge"; PXD = f"{E_}/px"; os.makedirs(PXD, exist_ok=True); OUT = "/workspace/triage_os_data/edge_lab.json"
OOS = "2022-01-01"; random.seed(7); csv.field_size_limit(10**9)
def px(t):
    p = f"{PXD}/{t.replace('/', '_')}.json"
    if os.path.exists(p): return json.load(open(p))
    rows = []
    try:
        r = json.loads(subprocess.run(["curl", "-s", "-m", "40", "-A", "Mozilla/5.0", f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=10y&interval=1d"], capture_output=True, text=True).stdout)["chart"]["result"][0]
        rows = [[datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date().isoformat(), c] for ts, c in zip(r["timestamp"], r["indicators"]["adjclose"][0]["adjclose"]) if c]
    except Exception: pass
    json.dump(rows, open(p, "w")); return rows
def prefetch(ts):
    with cf.ThreadPoolExecutor(8) as ex: list(ex.map(px, sorted(set(ts))))
def idx_rows(forms):
    for f in sorted(glob.glob(f"{E_}/idx/*.idx")):
        for l in open(f, encoding="latin-1"):
            ft = l[:17].strip()
            if ft in forms:
                p = l.split()
                yield ft, l[17:79].strip(), p[-3], p[-2], p[-1]   # form, company, cik, date, path
CT = {str(v["cik_str"]): v["ticker"] for v in json.load(open(f"{E_}/company_tickers.json")).values()}
import bisect
def study(events, h, cost_bp, direction=1, bench="IWM"):
    B = dict(px(bench)); bk = sorted(B); ev = []; last = {}; n_all = len(events); priced = 0
    for t, d in sorted(events, key=lambda x: x[1]):
        P = px(t)
        if len(P) < 30: continue
        ks = [r[0] for r in P]; i = bisect.bisect_right(ks, d)
        if i >= len(P) - h: continue
        priced += 1
        if t in last and i - last[t] < h: continue
        e0, e1 = P[i][0], P[i + h][0]
        b0, b1 = B.get(e0), B.get(e1)
        if not b0 or not b1 or P[i][1] <= 0: continue
        x = direction * ((P[i + h][1] / P[i][1] - 1) - (b1 / b0 - 1)) - cost_bp / 1e4
        x = max(x, -1.0)  # long: cannot lose more than 100%; short: assume a stop/buy-in at -100% (a squeeze beyond that is not survivable)
        ev.append(dict(t=t, d=e0, x=x)); last[t] = i
    def agg(es):
        if not es: return dict(n=0)
        xs = [e["x"] for e in es]; xw = sorted(xs)[int(.02 * len(xs)):max(1, int(.98 * len(xs)))]
        return dict(n=len(xs), precision=round(100 * sum(x > 0 for x in xs) / len(xs)), mean=round(100 * st.mean(xs), 2), median=round(100 * st.median(xs), 2),
                    mean_w2=round(100 * st.mean(xw), 2), t=round(st.mean(xs) / (st.stdev(xs) / math.sqrt(len(xs))), 2) if len(xs) > 2 and st.stdev(xs) > 0 else None)
    IS = agg([e for e in ev if e["d"] < OOS]); OS = agg([e for e in ev if e["d"] >= OOS])
    if OS["n"] < 8: v = f"UNTESTED (n_oos={OS['n']})"
    elif OS["mean"] <= 0 or OS["precision"] < 52 or OS["median"] <= 0 and OS["mean_w2"] <= 0: v = "KILLED"
    elif IS.get("n", 0) >= 8 and (IS["mean"] <= 0 or IS["precision"] < 50): v = "FRAGILE (IS disagrees)"
    else: v = "KEPT"
    return dict(h=h, cost_bp=cost_bp, direction=direction, events_found=n_all, priced=priced, coverage=round(100 * priced / max(1, n_all)), IS=IS, OOS=OS, status=v, sample=ev[-5:])

# ---------- event builders ----------
def insider_clusters():
    rows = []
    for z in sorted(glob.glob(f"{E_}/f345/*.zip")):
        try: Z = zipfile.ZipFile(z)
        except Exception: continue
        sub = {r["ACCESSION_NUMBER"]: r for r in csv.DictReader(io.TextIOWrapper(Z.open("SUBMISSION.tsv"), "utf-8", "ignore"), delimiter="\t")}
        own = collections.defaultdict(set)
        for r in csv.DictReader(io.TextIOWrapper(Z.open("REPORTINGOWNER.tsv"), "utf-8", "ignore"), delimiter="\t"): own[r["ACCESSION_NUMBER"]].add(r["RPTOWNERCIK"])
        for r in csv.DictReader(io.TextIOWrapper(Z.open("NONDERIV_TRANS.tsv"), "utf-8", "ignore"), delimiter="\t"):
            if r["TRANS_CODE"] != "P" or r["TRANS_ACQUIRED_DISP_CD"] != "A": continue
            s = sub.get(r["ACCESSION_NUMBER"])
            if not s or s["DOCUMENT_TYPE"] != "4": continue
            try: v = float(r["TRANS_SHARES"] or 0) * float(r["TRANS_PRICEPERSHARE"] or 0); fd = datetime.datetime.strptime(s["FILING_DATE"], "%d-%b-%Y").date()
            except Exception: continue
            tk = (s["ISSUERTRADINGSYMBOL"] or "").strip().upper()
            if not tk or tk in ("NONE", "N/A") or v <= 0: continue
            rows.append((tk, fd, min(own[r["ACCESSION_NUMBER"]] or {"?"}), v))
    by = collections.defaultdict(list)
    for tk, fd, o, v in rows: by[tk].append((fd, o, v))
    ev = []
    for tk, L in by.items():
        L.sort(); lastev = None
        for j in range(len(L)):
            w = [x for x in L[:j + 1] if (L[j][0] - x[0]).days <= 14]
            if len({x[1] for x in w}) >= 3 and sum(x[2] for x in w) >= 100_000 and (lastev is None or (L[j][0] - lastev).days > 120):
                ev.append((tk.replace(".", "-"), L[j][0].isoformat(), round(sum(x[2] for x in w)))); lastev = L[j][0]
    return ev
def first_per_cik(forms, need_ticker=True):
    seen = {}
    for f, co, cik, d, p in idx_rows(forms):
        if cik not in seen or d < seen[cik][1]: seen[cik] = (co, d)
    return [(CT[c].replace(".", "-"), d, co) for c, (co, d) in seen.items() if (c in CT or not need_ticker)]
def thirteen_d():
    acc = collections.defaultdict(list)
    for f, co, cik, d, p in idx_rows({"SC 13D"}): acc[p].append((cik, d))
    ev = []; seen = set()
    for p, L in acc.items():
        for cik, d in L:
            if cik in CT and (cik, d[:7]) not in seen: ev.append((CT[cik].replace(".", "-"), d)); seen.add((cik, d[:7])); break
    return ev
def ipo_lockups():
    ev = []
    for t, d, co in first_per_cik({"424B4"}):
        P = px(t)
        if not P or abs((datetime.date.fromisoformat(P[0][0]) - datetime.date.fromisoformat(d)).days) > 10: continue  # first price within 10d of 424B4 = IPO
        ev.append((t, (datetime.date.fromisoformat(P[0][0]) + datetime.timedelta(days=173)).isoformat()))
    return ev
def emergences():
    H = json.load(open(f"{E_}/emergence_hits.json")); first = {}
    for h in H:
        c = h["cik"].lstrip("0")
        if c not in first or h["date"] < first[c]: first[c] = h["date"]
    out = []
    for c, d in first.items():
        if c not in CT: continue
        t = CT[c].replace(".", "-"); P = px(t)
        if not P: continue
        p0 = P[0][0]
        # new post-reorg equity only: price history must START within -30..+180 days of the first public mention (old equity that kept trading is excluded)
        if -30 <= (datetime.date.fromisoformat(p0) - datetime.date.fromisoformat(d)).days <= 180: out.append((t, max(d, p0)))
    return out
def samp(ev, k=700): return ev if len(ev) <= k else random.sample(ev, k)

def rerun(keys):
    J = json.load(open(OUT)); R = J["results"]
    if "M3" in keys:
        reorg = emergences(); J["counts"]["reorg"] = len(reorg)
        R["M3 post-reorganization equity (8-K 'emerged from chapter 11', 250d)"] = study(reorg, 250, 75)
    if "M5" in keys:
        nt = [(t, d) for t, d, co in first_per_cik({"NT 10-K"})]
        r = study(samp(nt), 120, 100, direction=-1); R["M5 NT 10-K late filers, SHORT (120d)"] = r
        # borrow-cost sensitivity: hard-to-borrow micro caps; 120 trading days ~ 0.48 yr
        r["borrow_sensitivity"] = {f"{b}%/yr": round(r["OOS"]["mean"] - b * 0.48, 2) for b in (5, 20, 50)} if r["OOS"]["n"] else {}
    json.dump(J, open(OUT, "w"), indent=1)
    for k, v in R.items(): print(k, "|", v["status"], "|", v.get("coverage"), "| IS", v.get("IS"), "| OOS", v.get("OOS"), v.get("borrow_sensitivity", ""))
def run():
    R = {}; M = {}
    ins = insider_clusters(); M["insider"] = ins
    spin = [(t, d) for t, d, co in first_per_cik({"10-12B"})]
    reorg = emergences(); d13 = thirteen_d(); nt = [(t, d) for t, d, co in first_per_cik({"NT 10-K"})]
    allt = [e[0] for e in samp(ins, 900)] + [e[0] for e in spin] + [e[0] for e in reorg] + [e[0] for e in samp(d13)] + [e[0] for e in samp(nt)] + ["IWM", "SPY"]
    prefetch(allt)
    ipo_c = first_per_cik({"424B4"}); prefetch([t for t, d, c in ipo_c]); ipo = ipo_lockups()
    ins_s = samp(ins, 900)
    R["M1 insider cluster buys (>=3 insiders, >=$100k, 14d)"] = study([(t, d) for t, d, v in ins_s], 120, 50)
    dist = []
    for t, d, v in ins_s:
        P = px(t); ks = [r[0] for r in P]; i = bisect.bisect_right(ks, d)
        if i > 126 and i < len(P) and P[i - 1][1] <= 0.6 * max(r[1] for r in P[i - 126:i]): dist.append((t, d))
    R["M1b insider clusters in distressed names (price <=60% of 6m high)"] = study(dist, 120, 75)
    R["M2 spin-offs (Form 10-12B spinco, 250d)"] = study(spin, 250, 30)
    R["M3 post-reorganization equity (8-K 'emerged from chapter 11', 250d)"] = study(reorg, 250, 75)
    R["M4 activist 13D initial filings (120d)"] = study(samp(d13), 120, 50)
    R["M5 NT 10-K late filers, SHORT (120d)"] = study(samp(nt), 120, 100, direction=-1)
    R["M6 IPO lockup expiry window, SHORT (day 173 -> +10 trading days)"] = study(samp(ipo), 10, 40, direction=-1)
    R["M7 merger-arb spread"] = dict(status="UNTESTED (data)", note="Targets delist on completion, so Yahoo drops most of them, and offer prices are not in a free structured feed. A survivorship-clean test needs CRSP-style delisting returns.")
    R["M8 earnings-revision / PEAD"] = dict(status="UNTESTED (data)", note="No free point-in-time consensus estimates. A price-reaction proxy is possible but was not run this pass.")
    R["M9 fallen angels / forced IG selling"] = dict(status="UNTESTED (data)", note="No free point-in-time rating-action history; agency press releases are not bulk-downloadable without registration.")
    json.dump(dict(asof="2026-10-23", method=__doc__, results=R, counts={k: len(v) for k, v in dict(insider=ins, spin=spin, reorg=reorg, d13=d13, nt=nt, ipo=ipo).items()}), open(OUT, "w"), indent=1)
    for k, v in R.items(): print(k, "|", v["status"], "|", v.get("coverage"), "| IS", v.get("IS"), "| OOS", v.get("OOS"))
if __name__ == "__main__":
    import sys
    rerun(sys.argv[2:]) if sys.argv[1:2] == ["rerun"] else run()
