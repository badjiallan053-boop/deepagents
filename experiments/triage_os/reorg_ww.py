"""M3 expanded: post-reorganisation equity, US (EDGAR) + curated non-US, 2010-2026.
Dating (point-in-time):
  confirmation = first 8-K with Item 1.03 whose text matches 'confirmation order' (filed <=4 business days after the court order; the docket itself was NOT queried)
  effective    = first 8-K on/after confirmation with Item 5.01/3.03/2.01 or the phrase 'the Effective Date occurred'
  first trade  = first Yahoo close of the ticker; accepted as NEW equity only if it starts within -30..+180 days of the effective (or confirmation) date
Survivorship: CIKs whose new equity was registered (Form 8-A12B/12G within 120 days of the effective date) but which have no current ticker or no Yahoo prices
are logged as MISSING and tested two ways: excluded, and as -100%.
Windows 20/60/120/250 trading days from the first trade, and from day 5. Excess vs local small-cap ETF, 100bp round trip. IS < 2021 <= OOS.
Non-US events are curated (labelled JUDGEMENT: dates from public restructuring completion; first trade from Yahoo) and need primary verification.
"""
import json, os, re, glob, datetime, statistics as st, math, collections, subprocess, time, bisect
import edge_lab as L, bnf_cis as BC
E_ = "/workspace/triage_os_data/edge"; OUT = "/workspace/triage_os_data/reorg_ww.json"; OOS = "2021-01-01"; UA = "TRIAGE research badjiallan053@gmail.com"
NONUS = [  # ticker, country, completion date (judgement), note, bench
 ("VIRI.PA", "FR", "2018-02-21", "CGG sauvegarde: debt-for-equity, rights issue backstopped", "EWQ"),
 ("VK.PA", "FR", "2021-06-30", "Vallourec: creditors took majority, rights issue backstopped", "EWQ"),
 ("CO.PA", "FR", "2024-03-27", "Casino: Kretinsky consortium + creditors, accelerated sauvegarde", "EWQ"),
 ("ATO.PA", "FR", "2024-12-18", "Atos: accelerated sauvegarde, massive debt-for-equity", "EWQ"),
 ("EMEIS.PA", "FR", "2024-03-25", "Orpea/emeis: accelerated sauvegarde, CDC consortium + creditors", "EWQ"),
 ("VANTI.PA", "FR", "2020-09-22", "Technicolor (now Vantiva): sauvegarde financière accélérée", "EWQ"),
 ("NAS.OL", "NO", "2021-05-26", "Norwegian Air: Irish examinership + Norwegian reconstruction, debt-for-equity", "NORW"),
 ("9201.T", "JP", "2012-09-19", "Japan Airlines: corporate rehabilitation 2010, relisted", "EWJ"),
 ("GIAA.JK", "ID", "2022-12-30", "Garuda Indonesia: PKPU homologation, debt-for-equity", "EIDO"),
 ("1918.HK", "HK", "2023-12-28", "Sunac: offshore scheme, debt-for-equity and convertibles", "2800.HK"),
 ("SDRL", "NO/US", "2022-02-24", "Seadrill: Ch11 emergence, relisted OSE/NYSE", "IWM"),
]
def hits():
    H = json.load(open(f"{E_}/reorg_hits.json")); by = collections.defaultdict(list)
    for h in H: by[h["cik"]].append(h)
    return by
def registrations():
    R = collections.defaultdict(list)
    for f, co, cik, d, p in L.idx_rows({"8-A12B", "8-A12G"}): R[cik.lstrip("0")].append(d)
    return R
def build():
    by = hits(); REG = registrations(); ev = []; missing = []; old_eq = 0; nodate = 0
    for cik, H in by.items():
        H.sort(key=lambda h: h["date"])
        conf = next((h for h in H if "1.03" in (h["items"] or []) and "confirmation order" in h["q"]), None)
        anchor = conf["date"] if conf else None
        eff = next((h for h in H if (anchor is None or h["date"] >= anchor) and (set(h["items"] or []) & {"5.01", "3.03", "2.01"} or "Effective Date occurred" in h["q"])), None)
        if not conf and not eff: nodate += 1; continue
        ed = (eff or conf)["date"]; t = L.CT.get(cik)
        regd = [d for d in REG.get(cik, []) if 0 <= (datetime.date.fromisoformat(d) - datetime.date.fromisoformat(ed)).days <= 120 or -30 <= (datetime.date.fromisoformat(d) - datetime.date.fromisoformat(ed)).days < 0]
        P = BC.pxv(t.replace(".", "-")) if t else []
        if not P:
            if regd: missing.append(dict(cik=cik, name=H[0]["name"], eff=ed, reason="no current ticker" if not t else "no Yahoo prices"))
            continue
        gap = (datetime.date.fromisoformat(P[0][0]) - datetime.date.fromisoformat(ed)).days
        if not -30 <= gap <= 180: old_eq += 1; continue
        ev.append(dict(t=t.replace(".", "-"), country="US", conf=conf["date"] if conf else None, eff=eff["date"] if eff else None, first=P[0][0], adsh=(eff or conf)["adsh"], cik=cik, bench="IWM", name=H[0]["name"]))
    for t, c, d, note, b in NONUS:
        P = BC.pxv(t)
        if not P: missing.append(dict(cik=None, name=t, eff=d, reason="no Yahoo prices")); continue
        i = bisect.bisect_left([r[0] for r in P], d)
        if i < len(P): ev.append(dict(t=t, country=c, conf=None, eff=d, first=P[i][0], note=note, bench=b, curated=True))
    return ev, missing, dict(ciks=len(by), no_date=nodate, old_equity_continued=old_eq)
def enrich(ev):
    for e in ev:
        if e.get("curated") or not e.get("adsh"): continue
        p = f"{E_}/f4cache/reorg_{e['adsh']}.txt"
        if not os.path.exists(p):
            t = subprocess.run(["curl", "-s", "-m", "40", "-A", UA, f"https://www.sec.gov/Archives/edgar/data/{e['cik']}/{e['adsh']}.txt"], capture_output=True, text=True).stdout
            open(p, "w").write(t); time.sleep(0.15)
        x = re.sub(r"<[^>]+>", " ", open(p, errors="ignore").read())
        e["backstop"] = bool(re.search(r"backstop", x, re.I))
        m = re.findall(r"(\d{2,3}(?:\.\d+)?)\s*%\s+of the\s+(?:issued and outstanding\s+)?(?:shares of\s+)?New (?:Common Stock|Equity|Shares)", x, re.I)
        vals = [float(v) for v in m if 0 < float(v) <= 100]
        e["creditor_pct"] = max(vals) if vals else None
def insider_after(ev):
    import zipfile, io, csv
    want = {e["t"].replace("-", ".").upper(): e for e in ev if e["country"] == "US"}; hit = collections.defaultdict(set)
    for z in sorted(glob.glob(f"{E_}/f345/*.zip")):
        try: Z = zipfile.ZipFile(z)
        except Exception: continue
        sub = {}
        for r in csv.DictReader(io.TextIOWrapper(Z.open("SUBMISSION.tsv"), "utf-8", "ignore"), delimiter="\t"):
            tk = (r["ISSUERTRADINGSYMBOL"] or "").strip().upper()
            if tk in want: sub[r["ACCESSION_NUMBER"]] = (tk, r["FILING_DATE"])
        if not sub: continue
        for r in csv.DictReader(io.TextIOWrapper(Z.open("NONDERIV_TRANS.tsv"), "utf-8", "ignore"), delimiter="\t"):
            if r["ACCESSION_NUMBER"] in sub and r["TRANS_CODE"] == "P":
                tk, fd = sub[r["ACCESSION_NUMBER"]]
                try: fd = datetime.datetime.strptime(fd, "%d-%b-%Y").date().isoformat()
                except Exception: continue
                e = want[tk]
                if 0 <= (datetime.date.fromisoformat(fd) - datetime.date.fromisoformat(e["first"])).days <= 90: hit[tk].add(fd)
    for tk, e in want.items(): e["insider_buy_90d"] = sorted(hit.get(tk, []))[:1] or None
def ret(e, start, h):
    P = BC.pxv(e["t"]); B = {r[0]: r[1] for r in BC.pxv(e["bench"])}
    if len(P) <= start + h: return None
    b0, b1 = B.get(P[start][0]), B.get(P[start + h][0])
    if not b0 or not b1 or P[start][1] <= 0: return None
    return (P[start + h][1] / P[start][1] - 1) - (b1 / b0 - 1) - 0.01
def test(evs, start, h, missing_as=None, nmiss=0):
    xs = [(e["first"], ret(e, start, h)) for e in evs]; xs = [(d, x) for d, x in xs if x is not None]
    if missing_as is not None: xs += [("2021-06-30" if i % 2 else "2015-06-30", missing_as) for i in range(nmiss)]  # spread missing names across IS/OOS evenly (dates unknown for some)
    IS = BC.agg([x for d, x in xs if d < OOS]); OS = BC.agg([x for d, x in xs if d >= OOS])
    return dict(start=start, h=h, IS=IS, OOS=OS, status=BC.verdict(IS, OS))
def run():
    ev, missing, stats = build()
    for b in {e["bench"] for e in ev}: BC.pxv(b)
    enrich(ev); insider_after(ev)
    for e in ev:
        P = BC.pxv(e["t"]); e["r20"] = (P[20][1] / P[0][1] - 1) if len(P) > 20 else None
        e["adv20_usd"] = round(st.mean(r[1] * r[2] for r in P[:20])) if len(P) > 20 else None
    R = {}
    for s in (0, 5):
        for h in (20, 60, 120, 250): R[f"ALL from day {s}, {h}d"] = test(ev, s, h)
    reg = collections.Counter(e["country"] for e in ev)
    R["US only, day 5, 250d"] = test([e for e in ev if e["country"] == "US"], 5, 250)
    R["Non-US (curated), day 5, 250d"] = test([e for e in ev if e["country"] != "US"], 5, 250)
    med = st.median([e["adv20_usd"] for e in ev if e["adv20_usd"]] or [0])
    R["Small (first-20d $ volume below median), day 5, 250d"] = test([e for e in ev if (e["adv20_usd"] or 0) < med], 5, 250)
    R["Large (above median), day 5, 250d"] = test([e for e in ev if (e["adv20_usd"] or 0) >= med], 5, 250)
    R["Creditor ownership >50% (8-K text), day 5, 250d"] = test([e for e in ev if (e.get("creditor_pct") or 0) > 50], 5, 250)
    R["Backstop mentioned, day 5, 250d"] = test([e for e in ev if e.get("backstop")], 5, 250)
    R["No backstop mentioned, day 5, 250d"] = test([e for e in ev if e.get("backstop") is False], 5, 250)
    R["SUB insider open-market buy within 90d of first trade, entry day 90 -> 250d"] = test([e for e in ev if e.get("insider_buy_90d")], 90, 160)
    R["SUB no insider buy, entry day 90 -> 250d"] = test([e for e in ev if e["country"] == "US" and not e.get("insider_buy_90d")], 90, 160)
    R["SUB orphan dump: first 20d excess return < -20%, entry day 20 -> 250d"] = test([e for e in ev if e["r20"] is not None and e["r20"] < -0.2], 20, 230)
    R["SUB no early dump, entry day 20 -> 250d"] = test([e for e in ev if e["r20"] is not None and e["r20"] >= -0.2], 20, 230)
    S = dict(excluded=R["ALL from day 5, 250d"], missing_as_minus100=test(ev, 5, 250, -1.0, len(missing)))
    J = dict(asof="2026-10-23", method=__doc__, counts=dict(events=len(ev), by_region=dict(reg), missing=len(missing), **stats), results=R, survivorship=S, events=ev, missing=missing)
    json.dump(J, open(OUT, "w"), indent=1, default=str)
    print(J["counts"]); [print(k, "|", v["status"], "| IS", v["IS"], "| OOS", v["OOS"]) for k, v in R.items()]
    print("SURV -100%:", S["missing_as_minus100"]["status"], S["missing_as_minus100"]["OOS"])
if __name__ == "__main__": run()
