"""TRIAGE Bottleneck Hunt: small listed companies sitting inside supply chokepoints, scored, base-rated and logged as paper WATCH calls.
Research only. Not investment advice. Asymmetric setups, not promises: nothing here claims 100x.
Prices/market caps: Yahoo Finance public quote + chart endpoints (anonymous session crumb), fetched with curl.
"""
import json, os, sys, subprocess, datetime, statistics as st, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
D = "/workspace/triage_os_data/bottleneck"; os.makedirs(D, exist_ok=True); ASOF = "2026-10-23"
CK = f"{D}/yc.txt"
def sh(*a): return subprocess.run(list(a), capture_output=True, text=True, timeout=90).stdout
def crumb():
    sh("curl", "-s", "-c", CK, "-A", "Mozilla/5.0", "https://fc.yahoo.com"); return sh("curl", "-s", "-b", CK, "-A", "Mozilla/5.0", "https://query1.finance.yahoo.com/v1/test/getcrumb").strip()
def quotes(syms):
    c = crumb(); out = {}
    for i in range(0, len(syms), 40):
        j = json.loads(sh("curl", "-s", "-b", CK, "-A", "Mozilla/5.0", f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={','.join(syms[i:i+40])}&crumb={c}"))
        for q in j["quoteResponse"]["result"]: out[q["symbol"]] = q
    return out
def hist(t):
    p = f"{D}/px_{t}.json"
    if os.path.exists(p): return json.load(open(p))
    try:
        r = json.loads(sh("curl", "-s", "-m", "60", "-A", "Mozilla/5.0", f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=5y&interval=1d"))["chart"]["result"][0]
        rows = [(datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date().isoformat(), c) for ts, c in zip(r["timestamp"], r["indicators"]["adjclose"][0]["adjclose"]) if c]
    except Exception: rows = []
    json.dump(rows, open(p, "w")); return rows

MOF = "https://www.mofcom.gov.cn/zcfb/blgg/gg/2025/art/2025/art_bc4513421bb24faaa84e44c2e4f36dc5.html"
# grade: A = government/regulatory primary document read this pass; B = company primary disclosure read this pass; C = company claim, not re-read this pass
C = [
 dict(t="UAMY", name="United States Antimony", choke="Antimony (defence: primers, munitions; flame retardants)", chain="US DoD National Defense Stockpile → antimony metal ingots → USAC, operator of North America's only two antimony smelters",
      ev=["https://www.sec.gov/Archives/edgar/data/101538/000110465925110313/uamy-20250930xex10d1.htm", "https://www.sec.gov/Archives/edgar/data/101538/000165495425011011/uamy_8k.htm", MOF],
      fact="DLA sole-source 5-yr IDIQ SP8000-25-D-0007, max $245m (no obligation beyond $5k minimum); first delivery order ~$10m (315,000 lb). China's US antimony ban (MOFCOM Ann. 46/2024 Art. 2) is suspended only until 27 Nov 2026 (Ann. 72/2025).",
      cat=("2026-11-27", "MOFCOM suspension of the US-specific antimony/gallium/germanium ban expires unless renewed"), share=4, sens=4, grade="A",
      risks="IDIQ max is not revenue; feed-ore sourcing (Mexico/Bolivia); China renews the suspension → price normalises", kill="MOFCOM renews the suspension AND antimony price (Rotterdam) falls >30% from 23 Oct 2026; or no second DLA delivery order by 30 Jun 2027"),
 dict(t="LRV.AX", name="Larvotto Resources", choke="Antimony concentrate (non-China mine supply)", chain="Western antimony smelters/trader Wogen → Sb concentrate → Hillgrove (NSW), production started Aug 2026",
      ev=["https://www.larvottoresources.com/wp-content/uploads/2026/08/61341464.pdf", "https://www.larvottoresources.com/wp-content/uploads/2026/10/61349174.pdf", "https://www.larvottoresources.com/wp-content/uploads/2024/12/61241120.pdf"],
      fact="Production commenced Aug 2026; first concentrate shipped Oct 2026; Wogen exclusive offtake for 7 years with US$4m prepayment.", cat=("2026-11-27", "MOFCOM suspension expiry; first quarterly production report (Jan 2027)"), share=3, sens=5, grade="B",
      risks="ramp-up recoveries; single offtaker sets terms; antimony price mean-reversion", kill="Quarterly report shows concentrate output <50% of nameplate two quarters running"),
 dict(t="TUN.L", name="Tungsten West", choke="Tungsten (APT for tooling, armour, munitions)", chain="EU/UK tungsten processors → WO3 concentrate → Hemerdon (Devon), one of the few large Western tungsten deposits",
      ev=["https://www.nationalwealthfund.org.uk/news-and-publications/news/national-wealth-fund-backs-tungsten-west-to-unlock-critical-uk-tungsten-supply/", "https://www.investormeetcompany.com/companies/tungsten-west-plc/rns/4876733/view"],
      fact="UK National Wealth Fund £71m package (£36m equity, £25m loan, £10m accordion); processing started Sep 2026; full production targeted Q1 2027.", cat=("2027-03-31", "Hemerdon full commissioning target (Q1 2027)"), share=3, sens=4, grade="A",
      risks="Hemerdon failed once before (Wolf Minerals, 2018) on recoveries and noise permits; NWF holds heavy equity → dilution overhang", kill="Commissioning slips past Q2 2027 or recoveries below plan in two consecutive updates"),
 dict(t="GMET.L", name="Guardian Metal Resources", choke="Tungsten (US domestic mine supply)", chain="US DoD (DPA Title III) → WO3 → Pilot Mountain, Nevada",
      ev=["https://www.war.gov/News/Releases/Release/Article/4252264/department-of-defense-awards-62-million-to-sustain-critical-production-of-tungs/", "https://www.sec.gov/Archives/edgar/data/2039972/000165495426006317/a2026-0630_pfsresultsfina.htm"],
      fact="DoD DPA Title III $6.2m award (Jul 2025); PFS June 2026: 8-year mine, 15,916 t WO3, first production targeted late 2028 subject to permitting.", cat=("2026-11-27", "MOFCOM step; Pilot Mountain permitting milestones 2027"), share=2, sens=5, grade="A",
      risks="pre-production, 2028 at earliest; financing dilution; permitting", kill="Permitting timeline slips beyond 2029 or equity raise below 50% of 23 Oct 2026 price"),
 dict(t="UCU.V", name="Ucore Rare Metals", choke="Rare-earth separation (Dy/Tb/Sm outside China)", chain="US DoD magnet supply chain → separated REE oxides → RapidSX plant, Alexandria, Louisiana",
      ev=["https://ucore.com/ucore-executes-us18-4m-award-with-u-s-dod-for-rare-earth-processing/", "https://ucore.com/FinancialStatements/Ucore_MDA_Q2_2025.pdf"],
      fact="DoD OT Agreement total US$22.4m (non-repayable); target 'Early Production' readiness in Louisiana in H2 2026; DPAS DO-B8 rating.", cat=("2026-12-31", "H2-2026 Early Production readiness deadline in Louisiana"), share=3, sens=5, grade="B",
      risks="RapidSX unproven at commercial scale; feedstock sourcing; deadline slip", kill="No early-production announcement by 31 Mar 2027"),
 dict(t="ARA.TO", name="Aclara Resources", choke="Heavy rare earths (Dy/Tb) from ionic clays, US separation", chain="Magnet makers → Dy/Tb oxide → Project Dynamo, Vinton LA ($494m) fed by Chile/Brazil clays",
      ev=["https://www.opportunitylouisiana.gov/news/aclara-completes-basic-engineering-for-its-u-s-heavy-rare-earths-separation-facility-in-louisiana", "https://www.enr.com/articles/63926-494m-rare-earth-processing-plant-in-louisiana-advances-toward-construction"],
      fact="Basic engineering complete; ~200 t/yr Dy oxide and 35 t/yr Tb oxide planned; Dy/Tb spec results from the Virginia Tech pilot expected Q4 2026; construction to H2 2028.", cat=("2026-12-31", "Q4-2026 Dy/Tb pilot specification results"), share=3, sens=4, grade="A",
      risks="$494m capex vs ~C$645m cap → large financing; Chile permitting history", kill="Pilot misses Dy/Tb spec or the Q1-2027 site prep slips"),
 dict(t="NB", name="NioCorp Developments", choke="Scandium (Al-Sc alloys; China-controlled since Apr 2025) + niobium", chain="Defence prime (Al-Sc aerospace alloys) → scandium oxide → Elk Creek, Nebraska",
      ev=["https://www.war.gov/News/Releases/Release/Article/4264389/department-of-defense-awards-10-million-to-develop-a-domestic-mine-to-master-al/", "https://niocorp.com/u-s-department-of-defense-awards-up-to-10-million-to-niocorps-subsidiary-elk-creek-resources-corp/"],
      fact="DoD DPA Title III up to $10m (Aug 2025); pursuing up to $800m EXIM debt (not committed).", cat=("2027-06-30", "EXIM final commitment decision (judgement: H1 2027)"), share=3, sens=5, grade="A",
      risks="~$1bn+ capex; financing not committed; history of delays and dilution", kill="EXIM declines or no final commitment by end-2027"),
 dict(t="GPH.V", name="Graphite One", choke="Natural graphite + anode material (China export controls since Dec 2023)", chain="US battery and defence users → anode active material → Graphite Creek (Alaska) + Ohio anode plant",
      ev=["https://www.defense.gov/News/Releases/Release/Article/3459556/dod-enters-agreement-to-expand-capabilities-for-domestic-graphite-mining-and-pr/", "https://www.graphiteoneinc.com/exim-bank-increases-letters-of-interest-for-the-graphite-one-supply-chain-to-2-07-billion/"],
      fact="DoD DPA Title III $37.5m (Jul 2023); EXIM non-binding LoIs total $2.07bn; formal application expected 2026.", cat=("2026-11-27", "MOFCOM graphite end-use review suspension expiry; EXIM application 2026"), share=2, sens=5, grade="A",
      risks="LoIs non-binding; Arctic mine capex; EV demand", kill="No EXIM application filed by 30 Jun 2027"),
 dict(t="LPTH", name="LightPath Technologies", choke="Germanium-free infrared optics (BlackDiamond chalcogenide glass)", chain="US DoW EO/IR & counter-UAS systems → IR lenses → BlackDiamond (licensed from the US Naval Research Lab)",
      ev=["https://finance.yahoo.com/technology/articles/lightpath-technologies-wins-department-war-123100543.html", "https://www.newswire.com/news/lightpath-technologies-receives-additional-6-3-million-follow-on-optical"],
      fact="Funded DoW CLEAR prototype agreement (Sep 2026); 2026 NDAA adds germanium to covered-material restrictions with a Dec 2027 sourcing deadline; >$19m orders from one C-UAS customer since 1 Jul 2026.", cat=("2027-12-31", "NDAA germanium sourcing restriction takes effect (Dec 2027)"), share=3, sens=4, grade="B",
      risks="customer concentration; already re-rated; CLEAR value undisclosed", kill="No production follow-on from CLEAR by end-2027"),
 dict(t="6855.T", name="Japan Electronic Materials", choke="Probe cards for DRAM/HBM wafer test", chain="Micron (HBM/DRAM) → memory probe cards → JEM (Micron entities ~31% of FY3/26 sales)",
      ev=["https://www.jem-net.co.jp/images/top/pdf/2026/260624_yukashokenhokokusho.pdf", "https://edinetdb.jp/company/E02043/main-customers"],
      fact="Annual securities report FY3/26: Micron Memory Japan ¥4.567bn (15.6%) and Micron Memory Taiwan ¥4.495bn (15.3%) of sales.", cat=("2026-11-10", "1H FY3/27 results (judgement: early Nov, check TDnet calendar)"), share=2, sens=4, grade="B",
      risks="FormFactor/MJC competition; memory cycle; Micron dependence", kill="Micron share of sales falls below 20% or 1H order book declines y/y"),
 dict(t="4369.T", name="Tri Chemical Laboratories", choke="Hafnium high-k ALD precursors for DRAM", chain="SK hynix (~80% of Hf precursor via SK Tri Chem JV) and Samsung (~20% since 2025) → high-k precursor → Tri Chemical",
      ev=["https://www.thelec.net/news/articleView.html?idxno=12207", "https://www.trichemical.com/english/ir/pdf/2025031402.pdf"],
      fact="High-k revenue ¥9.42bn (FY1/25); SK hynix diversifying Hf precursor suppliers (The Elec, trade press, not primary).", cat=("2026-12-12", "Q3 FY1/27 results (judgement: mid-Dec)"), share=4, sens=3, grade="C",
      risks="SK hynix dual-sourcing erodes share; customer split not disclosed by the company", kill="SK hynix share for SK Tri Chem reported below 60%"),
 dict(t="PLSR.V", name="Pulsar Helium", choke="Helium (US federal reserve sold; Qatar/Russia concentration)", chain="Semiconductor fabs / MRI / space → liquid helium → Topaz, Minnesota (high-grade primary helium)",
      ev=["https://pulsarhelium.com/wp-content/uploads/2026/10/PLSRNR2026-70_Chart-RNS.pdf", "https://pulsarhelium.com/projects/topaz/"],
      fact="Accepted Chart Industries $85.5m firm proposal for a helium liquefaction plant (Oct 2026); first production targeted Q4 2027; no helium sales agreement disclosed.", cat=("2027-06-30", "Up to six more wells Q1–Q2 2027"), share=2, sens=5, grade="B",
      risks="no offtake yet; $85.5m plant vs ~C$267m cap → dilution; helium price has softened", kill="Appraisal wells fail to confirm flow rates"),
 dict(t="IXR.AX", name="Ionic Rare Earths", choke="Magnet recycling + Uganda ionic clay (Makuutu)", chain="EU/UK magnet users → recycled NdPr/Dy/Tb oxides → Belfast plant; Makuutu feed",
      ev=["https://ionicre.com/"], fact="Company claims (not re-verified this pass): Belfast magnet recycling demonstration; Makuutu mining licence.", cat=("2027-03-31", "Belfast scale-up (judgement)"), share=2, sens=5, grade="C",
      risks="tiny scale; serial dilution; Uganda jurisdiction", kill="No commercial-scale funding by end-2027"),
 dict(t="ASPI", name="ASP Isotopes", choke="Isotope enrichment (Mo-100, Yb-176; HALEU ambition)", chain="Nuclear medicine and advanced reactors → enriched isotopes / HALEU → ASPI aerodynamic separation (South Africa)",
      ev=["https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001921865&type=10-K"], fact="Company claims (10-K, not re-read this pass): isotope enrichment plants in Pretoria; HALEU via QLE.", cat=("2027-06-30", "Commercial isotope deliveries (judgement)"), share=2, sens=5, grade="C",
      risks="technology claims, short-seller reports in 2025, dilution", kill="No audited isotope revenue growth in FY2026 10-K"),
 dict(t="AREC", name="American Resources (ReElement)", choke="Rare-earth refining (chromatographic) in the US", chain="Magnet makers → separated oxides → ReElement Technologies (Indiana)",
      ev=["https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001590715&type=10-K"], fact="Company claims (not re-verified this pass): ReElement refining capacity and offtake MOUs.", cat=("2027-03-31", "ReElement financing (judgement)"), share=1, sens=5, grade="C",
      risks="going-concern history, coal legacy liabilities, related-party complexity", kill="Going-concern qualification in the next 10-K"),
]
UNIV = ["UAMY","PPTA","AII.TO","AXTI","POET","LTBR","UCU.V","ARA.TO","NB","GPH.V","WWR","IPX","TMC","LPTH","AREC","TLO.TO","VML.AX","HAS.AX","IXR.AX","BRES.L","EMH.AX","ATC.AX","AVL.AX","SLI","KULR","PPSI","BNL.AX","LRV.AX","TUN.L","ARU.AX","AAOI","LEU","6855.T","4369.T","ASPI","AAJ.AX","KTA.AX","IVR.AX","NMG","SYR.AX","EQR.AX","ARA.TO","NEO.TO","VNP.TO","SGML","PLL","SMR","USAS","WRN","ALM.AX"]
FXT = {"AUD": "AUDUSD=X", "CAD": "CADUSD=X", "GBP": "GBPUSD=X", "GBp": "GBPUSD=X", "JPY": "JPYUSD=X", "USD": None}

def base_rate(fx, Q):
    rows = []
    for t in sorted(set(UNIV)):
        h = hist(t)
        if not h or h[0][0] > "2023-01-31": continue
        q = Q.get(t, {}); cur = q.get("currency", "USD"); f = 1 if cur == "USD" else fx.get(cur, 0)
        sh_out = (q.get("marketCap") or 0) / (q.get("regularMarketPrice") or 1)
        months = sorted({d[:7] for d, _ in h if "2023-01" <= d[:7] <= "2025-10"})
        for m in months:
            i = next(k for k, (d, _) in enumerate(h) if d[:7] == m); p0 = h[i][1]
            fut = [c for d, c in h[i:] if d <= (datetime.date.fromisoformat(h[i][0]) + datetime.timedelta(days=365)).isoformat()]
            if len(fut) < 200: continue
            cap = p0 * sh_out * f * (0.01 if cur == "GBp" else 1)
            mx = max(fut) / p0; end = fut[-1] / p0; dd = min(c / max(fut[:k + 1]) for k, c in enumerate(fut)) - 1
            rows.append(dict(t=t, m=m, cap_usd=cap, max12=mx, end12=end, dd=dd))
    small = [r for r in rows if 0 < r["cap_usd"] < 300e6]
    def stats(rs):
        if not rs: return {}
        return dict(n_entries=len(rs), names=len({r["t"] for r in rs}), touch_10x_pct=round(100 * sum(r["max12"] >= 10 for r in rs) / len(rs), 1), touch_5x_pct=round(100 * sum(r["max12"] >= 5 for r in rs) / len(rs), 1),
                    touch_2x_pct=round(100 * sum(r["max12"] >= 2 for r in rs) / len(rs), 1), hold_10x_pct=round(100 * sum(r["end12"] >= 10 for r in rs) / len(rs), 1),
                    end_2x_pct=round(100 * sum(r["end12"] >= 2 for r in rs) / len(rs), 1), lose_50_pct=round(100 * sum(r["end12"] <= 0.5 for r in rs) / len(rs), 1),
                    median_end12=round(100 * (st.median(r["end12"] for r in rs) - 1), 1), median_maxdd=round(100 * st.median(r["dd"] for r in rs), 1))
    per = {}
    for r in small: per.setdefault(r["t"], []).append(r)
    winners = sorted(((t, round(max(x["max12"] for x in v), 1)) for t, v in per.items()), key=lambda z: -z[1])
    return dict(all=stats(rows), sub300=stats(small), by_name=winners, universe=len({r["t"] for r in rows}))

def main():
    syms = [c["t"] for c in C]; Q = quotes(list(dict.fromkeys(syms + UNIV + [v for v in FXT.values() if v])))
    fx = {k: (Q.get(v, {}).get("regularMarketPrice") if v else 1) for k, v in FXT.items()}
    for c in C:
        q = Q.get(c["t"], {}); cur = q.get("currency", "USD"); f = fx.get(cur) or 0
        mc = (q.get("marketCap") or 0) * f; px = q.get("regularMarketPrice"); hi, lo = q.get("fiftyTwoWeekHigh"), q.get("fiftyTwoWeekLow")
        if cur == "GBp" and mc > 0: mc = mc  # Yahoo reports LSE marketCap in GBP even when the price is in pence
        adv = (q.get("averageDailyVolume3Month") or 0) * (px or 0) * f * (0.01 if cur == "GBp" else 1)
        h = hist(c["t"]); r3 = (h[-1][1] / h[-64][1] - 1) if len(h) > 64 else None; r12 = (h[-1][1] / h[-252][1] - 1) if len(h) > 252 else None
        pos = (px - lo) / (hi - lo) if px and hi and lo and hi > lo else None
        c.update(px=px, cur=cur, mcap_usd=round(mc / 1e6, 1), adv_usd_k=round(adv / 1e3), r3m=None if r3 is None else round(100 * r3), r12m=None if r12 is None else round(100 * r12), range_pos=None if pos is None else round(pos, 2))
        size = 5 if 0 < mc < 150e6 else 4 if mc < 300e6 else 3 if mc < 600e6 else 2 if mc < 1.5e9 else 1
        liq = 1 if adv < 100e3 else 3 if adv < 1e6 else 5
        crowd = (2 if (r12 or 0) > 2 else 0) + (1 if (pos or 0) > 0.8 else 0) + (1 if (r3 or 0) > 0.6 else 0)
        gr = dict(A=5, B=4, C=2)[c["grade"]]
        c["score"] = round(0.25 * c["share"] + 0.2 * c["sens"] + 0.15 * size + 0.15 * gr + 0.1 * liq + 0.15 * (5 - min(4, crowd) * 1.25), 2)
        c["contrarian"] = "CROWDED: up >200% in 12m and/or near 52w high, wait for the catalyst or a drawdown" if crowd >= 3 else "Partly crowded" if crowd >= 2 else "Not crowded on price"
        c["quant_validation"] = "VETO for recommendation-grade (no backtested KEPT signal; WATCH only)"
        c["dilution_flag"] = "HIGH" if c["t"] in ("UCU.V", "ARA.TO", "NB", "GPH.V", "PLSR.V", "IXR.AX", "ASPI", "AREC", "GMET.L", "TUN.L") else "MEDIUM"
    C.sort(key=lambda c: -c["score"])
    BR = base_rate(fx, Q)
    # ledger: idempotent WATCH calls
    import committee as K
    have = set()
    if os.path.exists(K.LEDGER):
        for l in open(K.LEDGER):
            r = json.loads(l)
            if r.get("kind") == "bottleneck_watch": have.add((r["ticker"], r["asof"]))
    for c in C:
        if (c["t"], ASOF) in have: continue
        K.append(dict(kind="bottleneck_watch", asof=ASOF, ticker=c["t"], call="WATCH", px=c["px"], cur=c["cur"], catalyst=c["cat"][0], kill=c["kill"], score=c["score"], note="paper only; not advice; asymmetric setup, not a forecast"))
    ok = K.verify()
    json.dump(dict(asof=ASOF, top=C, base=BR, ledger_ok=ok, fx=fx), open(f"{D}/../bottleneck.json", "w"), indent=1, default=str)
    write_md(C, BR, ok); return C, BR

def write_md(C, BR, ok):
    s, a = BR["sub300"], BR["all"]
    L = ["# TRIAGE Bottleneck Hunt", "", f"*As of 23 Oct 2026 (SGT). Research only, not investment advice, paper ledger only. These are asymmetric setups, not promises. We do not claim 100x for anything.*", "",
         "## 1. The honest base rate first", "",
         f"Universe: {BR['universe']} chokepoint-adjacent small and micro caps (antimony, tungsten, rare earths, graphite, scandium, helium, InP/optics, isotopes, probe cards, lithium) with prices back to Jan 2023. Each month from Jan 2023 to Oct 2025 is an entry; we look 12 months ahead.", "",
         "| Bucket | Entries | Names | Touched 2x | Touched 5x | Touched 10x | Still ≥10x at 12m | Ended ≥2x | Lost ≥50% | Median 12m return | Median max drawdown |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in (("Entry cap < $300m (approx.)", s), ("All entries", a)):
        if v: L.append(f"| {k} | {v['n_entries']} | {v['names']} | {v['touch_2x_pct']}% | {v['touch_5x_pct']}% | {v['touch_10x_pct']}% | {v['hold_10x_pct']}% | {v['end_2x_pct']}% | {v['lose_50_pct']}% | {v['median_end12']}% | {v['median_maxdd']}% |")
    L += ["", "Best 12-month peak multiple per name (sub-$300m entries): " + ", ".join(f"{t} {m}x" for t, m in BR["by_name"][:12]) + ".", "",
          "**Read this before anything else.** The universe was chosen in 2026 from names we remember, so it is biased towards names that moved (survivorship and recall bias). Delisted and failed names are under-represented. Entry market caps are approximated using today's share count, which understates the true small-cap count for heavy diluters. The true base rate is lower than this table. A 100x in months is not in the distribution we can measure.", "",
          "## 2. Method", "", "Top-down chokepoints (MOFCOM export controls, DoD DPA Title III/DLA awards, NWF/EXIM finance, NDAA sourcing rules) → small listed firms that hold the scarce asset, permit or qualification → evidence graded A (government document), B (company primary filing) or C (company claim or trade press, not re-verified) → score.", "",
          "Score (0–5) = 25% chokepoint share + 20% revenue sensitivity + 15% size + 15% evidence grade + 10% liquidity + 15% not-crowded. The weights are judgement. Contrarian check: 12-month return >200%, top 20% of 52-week range, 3-month return >60%. Quant Validation: every name is VETOED as recommendation-grade because no backtested KEPT signal underlies it, so all are paper WATCH calls.", "",
          "**The dated catalyst for the whole metals cluster:** MOFCOM Announcement 72/2025 suspends the US-specific ban on gallium, germanium, antimony and superhard materials (Ann. 46/2024 Art. 2) **only until 27 Nov 2026**. Art. 1 (no dual-use items to US military end users) stays in force. Source: " + MOF, "",
          "## 3. Top 15", "", "| # | Company | Chokepoint | Mcap $m | ADV $k | 12m | Score | Grade | Crowding | Catalyst |", "|---|---|---|---|---|---|---|---|---|---|"]
    for i, c in enumerate(C, 1):
        L.append(f"| {i} | {c['name']} ({c['t']}) | {c['choke']} | {c['mcap_usd']} | {c['adv_usd_k']} | {c['r12m']}% | {c['score']} | {c['grade']} | {c['contrarian'].split(':')[0]} | {c['cat'][0]}: {c['cat'][1]} |")
    L += [""]
    for i, c in enumerate(C, 1):
        L += [f"### {i}. {c['name']} ({c['t']})", "", f"- **Chain:** {c['chain']}", f"- **Verified fact:** {c['fact']}", f"- **Catalyst:** {c['cat'][0]}: {c['cat'][1]}",
              f"- **Key risks:** {c['risks']}. Dilution risk: {c['dilution_flag']}.", f"- **Kill condition:** {c['kill']}", f"- **Contrarian:** {c['contrarian']}. **Quant Validation:** {c['quant_validation']}.",
              "- **Evidence:** " + " · ".join(c["ev"]), ""]
    L += ["## 4. Kills and exclusions", "",
          "- **Already re-rated past the size filter (excluded, but they show the pattern):** AXT (InP substrates, $3.4bn), USA Rare Earth ($3.6bn), MP Materials ($6.8bn), Centrus ($2.1bn), Perpetua ($2.2bn), 5N Plus (C$2.4bn), ACM Research. The bottleneck trade in these names is mostly done; they are context, not candidates.",
          "- **Killed on evidence:** Pioneer Power (no chokepoint), KULR (no chokepoint), Standard Lithium and Sigma (lithium is in surplus), Westwater (no customer, serial dilution), Altech/Aruma/Krakatoa (sub-cent, no asset under a dated catalyst).",
          "- **Chokepoints with no small listed pure play found:** HBM itself, CoWoS/ABF substrates (Ajinomoto, Ibiden and Unimicron are large caps), glass substrates (private), photomasks (Photronics is mid-cap), high-purity quartz (Sibelco and The Quartz Corp are private), neon, GOES electrical steel, gas turbines, shipyards, solid rocket motors and energetics, BIOSECURE-driven CDMO.",
          "", "## 5. Gaps", "",
          "- No 13F/large-holder crowding pull this pass (Crustdata and Apify not used, $0 spent); crowding is price-based only. Analyst coverage counts not pulled. Google Trends and X mention checks not run.",
          "- Japan EDINET API needs a key; JEM's customer data came from the published yuho PDF.",
          "- Grade C names (Tri Chemical, Ionic, ASP Isotopes, American Resources) need primary re-verification before they move up.",
          "- UN Comtrade monthly China exports (antimony, Ga/Ge, graphite, rare earths, tungsten) are being ingested; not yet joined to the catalysts.",
          f"- Ledger: 15 WATCH calls appended (hash chain verified = {ok}). They are scored forward from 23 Oct 2026 and anchored daily."]
    m = "\n".join(L); open(os.path.join(HERE, "bottleneck.md"), "w").write(m)
    from design import report_from_markdown
    report_from_markdown(m, "TRIAGE Bottleneck Hunt", "Research · 23 Oct 2026", "Small listed companies inside supply chokepoints: asymmetric setups, base rates and kill conditions",
        [("Setups", "15 WATCH calls, hash-chained"), ("Base rate", f"{s.get('touch_10x_pct','?')}% of sub-$300m entries touched 10x in 12m"), ("Rules", "public data · research only · not advice")],
        os.path.join(HERE, "TRIAGE_Bottleneck_Hunt.html"), os.path.join(HERE, "TRIAGE_Bottleneck_Hunt.pdf"))
if __name__ == "__main__":
    C2, BR = main()
    for c in C2: print(c["t"], c["mcap_usd"], c["score"], c["r12m"], c["contrarian"][:20])
    print(json.dumps(BR["sub300"]), json.dumps(BR["all"])); print(BR["by_name"][:15])
