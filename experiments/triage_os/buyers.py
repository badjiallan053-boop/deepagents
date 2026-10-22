"""Company-level buyer target list (no individuals). All UNVERIFIED; fit is a hypothesis.

Signals (from world_10k_report): S1 pre-filing watchlist, S2 BDC/CLO marks, S3 CMBS SS/maturity,
S4 cross-border petition calendar, S5 EU bond votes, S6 Ch11 dockets, S7 operational stress, S8 Japan/Asia flash.
"""
import argparse, csv, sqlite3

TYPES = {  # type: (signals, tier, base score, why)
 "distressed_hf": ("S1;S6;S2;S7", "Desk $30k / Global $60k", 90, "Needs earliest pre-filing and docket signals to source trades"),
 "bdc_manager": ("S2;S1;S7", "Desk $30k", 85, "Benchmarks own marks vs peers; early warning on portfolio names"),
 "private_credit": ("S2;S1;S7", "Desk $30k", 82, "Portfolio surveillance and secondary/rescue-financing origination"),
 "clo_manager": ("S2;S1", "Watch $12k / Desk $30k", 78, "CCC-bucket and OC-test management; exit before downgrades"),
 "cre_opportunity": ("S3", "Desk $30k", 80, "Sources discounted CRE loans/notes from special servicing"),
 "restructuring_adviser": ("S1;S4;S5;S6", "Global $60k", 76, "Mandate origination: reach companies before filing"),
 "claims_trader": ("S6;S1;S4", "Watch $12k / Desk $30k", 74, "Trade claims early; needs fresh filings and creditor lists"),
 "litigation_funder": ("S6;S1", "Watch $12k", 62, "Estate and fraud-claim origination"),
 "asia_eu_credit": ("S4;S5;S8", "Global $60k", 72, "Cross-border scheme/petition calendar coverage"),
 "insurer": ("S2;S3;S1", "Desk $30k", 60, "NAIC 5/6 migration risk on private credit and CMBS books"),
 "strategic_acquirer": ("S1;S6;S7", "Watch $12k", 55, "Section 363 and distressed M&A targets"),
}
# (firm, type, region, public url, matched DB situation or '')
FIRMS = [
 # distressed / special sits HF
 ("Elliott Management","distressed_hf","US/UK","https://www.elliottmgmt.com/",""),
 ("Oaktree Capital Management","distressed_hf","US","https://www.oaktreecapital.com/","OCSL holdings (BDC marks)"),
 ("Apollo Global Management","distressed_hf","US","https://www.apollo.com/","MFIC holdings (BDC marks)"),
 ("Centerbridge Partners","distressed_hf","US","https://www.centerbridge.com/",""),
 ("King Street Capital Management","distressed_hf","US/UK","https://www.kingstreet.com/",""),
 ("Silver Point Capital","distressed_hf","US","https://www.silverpointcapital.com/","SCP: Hughes 26-90739 type situations"),
 ("Anchorage Capital Group","distressed_hf","US","https://www.anchoragecap.com/",""),
 ("Monarch Alternative Capital","distressed_hf","US","https://www.monarchlp.com/",""),
 ("Davidson Kempner Capital Management","distressed_hf","US/UK","https://www.davidsonkempner.com/","BayWa / Branicks (EU votes)"),
 ("Canyon Partners","distressed_hf","US","https://www.canyonpartners.com/","Fresno Fashion Fair CMBS"),
 ("Marathon Asset Management","distressed_hf","US","https://www.marathonfund.com/",""),
 ("Whitebox Advisors","distressed_hf","US","https://www.whiteboxadvisors.com/",""),
 ("Mudrick Capital Management","distressed_hf","US","https://www.mudrickcapital.com/","DISH DBS 26-90627"),
 ("Diameter Capital Partners","distressed_hf","US","https://www.diametercap.com/","Hughes 26-90739"),
 ("Sculptor Capital","distressed_hf","US","https://www.sculptor.com/",""),
 ("Redwood Capital Management","distressed_hf","US","https://www.redwoodcap.com/",""),
 ("Owl Creek Asset Management","distressed_hf","US","https://www.owlcreek.com/",""),
 ("Brigade Capital Management","distressed_hf","US","https://www.brigadecapital.com/","Medallia / Peraton loans"),
 ("Arini Capital","distressed_hf","UK","https://www.arini.com/","BayWa hybrid"),
 ("Sona Asset Management","distressed_hf","UK","https://www.sona-am.com/","Branicks bond"),
 ("Attestor","distressed_hf","UK","https://attestor.com/","Rath AG / BayWa"),
 ("Bybrook Capital","distressed_hf","UK","https://www.bybrookcapital.com/","Agile offshore debt"),
 ("Cheyne Capital","distressed_hf","UK","https://www.cheynecapital.com/","EU CRE / Branicks"),
 ("CQS","distressed_hf","UK","https://www.cqs.com/",""),
 ("Polus Capital Management","distressed_hf","UK","https://www.poluscapital.com/","TG Jones"),
 ("Hayfin Capital Management","private_credit","UK","https://www.hayfin.com/","Maxeda"),
 ("ADV Partners","asia_eu_credit","APAC","https://www.advpartners.com/","Zhenro / Agile"),
 ("SC Lowy","asia_eu_credit","APAC","https://www.sclowy.com/","LVGEM / Redsun"),
 ("Pag (Pacific Alliance Group)","asia_eu_credit","APAC","https://www.pag.com/","Kong Hwee / MM2 Asia"),
 ("Nexus Point Capital","asia_eu_credit","APAC","https://www.nexuspointcapital.com/","China SCE new notes"),
 ("Ares SSG","asia_eu_credit","APAC","https://www.aresmgmt.com/","Zentoshin / Toys R Us Japan"),
 ("Tor Investment Management","asia_eu_credit","APAC","https://www.torinvestment.com/","VPower"),
 ("Hamblin Watsa / Fairfax (Asia credit)","asia_eu_credit","APAC","https://www.fairfax.ca/",""),
 ("Clearwater Capital Partners","asia_eu_credit","APAC","https://www.clearwatercp.com/","QPM Energy"),
 ("Keyridge Asset Management","asia_eu_credit","APAC","https://www.keyridge.com/",""),
 ("Värde Partners","distressed_hf","US/EU","https://www.varde.com/","Branicks / EU CRE"),
 ("Bain Capital Credit","private_credit","US","https://www.baincapitalcredit.com/","BCSF holdings"),
 ("Strategic Value Partners","distressed_hf","US/EU","https://www.svpglobal.com/","Rath AG"),
 ("Glendon Capital Management","distressed_hf","US","https://www.glendoncap.com/",""),
 ("Saba Capital Management","distressed_hf","US","https://www.sabacapital.com/","Volta Finance NAV discount"),
 # BDC managers (DB-backed)
 ("Ares Capital (ARCC)","bdc_manager","US","https://www.arescapitalcorp.com/","BDC:ARCC"),
 ("Blackstone Secured Lending (BXSL)","bdc_manager","US","https://www.bxsl.com/","BDC:BXSL"),
 ("FS KKR Capital (FSK)","bdc_manager","US","https://www.fskkradvisor.com/","BDC:FSK"),
 ("Blue Owl Capital Corp (OBDC/OTF)","bdc_manager","US","https://www.blueowlcapitalcorporation.com/","BDC:OBDC"),
 ("Golub Capital BDC (GBDC)","bdc_manager","US","https://www.golubcapitalbdc.com/","BDC:GBDC"),
 ("New Mountain Finance (NMFC)","bdc_manager","US","https://www.newmountainfinance.com/","BDC:NMFC"),
 ("Nuveen Churchill Direct Lending (NCDL)","bdc_manager","US","https://www.nuveen.com/","BDC:NCDL"),
 ("Prospect Capital (PSEC)","bdc_manager","US","https://www.prospectstreet.com/","BDC:PSEC"),
 ("Goldman Sachs BDC (GSBD)","bdc_manager","US","https://www.goldmansachsbdc.com/","BDC:GSBD"),
 ("Sixth Street Specialty Lending (TSLX)","bdc_manager","US","https://www.sixthstreetspecialtylending.com/","BDC:TSLX"),
 ("Main Street Capital (MAIN)","bdc_manager","US","https://www.mainstcapital.com/","BDC:MAIN"),
 ("Hercules Capital (HTGC)","bdc_manager","US","https://www.htgc.com/","BDC:HTGC"),
 ("Oaktree Specialty Lending (OCSL)","bdc_manager","US","https://www.oaktreespecialtylending.com/","BDC:OCSL"),
 ("MidCap Financial Investment (MFIC)","bdc_manager","US","https://www.midcapfinancialic.com/","BDC:MFIC"),
 ("Carlyle Secured Lending (CGBD)","bdc_manager","US","https://www.carlylesecuredlending.com/","BDC:CGBD"),
 ("Barings BDC (BBDC)","bdc_manager","US","https://www.baringsbdc.com/","BDC:BBDC"),
 ("Morgan Stanley Direct Lending (MSDL)","bdc_manager","US","https://www.msdl.com/","BDC:MSDL"),
 ("Kayne Anderson BDC (KBDC)","bdc_manager","US","https://www.kaynebdc.com/","BDC:KBDC"),
 ("CION Investment Corp (CION)","bdc_manager","US","https://www.cionbdc.com/","BDC:CION"),
 ("PennantPark (PFLT/PNNT)","bdc_manager","US","https://www.pennantpark.com/","BDC:PFLT"),
 ("SLR Investment Corp (SLRC)","bdc_manager","US","https://www.slrinvestmentcorp.com/","BDC:SLRC"),
 ("BlackRock TCP Capital (TCPC)","bdc_manager","US","https://www.tcpcapital.com/","BDC:TCPC"),
 ("Gladstone Capital / Investment (GLAD/GAIN)","bdc_manager","US","https://www.gladstonecapital.com/","BDC:GLAD"),
 ("Crescent Capital BDC (CCAP)","bdc_manager","US","https://www.crescentbdc.com/","BDC:CCAP"),
 ("Fidus Investment (FDUS)","bdc_manager","US","https://www.fdus.com/","BDC:FDUS"),
 ("Capital Southwest (CSWC)","bdc_manager","US","https://www.capitalsouthwest.com/","BDC:CSWC"),
 ("WhiteHorse Finance (WHF)","bdc_manager","US","https://www.whitehorsefinance.com/","BDC:WHF"),
 ("Trinity Capital (TRIN)","bdc_manager","US","https://www.trinitycap.com/","BDC:TRIN"),
 ("Runway Growth Finance (RWAY)","bdc_manager","US","https://www.runwaygrowth.com/","BDC:RWAY"),
 ("Palmer Square Capital BDC (PSBD)","bdc_manager","US","https://www.palmersquarebdc.com/","BDC:PSBD"),
 ("Great Elm Capital (GECC)","bdc_manager","US","https://www.greatelmcc.com/","BDC:GECC"),
 ("OFS Capital (OFS)","bdc_manager","US","https://www.ofscapital.com/","BDC:OFS"),
 ("Stellus Capital (SCM)","bdc_manager","US","https://www.stelluscapital.com/","BDC:SCM"),
 ("TriplePoint Venture Growth (TPVG)","bdc_manager","US","https://www.tpvg.com/","BDC:TPVG"),
 ("Horizon Technology Finance (HRZN)","bdc_manager","US","https://www.horizontechfinance.com/","BDC:HRZN"),
 # private credit / CLO
 ("HPS Investment Partners","private_credit","US","https://www.hpspartners.com/",""),
 ("Antares Capital","private_credit","US","https://www.antares.com/","Symplr / Medallia overlap"),
 ("Monroe Capital","private_credit","US","https://www.monroecap.com/",""),
 ("Benefit Street Partners","private_credit","US","https://www.benefitstreetpartners.com/",""),
 ("Twin Brook (AG)","private_credit","US","https://www.twinbrook.com/",""),
 ("Fortress Investment Group","private_credit","US","https://www.fortress.com/","Fresno Fashion Fair CMBS"),
 ("Arcmont Asset Management","private_credit","UK","https://www.arcmont.com/",""),
 ("Pemberton Asset Management","private_credit","UK","https://pembertonam.com/",""),
 ("Tikehau Capital","private_credit","EU","https://www.tikehaucapital.com/","Colisée / France"),
 ("ICG","private_credit","UK","https://www.icgam.com/",""),
 ("Muzinich & Co","private_credit","UK/EU","https://www.muzinich.com/",""),
 ("Alcentra (Franklin Templeton)","clo_manager","UK","https://www.alcentra.com/",""),
 ("CVC Credit","clo_manager","UK/EU","https://www.cvc.com/","Maxeda"),
 ("Blackstone Credit (CLO)","clo_manager","US","https://www.blackstone.com/","Medallia (BXSL)"),
 ("Octagon Credit Investors","clo_manager","US","https://www.octagoncredit.com/",""),
 ("CIFC Asset Management","clo_manager","US","https://www.cifc.com/",""),
 ("Palmer Square Capital Management","clo_manager","US","https://www.palmersquarecap.com/",""),
 ("Neuberger Berman (loan funds)","clo_manager","US","https://www.nb.com/","NFE term loan @59.6 (N-PORT)"),
 ("Invesco Senior Loans","clo_manager","US","https://www.invesco.com/","NFE (N-PORT)"),
 ("Fidelity (floating rate funds)","clo_manager","US","https://www.fidelity.com/","Peraton 1L/2L crossholding"),
 ("Carlyle Global Credit (CLO)","clo_manager","US/EU","https://www.carlyle.com/",""),
 ("Sound Point Capital","clo_manager","US","https://www.soundpointcap.com/",""),
 ("Bain Capital Credit CLO","clo_manager","US","https://www.baincapitalcredit.com/",""),
 ("Volta Finance (AXA IM)","clo_manager","EU","https://www.voltafinance.com/","Volta ~9% NAV discount"),
 ("Blackstone Loan Financing","clo_manager","EU","https://www.blackstone.com/",""),
 # CRE opportunity
 ("Starwood Capital Group","cre_opportunity","US","https://www.starwoodcapital.com/","CMBS SS transfers"),
 ("Rialto Capital","cre_opportunity","US","https://www.rialtocapital.com/","Special servicer exposure"),
 ("LNR Partners","cre_opportunity","US","https://www.lnrpartners.com/",""),
 ("Brookfield Real Estate Credit","cre_opportunity","US","https://www.brookfield.com/","Fresno Fashion Fair"),
 ("Torchlight Investors","cre_opportunity","US","https://www.torchlightinvestors.com/","Benchmark 2025-V17"),
 ("Square Mile Capital","cre_opportunity","US","https://www.squaremilecapital.com/","225 Bush St (SF)"),
 ("Kennedy-Wilson","cre_opportunity","US","https://www.kennedywilson.com/","620 Hudson House"),
 ("Madison Realty Capital","cre_opportunity","US","https://www.madisonrealtycapital.com/","620 Hudson House"),
 ("Ellington Financial","cre_opportunity","US","https://www.ellingtonfinancial.com/","CMBS B-pieces"),
 ("Arbor Realty Trust","cre_opportunity","US","https://www.arbor.com/","Parkmerced (SF)"),
 ("Cain International","cre_opportunity","UK","https://www.cainint.com/","Branicks"),
 ("Cerberus Capital Management","cre_opportunity","US/EU","https://www.cerberus.com/","EU NPL/CRE"),
 ("Lone Star Funds","cre_opportunity","US/EU","https://www.lonestarfunds.com/","Branicks"),
 ("Bain Capital Real Estate","cre_opportunity","US","https://www.baincapitalrealestate.com/",""),
 ("KKR Real Estate Finance","cre_opportunity","US","https://www.kkrreit.com/",""),
 # restructuring advisers / liquidators
 ("Alvarez & Marsal","restructuring_adviser","Global","https://www.alvarezandmarsal.com/","AgWest CCAA monitor"),
 ("FTI Consulting","restructuring_adviser","Global","https://www.fticonsulting.com/","Western Potash"),
 ("AlixPartners","restructuring_adviser","Global","https://www.alixpartners.com/",""),
 ("Houlihan Lokey","restructuring_adviser","Global","https://hl.com/","Hughes noteholders"),
 ("PJT Partners","restructuring_adviser","US/UK","https://www.pjtpartners.com/",""),
 ("Moelis & Company","restructuring_adviser","US/UK","https://www.moelis.com/",""),
 ("Perella Weinberg Partners","restructuring_adviser","US","https://pwpartners.com/",""),
 ("Lazard","restructuring_adviser","Global","https://www.lazard.com/",""),
 ("Kroll","restructuring_adviser","Global","https://www.kroll.com/","Claims agent / UK plans"),
 ("Interpath Advisory","restructuring_adviser","UK","https://www.interpath.com/","TG Jones / Iguanas"),
 ("Teneo","restructuring_adviser","UK","https://www.teneo.com/",""),
 ("Grant Thornton (restructuring)","restructuring_adviser","Global","https://www.grantthornton.global/",""),
 ("Borrelli Walsh / Kroll APAC","restructuring_adviser","APAC","https://www.kroll.com/","Zhenro / LVGEM"),
 ("KPMG Restructuring","restructuring_adviser","Global","https://kpmg.com/","Kong Hwee JM"),
 ("Deloitte Restructuring","restructuring_adviser","Global","https://www.deloitte.com/","MM2 Asia"),
 ("Ernst & Young (Turnaround)","restructuring_adviser","Global","https://www.ey.com/","Gumpert CCAA"),
 ("PwC Business Restructuring","restructuring_adviser","Global","https://www.pwc.com/",""),
 ("Raymond Chabot","restructuring_adviser","CA","https://www.rcgt.com/","Goodfood CCAA"),
 ("Ankura","restructuring_adviser","US","https://ankura.com/",""),
 ("Riveron","restructuring_adviser","US","https://riveron.com/","True Food Kitchen"),
 # claims traders / lit funders
 ("Cherokee Acquisition","claims_trader","US","https://www.cherokeeacquisition.com/","DISH DBS claims"),
 ("Argo Partners","claims_trader","US","https://www.argopartners.net/","True Food Kitchen claims"),
 ("Bradford Capital","claims_trader","US","https://www.bradfordcapitalmgmt.com/",""),
 ("Hain Capital Group","claims_trader","US","https://www.haincapital.com/",""),
 ("Contrarian Capital Management","claims_trader","US","https://www.contrariancapital.com/","Hughes 26-90739"),
 ("Fair Harbor Capital","claims_trader","US","https://www.fairharborcapital.com/",""),
 ("Burford Capital","litigation_funder","US/UK","https://www.burfordcapital.com/","Zentoshin fraud estate"),
 ("Omni Bridgeway","litigation_funder","APAC","https://omnibridgeway.com/","QPM / Zentoshin"),
 ("Harbour Litigation Funding","litigation_funder","UK","https://www.harbourlitigationfunding.com/",""),
 ("Therium Capital","litigation_funder","UK","https://www.therium.com/",""),
 ("Fortress Legal Assets","litigation_funder","US","https://www.fortress.com/",""),
 # insurers / strategics
 ("Athene (Apollo)","insurer","US","https://www.athene.com/","Private credit NAIC migration"),
 ("Brighthouse Financial","insurer","US","https://www.brighthousefinancial.com/","CMBS exposure"),
 ("MetLife Investment Management","insurer","US","https://investments.metlife.com/","CRE loans"),
 ("Allianz Global Investors","insurer","EU","https://www.allianzgi.com/","Branicks"),
 ("Swiss Re (credit solutions)","insurer","EU","https://www.swissre.com/",""),
 ("Atradius","insurer","EU","https://group.atradius.com/","Trade credit: Rath / BayWa"),
 ("Allianz Trade","insurer","EU","https://www.allianz-trade.com/","Trade credit: TG Jones"),
 ("Coface","insurer","EU","https://www.coface.com/","France BODACC flow"),
 ("Hilco Global","strategic_acquirer","US/UK","https://www.hilcoglobal.com/","TG Jones / True Food Kitchen"),
 ("Gordon Brothers","strategic_acquirer","US/UK","https://www.gordonbrothers.com/","Chain Reaction Cycles USA"),
 ("Authentic Brands Group","strategic_acquirer","US","https://www.authentic.com/","Retail 363 sales"),
 ("EchoStar","strategic_acquirer","US","https://www.echostar.com/","Hughes 26-90739"),
]

def bdc_match(con, ticker):
    r = con.execute("""select borrower, mark, source_url from bdc_marks where bdc=? and period='2026-06-30' and par>1e6
        and mark is not null order by mark asc limit 1""", (ticker,)).fetchone()
    return r

def build(db, out):
    con = sqlite3.connect(db) if db else None
    rows = []
    for firm, t, region, url, match in FIRMS:
        sig, tier, score, why = TYPES[t]
        evidence = url
        if match.startswith("BDC:") and con:
            r = bdc_match(con, match[4:])
            if r:
                match = f"Lowest Q2-26 mark: {r[0]} @ {r[1]:.1f}"; evidence = r[2]; score += 5
        elif match:
            match = "fit hypothesis (holding NOT evidenced): " + match
        rows.append({"firm": firm, "type": t, "region": region, "signals": sig, "price_tier": tier,
                     "why": why, "db_match": match, "data_buying_evidence": "not yet checked (no vendor case study pulled)",
                     "evidence_url": evidence, "score": score, "src_date": "2026-10-22", "status": "UNVERIFIED"})
    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows, 1): r["rank"] = i
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["rank"] + [k for k in rows[0] if k != "rank"]); w.writeheader(); w.writerows(rows)
    return rows

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--db"); ap.add_argument("--out", required=True); a = ap.parse_args()
    print(len(build(a.db, a.out)), "buyers")
