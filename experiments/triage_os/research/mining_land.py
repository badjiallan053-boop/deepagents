"""TRIAGE Cross-Asset Radar — Mining + Land layer and Dalio-style macro regime. Public data only; reads files
written by mining_ingest.py / xasset_ingest.py. Every fact carries its source; judgement is labelled."""
import os, sys, json, csv, re, datetime, statistics as st
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
X = "/workspace/triage_os_data/xasset"; M = f"{X}/mining"; OUT = "/workspace/triage_os_data/mining.json"
R = os.path.dirname(os.path.abspath(__file__))
def series(fn, col=1):
    p = f"{X}/{fn}"
    if not os.path.exists(p): return {}
    out = {}
    for r in list(csv.reader(open(p)))[1:]:
        try: out[r[0][:10]] = float(r[col])
        except Exception: pass
    return out
def at(s, d, fwd=True):
    ks = sorted(s); 
    c = [k for k in ks if (k >= d if fwd else k <= d)]
    return (c[0] if fwd else c[-1]) if c else None
def ret(s, d0, n):
    ks = sorted(s); k0 = at(s, d0, False)
    if not k0: return None
    i = ks.index(k0); j = i + n
    return None if j >= len(ks) else s[ks[j]] / s[k0] - 1
# ---------- export-control event study (MOFCOM primary) ----------
EVENTS = [("2023-07-03", "Ga/Ge export controls (MOFCOM/GACC 2023 No.23, effective 1 Aug 2023)", "gage", "本公告自2023年8月1日起正式实施", ["REMX", "MP", "LYC.AX"]),
          ("2024-08-15", "Antimony + superhard materials (2024 No.33, effective 15 Sep 2024)", "sb", "本公告自2024年9月15日起正式实施", ["PPTA", "REMX"]),
          ("2025-04-04", "Seven medium/heavy REEs incl. Sm, Gd, Tb, Dy, Lu, Sc, Y (2025 No.18, effective on publication)", "ree18", "本公告自发布之日起正式实施", ["MP", "LYC.AX", "ARU.AX", "REMX"]),
          ("2025-10-09", "Ho, Er, Tm, Eu, Yb added (2025 No.57, effective 8 Nov 2025)", "ree57", "本公告自2025年11月8日起正式实施", ["MP", "LYC.AX", "ARU.AX", "REMX"])]
# announcements after the Shanghai close (18:00/17:00 CST) → day 0 = last close before; US names react same calendar day, AU names next day
def bench(t): return "I_AXJO" if t.endswith(".AX") else "SPY"
def events():
    rows = []
    for d, what, key, tok, tks in EVENTS:
        meta = open(f"{M}/src/mofcom_{key}.meta").read().split(); txt = open(f"{M}/src/mofcom_{key}.txt").read()
        ev = dict(date=d, what=what, url=meta[0], fetched=meta[1][:10], quote=tok, found=tok in txt, legs=[])
        d0 = d if not False else d
        for t in tks:
            s = series(f"px_{t}.csv"); b = series(f"px_{bench(t)}.csv")
            # US: event day close d is pre-announcement? MOFCOM 18:00 CST = 06:00 ET same day → US session of day d already reacts: base = prior close
            base = (datetime.date.fromisoformat(d) - datetime.timedelta(days=1)).isoformat()
            leg = dict(ticker=t, bench=bench(t).replace("I_", "^"))
            for n in (1, 5, 20):
                a, c = ret(s, base, n), ret(b, base, n)
                leg[f"x{n}"] = None if a is None or c is None else round(100 * (a - c), 1)
            ev["legs"].append(leg)
        rows.append(ev)
    allx = {n: [l[f"x{n}"] for e in rows for l in e["legs"] if l[f"x{n}"] is not None] for n in (1, 5, 20)}
    summ = {f"x{n}": dict(n=len(v), mean=round(st.mean(v), 1), median=round(st.median(v), 1), hit=round(100 * sum(1 for z in v if z > 0) / len(v))) for n, v in allx.items() if v}
    return rows, summ
# ---------- BLM claims cross-section ----------
def claims():
    j = json.load(open(f"{M}/blm_claims.json")); out = []
    for name, s in j["sites"].items():
        r = s["records"]; act = [x for x in r if x["layer"] == 1]; clo = [x for x in r if x["layer"] == 2]
        filed = sum(1 for x in act if x["CSE_DISP"] in ("Filed", "Under Review"))
        post = sum(1 for x in act if not (x.get("LEG_CSE_NR") or "").strip())
        out.append(dict(site=name, mineral=s["mineral"], ticker=s["ticker"], active=len(act), filed_pending=filed, closed=len(clo),
                        lapse_ratio=round(len(clo) / max(1, len(r)), 2), pending_share=round(filed / max(1, len(act)), 2),
                        post_mlrs_share=round(post / max(1, len(act)), 2)))
    return dict(source=j["source"], fetched=j["fetched"][:10], sites=out,
                caveat="Public MLRS layer has LOC_DT null for every record (count where LOC_DT IS NOT NULL = 0, both layers, checked 23 Oct 2026). "
                       "Dated staking surges therefore cannot be backtested from this endpoint; 'Filed/Under Review' share is used as a live proxy for fresh staking.")
# ---------- Sentinel-2 ----------
def sat():
    j = json.load(open(f"{M}/stac_s2.json")); out = []
    try:
        from PIL import Image, ImageOps, ImageDraw
        tiles = []
        for name, r in j["sites"].items():
            ims = []
            for lab in ("2024-autumn", "2026-autumn"):
                p = r[lab].get("thumb")
                im = Image.open(p).convert("RGB").resize((360, 360)) if p and os.path.exists(p) else Image.new("RGB", (360, 360), "grey")
                ImageDraw.Draw(im).text((8, 8), f"{name.split(' —')[0]} {r[lab].get('best_date')}", fill="yellow"); ims.append(im)
            row = Image.new("RGB", (720, 360)); row.paste(ims[0], (0, 0)); row.paste(ims[1], (360, 0)); tiles.append(row)
            out.append(dict(site=name, before=r["2024-autumn"]["best_id"], after=r["2026-autumn"]["best_id"], n_before=r["2024-autumn"]["n_scenes"], n_after=r["2026-autumn"]["n_scenes"]))
        mont = Image.new("RGB", (720, 360 * len(tiles)), "white")
        for i, t in enumerate(tiles): mont.paste(t, (0, 360 * i))
        mont.save(f"{M}/s2_montage.png")
    except Exception as e: out.append(dict(err=str(e)))
    return dict(source=j["source"], fetched=j["fetched"][:10], scenes=out, montage=f"{M}/s2_montage.png",
                caveat="Whole-tile previews (110 km) — demonstrates the pipeline only; pit-scale change detection needs band COGs clipped to a site polygon (next step, rasterio not installed).")
# ---------- concentration (USGS MCS 2026) ----------
CONC = [("Gallium", "Gallium       100%"), ("Antimony", "Antimony         91%       55%, CN3"), ("Rare earths", "Rare earths        67%       71%, CN3"),
        ("Germanium", "Germanium         >50%       41%, BE"), ("Tungsten", "Tungsten        >50%       26%, CN3"), ("Graphite (natural)", "Graphite (natural)")]
def conc():
    t = open(f"{X}/mcs.txt").read(); out = []
    for m, tok in CONC:
        i = t.find(tok); line = t[i:t.find("\n", i)] if i >= 0 else ""
        out.append(dict(mineral=m, quote=re.sub(r"\s{2,}", " · ", line.strip()), found=i >= 0))
    return dict(source="https://pubs.usgs.gov/periodicals/mcs2026/mcs2026.pdf", rows=out)
# ---------- macro regime ----------
def last(s): k = max(s); return k, s[k]
def chg(s, days):
    k, v = last(s); d0 = (datetime.date.fromisoformat(k) - datetime.timedelta(days=days)).isoformat(); k0 = at(s, d0, False)
    return v - s[k0] if k0 else None
def pctl(s, v, yrs=20):
    k = max(s); lo = (datetime.date.fromisoformat(k) - datetime.timedelta(days=365 * yrs)).isoformat()
    xs = [x for d, x in s.items() if d >= lo]; return round(100 * sum(1 for x in xs if x <= v) / len(xs))
def cofer():
    x = open(f"{M}/cofer.xml").read(); res = {}
    for a, b in re.findall(r"<Series ([^>]*)>(.*?)</Series>", x, re.S):
        if 'TYPE_OF_TRANSFORMATION="SHRO_PT"' in a and 'FREQUENCY="Q"' in a:
            cur = re.search(r'FXR_CURRENCY="([^"]+)"', a).group(1)
            v = sorted(re.findall(r'TIME_PERIOD="([^"]+)" OBS_VALUE="([^"]+)"', b), key=lambda z: z[0])
            if v and (cur not in res or v[-1][0] > res[cur][-1][0]) and 'COUNTRY="G001"' in a: res[cur] = v
    return res
def regime():
    D = []
    r = series("fred_DFII10.csv"); k, v = last(r)
    D.append(dict(pillar="Real rates", metric="US 10y TIPS real yield", value=f"{v:.2f}% ({k})", change=f"{chg(r,365):+.2f}pp y/y", pctile=pctl(r, v), read="Restrictive" if v > 1.5 else "Neutral/easy", src="FRED DFII10"))
    h = series("fred_BAMLH0A0HYM2.csv"); k, v = last(h)
    D.append(dict(pillar="Debt cycle (credit)", metric="US HY OAS", value=f"{v:.2f}% ({k})", change=f"{chg(h,365):+.2f}pp y/y", pctile=pctl(h, v), read="Late-cycle complacency" if pctl(h, v) < 20 else "Stress building" if pctl(h, v) > 60 else "Mid", src="FRED BAMLH0A0HYM2"))
    c = series("fred_T10Y2Y.csv"); k, v = last(c)
    D.append(dict(pillar="Debt cycle (curve)", metric="UST 10y–2y", value=f"{v:.2f}pp ({k})", change=f"{chg(c,365):+.2f}pp y/y", pctile=pctl(c, v), read="Re-steepening after inversion" if v > 0 and chg(c, 730) and chg(c, 730) > 0 else "Flat/inverted", src="FRED T10Y2Y"))
    g = series("px_GC_F.csv"); dx = series("px_DX-Y.NYB.csv"); k, v = last(g); kd, vd = last(dx)
    g1 = v / g[at(g, (datetime.date.fromisoformat(k) - datetime.timedelta(days=365)).isoformat(), False)] - 1
    d1 = vd / dx[at(dx, (datetime.date.fromisoformat(kd) - datetime.timedelta(days=365)).isoformat(), False)] - 1
    D.append(dict(pillar="Currency debasement", metric="Gold $/oz vs DXY, 1y", value=f"gold {v:,.0f} ({k}); DXY {vd:.1f}", change=f"gold {100*g1:+.0f}% / DXY {100*d1:+.0f}%", pctile=pctl(g, v), read="Debasement bid" if g1 > 0.15 else "Neutral", src="Yahoo GC=F, DX-Y.NYB"))
    cf = cofer(); u = cf.get("CI_USD", [])
    if u:
        q, val = u[-1]; q0, v0 = u[-9] if len(u) > 8 else u[0]
        D.append(dict(pillar="Reserve-currency share", metric="USD share of FX reserves (IMF COFER, all reserves, post-2025Q3 method)", value=f"{float(val):.1f}% ({q})", change=f"{float(val)-float(v0):+.1f}pp vs {q0}", pctile=None, read="Slow erosion" if float(val) < float(v0) else "Stable", src="IMF COFER SDMX api.imf.org"))
    D.append(dict(pillar="Central-bank gold buying", metric="WGC Gold Demand Trends (central banks, tonnes)", value="not ingested", change="", pctile=None, read="GAP", src="WGC requires site download (Goldhub); not fetched this pass"))
    sp = series("px_I_GSPC.csv"); bas = {}
    for d in sp:
        try:
            if min(g[d], series_cache["HG"][d], series_cache["CL"][d]) <= 0: continue
            bas[d] = (g[d] * series_cache["HG"][d] * series_cache["CL"][d]) ** (1 / 3) / sp[d]
        except Exception: pass
    if bas:
        k, v = last(bas); D.append(dict(pillar="Commodity super-cycle", metric="Geo-mean(gold, copper, WTI) / S&P 500", value=f"{v:.3f} ({k})", change="", pctile=pctl(bas, v, 25), read="Commodities cheap vs equities" if pctl(bas, v, 25) < 25 else "Mid-cycle" if pctl(bas, v, 25) < 75 else "Commodities rich", src="Yahoo GC=F, HG=F, CL=F, ^GSPC"))
    D.append(dict(pillar="Supply concentration", metric="China share, controlled minerals (USGS MCS 2026)", value="see table", change="", pctile=None, read="Extreme (Ga, graphite, REE, W)", src="USGS MCS 2026"))
    return D
series_cache = {"HG": series("px_HG_F.csv"), "CL": series("px_CL_F.csv")}
def build():
    ev, summ = events(); J = dict(asof="2026-10-23", events=ev, event_summary=summ, claims=claims(), sat=sat(), concentration=conc(), regime=regime(),
        cofer_usd=cofer().get("CI_USD", [])[-12:],
        gaps=["USGS MRDS/USMIN/NGDB bulk download: mrdata.usgs.gov returns 403 to the box (curl, 23 Oct) → deposit join uses hand-placed district centres (labelled).",
              "Geoscience Australia services.ga.gov.au 403; WA DMIRS/QLD, Ontario MLAS, BC MTO, GESTIM, BGS, EGDI, GEUS, Chile/Peru/DRC cadastres: not ingested this pass.",
              "BLM MLRS public layer has no location dates → staking-surge backtest impossible from it; needs MLRS bulk reports (reports.blm.gov) or county recorder data.",
              "NASA FIRMS needs a free MAP_KEY (registration = account creation, not done); VIIRS night lights not ingested.",
              "WGC central-bank gold: not fetched. SEDAR+/ASX owner mapping: not done.",
              "Internet Archive: search works (leads saved) but no deposit has been matched to a lapsed claim yet."],
        archive=json.load(open(f"{M}/archive_leads.json")))
    json.dump(J, open(OUT, "w"), indent=1, ensure_ascii=False); return J
def md(J):
    L = ["# TRIAGE Cross-Asset Radar — Mining + Land layer and macro regime", "",
         "_As of 23 Oct 2026 (SGT). Public data only. Facts carry source + fetch date; **JUDGEMENT** marks our reads. Nothing sent._", "",
         "## What this layer does", "",
         "Joins (1) export-control events from MOFCOM primary text, (2) US federal mining-claim status around documented deposits of controlled minerals (BLM MLRS), (3) Sentinel-2 scene coverage at three sites (Earth Search STAC), (4) supply concentration (USGS MCS 2026) and (5) a Dalio-style macro regime. The target signal — *staking surge or lapse near a historically documented controlled-mineral deposit* — is only partly testable today; we say exactly where.", "",
         "## Backtest: junior/REE equities after Chinese export-control announcements", "",
         "Excess return vs SPY (US) or ^AXJO (ASX), base = close before the announcement date. MOFCOM announcements land 17:00–18:00 Beijing, i.e. before the US open the same day.", "",
         "| Event (MOFCOM, primary) | Ticker | +1d | +5d | +20d |", "|---|---|---|---|---|"]
    for e in J["events"]:
        for l in e["legs"]:
            f = lambda z: "n/a" if z is None else f"{z:+.1f}%"
            L.append(f"| {e['date']} {e['what'][:48]} | {l['ticker']} | {f(l['x1'])} | {f(l['x5'])} | {f(l['x20'])} |")
    s = J["event_summary"]
    L += ["", "| Horizon | legs | mean excess | median | % positive |", "|---|---|---|---|---|"] + [f"| {k[1:]}d | {v['n']} | {v['mean']:+.1f}% | {v['median']:+.1f}% | {v['hit']}% |" for k, v in s.items()]
    L += ["", "**Honest read (JUDGEMENT):** four events, overlapping tickers — this is an event study, not a statistically powered backtest. Legs are not independent (same day, same theme). The April 2025 event coincides with the US tariff sell-off, which the market adjustment only partly removes. Use as a playbook with a known small-n, not a proven edge.", "",
         "Event sources (fetched 23 Oct 2026, quote = effective-date clause):", ""]
    L += [f"- {e['date']}: {e['url']} — “{e['quote']}” ({'found' if e['found'] else 'NOT FOUND'})" for e in J["events"]]
    c = J["claims"]
    L += ["", "## Claims around controlled-mineral deposits (BLM MLRS, fetched " + c["fetched"] + ")", "", "Box = ±0.15° around a district centre (JUDGEMENT: hand-placed, MRDS blocked).", "",
          "| District | Mineral | Active | Filed/under review | Closed | Lapse ratio |", "|---|---|---|---|---|---|"]
    L += [f"| {x['site']} | {x['mineral']} | {x['active']:,} | {x['filed_pending']:,} ({100*x['pending_share']:.0f}%) | {x['closed']:,} | {x['lapse_ratio']} |" for x in c["sites"]]
    L += ["", f"Caveat: {c['caveat']}", "", "**Read (JUDGEMENT):** Mountain Pass (42% of active claims still pending) and Stibnite (21%) show the heaviest fresh staking; Thacker Pass has ~0.4% pending against 8,136 closed claims — a lapse-dominated district. That fits the playbook (follow-on staking near a permitted controlled-mineral project) but is cross-sectional, not timed.", "",
          "## Satellite: Sentinel-2 L2A scenes (Earth Search STAC)", "", "| Site | Before (best ≤10% cloud) | After | scenes before/after |", "|---|---|---|---|"]
    L += [f"| {x['site']} | {x.get('before')} | {x.get('after')} | {x.get('n_before')}/{x.get('n_after')} |" for x in J["sat"]["scenes"]]
    L += ["", f"Caveat: {J['sat']['caveat']}", "", "## Supply concentration (USGS MCS 2026, net import reliance / top import source)", "", "| Mineral | Quoted line |", "|---|---|"]
    L += [f"| {x['mineral']} | {x['quote'][:110]} |" for x in J["concentration"]["rows"]]
    L += ["", "Source: " + J["concentration"]["source"], "", "## Macro regime dashboard (Dalio-style)", "", "| Pillar | Metric | Latest | Change | 20y pctile | Read (JUDGEMENT) | Source |", "|---|---|---|---|---|---|---|"]
    L += [f"| {d['pillar']} | {d['metric']} | {d['value']} | {d['change']} | {d['pctile'] if d['pctile'] is not None else '—'} | {d['read']} | {d['src']} |" for d in J["regime"]]
    L += ["", "## Gaps (honest)", ""] + [f"- {g}" for g in J["gaps"]]
    L += ["", "## Who pays for this layer (JUDGEMENT)", "", "- Resource/royalty funds and critical-minerals desks (event playbook + claim-pressure map).", "- Government/strategic buyers and DFIs tracking Western supply response.", "- Credit desks holding miner/battery-chain paper: export-control shock → forced-seller map in the TRIAGE credit layer."]
    return "\n".join(L)
if __name__ == "__main__":
    J = build(); m = md(J)
    cm = f"{R}/committee.md"
    if os.path.exists(cm): m += "\n" + open(cm).read()
    open(f"{R}/cross_asset_mining.md", "w").write(m)
    from design import report_from_markdown
    report_from_markdown(m, "TRIAGE Cross-Asset Radar", "Mining + Land · Macro regime · 23 Oct 2026", "Export controls, claims, satellites and the regime — public data, sourced, honest about gaps",
        [("Layers", "Mining + Land, Macro, Alpha Committee"), ("Data", "MOFCOM · BLM MLRS · Earth Search · USGS MCS · IMF COFER · FRED"), ("Rules", "public data · nothing sent")],
        f"{R}/TRIAGE_Cross_Asset_Radar.html", f"{R}/TRIAGE_Cross_Asset_Radar.pdf")
    print(json.dumps(J["event_summary"]), [ (d['pillar'], d['value'], d['read']) for d in J['regime']])
