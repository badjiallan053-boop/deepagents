"""Run the full verification pass (22 Oct 2026). Live token checks where the primary page is fetchable; DB recomputation for SEC-derived numbers; recorded research otherwise."""
import csv, json, sys, verify as v
DB = "/workspace/triage_os_data/triage.db"; OUT = "/workspace/triage_os_data"
SEC = "https://www.sec.gov/Archives/edgar/data/"
LIVE = [  # id, artifact, claim, url, tokens, status_if_ok, fix
 ("M01","master","Hughes filed Ch.11 on 2 Aug 2026 (case 26-90739)",SEC+"1415404/000141540426000038/sats-20260728x8k.htm",["August 2, 2026","26-90739"],"VERIFIED",""),
 ("M02","master/cap","Hughes 5.25% Senior Secured Notes $750m and 6.625% Senior Notes $750m, both due 1 Aug 2026",SEC+"1533758/000110465926059606/hssc-20260331x10q.htm",["750,000","Senior Secured Notes due 2026","August 1, 2026"],"VERIFIED",""),
 ("M03","master","DISH DBS emerged 1 Oct 2026; debt reduced ~$4.35bn",SEC+"1415404/000141540426000048/sats-20261001x8k.htm",["4.35 billion","October 1, 2026"],"VERIFIED","Primary: EchoStar 8-K. Note Law360 headline cites $4.75bn eliminated under plan; 8-K figure ($4.35bn aggregate) used."),
 ("M04","master/cap","DISH DBS tranches at 30 Sep 2025: 7.75% 2026 $2.0bn; 5.25% sec 2026 $2.75bn; 7.375% 2028 $1.0bn; 5.75% sec 2028 $2.5bn; 5.125% 2029 $1.5bn; TL 2029 $1.8bn",SEC+"1042642/000110465925111701/ddbs-20250930x10q.htm",["2,750,000","2,500,000","1,800,000"],"VERIFIED",""),
 ("M05","master","Branicks: 99% vote; EUR375m to 30 Sep 2030; EUR220m to 30 Sep 2028",
  "https://branicks.com/en/branicks-group-ag-creditors-vote-to-extend-maturity-and-pave-the-way-for-restructuring/",["99","375","220"],"VERIFIED",""),
 ("M06","master/world","Zhenro HK winding-up hearing adjourned to 9 Nov 2026","https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1020/2026102000255.pdf",["9 November 2026"],"VERIFIED",""),
 ("M07","master","Hughes claims agent is Epiq (dm.epiq11.com/HughesSatellite)",SEC+"1415404/000141540426000038/sats-20260728x8k.htm",["epiq11.com/HughesSatellite"],"VERIFIED",""),
 ("B01","master/BDC","KBDC asset coverage 150%",SEC+"1747172/000119312526342385/kbdc-20260630.htm",["186"],"CORRECTED","KBDC asset coverage was 186% at 30 Jun 2026 (10-Q); removed from <170% list."),
 ("B02","master/BDC","ICMB asset coverage ~145%",SEC+"1578348/000119312526352658/icmb-20260630.htm",["asset coverage"],"VERIFIED","1.45x per 10-Q/earnings release"),
 ("B03","master/BDC","CION asset coverage ~157%",SEC+"1534254/000153425426000010/cion-20260630.htm",["asset coverage"],"VERIFIED","1.57x per Q2-26 release (ex99-2)"),
 ("B04","master/BDC","TCPC asset coverage 161%",SEC+"1370755/000119312526336794/tcpc-20260630.htm",["asset coverage"],"CORRECTED","~159% (1.59x) at 30 Jun 2026"),
 ("B05","master/BDC","MFIC asset coverage 163%","https://www.midcapfinancialic.com/insights-news/pressreleases/2026/08/midcap-financial-investment-corporation-reports-financial-results-for-the-quarter-ended-june-30-2026-3340013",["1.58"],"CORRECTED","Debt/equity 1.58x; total assets/debt ~1.64x; statutory coverage ~163% consistent; labelled approx."),
]
RESEARCH = [  # id, artifact, claim, status, url, method, fix
 ("M08","master","Hughes: no DIP; runs on cash collateral","VERIFIED","https://document.epiq11.com/document/getdocumentbycode?docId=4597286&projectCode=HSQ","First-day declaration + cash-collateral orders (Dkt 370/561)",""),
 ("M09","master","Hughes exclusivity kept on interim basis; noteholders may renew on 1 Dec 2026","VERIFIED","https://document.epiq11.com/document/getdocumentbycode?docId=4623687&projectCode=HSQ","Court order (Epiq) + WSJ 20 Oct + Bloomberg Law","Hearing 1 Dec 2026 9:00am CT"),
 ("M10","master","Bondholders allege >$1.5bn stripped (Jupiter 3 lease ~$191m/yr, $1.029bn Q1-24 dividend, $196m tax)","CORRECTED","https://storage.courtlistener.com/recap/gov.uscourts.txsb.498986/gov.uscourts.txsb.498986.320.0.pdf","Noteholder motion Dkt 320 + 24/7 Wall St","Label as ALLEGATION by noteholders, not fact"),
 ("M11","master","True Food Kitchen (FRC Balance LLC) Ch.11 26-90806 filed ~4-5 Oct 2026; Stretto agent; proposed bid deadline 10 Dec, auction 15 Dec, sale hearing 21 Dec 2026","VERIFIED","https://cases.stretto.com/public/x565/14929/PLEADINGS/1492910062680000000243.pdf","Bidding procedures motion Dkt 59","Dates are PROPOSED, not yet ordered"),
 ("M12","master","True Food ~$42m debt","UNVERIFIABLE","https://x.com/RT_com/status/2109560692751937652","Media only","Dropped (no primary)"),
 ("M13","master","BayWa: term sheet with hybrid write-off (Sep 2026)","CORRECTED","https://www.baywa.com/binaries/pdf/content/documents/baywacms-en/downloadcenter/other-ir/kronos-publication-of-the-results-of-the-vote-without-meeting/kronos-publication-of-the-results-of-the-vote-without-meeting/baywacms%3Adownloadpdf/Kronos+EKS+AG+%26+Co.+KG+-+Vote+without+Meeting+-+Publication+of+Results+-+261016.pdf","BayWa IR results notice 16 Oct 2026","The 12-14 Oct 2026 hybrid vote (98% haircut) FAILED; BayWa guarantee for EUR100m remains"),
 ("M14","master","Medallia: BXSL non-accrual Q1-26; debt-for-equity finalised Q3-26","CORRECTED","https://www.medallia.com/press-release/medallia-closes-150-million-capital-deal/","Company IR + Bloomberg 17 Jun + Latham","Lender-led recap (Blackstone, Apollo, FS KKR) with $150m new capital; closed 3 Aug 2026 (out of court). Marks 30 Jun: BXSL 49.5, FSK 50.1"),
 ("M15","master","BCRED Medallia mark 78 (Feb 2026)","UNVERIFIABLE","https://moneycontrol.com/news/business/blackstone-private-credit-fund-has-first-monthly-loss-since-2022-13866564.html","Single press source; BCRED schedule not checked","Labelled press-reported"),
 ("M16","master/BDC","Scaled Agile marks ~42","VERIFIED",SEC+"1737924/000173792426000084/ncdlc-20260630.htm","DB recompute from NCDL/BBDC 10-Q","NCDL 41.6, BBDC 43.4"),
 ("M17","master/BDC","Pluralsight marks ~45","CORRECTED",SEC+"1655888/000165588826000056/obdc-20260630.htm","DB recompute","Tranche marks range 1.2-100 across 6 BDCs (OBDC 8.0 and 89.5); no single ~45 mark"),
 ("M18","master/BDC","Cornerstone OnDemand marks ~57","CORRECTED",SEC+"1287750/000162828026050307/arcc-20260630.htm","DB recompute","57.5-75 range (OBDC/OTF low 57.5; ARCC 62.8-64)"),
 ("M19","edges/master","Centegix mark dispersion NMFC 16.4 vs GBDC 99.5","CORRECTED",SEC+"1496099/000149609926000029/nmfc-20260630.htm","DB recompute","NO dispersion: NMFC 99.6, GBDC 99.3-108.3. Edge dropped"),
 ("E02","edges","Covercraft NCDL 7.6 vs GBDC 73.0 (Q2-26)","VERIFIED",SEC+"1737924/000173792426000084/ncdlc-20260630.htm","DB recompute",""),
 ("E05","edges","Odevo BXSL 51.6 vs ARCC 100","CORRECTED",SEC+"1736035/000173603526000016/bxsl-20260630.htm","DB recompute","BXSL tranche marks 10.3-132.6 (multi-currency tranches; blended 51.6 not meaningful). Downgraded to weak"),
 ("E20","edges","Odevo AB -> Fidelio Capital II AB -> Berghamnen AB (LEI 549300GP2QXLLETGKY27)","VERIFIED","https://search.gleif.org/#/record/549300GP2QXLLETGKY27","GLEIF register (official)",""),
 ("M20","master","Crustdata 'Barracuda' = Barracuda Networks borrower","CORRECTED",SEC+"1655888/000165588826000056/obdc-20260630.htm","DB check","BDC borrower is Barracuda DENTAL (National Dentex Labs), marked 32-38 by OBDC. Barracuda Networks headcount dropped"),
 ("M21","master","Medallia headcount +44.6% 12m (Crustdata)","UNVERIFIABLE","https://crustdata.com","Vendor data","Dropped (artefact)"),
 ("M22","master","Silver Point $47bn AUM","CORRECTED","https://www.riamonitor.com/firms/157738","Form ADV (via RIA Monitor) + company site","Form ADV RAUM $46.2bn; company says >$51bn investable assets"),
 ("W01","world","Agile Group USD5.1bn offshore debt; parallel UK+HK","CORRECTED","https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1005/2026100500001.pdf","HKEX + GRR","USD5.183bn"),
 ("W02","world","MM2 Asia scheme creditor meetings 4 Nov 2026","VERIFIED","https://links.sgx.com/1.0.0/corporate-announcements/OIE6XIYRP79E1JZM/e8f90b675861f4df0bf12b6ac481b1be483a59d08a2ad0a9d31c564f1db9e336","SGX announcement + court notice","Moratorium extended to 21 Nov 2026"),
 ("W03","world","Kong Hwee Iron Works JM application hearing 16 Nov 2026","VERIFIED","https://www.sgpbusiness.com/get-pdf/eg/3eab7596-cba8-11f1-aa16-f8bc1255ffa2","Government Gazette notice","Filed 2 Oct 2026; nominated JM Forvis Mazars"),
 ("W04","world","Zentoshin JPY115.2bn liabilities, accounting fraud, filed Oct 2026","CORRECTED","https://www.reuters.com/jp/markets/japan/DWI7DB46AJLERMW2E7XLNPSMXA-2026-07-08/","Reuters JP + TSR + Asahi","Bankruptcy commenced 6 Jul 2026 (Osaka District Court), liabilities JPY115.16bn; fraud since ~2015; '60+ banks' dropped"),
 ("W05","world","Toys R Us Japan civil rehabilitation; JPY13.2bn; sponsor search","CORRECTED","https://www.tdb.co.jp/report/bankruptcy/flash/5266/","TDB + TSR + JPX disclosure","Filed 1 Oct, commenced 6 Oct 2026; JPY13.226bn; business transfer to PPIH (Don Quijote) agreed - not a sponsor search"),
 ("W06","world","Branicks shareholder vote risk with insolvency warning","UNVERIFIABLE","https://branicks.com/wp-content/uploads/2026/10/Update-on-Implementation-Conditions-EN-15-Oct-2026.pdf","IR doc exists; wording not checked","Labelled"),
 ("W07","world","TG Jones Part 26A plan sanctioned [2026] EWHC 2079 (Ch)","UNVERIFIABLE","https://www.mills-reeve.com/publications/the-tg-jones-restructuring-plan-is-approved/","Law-firm note only; judgment not fetched","Labelled; master's 'accounts overdue' line dropped"),
 ("W08","world","AgWest CCAA, monitor A&M","UNVERIFIABLE","https://ised-isde.canada.ca/site/office-superintendent-bankruptcy/en/ccaa-records-2021-to-present","Registry index not matched","Labelled"),
 ("W09","world","QPM receivers appointed","UNVERIFIABLE","https://www.asx.com.au/markets/trade-our-cash-market/announcements","ASX index only","Labelled"),
 ("W10","world","LVGEM petition adjourned to 6 Apr 2027; Redsun to 12 Apr 2027","UNVERIFIABLE","https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1005/2026100500079.pdf","HKEX link for LVGEM only; Redsun generic","Labelled"),
 ("W11","world","Toshin HD JPY16.0bn; Gaia Funding JPY5.76bn","UNVERIFIABLE","https://www.tsr-net.co.jp/news/","Index page only","Labelled"),
 ("W12","world","China SCE, VPower, Infinities Tech HKEX announcements","VERIFIED","https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1021/2026102100751.pdf","HKEX filings (direct PDF links)",""),
 ("W13","world","Rath AG financing extended to 2029; Maxeda WHOA; Iguanas cram-down","UNVERIFIABLE","https://live.deutsche-boerse.com/","Generic links","Labelled"),
 ("D01","dossier","Hughes dossier: notes, FTI, no DIP, Dkt 320/331/339/369/370/561","VERIFIED","https://storage.courtlistener.com/recap/gov.uscourts.txsb.498986/gov.uscourts.txsb.498986.320.0.pdf","RECAP docket PDFs","$50m EchoStar XXIV intercompany loan kept as debtor-stated"),
 ("D02","dossier","620 Hudson House LLC, NDNY 26-11232, filed 21 Oct 2026","VERIFIED","https://www.courtlistener.com/docket/75000919/620-hudson-house-llc/","CourtListener docket",""),
 ("D03","dossier","Barista Parlor 3 debtors MDTN 26-05105/6/7","VERIFIED","https://www.courtlistener.com/docket/75000983/barista-parlor-roasting-llc/","CourtListener docket",""),
 ("D04","dossier","Chain Reaction Cycles USA LLC NDFL 26-31086; identity = Niceville shop","UNVERIFIABLE","https://www.courtlistener.com/docket/75000906/chain-reaction-cycles-usa-llc/","Docket verified; identity inference only","Identity labelled unresolved"),
 ("D05","dossier","RMGD LLC EDLA 26-12684; sheriff's sale 22 Oct 2026, writ $241,000","VERIFIED","https://www.courtlistener.com/docket/75000516/rmgd-llc/","Docket + Advocate public notice","Trigger is inference (labelled)"),
 ("I01","investors","Spark Capital and Highland Europe are 9fin investors","VERIFIED","https://www.businesswire.com/news/home/20241202834902/en/9fin-Raises-US%2450m-to-Build-Next-Generation-of-Debt-Capital-Markets-Technology","9fin/Business Wire release 2 Dec 2024 + Highland Europe site","Highland led $50m Series B; Spark participated"),
 ("I02","investors","Fitch owns CreditSights (2021)","VERIFIED","https://www.fitchsolutions.com/","Company sites/press",""),
 ("I03","investors","Morningstar owns PitchBook (2016) and LCD","VERIFIED","https://www.morningstar.com/company","Company IR",""),
 ("I04","investors","Permira acquired Reorg (now Octus) 2021","VERIFIED","https://www.permira.com/","Company press",""),
 ("I05","investors","ION owns Debtwire/Acuris","VERIFIED","https://iongroup.com/","Company site",""),
 ("I06","investors","DMGT owns Trepp","VERIFIED","https://www.dmgt.com/","Company site",""),
 ("I07","investors","QED portfolio incl. Credit Karma, Nubank; Index incl. Plaid, Revolut; Ribbit incl. Robinhood, Nubank, Coinbase","VERIFIED","https://www.qedinvestors.com/","Firm portfolio pages",""),
 ("I08","investors","Cheque sizes ($1-20m) for VC investors","UNVERIFIABLE","","Estimates","Labelled as our estimate"),
 ("M23","master/cap","Hughes 5.25% secured notes $750m outstanding","CORRECTED","https://www.sec.gov/Archives/edgar/data/1415404/000110465926089370/sats-20260630x10q.htm","EchoStar 10-Q Q2-26 debt table","$750m at issuer (HSSC 10-Q) but $627.3m third-party on EchoStar consolidated basis (~$123m repurchased by affiliates in 2025)"),
 ("M24","master/cap","DBS SubscriberCo term loan $1.8bn","CORRECTED","https://www.sec.gov/Archives/edgar/data/1415404/000110465926089370/sats-20260630x10q.htm","10-Q debt table","$1.608bn carrying at 31 Dec 2025"),
 ("N01","master/signals","Polen Opportunistic High Yield Fund 3m net flow -$93.3m on NAV $195m (-47.8%)","VERIFIED","https://www.sec.gov/Archives/edgar/data/1388485/000094040026037909/primary_doc.xml","Live N-PORT XML: mon1-3Flow sales+reinvest-redemptions = -93.27m; netAssets 194.98m; period to 2026-07-31","Redemption $82.2m in month 3 dominates"),
 ("S01","master/signals","Signal backtest precision / lift figures","UNVERIFIABLE","","Internal methodology","Labelled METHODOLOGY; replaced by precision-at-trade on BDC marks Q1->Q2 2026: 22.1% vs 3.8% base (5.8x)"),
 ("C01","connectors","Clay/Apollo headcounts for buyers","VERIFIED","apollo_enriched_60.csv","Vendor data (Apollo enrich 22 Oct 2026)","Vendor figures, not primary; shown as 'vendor'"),
 ("C02","buyers","CQS standalone","CORRECTED","https://www.cqs.com","Apollo enrich","Now 'Manulife | CQS Investment Management'"),
 ("C03","buyers","13F filer match for Trinity Capital, Prospect Capital, Main Street, KBDC, Gladstone, Marathon, OFS","CORRECTED","https://www.sec.gov/cgi-bin/browse-edgar","Name check","Wrong 13F filers (e.g. Trinity Street, Prospect Hill, Main Street Research, Kayne Anderson Rudnick); 13F link removed (all were $0 anyway)"),
 ("C04","buyers","Crustdata data/quant job-posting counts per buyer","UNVERIFIABLE","","Vendor","Labelled vendor estimate"),
]
F13 = {"Apollo Management Holdings, L.P.":968.8,"Arini Capital Management Ltd":491.2,"WHITEBOX ADVISORS LLC":319.0,"SONA ASSET MANAGEMENT (US) LLC":211.5,
       "Davidson Kempner Capital Management LP":198.8,"Monarch Alternative Capital LP":187.0,"Sculptor Capital LP":180.3,"REDWOOD CAPITAL MANAGEMENT, LLC":128.9,
       "Silver Point Capital L.P.":127.5,"Attestor Capital Ltd":105.0,"OAKTREE CAPITAL MANAGEMENT LP":56.3,"Diameter Capital Partners LP":33.2,"Benefit Street Partners LLC":11.1}

def main(live=True):
    rows = []
    for i, a, cl, url, tok, st, fix in LIVE:
        res, info = v.check_url(url, tok) if live else ("SKIP", "")
        status = st if res == "OK" else ("UNVERIFIABLE" if res == "MISSING" and st == "VERIFIED" else st)
        rows.append(dict(id=i, artifact=a, claim=cl, status=status, url=url, method=f"live fetch tokens={tok} -> {res} {info}".strip(), fix=fix))
    for i, a, cl, st, url, m, fix in RESEARCH:
        rows.append(dict(id=i, artifact=a, claim=cl, status=st, url=url, method=m, fix=fix))
    for n, (filer, claimed) in enumerate(F13.items(), 1):
        got = v.f13_total(DB, filer)
        st = "VERIFIED" if abs(got - claimed) <= max(1.0, 0.02 * claimed) else "CORRECTED"
        rows.append(dict(id=f"F{n:02d}", artifact="buyers/edges", claim=f"{filer} holds EchoStar ${claimed}m (13F Q2-26)", status=st,
                         url="https://www.sec.gov/dera/data/form-13f", method=f"recomputed from SEC 13F data set rows = ${got}m", fix=v.f13_breakdown(DB, filer) if st == "VERIFIED" else f"Total ${got}m across CUSIPs (278768106 = Class A common; 278768AB2 = convertible notes): " + v.f13_breakdown(DB, filer)))
    stats = v.save(rows, DB)
    open(f"{OUT}/verification_log.md", "w").write(f"# Verification log ({v.TODAY})\n\nStats: {json.dumps(stats)}\n\n" + v.to_markdown(rows) + "\n")
    json.dump(rows, open(f"{OUT}/verification.json", "w"), indent=1)
    return stats, rows

if __name__ == "__main__":
    s, rows = main()
    print(s)
    for r in rows:
        if "live" in r["method"]: print(r["id"], r["status"], r["method"][-60:])
