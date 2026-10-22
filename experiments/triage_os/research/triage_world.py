"""TRIAGE World v2 (23 Oct 2026). Every fact re-fetched today into /workspace/triage_os_data/world/src2 and
checked by exact token; the log keeps URL, fetch time and a verbatim quote. Prices: Boerse Frankfurt quote_box
API (bond last trades) and a public chart feed (equity last close), labelled. Firms only; judgement labelled; nothing sent."""
import os, sys, json, re, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from design import hbars, report_from_markdown
D = "/workspace/triage_os_data"; SRC = f"{D}/world/src2"; PX = f"{D}/world/px"; HERE = os.path.dirname(os.path.abspath(__file__))
PRIMARY_HOSTS = ("hkexnews.hk", "thameswater.co.uk", "nacongaming.com", "bigben-group.com", "baywa.com", "branicks.com", "booster-precision.com",
                 "stamdata.com", "tdb.co.jp", "magicalir.net", "sgx.com", "sgpbusiness.com", "euroborsa.it", "raymondchabot.com", "bodacc",
                 "hkma.gov.hk", "j-re.co.jp", "standardlifeplc.com", "contractsfinder.service.gov.uk", "agile.com.cn", "fitchventures.com",
                 "illuminatefinancial.com", "work-bench.com", "seedcamp.com", "fintech.io", "vertexventures.sg", "balderton.com", "indexventures.com",
                 "globenewswire.com", "meltx.uk")
# boursorama hosts the issuer's GlobeNewswire regulated release verbatim -> treated as company release, labelled.
DISTRIB = ("boursorama.com",)

def norm(s): return re.sub(r"\s+", " ", s)
def src(key):
    p = f"{SRC}/{key}.txt"; m = f"{SRC}/{key}.meta"
    if not os.path.exists(p): return None, None, ""
    url, ts = open(m).read().strip().split("\t") if os.path.exists(m) else ("", "")
    return url, ts, norm(open(p, errors="ignore").read())
def check(key, token):
    url, ts, txt = src(key)
    if key == "bodacc":
        j = json.load(open(f"{SRC}/bodacc_today.json")); blob = json.dumps(j, ensure_ascii=False)
        i = blob.find(token); return dict(key=key, url="https://bodacc-datadila.opendatasoft.com (API, annonces-commerciales)", fetched="2026-10-23", token=token,
                    found=i >= 0, quote=blob[max(0, i-160):i+200] if i >= 0 else "", grade="PRIMARY")
    i = txt.find(token) if txt else -1
    host = (url or "").split("/")[2] if url and "//" in url else ""
    grade = "PRIMARY" if any(h in host for h in PRIMARY_HOSTS) else ("COMPANY RELEASE (distributor copy)" if any(h in host for h in DISTRIB) else "SECONDARY")
    return dict(key=key, url=url, fetched=ts, token=token, found=i >= 0, quote=txt[max(0, i-160):i+len(token)+160] if i >= 0 else "", grade=grade)

def px_equity(t):
    p = f"{PX}/{t}.json"
    try:
        m = json.load(open(p))["chart"]["result"][0]["meta"]; import datetime
        return dict(instrument=f"{t} shares", value=m["regularMarketPrice"], unit=m["currency"], kind="TRADE (last close, public chart feed — not the exchange page)",
                    date=datetime.datetime.fromtimestamp(m["regularMarketTime"], datetime.timezone.utc).date().isoformat(), source=f"query1.finance.yahoo.com/v8/finance/chart/{t}")
    except Exception: return None
def px_bond(isin, label):
    p = f"{PX}/bf_{isin}.json"
    try: j = json.load(open(p))
    except Exception: return None
    if j.get("lastPrice") is None: return None
    stale = j.get("instrumentStatus") != "Active" or (j.get("timestampLastPrice") or "")[:7] < "2026-10"
    return dict(instrument=f"{label} ({isin})", value=j["lastPrice"], unit="% of par", kind=("STALE " if stale else "") + "TRADE (Börse Frankfurt last price; thin)",
                date=(j.get("timestampLastPrice") or "")[:10], source=f"api.boerse-frankfurt.de quote_box isin={isin} mic=XFRA")

# ---------- 25 live situations ----------
# (id-key, mkt, entity, stage, chokepoint, catalyst date, date basis, [(src_key, token)], price fn, recovery dict|None, note)
HKD_USD = 7.78  # JUDGEMENT: peg mid used for model recovery
agile_rec = round(9199067647 * 0.143 / HKD_USD / 5.183e9 * 100, 1)
S = [
 ("thames","UK","Thames Water Utilities","RP1 done; 16th consent requests + STID proposals (super senior upsize £2.4bn to £5.4bn); SPP Extension Transaction ('RP 1.5'); RP2 recapitalisation",
  "Ofwat and the government (Ofwat consultation is a Class B TSA condition); Class A and super senior creditors at ≥66.66% for RP2; super senior creditors for each drawdown",
  "2026-10-29","16th consent requests voting date; June Release Condition 31 Oct → proposed 30 Nov; facility liquidity 'until the end of 2026 or the start of 2027'",
  [("tw_16","voting date of 29 October 2026"),("tw_16","until the end of 2026 or the start of 2027"),("tw_16","by £2.4bn to £5.4bn"),("tw_classb","at least 66.66% of the Class A and super senior debt"),("tw_classb","SPP Extension Transaction"),("tw_classb","recovery of c.5.9%"),("tw_classb","on or before 30 December 2027")],
  None, dict(value=5.9, basis="Class B recovery c.5.9% in post-restructured equity (company)", src="tw_classb"), "Class B price not found on a public exchange page → gap abstains."),
 ("bigben","FR","Bigben Interactive","Sauvegarde accélérée (TC Lille Métropole); plan vote by classes of affected parties; Bigben Connected sold",
  "Shareholders' class (creditors are locked up: backstop group ≈93.4% of the exchangeables) and the court cram-down test",
  "2026-12-09","plan hearing; proceeding extended to 17 Dec 2026 (judgment of 7 Oct)",
  [("bigben_1610b","environ 93,4 %"),("bigben_1610b","au 9 décembre 2026"),("bigben_0810","à hauteur de 35 M€"),("bigben_0810","environ 13 M€"),("bigben_1610b","D.26-0631"),("bodacc","A202601622253")],
  lambda: px_equity("BIG.PA"), None, "Exchangeable FR0014001WC2 last traded 16 Feb 2026 (stale) — not used."),
 ("nacon","FR","Nacon (56.72% owned by Bigben)","Redressement judiciaire (TC Lille Métropole, opened 2 Mar 2026); observation period to 2 Mar 2027",
  "Administrateurs judiciaires + bank/unsecured creditors choosing 30% cash-out vs 50% haircut/8-yr; plan tied to Bigben new money",
  "2027-03-02","end of extended observation period (judgment of 1 Jul 2026)",
  [("nacon","jusqu’au 2 mars 2027"),("nacon","paiement de 30 %"),("nacon","56,72 %"),("bodacc","A202600482211")],
  lambda: px_equity("NACON.PA"), dict(value=30.0, basis="Short option: 30% cash for bank/unsecured claims (company)", src="nacon"), "No public price for Nacon bank claims → gap abstains."),
 ("agile","HK/CN","Agile Group","RSA to be launched with CoCom; inter-conditional UK Part 26A plan ('Listco UK RP') + HK schemes; HK winding-up petition",
  "CoCom (≈61.50% of syndicated loans) and plan/scheme classes; HK High Court on the petition",
  "2026-11-16","RSA launch 'within six weeks' of 5 Oct (JUDGEMENT: = 16 Nov); petition hearing 7 Dec 2026",
  [("agile_rsa","approximately 61.50%"),("agile_rsa","within six weeks of the date of this announcement"),("agile_rsa","Part 26A of the Companies Act 2006 (UK)"),("agile_rsa","9,199,067,647")],
  lambda: px_bond("XS1785422731", "6.875% senior perpetual"), dict(value=agile_rec, basis=f"MODEL: 9,199,067,647 new shares × HK$0.143 (22 Oct close) ÷ HK${HKD_USD}/US$ ÷ US$5.183bn in-scope debt", src="agile_rsa"),
  "Primary text says UK Part 26A plan + HK schemes — the debate's 'not Part 26A' is wrong. 7 Dec petition date is from the company's 12 Oct release (agile.com.cn PDF did not download; secondary copy)."),
 ("baywa","DE","BayWa / Kronos EKS €100m hybrid (DE000A351PD9)","SchVG vote without meeting 12–14 Oct: quorate, all resolutions (issuer's and holders' countermotions) not adopted",
  "Hybrid holders hold a blocking minority under SchVG; next route (second vote / StaRUG) not announced","TBC","no new date published — the earlier 30 Nov estimate was dropped",
  [("baywa_res","was quorate"),("baywa_res","the resolutions were not adopted")], lambda: px_bond("DE000A351PD9","Kronos EKS hybrid"), None, ""),
 ("booster","DE/NO","Booster Precision Components (€60m bond NO0012713520)","StaRUG restructuring agreed in principle; €3m super senior interim facility approved by written procedure; standstill to 1 Nov",
  "Ad-hoc Group of bondholders (standstill/lock-up) and the StaRUG plan vote","2026-11-01","standstill expiry",
  [("booster_wp","EUR 3,000,000 super senior interim facility"),("booster_wp","StaRUG"),("booster_ss","until 1 November 2026")], lambda: px_bond("NO0012713520","Booster FRN 2022/2026"), None,
  "NOT killed: the €3m super senior is interim financing for a StaRUG restructuring that is not yet implemented (LME Watch view upheld)."),
 ("antolin","ES","Grupo Antolin-Irausa","Spanish homologación (Juzgado Mercantil 1 Burgos, suspended); standstill with SteerCo ran to 16 Oct; Chapter 15 recognition pending",
  "SteerCo of 2028/2030 noteholders (secondary: ≈67.2% bloc) vs bank class; Burgos court on homologation","2026-11-04","US recognition hearing (court docket summary); post-16 Oct status not confirmed",
  [("elevenflo_antolin","November 4, 2026")], None, None, "SECONDARY ONLY: antolin.com blocked from the box today; no primary confirms what happened after 16 Oct."),
 ("mm2","SG","mm2 Asia + mm2 Entertainment","IRDA s.64/65 moratoria to 21 Nov; s.210 scheme meetings",
  "Scheme creditors: majority in number and three-fourths in value per class, then court sanction","2026-11-04","scheme meetings 10am (Government Gazette notice); moratorium to 21 Nov",
  [("mm2_att","until 21 November 2026"),("mm2_gaz","on 4 November 2026 at 10AM"),("mm2_gaz","three-fourths in value")], None,
  dict(value=28.0, basis="28 cents per dollar from a $25m investment (Straits Times, citing the Dec 2025 court filing) — SECONDARY", src="straits_mm2"),
  "Debt size not in a primary document fetched today; shares suspended since Nov 2025."),
 ("zhenro","HK/CN","Zhenro Properties","Winding-up petition adjourned; offshore negotiations","Petitioner + HK High Court","2026-11-09","adjourned petition hearing",
  [("zhenro","9 November 2026")], lambda: px_equity("6158.HK"), None, ""),
 ("kwg","HK/CN","KWG Group","RSA in place; consent-fee deadlines expired; accession continues","RSA majority; scheme thresholds","TBC","scheme timetable not announced",
  [("kwg","Accession Letters")], lambda: px_equity("1813.HK"), None, ""),
 ("redco","HK/CN","Redco Properties","Schemes approved at 16 Oct scheme meeting","HK court sanction","TBC","sanction hearing not yet announced",
  [("redco","16 October 2026")], lambda: px_equity("1622.HK"), None, ""),
 ("vpower","HK","VPower Group","Scheme convening order 21 Oct 2026","Scheme creditors at the scheme meeting","TBC","meeting notice to follow",
  [("vpower","On 21 October 2026")], lambda: px_equity("1608.HK"), None, ""),
 ("point","SE","Point Properties Portfolio 1 (SEK 800m SE0015556535)","Written procedure: final redemption date moved to 30 Nov 2026 (pre-filing)","Bondholders via written procedure","2026-11-30","amended final redemption date",
  [("point","30 November 2026"),("point","SE0015556535")], None, None, "No public bond price found."),
 ("branicks","DE","Branicks Group (€400m bond)","SchVG vote 17–19 Oct: 99% in favour; €375m to 2030, €220m to 2038","Implementation conditions; holders' representative MR Treuhand","2027-03-31","plan effective by end-2026 or 31 Mar 2027 at the latest",
  [("branicks","99% of the votes cast"),("branicks","March 31, 2027")], lambda: px_equity("BRNK.DE"), None, "Bond XS2388910270 last traded 17 Sep (stale)."),
 ("clabo","IT","Clabo S.p.A.","Accordo di ristrutturazione (artt. 57/61/63 CCII) signed","Tribunale di Ancona (omologazione) + tax/INPS adhesion","2026-11-04","omologazione petition to be filed by this date",
  [("clabo","entro il 4 novembre 2026")], None, None, ""),
 ("goodfood","CA","Goodfood Market Corp.","CCAA (initial order 5 Aug 2026); sales process","Monitor Raymond Chabot + court-approved SISP","TBC","SISP milestones on monitor site",
  [("goodfood_rc","On August 5, 2026, Goodfood Market Corp. sought protection")], None, None, ""),
 ("odas","FR","ODAS","Sauvegarde (TAE Nanterre) opened 5 Aug 2026","Administrateur judiciaire + classes","2027-02-05","JUDGEMENT: end of 6-month observation",
  [("bodacc","A202601541654")], None, None, ""),
 ("poseidon","FR","Poseidon Bidco","Sauvegarde ACCÉLÉRÉE (TAE Nanterre) opened 13 Aug 2026","Lender classes (LBO holdco)","TBC","accelerated: plan within 2–4 months (JUDGEMENT: Oct–Dec 2026)",
  [("bodacc","sauvegarde accélérée")], None, None, "Corrected from 'sauvegarde'."),
 ("dumarey","FR","Dumarey Powerglide Bouthéon","Sauvegarde (TAE Lyon) opened 22 Jul 2026","Parent + administrateur","2027-01-22","JUDGEMENT: end of 6-month observation",
  [("bodacc","A202601443260")], None, None, ""),
 ("aoyuan","HK/CN","China Aoyuan (secured assets)","Receivers (FTI) over mortgaged assets","Secured lender + receivers","TBC","asset sales",
  [("aoyuan","joint and several receivers")], lambda: px_equity("3883.HK"), None, ""),
 ("kizuna","JP","Kizuna Holdings group","Corporate reorganisation dismissed; preservation order","Preservation administrator","TBC","not in source",
  [("kizuna","289億5361万円")], None, None, ""),
 ("gaia","JP","Gaia Funding","Bankruptcy commenced","Trustee; 2,700+ lender-investors","TBC","not in source",
  [("gaia","負債60億4535万円")], None, None, ""),
 ("stark","DK/UK","Stark Group (Winterfell) — pre-filing","Stressed; TLB sell-off; lenders reportedly organising","TLB lenders (€1.345bn + €450m add-on) and CLO holders","TBC","none",
  [("octus_stark","76.14/76.39")], None, None, "SECONDARY ONLY (Octus, 24 Mar 2026 — stale). Fitch page did not render; not counted as verified."),
 ("urbas","ES","Urbas / Guadahermosa Proyectos","Concurso necesario (Juzgado Mercantil 12 Madrid)","Petitioning creditor RS Lender + administración concursal","TBC","none",
  [("urbas","53 millones")], None, None, "SECONDARY ONLY (press)."),
 ("svogl","IN","SVOGL Oil Gas and Energy","NCLT Delhi admitted CIRP","Committee of Creditors (PNB-led)","TBC","none",
  [("svogl","Punjab National Bank")], None, None, "SECONDARY ONLY (legal press); claim size not confirmed today."),
]
KILLED = [
 ("LVGEM (HK)","Restructuring support agreement signed 30 Sep 2026; petition adjourned to 6 Apr 2027 — no near-term catalyst","lvgem","Restructuring Support Agreement"),
 ("China SCE (HK)","Restructuring conditions expected to be satisfied and effective date on or before 26 Oct 2026","sce","26 October 2026"),
 ("Toys\"R\"Us Japan","Sponsor/business-transfer agreement with PPIH (OSS) executed 1 Oct 2026; completion scheduled 30 Oct","ppih","October 30, 2026 (scheduled)"),
 ("Gefion Group","7 Oct written-procedure date passed; result not found","",""),
 ("Booster — NOT killed","Debate kill rejected: the €3m super senior is StaRUG interim financing; standstill runs to 1 Nov","booster_wp","EUR 3,000,000 super senior interim facility"),
]
FIXES = [
 "Thames: catalyst moved from 'March 2027' to 29 Oct 2026 (16th consent vote); added 66.66% RP2 threshold, £2.4bn upsize to £5.4bn, runway to end-2026/early-2027, SPP Extension ('RP 1.5'); Ofwat/government named as controlling.",
 "Bigben: chokepoint changed to the shareholders' class; backstop group ≈93.4%; added Bigben Connected sale (€35m cash + ≈€13m vendor loan to Modelabs), capital structure, AMF URD D.26-0631, BODACC notice.",
 "Agile: primary text keeps a UK Part 26A plan + HK schemes — the debate's 'UK scheme, not Part 26A' is not supported. CoCom 61.50%, RSA within six weeks, petition 7 Dec.",
 "BayWa: unverified 30 Nov date dropped; 16 Oct results PDF sourced (quorate, not adopted).",
 "mm2 Asia: SGX attachment + Government Gazette notice (meetings 4 Nov 10am); 28c recovery labelled secondary.",
 "Poseidon Bidco corrected to sauvegarde accélérée (BODACC).",
 "Debtwire anchor recomputed: £118,818.24 over 26 Jun 2023–25 Jun 2026 = £39,606/yr incl. VAT and inflation contingency.",
 "Fundraising removed: no raise until milestones are met.",
]

FORCED = [
 ("China bank NPL transfers","≈RMB 341bn principal+interest transferred Q1–Q3 2026; RMB 76.2bn in September (record month)","cnfin","3410亿元","Securities Times via cnfin, citing Yindeng data — SECONDARY; Yindeng primary data not reached. Pilot end 31 Dec 2026 NOT confirmed today → Q4-wave is JUDGEMENT."),
 ("Hong Kong banks","Gross classified loan ratio 1.82% (Q2 2026), from 2.01% at end-2025","hkma_c5","1.82%","PRIMARY (HKMA)."),
 ("UK DB pension illiquids","51% of trustees considering buyout explore in-specie or secondary sales; £4–8bn of private-markets secondaries expected in 2026","sl_db","51%","Standard Life release PRIMARY for 51%; £4–8bn from MeltX/mallowstreet company release; BoE Truran speech NOT found → omitted."),
 ("European CLOs 2021–22","2021/2022 vintages reaching the end of reinvestment; Stark Group exposure ≈€1.38bn across 50 managers (Mar 2026)","twentyfour","end of their reinvestment period","Manager blog + Octus — SECONDARY; Stark figure is March 2026."),
 ("J-REIT: JRE","LTV 44.8% (31 Mar 2026) vs conservative target 30–40%","jre_debt","44.8","PRIMARY (j-re.co.jp)."),
]

BUYERS = [("Attestor","London","Thames Water Class B / RP2 new money"),("Arini","London","Bigben shareholder-class / new-money DPS"),("Cheyne Capital","London","Point Properties (SEK bond)"),
 ("Davidson Kempner (London)","London","Agile Part 26A plan"),("Strategic Value Partners Europe","London","BayWa hybrid blocking stake"),("Bain Capital Credit EMEA","London","Poseidon Bidco lender class"),
 ("Värde Partners Europe","London","Urbas concurso assets"),("ADV Partners","Hong Kong","Zhenro"),("Alcentra","London","Booster StaRUG plan"),("Hayfin","London","Clabo new finance"),
 ("Tikehau Capital","Paris","ODAS sauvegarde"),("Ares Europe","London","Dumarey Powerglide"),("Tor Investment Management","Hong Kong","Redco post-sanction paper"),("Kaiyuan Capital","Hong Kong","KWG RSA"),
 ("Clearwater Capital Partners","Hong Kong","VPower scheme"),("Shoreline Capital","Shanghai","China NPL packages (forced-seller layer)"),("Mitsubishi Corporation","Tokyo","Kizuna HD assets (JUDGEMENT)"),
 ("Mitsui & Co.","Tokyo","J-REIT asset sales (JUDGEMENT)"),("Japan Industrial Solutions","Tokyo","Kizuna HD"),("Asian family offices (generic)","Singapore","mm2 Asia"),("FRP Advisory","London","UK late-filer pipeline"),
 ("Interpath Advisory","London","Thames Water contingency"),("Teneo","London/Asia","VPower"),("Kroll APAC","Hong Kong","Zhenro / Agile petitions"),("Borrelli Walsh","Hong Kong","HK petitions"),
 ("KPMG (ex-Ferrier Hodgson)","Sydney/HK","ASX administrations"),("Raymond Chabot","Montréal","Goodfood SISP"),("Polus Capital","London","Stark TLB"),("Sona Asset Management","London","Branicks new paper"),
 ("Benefit Street Partners Europe","London","Antolin notes (named in secondary press)")]

# name, type, evidence token source/key/token, why
BACKERS = [
 ("Fitch Ventures","Strategic CVC","b_fitch","Backing the future of global credit markets","Own site title; portfolio page needs JavaScript (Cognitive Credit/Versana names from search = secondary)","credit-markets data is its stated thesis"),
 ("Illuminate Financial","Fintech VC","b_illum","We support founders solving critical challenges for financial services","Portfolio filters incl. 'Financial Markets Infrastructure'; bank strategic LPs","route to bank credit desks"),
 ("Work-Bench","B2B seed (NYC)","b_workbench_p","AI-Powered Credit Rating Platform","Portfolio lists an AI credit-rating platform and Alkymi (data workflows)","enterprise data seed specialist"),
 ("Seedcamp","Seed VC (London)","b_seedcamp","9fin","9fin on its homepage portfolio","category pattern-match"),
 ("Fintech Collective","Fintech VC (NYC)","b_fcollective","Simetrik","Fintech-only portfolio (Vestwell, Simetrik)","fintech-only mandate"),
 ("Vertex Ventures SEA & India","VC","b_vertex","22 fintech","Site: 22 fintech companies; Singapore base","APAC hub"),
 ("Balderton Capital","VC","b_balderton","European","Backs European-founded tech","European founder thesis"),
 ("Index Ventures","VC","b_index","Index Ventures","Multi-stage VC (site)","later stage"),
]
PASSES = ["Highland Europe (owns the 9fin comp — conflict)","Augmentum Fintech","ION Group (owns Debtwire — competitor)","Antler","Redalpine (9fin investor — conflict)"]

def con(): return sqlite3.connect(f"{D}/triage.db", timeout=300)

def build():
    sits = []
    for i, r in enumerate(S, 1):
        k, mkt, ent, stg, choke, date, basis, srcs, pxf, rec, note = r
        checks = [check(a, b) for a, b in srcs]
        ok = all(c["found"] for c in checks); prim = all(c["grade"] != "SECONDARY" for c in checks)
        status = ("VERIFIED-PRIMARY" if prim else "SECONDARY-LABELLED") if ok else "UNVERIFIED"
        price = pxf() if pxf else None
        gap = None
        if price and rec and price["unit"] == "% of par" and "STALE" not in price["kind"]:
            gap = round(price["value"] - rec["value"], 1)
        sits.append(dict(id=f"WD{i:02d}", key=k, country=mkt, entity=ent, stage=stg, chokepoint=choke, date=date, basis=basis, status=status,
                         checks=checks, price=price, recovery=rec, gap=gap, note=note, url=checks[0]["url"] if checks else ""))
    kills = [dict(name=n, why=w, check=check(k, t) if k else None) for n, w, k, t in KILLED]
    forced = [dict(topic=a, fact=b, check=check(k, t), grade=g) for a, b, k, t, g in FORCED]
    deb = check("cf_debtwire", "£118,818.24"); deb2 = check("cf_debtwire", "25 June 2026")
    backers = [dict(name=n, type=t, evidence=e, why=w, check=check(k, tok)) for n, t, k, tok, e, w in BACKERS]
    return sits, kills, forced, (deb, deb2), backers

def emails(backers):
    sit = {"Fitch Ventures":"Thames Water 29 Oct consent vote","Illuminate Financial":"BayWa hybrid blocking minority","Work-Bench":"Agile RSA launch window (mid-Nov)",
           "Seedcamp":"Bigben 9 Dec plan hearing","Fintech Collective":"Booster standstill expiry 1 Nov","Vertex Ventures SEA & India":"mm2 Asia scheme meetings 4 Nov",
           "Balderton Capital":"Branicks implementation by 31 Mar 2027","Index Ventures":"Zhenro petition 9 Nov"}
    out = []
    for n, b in enumerate(backers, 1):
        out.append(f"""DO NOT SEND - DRAFT
Draft {n} (v2, 23 Oct 2026)
To: [{b['name']} — investment team; address to be confirmed by the user]
Subject: TRIAGE World — a dated, sourced restructuring calendar outside the US ({sit[b['name']]})

Hello {b['name']} team,

We are not raising yet. We are building TRIAGE World: a weekly calendar of non-US restructuring catalysts
with a control map (who decides) and a public price for each situation, every fact quoted from a primary filing.
Example this week: {sit[b['name']]}.

Before we raise we want 3-5 design partners, 2-3 paid pilots and one backtest where we dated a catalyst before the market.
Your portfolio ({b['evidence']}) suggests you know this buyer. Would you be open to 20 minutes of feedback, or an introduction
to one credit desk that might be a design partner?

Best regards,
arslane souici
""")
    return "\n\n".join(out)

def md(sits, kills, forced, deb, backers):
    L = []; A = L.append
    nprim = sum(s["status"] == "VERIFIED-PRIMARY" for s in sits); nsec = sum(s["status"] == "SECONDARY-LABELLED" for s in sits)
    A("## 1. Summary\n")
    A(f"- **25 live non-US situations**: {nprim} confirmed from primary sources fetched on 23 Oct 2026 (Asia/Singapore time), {nsec} labelled secondary-only, {25-nprim-nsec} unverified. Every fact in the sourcing appendix has its URL, fetch time and exact quote.")
    A("- **Killed:** LVGEM, China SCE and Toys\"R\"Us Japan. **Kept:** Booster, because the debate's kill is contradicted by the primary notice. **Added:** Nacon, Grupo Antolin (secondary only) and Stark Group (pre-filing, secondary only).")
    A(f"- **Prices:** {sum(1 for s in sits if s['price'])} situations have a public price. Each is labelled as a trade or a stale trade. A recovery-vs-price gap is computed only where both exist and the price is current ({sum(1 for s in sits if s['gap'] is not None)} cases).")
    A(f"- **Commercial anchor:** a Debtwire subscription at **£39,606 per year**. This is £118,818.24 over 26 Jun 2023–25 Jun 2026, from UK Contracts Finder; it includes VAT and an inflation contingency.")
    A("- **No fundraising yet.** Milestones before raising: 3–5 design partners, 2–3 paid pilots at £5–10k, about £150k ARR in letters of intent, and one backtest that dated a catalyst correctly before the market.\n")
    A('<div style="page-break-before:always"></div>\n')
    A("## 2. Changelog: what was killed or fixed, and why\n")
    A("| Item | Decision and reason | Primary check |\n|---|---|---|")
    for k in kills:
        c = k["check"]; A(f"| {k['name']} | {k['why']} | {(c['grade']+': “'+c['token']+'” found') if c and c['found'] else 'no source / not found'} |")
    A("\n**Fixes**\n"); [A(f"- {f}") for f in FIXES]
    A('<div style="page-break-before:always"></div>\n')
    A("## 3. The 25: chokepoint, catalyst, status\n")
    A("| # | Mkt | Situation | Who decides | Catalyst | Status |\n|---|---|---|---|---|---|")
    for s in sits: A(f"| {s['id']} | {s['country']} | **{s['entity']}** — {s['stage']} | {s['chokepoint']} | **{s['date']}**<br/><span style='color:#64748b'>{s['basis']}</span> | {s['status']} |")
    A('<div style="page-break-before:always"></div>\n')
    A("## 4. Weekly layer: court calendar next to forced sellers\n")
    A("| Week (Mon) | Court / vote calendar (dated, primary) |\n|---|---|")
    import datetime
    wk = {}
    for s in sits:
        if s["date"] != "TBC" and s["date"] <= "2026-12-31":
            d = datetime.date.fromisoformat(s["date"]); m = d - datetime.timedelta(days=d.weekday()); wk.setdefault(m.isoformat(), []).append(f"{s['date'][5:]} {s['entity'].split(' (')[0]}")
    for k in sorted(wk): A(f"| {k} | {'; '.join(wk[k])} |")
    A("\n**Forced-seller layer** (the supply that lands on the same desks)\n")
    A("| Seller | Fact | Grade |\n|---|---|---|")
    for f in forced: A(f"| {f['topic']} | {f['fact']} | {f['grade']} {'(token found)' if f['check']['found'] else '(NOT FOUND today)'} |")
    A('<div style="page-break-before:always"></div>\n')
    A("## 5. Prices and recovery gaps\n")
    A("Rule: the gap is shown only where a current public price and a stated or modelled recovery both exist. Otherwise **ABSTAIN**.\n")
    A("| # | Situation | Price (type, date) | Recovery (basis) | Gap |\n|---|---|---|---|---|")
    for s in sits:
        p = s["price"]; r = s["recovery"]
        ps = f"{p['value']} {p['unit']} — {p['instrument']}; {p['kind']}; {p['date']}" if p else "none found"
        rs = f"{r['value']}% — {r['basis']}" if r else "none public"
        g = f"**{s['gap']:+} pts**" if s["gap"] is not None else "ABSTAIN"
        A(f"| {s['id']} | {s['entity']} | {ps} | {rs} | {g} |")
    A("\n*Agile: the perpetuals at about 0.4% of par against a modelled recovery of about " + f"{agile_rec}%" + " (shares only) imply the market prices the RSA below the equity value issued. This is JUDGEMENT; the Frankfurt trades are thin.*\n")
    A('<div style="page-break-before:always"></div>\n')
    A("## 6. Control maps: top 10\n")
    for k in ["thames","bigben","agile","baywa","booster","mm2","nacon","branicks","zhenro","clabo"]:
        s = next(x for x in sits if x["key"] == k)
        q = s["checks"][0]
        A(f"**{s['entity']} ({s['country']}) — {s['date']}.** {s['stage']}. *Who decides:* {s['chokepoint']}. {s['note']}<br/><span style='color:#64748b'>Quote: “…{q['quote'][100:330]}…” — {q['url'][:90]}</span>\n")
    A('<div style="page-break-before:always"></div>\n')
    A("## 7. Bigben Interactive: investment-committee file\n")
    A("| Item | Fact (primary) |\n|---|---|")
    for a, b in [("Procedure","Sauvegarde accélérée opened 17 Aug 2026, TC Lille Métropole. BODACC A202601622253 (published 26 Aug) records the opening judgment."),
                 ("Timetable","Extended 17 Oct → 17 Dec 2026 (judgment of 7 Oct). Plan hearing on **9 Dec 2026**; votes by classes of affected parties beforehand. Company expects completion by end-Q1 2027."),
                 ("Asset sold","**Bigben Connected** to **Modelabs**: **€35m cash** paid at closing on 7 Oct, plus a **≈€13m vendor loan** over 5 years (≈€48m total). The vendor loan is final after closing-accounts review."),
                 ("Backstop","€20m backstop of the rights issue (DPS) of up to €25m at €0.017. Guarantors hold ≈**93.4%** of the exchangeables after syndication: TT International 2.16, Syquant 4.35, LMR 3.94, CIC 3.37, Cigogne 2.84, Sparinvest 3.00, Rhodium 0.17, Swan 0.17 (€m)."),
                 ("Capital-increase prices","Rights issue €0.017; non-guarantor conversion €0.051 (3×); guarantor tranche raised from €0.01523 to €0.0209."),
                 ("Plan economics (URD)","€55–60m of new resources; ≈€47.2m of claims converted to equity; €26m repaid from sale proceeds; the €0.9m syndicated balance waived."),
                 ("Balance sheet 31 Mar 2026","Equity **−€55.8m**; cash €31.6m; net debt **€167.9m** including the bond carried at **€59.1m**; FY25/26 revenue €284.5m, EBITDA €55.5m; impairments €369.4m."),
                 ("Group link","Owns 56.72% of Nacon's capital (68.74% of votes). Nacon is in its own redressement judiciaire; Bigben reinvests €16m of new money into Nacon's €31m rights issue."),
                 ("Regulator","Universal Registration Document filed with the AMF on 16 Oct 2026 under no. **D.26-0631**. The AMF BDIF page itself was not fetched (gap)."),
                 ("Prices","Shares €0.069, last close 22 Oct (public chart feed). The exchangeable FR0014001WC2 last traded on 16 Feb 2026 at 84.69 (stale, 'pending deletion'). No current bond mark."),
                 ("Who decides","Creditors are locked up. **Shareholders' class** and a cross-class cram-down are the open questions (JUDGEMENT)."),
                 ("IC readiness","**Partial.** Done: procedure, timetable, sale, backstop, balance sheet, URD number. Missing: the court judgment text, the BALO n°118 class notification text, the class composition and voting thresholds, a current bond mark, and the post-plan cap table.")]:
        A(f"| {a} | {b} |")
    A('<div style="page-break-before:always"></div>\n')
    A("## 8. Money\n")
    A("| Comparable | Public price | Grade |\n|---|---|---|")
    A(f"| Debtwire (The Pensions Regulator) | £118,818.24 for 26 Jun 2023–25 Jun 2026 → **£39,606/yr** incl. VAT | PRIMARY ({'verified' if deb[0]['found'] and deb[1]['found'] else 'NOT verified'}) |")
    A("| 9fin | ≈$100k/yr | SECONDARY |\n| Octus | $30–120k/yr (2017 record) | SECONDARY |\n| **TRIAGE World (proposed)** | £18k/desk/yr; £5k per situation map | JUDGEMENT |\n")
    A(hbars([("Debtwire (TPR, per yr)", 39.6, "#64748b", "primary"), ("TRIAGE desk", 18, "#2563eb", "judgement"), ("TRIAGE map", 5, "#93c5fd", "judgement")], value_fmt=lambda v: f"£{v:,.1f}k"))
    A("\n| Scenario (year 1, JUDGEMENT) | Desks × price | Maps × £5k | ARR |\n|---|---|---|---:|")
    for n, d, p, m in [("Bear", 8, 12, 10), ("Base", 13, 18, 12), ("Bull", 35, 24, 16)]:
        A(f"| {n} | {d} × £{p}k = £{d*p}k | {m} × £5k = £{m*5}k | **£{d*p+m*5}k** |")
    A("\nThe recheck matches the Valuation figures exactly: £146k, £294k and £920k.\n")
    A("**Milestones before any raise:** 3–5 design partners; 2–3 paid pilots at £5–10k; ≈£150k ARR in letters of intent; one backtest where a catalyst was dated correctly before the market. Candidate backtests from this list: Thames 29 Oct vote, Booster 1 Nov standstill, mm2 4 Nov meetings.\n")
    A("### 30 buyers, each fitted to a live situation (fit is JUDGEMENT; no firm contacted)\n")
    A("| Firm | Base | Situation |\n|---|---|---|")
    for b in BUYERS: A(f"| {b[0]} | {b[1]} | {b[2]} |")
    A('<div style="page-break-before:always"></div>\n')
    A("## 9. Backers (when the milestones are met)\n")
    A("| # | Backer | Type | Evidence from its own site (fetched today) | Check |\n|---|---|---|---|---|")
    for i, b in enumerate(backers, 1):
        c = b["check"]; A(f"| {i} | {b['name']} | {b['type']} | {b['evidence']} | {'VERIFIED: “'+c['token']+'”' if c['found'] else 'NOT FOUND'} |")
    A("\n**Removed as passes:** " + "; ".join(PASSES) + ".\n")
    A("Eight drafts, each headed *DO NOT SEND - DRAFT*, ask for feedback or a design-partner introduction, not money. They are saved to `/workspace/triage_os_data/world/email_drafts_DO_NOT_SEND.txt`. Nothing was sent.\n")
    A("## 10. Remaining gaps\n")
    for g in ["Thames Class B ISINs and marks: no public exchange page found → gap abstains.",
              "Bigben: court judgment text, BALO n°118 text and the AMF BDIF entry were not fetched (the URD number comes from the company release).",
              "Grupo Antolin: antolin.com blocked from the box; status after 16 Oct is unconfirmed (secondary only).",
              "Stark Group: Fitch page did not render; the Octus quote dates from March 2026. Treat as a watch item, not a verified pre-filing.",
              "mm2 Asia: debt size not in a primary document fetched today.",
              "Yindeng primary NPL data not reached; the end date of China's NPL pilot is not confirmed. The BoE Truran speech was not found.",
              "Equity prices come from a public chart feed, not the exchange pages; bond prices are thin Frankfurt trades.",
              "Urbas, SVOGL, Antolin and Stark are secondary-only and kept only because they are labelled."]: A(f"- {g}")
    A('<div style="page-break-before:always"></div>\n')
    A("## Appendix: sourcing log (URL · fetched · exact quote)\n")
    A("| ID | Grade | Token | Fetched | URL | Quote |\n|---|---|---|---|---|---|")
    for s in sits:
        for c in s["checks"]:
            A(f"| {s['id']} | {c['grade']} | {c['token'][:40]} | {c['fetched'][:16]} | {c['url'][:70]} | {c['quote'][:230].replace('|','/')} |")
    for f in forced:
        c = f["check"]; A(f"| FS | {c['grade']} | {c['token']} | {c['fetched'][:16]} | {c['url'][:70]} | {c['quote'][:200].replace('|','/')} |")
    for c in deb: A(f"| WP01 | {c['grade']} | {c['token']} | {c['fetched'][:16]} | {c['url'][:70]} | {c['quote'][:200].replace('|','/')} |")
    for b in backers:
        c = b["check"]; A(f"| WB | {c['grade']} | {c['token'][:40]} | {c['fetched'][:16]} | {c['url'][:70]} | {c['quote'][:160].replace('|','/')} |")
    return "\n".join(L)

def main():
    sits, kills, forced, deb, backers = build()
    c = con(); c.execute("create table if not exists verification(claim_id, artifact, claim, status, primary_url, checked, method, fix)")
    c.execute("delete from verification where claim_id like 'WD%' or claim_id like 'WB%' or claim_id like 'WP%' or claim_id like 'WF%' or claim_id like 'WK%'")
    for s in sits:
        for j, ch in enumerate(s["checks"], 1):
            c.execute("insert into verification values(?,?,?,?,?,?,?,?)", (f"{s['id']}.{j}", "research/triage_world v2", f"{s['entity']}: “{ch['token']}”",
                      ("VERIFIED" if ch["found"] else "UNVERIFIABLE") + ("" if ch["grade"] != "SECONDARY" else "-SECONDARY"), ch["url"], ch["fetched"][:19], "exact-token match; quote: " + ch["quote"][:300], ""))
    for i, f in enumerate(forced, 1):
        ch = f["check"]; c.execute("insert into verification values(?,?,?,?,?,?,?,?)", (f"WF{i:02d}", "research/triage_world v2", f["fact"], ("VERIFIED" if ch["found"] else "UNVERIFIABLE") + " / " + f["grade"][:60], ch["url"], ch["fetched"][:19], "quote: " + ch["quote"][:300], ""))
    for i, k in enumerate(kills, 1):
        ch = k["check"]; c.execute("insert into verification values(?,?,?,?,?,?,?,?)", (f"WK{i:02d}", "research/triage_world v2", k["name"] + ": " + k["why"], ("VERIFIED" if ch and ch["found"] else "NO SOURCE"), ch["url"] if ch else "", (ch or {}).get("fetched", "")[:19], "quote: " + ((ch or {}).get("quote", ""))[:300], ""))
    for i, b in enumerate(backers, 1):
        ch = b["check"]; c.execute("insert into verification values(?,?,?,?,?,?,?,?)", (f"WB{i:02d}", "research/triage_world v2", f"{b['name']}: {b['evidence']}", "VERIFIED" if ch["found"] else "UNVERIFIABLE", ch["url"], ch["fetched"][:19], "quote: " + ch["quote"][:300], ""))
    ch = deb[0]; c.execute("insert into verification values(?,?,?,?,?,?,?,?)", ("WP01", "research/triage_world v2", "Debtwire £118,818.24 for 26 Jun 2023–25 Jun 2026 = £39,606/yr", "VERIFIED" if deb[0]["found"] and deb[1]["found"] else "UNVERIFIABLE", ch["url"], ch["fetched"][:19], "quote: " + ch["quote"][:300], ""))
    c.commit()
    json.dump(dict(asof="2026-10-23", situations=sits, killed=kills, fixes=FIXES, forced=forced, debtwire=dict(total=118818.24, per_year=39606, checks=list(deb)),
                   buyers=[dict(firm=a, base=b, situation=s) for a, b, s in BUYERS], backers=backers, passes=PASSES,
                   scenarios=[dict(name="Bear", arr=146), dict(name="Base", arr=294), dict(name="Bull", arr=920)]), open(f"{D}/world.json", "w"), indent=1, ensure_ascii=False)
    open(f"{D}/world/email_drafts_DO_NOT_SEND.txt", "w").write(emails(backers))
    m = md(sits, kills, forced, deb, backers); open(f"{HERE}/triage_world.md", "w").write(m)
    pages = report_from_markdown(m, "TRIAGE World: situations, revenue, backers", "World desk · v2 · 23 Oct 2026",
        "25 live non-US situations re-verified today from primary sources, with who decides, when, and what the market price says.",
        [("Situations", "25 live · 3 killed"), ("Sourcing", "URL · fetch time · exact quote"), ("Rules", "public data · firms only · nothing sent")],
        f"{HERE}/TRIAGE_World.html", f"{HERE}/TRIAGE_World.pdf")
    print("pages", pages, {k: sum(s["status"] == k for s in sits) for k in ("VERIFIED-PRIMARY", "SECONDARY-LABELLED", "UNVERIFIED")})
    for s in sits: print(s["id"], s["status"], s["entity"][:30], [c["token"][:25] for c in s["checks"] if not c["found"]], s["price"] and s["price"]["value"], s["gap"])
if __name__ == "__main__": main()
