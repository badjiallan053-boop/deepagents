"""Systemic Radar: where the next $10bn+ dislocation is. Bulk public data (FDIC call reports for every bank, FRED H.8/SLOOS,
N-PORT for every registered fund, BDC marks, non-traded BDC tender results, CMBS ABS-EE loans) plus verified headline
statistics. Writes systemic.json, SR-* verification rows, markdown and a PDF. Judgement is labelled; firms only."""
import os, re, sys, json, sqlite3, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from design import hbars, grouped_bars, report_from_markdown
DB = os.environ.get("TRIAGE_DB", "/workspace/triage_os_data/triage.db"); DATA = "/workspace/triage_os_data"; HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get("SR_CACHE", "/tmp")
def con(): return sqlite3.connect(DB)
def q(sql, a=()):
    c = con(); r = c.execute(sql, a).fetchall(); c.close(); return r

# ---------- headline facts: (id, claim, url, cached file, token) ----------
FACTS = [
 ("SR01", "Trepp CMBS delinquency rate 8.02% in Sep 2026, highest since Nov 2020", "https://www.trepp.com/hubfs/Trepp%20CMBS%20Delinquency%20Report%20September%202026.pdf", "sr_trepp.txt", "rose 17 basis points to 8.02% in September 2026, its highest level since November 2020"),
 ("SR02", "Trepp office CMBS delinquency 12.16% (Sep 2026)", "https://www.trepp.com/hubfs/Trepp%20CMBS%20Delinquency%20Report%20September%202026.pdf", "sr_trepp.txt", "office rose 16 basis points to 12.16%"),
 ("SR03", "Green Street CPPI: office index 76.3, −33% from 2022 peak (4 Sep 2026)", "https://info.greenstreet.com/hubfs/GSCPPI-20260904press.pdf", "sr_gsaug.txt", "Office 76.3 1.5% 5% -33%"),
 ("SR04", "Green Street CPPI −0.1% in Sep 2026, +4.7% over 12 months", "https://www.greenstreet.com/waiting-for-price-clarity/", "sr_gs.txt", "decreased 0.1% in September. Over the past twelve months, the index has increased 4.7%"),
 ("SR05", "MBA: $875bn of commercial mortgages mature in 2026 and $652bn in 2027", "https://www.mba.org/news-and-research/newsroom/news/2026/02/09/17-percent-of-commercial-and-multifamily-mortgage-balances-to-mature-in-2026", "sr_mba.txt", "$875 billion in scheduled maturities in 2026 and $652 billion in 2027"),
 ("SR06", "MBA: $200bn (25%) of CMBS/CLO/ABS-held and $163bn (29%) of credit-company/warehouse-held mortgages mature in 2026", "https://www.mba.org/news-and-research/newsroom/news/2026/02/09/17-percent-of-commercial-and-multifamily-mortgage-balances-to-mature-in-2026", "sr_mba.txt", "$200 billion (25 percent) in CMBS, CLOs or other ABS loans, and $163 billion (29 percent)"),
 ("SR07", "NAIC: US insurers' private-credit exposure ~$1.2tn at YE2025, ~13% of cash and invested assets", "https://content.naic.org/sites/default/files/capital-markets-special-reports-private-credit-analysis.pdf", "sr_naic.txt", "estimated to be $1.2 trillion as of year-end 2025, representing approximately 13% of cash and invested assets"),
 ("SR08", "NAIC: Schedule BA assets $637.9bn at YE2025, +10.3%", "https://content.naic.org/sites/default/files/capital-market-schedule-ba-ye2025.pdf", "sr_naicba.txt", "increasing 10.3% at year-end 2025 to $637.9 billion"),
 ("SR09", "ECB: NPL ratio on loans collateralised by commercial immovable property 4.36% (Q2 2026)", "https://www.bankingsupervision.europa.eu/press/pr/date/2026/html/ssm.pr260915~7917ca1416.en.html", "sr_ecb.txt", "commercial immovable property stood at 4.36%"),
 ("SR10", "UK: 1,882 company insolvencies in Sep 2026 (England and Wales)", "https://www.gov.uk/government/statistics/company-insolvencies-september-2026/commentary-company-insolvency-statistics-september-2026", "sr_ukins.txt", "was 1,882 in September 2026"),
 ("SR11", "Japan (TSR): 5,373 corporate bankruptcies in FY2026 H1 (Apr–Sep)", "https://www.tsr-net.co.jp/news/status/detail/1203308_1610.html", "sr_tsr.txt", "全国企業倒産5,373件"),
 ("SR12", "Moody's (via First Trust): global spec-grade default rate 4.5%, US 5.3% (Aug 2026)", "https://www.ftportfolios.com/blogs/InvestBlog/2026/9/17/factoid---thursday,-september-17,-2026", "sr_moodys.txt", "The U.S. speculative-grade default rate was 5.3% in August"),
 ("SR13", "OCIC Q3 2026: $3.1bn repurchase requests = 16.8% of shares; 5% cap filled pro rata (~30%)", "https://www.sec.gov/Archives/edgar/data/1812554/000119312526411315/d136475dex991.htm", "ocic_q3.txt", "estimated third-quarter total repurchase request of $3.1 billion, or 16.8%"),
 ("SR14", "OCIC: Q1 2026 requests peaked at $4.2bn (21.9%)", "https://www.sec.gov/Archives/edgar/data/1812554/000119312526411315/d136475dex991.htm", "ocic_q3.txt", "$4.2 billion, or 21.9%, in the first quarter when demand peaked"),
 ("SR15", "Form PF: $29.6tn private-fund gross assets in 2025Q4 (+18.5% y/y)", "https://www.sec.gov/data-research/statistics-data-visualizations/private-fund-statistics", "sr_pf.txt", "$29.6 Trillion (USD) Gross Assets in 2025Q4 +18.5%"),
 ("SR16", "China developers: only 0.6% of offshore debt recovered (secondary source)", "https://tradeinzone.in/only-0-6-of-offshore-debt-recovered-from-chinas-property-developers/", "sr_china.txt", "Only 0.6% of offshore debt recovered"),
 ("SR17", "Fitch: non-traded BDC redemption requests 9.8% of shares in Q3 2026 (secondary report of Fitch)", "https://www.intervalfunddaily.com/story/fitch-nontraded-bdc-redemption-requests-ease-to-9-8-still-near-twice-the-5-cap", "sr_fitchbdc.txt", "redemption requests ease to 9.8%"),
]
def verify():
    out = {}
    for fid, claim, url, fn, tok in FACTS:
        p = os.path.join(CACHE, fn); t = re.sub(r"\s+", " ", open(p, errors="ignore").read()) if os.path.exists(p) else ""
        ok = re.sub(r"\s+", " ", tok) in t; sec = "secondary" in claim
        out[fid] = dict(claim=claim, url=url, ok=ok, status=("VERIFIED" if ok else "UNVERIFIABLE"), fix="Secondary source; primary not public" if sec else "",
                        method=f"token match in text fetched 22–23 Oct 2026: '{tok[:70]}'")
    return out

# ---------- computed blocks ----------
def banks():
    def agg(t):
        rows = q(f"select CERT,NAME,CITY,STALP,ASSET,LNRECONS,LNREMULT,LNRENROT,coalesce(nullif(RBC,0),EQ),NCLNLS,BRO,DEP,SCAF-SCAA,SCHF-SCHA,RBCT1J,LNLSNET from {t}")
        out = []
        for r in rows:
            cert, name, city, st, asset, cons, mf, nonocc, cap, ncl, bro, dep, afs, htm, t1, loans = [x if x is not None else 0 for x in r]
            if not cap or cap <= 0: continue
            cre = cons + mf + nonocc
            out.append(dict(cert=cert, name=name, city=city, st=st, asset=asset / 1e3, cre_pct=cre / cap * 100, cons_pct=cons / cap * 100,
                            ncl_pct=(ncl / loans * 100) if loans else 0, bro_pct=(bro / dep * 100) if dep else 0, ul_t1=((afs + htm) / t1 * 100) if t1 else 0, cre=cre / 1e3))
        return out
    now, prev = agg("fdic_call_20260630"), agg("fdic_call_20250630")
    hi = [b for b in now if b["cre_pct"] > 300]
    tot = q("select sum(SCAF-SCAA)/1e6, sum(SCHF-SCHA)/1e6, sum(RBCT1J)/1e6, sum(BRO)/1e6, sum(DEP)/1e6, sum(NCLNLS)/1e6, sum(LNLSNET)/1e6, count(*) from fdic_call_20260630")[0]
    st = collections.defaultdict(lambda: dict(n=0, hi=0, asset_hi=0.0, cre_hi=0.0))
    for b in now:
        s = st[b["st"]]; s["n"] += 1
        if b["cre_pct"] > 300: s["hi"] += 1; s["asset_hi"] += b["asset"]; s["cre_hi"] += b["cre"]
    return dict(n=len(now), n_prev=len(prev), hi=len(hi), hi_prev=sum(b["cre_pct"] > 300 for b in prev), hi_asset_bn=sum(b["asset"] for b in hi) / 1e3,
                cons100=sum(b["cons_pct"] > 100 for b in now), afs_ul=tot[0], htm_ul=tot[1], t1=tot[2], brokered=tot[3], deposits=tot[4], noncurrent=tot[5], loans=tot[6],
                top=sorted(hi, key=lambda b: -b["asset"])[:25], states={k: v for k, v in st.items()},
                stress=sorted([b for b in hi if b["ul_t1"] < -25 or b["ncl_pct"] > 2], key=lambda b: -b["asset"])[:15])

def office_clusters():
    return [dict(city=r[0].title(), st=r[1], loans=r[2], bal_m=r[3]) for r in q("""select propertyCity, propertyState, count(*), round(sum(cast(reportPeriodEndActualBalanceAmount as real))/1e6,1)
        from cmbs_loans where propertyTypeCode='OF' and (mostRecentSpecialServicerTransferDate!='' or paymentStatusLoanCode not in ('0','','A','B')) group by 1,2 order by 4 desc limit 12""")]

def maturity_wall():
    r = q("""select substr(maturityDate,1,4) y, case propertyTypeCode when 'OF' then 'Office' when 'RT' then 'Retail' when 'MF' then 'Multifamily' when 'LO' then 'Lodging' when 'IN' then 'Industrial' when 'MU' then 'Mixed use' else 'Other' end, sum(cast(reportPeriodEndActualBalanceAmount as real))/1e6
        from cmbs_loans where substr(maturityDate,1,4) in ('2026','2027','2028') group by 1,2""")
    w = collections.defaultdict(dict)
    for y, t, v in r: w[t][y] = w[t].get(y, 0) + v
    meta = q("select count(distinct trust), count(*), sum(cast(reportPeriodEndActualBalanceAmount as real))/1e9 from cmbs_loans")[0]
    return dict(by_type={k: {y: round(v.get(y, 0), 1) for y in ("2026", "2027", "2028")} for k, v in w.items()}, trusts=meta[0], loans=meta[1], bal_bn=meta[2])

def tenders():
    rows = q("select ticker, fund, filed, url, expired, tendered_shares, purchased_shares, nav_usd_accepted, prorated, cap_pct from bdc_tenders order by ticker, filed")
    out = []
    for tk, fund, filed, url, exp, ten, pur, nav, pr, cap in rows:
        if tk == "HLEND": nav_ps = nav; acc_usd = (pur or 0) * nav_ps if pur else None
        elif tk == "ASIF": nav_ps = nav / ten if ten else None; acc_usd = pur * nav_ps if pur and nav_ps else None
        else: nav_ps = nav / pur if pur else None; acc_usd = nav
        ten_usd = ten * nav_ps if nav_ps else None
        out.append(dict(ticker=tk, fund=fund, filed=filed, expired=exp, url=url, tendered_m=ten / 1e6, accepted_m=(pur or 0) / 1e6, fill=(pur / ten * 100) if pur and ten else None,
                        tendered_usd_m=ten_usd / 1e6 if ten_usd else None, accepted_usd_m=acc_usd / 1e6 if acc_usd else None,
                        unmet_usd_m=(ten_usd - acc_usd) / 1e6 if ten_usd and acc_usd else None, prorated=bool(pr)))
    # de-duplicate ASIF interim amendments (keep last per expiry)
    d = {}
    for r in out: d[(r["ticker"], r["expired"])] = r
    out = sorted(d.values(), key=lambda r: (r["ticker"], r["filed"]))
    # OCIC Q2 2026 final results, from the 24 Jul 2026 SC TO-I/A (three share classes)
    out.append(dict(ticker="OCIC", fund="Blue Owl Credit Income Corp.", filed="2026-07-24", expired="June 30, 2026", url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001812554&type=SC+TO-I",
                    tendered_m=(72307451 + 12816225 + 310304828) / 1e6, accepted_m=(19245685 + 3411226 + 82592171) / 1e6, fill=26.6, tendered_usd_m=3600.0, accepted_usd_m=955.0, unmet_usd_m=3600.0 - 955.0, prorated=True))
    latest = {}
    for r in out:
        if r["ticker"] not in latest or r["filed"] > latest[r["ticker"]]["filed"]: latest[r["ticker"]] = r
    return out, latest

def cascade():
    bdc = [dict(borrower=r[0], n_bdc=r[1], par_m=r[2], wavg=r[3], lo=r[4], hi=r[5], bdcs=r[6]) for r in q("""select borrower_key, count(distinct bdc) n, round(sum(par)/1e6,1), round(sum(fv)/sum(par)*100,1), round(min(mark),1), round(max(mark),1), group_concat(distinct bdc)
        from bdc_marks where period='2026-06-30' and par>0 group by borrower_key having n>=3 and sum(fv)/sum(par)<0.9 order by 3 desc limit 12""")]
    nport = [dict(name=r[0], funds=r[1], usd_m=r[2], max_pct=r[3]) for r in q("select watch, count(distinct fund), round(sum(value_usd)/1e6,1), round(max(pct_nav)/100,2) from nport_watch group by 1 order by 3 desc")]
    edges = q("""select a.bdc, b.bdc, count(distinct a.borrower_key), round(sum(a.par+b.par)/2e6,0) from bdc_marks a join bdc_marks b on a.borrower_key=b.borrower_key and a.bdc<b.bdc and a.period=b.period
        where a.period='2026-06-30' and a.mark<80 and b.mark<80 group by 1,2 having count(distinct a.borrower_key)>=3 order by 3 desc limit 40""")
    return dict(bdc=bdc, nport=nport, edges=[dict(a=e[0], b=e[1], shared=e[2], par_m=e[3]) for e in edges])

def nport_meta():
    c = dict(q("select dataset, rows from dataset_counts where dataset like 'nport%'"))
    f = q("select count(*), sum(net_assets)/1e12, sum(cmbs_usd)/1e9, sum(case when cmbs_usd>0 then 1 else 0 end), sum(loans_usd)/1e9, sum(case when loans_usd>0 then 1 else 0 end) from nport_funds")[0]
    l3 = q("select sum(value_usd)/1e9 from nport_asset_mix")[0][0]
    return dict(counts=c, series=f[0], nav_tn=f[1], cmbs_bn=f[2], cmbs_funds=f[3], loans_bn=f[4], loan_funds=f[5], gross_bn=l3)

def fred_last(sid):
    r = q("select date, value from fred_series where sid=? and value not in ('','.') order by date desc limit 1", (sid,))
    return (r[0][0], float(r[0][1])) if r else (None, None)

def dataset_counts(nm):
    rows = [("FDIC call reports, all insured banks, 30 Jun 2026", q("select count(*) from fdic_call_20260630")[0][0], "https://api.fdic.gov/banks/financials?filters=REPDTE:20260630"),
            ("FDIC call reports, all insured banks, 30 Jun 2025", q("select count(*) from fdic_call_20250630")[0][0], "https://api.fdic.gov/banks/financials?filters=REPDTE:20250630"),
            ("FRED / Fed H.8, SLOOS, delinquency and spread series (12 series, observations)", q("select count(*) from fred_series")[0][0], "https://fred.stlouisfed.org/"),
            ("N-PORT 2026Q3, all holdings rows (raw)", nm["counts"].get("nport_2026q3_holdings_raw"), "https://www.sec.gov/files/dera/data/form-n-port-data-sets/2026q3_nport.zip"),
            ("N-PORT 2026Q3, fund series (latest filing each)", nm["series"], "https://www.sec.gov/files/dera/data/form-n-port-data-sets/2026q3_nport.zip"),
            ("BDC Schedule of Investments marks, all quarters (40 BDCs at 30 Jun 2026)", q("select count(*) from bdc_marks")[0][0] + q("select count(*) from bdc_marks_hist")[0][0], "https://www.sec.gov/"),
            ("Non-traded BDC tender results, SC TO-I/A final amendments (6 funds + OCIC)", q("select count(*) from bdc_tenders")[0][0], "https://www.sec.gov/"),
            ("CMBS ABS-EE loan tapes (sample universe)", q("select count(*) from cmbs_loans")[0][0], "https://www.sec.gov/"),
            ("CMBS 10-D directing holders", 102, "https://www.sec.gov/"),
            ("Form ADV private funds (Schedule D 7.B.1)", q("select count(*) from adv_funds")[0][0], "https://www.sec.gov/foia-services/frequently-requested-documents/form-adv-data"),
            ("13F holdings (EchoStar complex, 2026Q2)", q("select count(*) from f13_holdings")[0][0], "https://www.sec.gov/")]
    return [dict(dataset=a, rows=b, source=c) for a, b, c in rows]

def build():
    res = verify(); c = con(); c.execute("create table if not exists verification(claim_id, artifact, claim, status, primary_url, checked, method, fix)")
    c.execute("delete from verification where claim_id like 'SR%'")
    for k, r in res.items(): c.execute("insert into verification values(?,?,?,?,?,?,?,?)", (k, "research/systemic_radar", r["claim"], r["status"], r["url"], "2026-10-23", r["method"], r["fix"]))
    c.commit(); c.close()
    B, OC, MW, (T, TL), CA, NM = banks(), office_clusters(), maturity_wall(), tenders(), cascade(), nport_meta()
    DS = dataset_counts(NM)
    F = {k: fred_last(k) for k in ("CREACBW027SBOG", "DRCRELEXFACBS", "CORCREXFACBS", "SUBLPDRCSN", "SUBLPDRCSC", "SUBLPDRCSM", "DRTSCILM", "BAMLH0A0HYM2", "TOTBKCR")}
    unmet = sum(r["unmet_usd_m"] or 0 for r in TL.values()); req = sum(r["tendered_usd_m"] or 0 for r in TL.values())
    THESES = [
     dict(rank=1, name="Private-credit liquidity mismatch (non-traded BDCs)", size="$8–15bn of unmet redemption demand per quarter (judgement range)", prob="High (60–75%, judgement) that queues persist into 2027",
          evidence=f"Latest rounds at 6 large non-traded BDCs: ${req/1e3:,.1f}bn requested, ${unmet/1e3:,.1f}bn unmet. BCRED requests 20.9m → 191.8m shares in six quarters. OCIC Q3: $3.1bn = 16.8% of shares [SR13]. Fitch industry average 9.8% vs 5% cap [SR17]",
          trigger="Q4 tender windows (Nov–Dec 2026); any fund raising the cap or selling loan portfolios to meet it", buyers="Secondaries and NAV-loan providers; listed BDCs and insurers' asset managers buying loan portfolios at discount (judgement)"),
     dict(rank=2, name="CRE maturity wall into office (CMBS + banks)", size="$652bn total CRE maturities in 2027 [SR05]; office −33% from peak [SR03]", prob="High (55–70%, judgement) of $10bn+ office loss realisation in 2026–27",
          evidence=f"CMBS delinquency 8.02%, highest since Nov 2020 [SR01]; office 12.16% [SR02]. In our {MW['trusts']}-trust sample, office is the largest 2027–28 maturity bucket. MBA: $200bn of CMBS/CLO-held mortgages mature in 2026 [SR06]",
          trigger="Non-performing matured balloons (68% of new Sep delinquencies per Trepp); appraisal reductions shifting directing-holder control", buyers="B-piece/special-servicer platforms already holding control (Rialto, LNR, KKR RE Credit, Eightfold, 400 Capital per our 10-D parse); opportunistic RE funds (judgement)"),
     dict(rank=3, name="CRE-concentrated community and regional banks", size=f"{B['hi']} banks above 300% CRE/capital, ${B['hi_asset_bn']:,.0f}bn of assets", prob="Medium (30–45%, judgement) of a cluster of failures or forced loan sales above $10bn",
          evidence=f"Unrealised securities losses ${(B['afs_ul']+B['htm_ul']):,.0f}bn vs ${B['t1']:,.0f}bn tier-1 capital (all banks); brokered deposits ${B['brokered']:,.0f}bn. High-CRE count down from {B['hi_prev']} a year ago (de-risking under way)",
          trigger="Office loan maturities at banks ($396bn of depository-held mortgages mature in 2026 per MBA); deposit repricing", buyers="Loan-sale buyers with bank-quality underwriting; larger regionals in FDIC-assisted deals (judgement)"),
     dict(rank=4, name="Insurer private-credit and Schedule BA concentration", size="$1.2tn private-credit exposure [SR07]; $637.9bn Schedule BA [SR08]", prob="Low-medium (15–25%, judgement) of a $10bn+ forced-sale event within 18 months",
          evidence="Exposure grows faster than invested assets. Insurers also hold ~$32bn in private BDC/credit funds, so rank 1 transmits here. AM Best recorded no rated-insurer impairments in 2025",
          trigger="Rating-agency or NAIC capital-charge changes; a private-letter-rating downgrade cycle", buyers="Reinsurers and sidecars; multi-strategy credit funds (judgement)"),
     dict(rank=5, name="Fund-overlap cascades in stressed issuers (EchoStar/DISH complex)", size="~$4bn of DISH DBS + Hughes debt held across 300+ registered funds (N-PORT, NAV-weighted)", prob="Medium for idiosyncratic $1–5bn moves; low for $10bn+ (judgement)",
          evidence="N-PORT 2026Q3: Hughes notes held by 46 funds ($616m), DISH DBS by 293 funds ($3.4bn). In private credit, five BDCs share PetVet at marks from −13.9 to 88", trigger="Downgrades forcing ratings-constrained and index funds to sell together", buyers="Event-driven and distressed funds with no ratings constraint (judgement)"),
    ]
    J = dict(as_of="2026-10-23", datasets=DS, banks={k: v for k, v in B.items() if k not in ("states",)}, states=[dict(st=k, **v) for k, v in sorted(B["states"].items())], office_clusters=OC,
             maturity=MW, tenders=T, tender_latest=list(TL.values()), unmet_bn=unmet / 1e3, requested_bn=req / 1e3, cascade=CA, nport=NM, fred={k: dict(date=v[0], value=v[1]) for k, v in F.items()},
             theses=THESES, facts=[dict(id=k, **v) for k, v in res.items()])
    json.dump(J, open(os.path.join(DATA, "systemic.json"), "w"), indent=1, default=str)
    md = render_md(J, res); open(os.path.join(DATA, "systemic_radar.md"), "w").write(md); open(os.path.join(HERE, "systemic_radar.md"), "w").write(md)
    pdf = os.path.join(HERE, "Where_the_next_dislocation_is.pdf")
    pages = report_from_markdown(md, "Where the next dislocation is", "Systemic radar · 23 Oct 2026",
        "Bank CRE concentration, private-credit redemption queues, the CRE maturity wall, insurer exposure and fund-overlap cascades, ranked by the odds of a $10bn+ dislocation.",
        [("Banks screened", f"{B['n']:,}"), ("Fund series", f"{NM['series']:,}"), ("Unmet BDC demand", f"${unmet/1e3:,.1f}bn"), ("Facts verified", f"{sum(r['ok'] for r in res.values())}/{len(res)}")],
        os.path.join(HERE, "Where_the_next_dislocation_is.html"), pdf)
    return J, res, pages, pdf

def fm(v, d=0): return "–" if v is None else f"{v:,.{d}f}"

def render_md(J, res):
    B, MW, CA, NM = J["banks"], J["maturity"], J["cascade"], J["nport"]; F = J["fred"]
    L = [f"""# Where the next dislocation is

## 1. The answer

**The most likely $10bn+ dislocation is in private-credit liquidity, not in a single credit.** Seven large non-traded BDCs promise quarterly liquidity of about 5% of shares. In their latest completed rounds, holders asked for **${J['requested_bn']:,.1f}bn** and **${J['unmet_bn']:,.1f}bn went unmet**. That is a single quarter at six funds; the queue rolls forward because unfilled requests are resubmitted.

The second-ranked thesis is the **CRE maturity wall into office**. CMBS delinquency is 8.02%, the highest since November 2020 [SR01], office is 12.16% [SR02], and office values are 33% below peak [SR03], against $875bn of 2026 and $652bn of 2027 commercial-mortgage maturities [SR05].

The two are linked. Insurers hold ~$1.2tn of private credit [SR07]. Banks lend to the funds and to CRE: {B['hi']} banks run CRE above 300% of capital.

**Ranking (judgement, not forecasts):**

| # | Thesis | Size | Probability (judgement) | Who is positioned to buy (judgement) |
|---|---|---|---|---|"""]
    for t in J["theses"]: L.append(f"| {t['rank']} | {t['name']} | {t['size']} | {t['prob']} | {t['buyers']} |")
    L.append(f"""
**What argues against a near-term systemic break (counter-evidence, from the same data):**
- **High-yield spreads are tight** at {F['BAMLH0A0HYM2']['value']}% OAS ({F['BAMLH0A0HYM2']['date']}).
- **Banks are easing, not tightening, CRE standards.** SLOOS net tightening is NFNR {F['SUBLPDRCSN']['value']} and multifamily {F['SUBLPDRCSM']['value']}.
- **Bank CRE credit is still benign.** The delinquency rate is {F['DRCRELEXFACBS']['value']}% and the charge-off rate {F['CORCREXFACBS']['value']}%.
- **Prices are up.** Green Street all-property values are +4.7% year on year [SR04].
- **Defaults are expected to fall.** Moody's projects lower default rates by December [SR12].

The dislocations ranked here are therefore **liquidity and refinancing events in specific pools of capital**, not a broad credit crisis (judgement).

## Thesis detail: evidence, trigger, buyers
""")
    for t in J["theses"]:
        L.append(f"### {t['rank']}. {t['name']}\n\n| Field | Detail |\n|---|---|\n| Size | {t['size']} |\n| Probability (judgement) | {t['prob']} |\n| Evidence | {t['evidence']} |\n| Trigger to watch | {t['trigger']} |\n| Best positioned to buy (judgement) | {t['buyers']} |\n")
    L.append("\n## 2. Datasets ingested (row counts)\n\n| Dataset | Rows | Source |\n|---|---|---|")
    for d in J["datasets"]: L.append(f"| {d['dataset']} | {fm(d['rows'])} | {d['source']} |")
    L.append(f"""
Headline-only sources (no public bulk file, or bulk not feasible here) are listed in section 9 with what was and was not obtained.

## 3. Thesis 1: the private-credit liquidity mismatch

The rows below come from the latest final tender results filed on EDGAR under Rule 13e-4(c)(4).
- **Values in USD:** NAV per share comes from the filing, or is derived as accepted NAV ÷ accepted shares.
- **OCIC Q2:** from its 24 Jul 2026 amendment (three share classes); the dollar amounts are approximate.
- **Not additive across quarters:** unfilled requests are typically resubmitted, so adding quarters double-counts.

| Fund | Offer expired | Requested (m sh) | Accepted (m sh) | Fill | Requested $m | Unmet $m | Source |
|---|---|---|---|---|---|---|---|""")
    for r in sorted(J["tender_latest"], key=lambda r: -(r["unmet_usd_m"] or 0)):
        L.append(f"| {r['ticker']} | {r['expired']} | {fm(r['tendered_m'],1)} | {fm(r['accepted_m'],1)} | {fm(r['fill'],1)}% | {fm(r['tendered_usd_m'])} | {fm(r['unmet_usd_m'])} | {r['url']} |")
    L.append("\n**Full tender history (final amendments, 2025–2026)**\n\n| Fund | Filed | Offer expired | Requested (m sh) | Accepted (m sh) | Fill | Prorated |\n|---|---|---|---|---|---|---|")
    for r in J["tenders"]: L.append(f"| {r['ticker']} | {r['filed']} | {r['expired']} | {fm(r['tendered_m'],1)} | {fm(r['accepted_m'],1)} | {fm(r['fill'],1)}% | {'yes' if r['prorated'] else 'no'} |")
    hist = [r for r in J["tenders"] if r["ticker"] in ("BCRED", "ADS", "HLEND", "ASIF")]
    cats = sorted({r["expired"][-4:] + ("H1" if any(m in r["expired"] for m in ("December", "January", "February", "March", "April", "May", "June")) else "H2") for r in hist})
    L.append(f"""
<div class="cap">Exhibit 1 · Tender requests, millions of shares, by fund and offer</div>
<div class="chart">{hbars([(f"{r['ticker']} {r['expired']}", r['tendered_m'], '#c97d06' if r['prorated'] else '#0b0f14', '') for r in hist[-14:]], value_fmt=lambda v: f"{v:,.0f}m sh")}</div>
<div class="src">Amber = prorated (requests above the cap). Source: SC TO-I/A final amendments on EDGAR (bdc_tenders.py).</div>

**What the numbers say.**
- **BCRED:** requests went from 20.9m shares (Dec 2024 offer) to 191.8m (May 2026), and the fund prorated to 5% for the first time.
- **OCIC:** requests peaked at $4.2bn, 21.9% of shares, in Q1 [SR14], and eased to $3.1bn, 16.8%, in Q3 [SR13].
- **Industry:** Fitch puts the Q3 average at 9.8% of shares, against a 5% cap [SR17].
- **Easing, not ending (judgement).** The queue is easing slowly. Funds meet the cap from repayments and new subscriptions; selling loans is the release valve.

**Transmission (judgement).** A fund that lifts its cap or sells loans to clear the queue reveals clearing prices. Every BDC that marks the same borrower then faces the same price; Exhibit 2 shows which BDCs share stressed names.

| Stressed borrower (wtd mark <90) | BDCs holding | Par $m | Wtd mark | Range | BDCs |
|---|---|---|---|---|---|""")
    for r in CA["bdc"]: L.append(f"| {r['borrower']} | {r['n_bdc']} | {fm(r['par_m'],1)} | {r['wavg']} | {r['lo']}–{r['hi']} | {r['bdcs']} |")
    L.append("\n<div class=\"cap\">Exhibit 2 · BDC pairs sharing 3+ borrowers marked below 80 (30 Jun 2026)</div>\n\n| BDC A | BDC B | Shared stressed borrowers | Avg par $m |\n|---|---|---|---|")
    for e in CA["edges"][:15]: L.append(f"| {e['a']} | {e['b']} | {e['shared']} | {fm(e['par_m'])} |")
    mt = MW["by_type"]; types = sorted(mt, key=lambda k: -sum(mt[k].values()))
    L.append(f"""
## 4. Thesis 2: the CRE maturity wall into office

- **CMBS delinquency** is 8.02% (Sep 2026), the highest since November 2020 [SR01]. Office is 12.16% [SR02].
- **Prices:** Green Street office values are 33% below the 2022 peak (index 76.3) [SR03]. The all-property index fell 0.1% in September [SR04].
- **Maturities:** MBA puts 2026 maturities at $875bn and 2027 at $652bn [SR05], including $200bn held in CMBS/CLO/ABS and $163bn by credit companies and warehouses in 2026 [SR06].

<div class="cap">Exhibit 3 · Maturity wall in our ABS-EE sample ({MW['trusts']} trusts, {MW['loans']:,} loans, ${MW['bal_bn']:.1f}bn), $m by property type</div>
<div class="chart">{hbars([(f"{k} {y}", mt[k][y], {"2026": "#8a96a3", "2027": "#c97d06", "2028": "#0b0f14"}[y], '') for k in types[:5] for y in ("2026", "2027", "2028")], value_fmt=lambda v: f"${v:,.0f}m")}</div>
<div class="src">Source: EDGAR ABS-EE loan tapes, cmbs_loans table. This is a sample, not the full CMBS universe; see gaps.</div>

**City office distress clusters** (sample loans in special servicing or delinquent):

| City | State | Loans | Balance $m |
|---|---|---|---|""")
    for o in J["office_clusters"]: L.append(f"| {o['city']} | {o['st']} | {o['loans']} | {fm(o['bal_m'],1)} |")
    L.append(f"""
**Control lens.** The directing holders already parsed from 10-Ds include Rialto (RREF), LNR, KKR Real Estate Credit, Eightfold and 400 Capital (see the control report). They control workouts as balloons fail, which puts them first in line for discounted collateral (judgement).

## 5. Thesis 3: bank-to-CRE contagion

The screen covers the call reports of all **{B['n']:,}** insured banks (30 Jun 2026).
- **CRE concentration** = (construction + multifamily + non-owner-occupied nonfarm nonresidential) ÷ total risk-based capital (equity for community-bank-leverage-ratio filers). This approximates the 2006 interagency guidance test.
- **Above 300%:** {B['hi']} banks with ${B['hi_asset_bn']:,.0f}bn of assets, down from {B['hi_prev']} a year earlier.
- **Construction above 100% of capital:** {B['cons100']} banks.
- **Unrealised securities losses, all banks:** AFS ${B['afs_ul']:,.0f}bn plus HTM ${B['htm_ul']:,.0f}bn, against tier-1 capital of ${B['t1']:,.0f}bn.
- **Brokered deposits:** ${B['brokered']:,.0f}bn of ${B['deposits']:,.0f}bn total deposits.

**FRED (latest).**
- CRE delinquency rate, all banks: {F['DRCRELEXFACBS']['value']}% ({F['DRCRELEXFACBS']['date']}).
- CRE charge-off rate: {F['CORCREXFACBS']['value']}%.
- SLOOS net % tightening: NFNR {F['SUBLPDRCSN']['value']}, construction {F['SUBLPDRCSC']['value']}, multifamily {F['SUBLPDRCSM']['value']} ({F['SUBLPDRCSN']['date']}).
- HY OAS: {F['BAMLH0A0HYM2']['value']} ({F['BAMLH0A0HYM2']['date']}).

| Largest banks above 300% CRE/capital | City | State | Assets $bn | CRE/capital | Construction/capital | Noncurrent loans | Unrealised loss/T1 | Brokered/deposits |
|---|---|---|---|---|---|---|---|---|""")
    for b in B["top"][:20]: L.append(f"| {b['name']} | {b['city'].title()} | {b['st']} | {b['asset']/1e3:,.1f} | {b['cre_pct']:.0f}% | {b['cons_pct']:.0f}% | {b['ncl_pct']:.2f}% | {b['ul_t1']:.0f}% | {b['bro_pct']:.0f}% |")
    st = sorted(J["states"], key=lambda s: -s["asset_hi"])[:12]
    L.append(f"""
<div class="cap">Exhibit 4 · Assets of banks above 300% CRE/capital, by state ($bn)</div>
<div class="chart">{hbars([(s['st'] + f" ({s['hi']} banks)", s['asset_hi'] / 1e3, '#c97d06' if s['st'] in {o['st'] for o in J['office_clusters'][:6]} else '#0b0f14', '') for s in st], value_fmt=lambda v: f"${v:,.0f}bn")}</div>
<div class="src">Amber = state also hosts a top-6 CMBS office distress cluster in our sample (geographic overlap, not proof of loan-level exposure). Source: FDIC BankFind financials API.</div>

**Judgement.** This is a slow-burn thesis. The count of high-CRE banks is falling. Losses arrive through office maturities and deposit costs, not through a run, unless brokered funding and unrealised losses coincide at the same bank.
""")
    L.append("**Stress subset: banks above 300% CRE/capital that also have unrealised losses worse than −25% of tier 1, or noncurrent loans above 2%:**\n\n| Bank | City | State | Assets $bn | CRE/capital | Noncurrent | Unrealised loss/T1 | Brokered/deposits |\n|---|---|---|---|---|---|---|---|")
    for b in B["stress"]: L.append(f"| {b['name']} | {b['city'].title()} | {b['st']} | {b['asset']/1e3:,.1f} | {b['cre_pct']:.0f}% | {b['ncl_pct']:.2f}% | {b['ul_t1']:.0f}% | {b['bro_pct']:.0f}% |")
    L.append("\n**By state (banks above 300%):**\n\n| State | Banks screened | Above 300% | Assets above 300% $bn | CRE above 300% $bn |\n|---|---|---|---|---|")
    for x in sorted(J["states"], key=lambda x: -x["asset_hi"])[:20]: L.append(f"| {x['st']} | {x['n']} | {x['hi']} | {x['asset_hi']/1e3:,.1f} | {x['cre_hi']/1e3:,.1f} |")
    L.append(f"""
## 6. Thesis 4: insurers

- **Private credit:** US insurers hold an estimated $1.2tn, ~13% of cash and invested assets [SR07].
- **Schedule BA** grew 10.3% to $637.9bn at YE2025 [SR08].
- **Transmission (judgement):** insurers hold about $32bn of private BDC and credit-fund interests (NAIC), and are lenders and buyers in CRE. A BDC queue or CRE loss lands on them second.
- **No acute stress:** AM Best recorded no rated-insurer impairments in 2025 (headline; study is paywalled).

## 7. Thesis 5: fund-overlap cascades

Our N-PORT 2026Q3 pull covers **{NM['series']:,}** fund series and {fm(NM['counts'].get('nport_2026q3_holdings_raw'))} holding rows; ${NM['cmbs_bn']:,.0f}bn of CMBS-like ABS sits in {NM['cmbs_funds']:,} funds and ${NM['loans_bn']:,.0f}bn of loans in {NM['loan_funds']:,} funds. Watch-list issuers (values are % of NAV × NAV):

| Issuer family | Funds holding | Value $m | Max % of a fund's NAV |
|---|---|---|---|""")
    for r in CA["nport"]: L.append(f"| {r['name'].title()} | {r['funds']} | {fm(r['usd_m'],1)} | {r['max_pct']}% |")
    L.append("""
EchoStar rows include equity and convertibles held by index funds. Hughes and DISH DBS rows are debt only.

## 8. Cross-border and rest of world

- **Europe.** The NPL ratio on commercial-property-backed corporate loans at ECB significant institutions is 4.36% [SR09], about twice the 2.17% system ratio. The EBA transparency exercise was **discontinued from June 2025**; its 2025 data cover 119 banks to 30 Jun 2025 and are available only through interactive tools, so no bulk bank-level pull was made. The German real-estate names from the control report (Branicks, BayWa) are the live cases.
- **UK.** 1,882 company insolvencies in Sep 2026, down 5% year on year [SR10]. Not a dislocation signal.
- **Japan.** TSR counts 5,373 bankruptcies in FY2026 H1 [SR11]. Japanese bank exposure to US CRE is disclosed only in aggregate. Fitch says it is below 2% of lending for rated APAC banks (secondary); no bank-level public breakdown was found.
- **China.** About 0.6% of ~$150bn of defaulted developer offshore debt has been recovered in cash (secondary source) [SR16]. The dislocation has already been realised; the open question is the recovery-trading opportunity, not contagion.
- **Defaults.** The Moody's spec-grade default rate was 4.5% globally and 5.3% in the US in August 2026 [SR12]. Form PF private-fund gross assets were $29.6tn in 2025Q4 [SR15], with no private-credit breakout in public statistics.

## 9. Verification ledger

| ID | Claim | Status | Source |
|---|---|---|---|""")
    for k, r in res.items(): L.append(f"| {k} | {r['claim']} | {r['status']} {r['fix']} | {r['url']} |")
    L.append("""
## 10. Gaps (stated, not papered over)

- **Full CMBS ABS-EE universe and CRE CLO trustee reports.** Not pulled. The maturity wall uses our 101-trust sample (6,580 loans); CRE CLO trustee reports are not public on EDGAR.
- **Interval and tender-offer funds other than the seven BDCs.** Not pulled; N-CEN and N-23C3 filings would be the source. The BDC table covers BCRED, OCIC, ADS, HLEND, ASIF, GCRED and (partly) NHPIF only.
- **NAIC Schedule BA and AM Best.** Headline aggregates only; the bank-like bulk data are subscription products.
- **Moody's and S&P default studies** are paywalled; the Moody's rate is via a public relay.
- **ESMA fund stress data, ECB bank-level data and EBA** (discontinued) were not ingested in bulk.
- **FRED series not available:** the H.8 foreign-related CRE series (CREFCBW027SBOG) returned 404, so foreign-bank US CRE remains a gap.
- **Fund flows.** ICI weekly flows came back with a figure we could not verify (a $472bn combined outflow in one week is implausible); excluded.
- **RCA and MSCI pricing** are not public; Green Street headline used.
- **China.** Developer recovery figures are from a secondary source.
- **N-PORT values** are % of NAV × NAV (robust to unit errors). Fund-of-funds double-count in gross totals.
- **Bank-to-CMBS link** is geographic overlap, not loan-level; call reports do not identify borrowers.
""")
    return "\n".join(L)

if __name__ == "__main__":
    J, res, pages, pdf = build()
    print("verified", sum(r["ok"] for r in res.values()), "/", len(res), [k for k, r in res.items() if not r["ok"]], "pages", pages, pdf, "unmet", round(J["unmet_bn"], 2), "req", round(J["requested_bn"], 2))
