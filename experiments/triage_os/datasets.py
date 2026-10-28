"""Offshore / ownership / asset datasets (companies only; individuals filtered out). Each loader streams a public bulk file into SQLite."""
import csv, io, json, re, sqlite3, zipfile
csv.field_size_limit(10**9)
RAW = "/workspace/triage_os_data/raw2"
CORP = re.compile(r"\b(INC|INCORPORATED|LLC|L\.L\.C|LTD|LIMITED|CORP|CORPORATION|CO|COMPANY|LP|L\.P|LLP|PLC|SA|S\.A|AG|GMBH|BV|B\.V|NV|N\.V|SARL|S\.A R\.L|SPA|S\.P\.A|AB|AS|OY|KK|PTE|PTY|HOLDINGS?|GROUP|TRUST|FUND|PARTNERS|BANK|CAPITAL|INVESTMENTS?|ENTERPRISES?|INTERNATIONAL|SERVICES|FOUNDATION|ASSOCIATES)\b\.?", re.I)
SUFFIX = re.compile(r"\b(the|inc|incorporated|llc|l l c|ltd|limited|corp|corporation|co|company|lp|l p|llp|plc|sa|ag|gmbh|bv|nv|sarl|s a r l|spa|holdings?|group|parent|midco|topco|intermediate|acquisition|buyer|borrower|i|ii|iii|iv|\d+)\b")
def norm(s):
    s = re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower().replace(".", "").replace("&", " and "))
    return re.sub(r"\s+", " ", SUFFIX.sub(" ", s)).strip()
def is_company(name): return bool(CORP.search(name or ""))
def _f(x):
    try: return float(x or 0)
    except ValueError: return None
def _db(db): c = sqlite3.connect(db, timeout=120); c.execute("pragma journal_mode=wal"); return c
def _load(c, table, cols, rows, idx=("nkey",)):
    c.execute(f"drop table if exists {table}"); c.execute(f"create table {table}({','.join(cols)})")
    n = 0; buf = []
    for r in rows:
        buf.append(r); n += 1
        if len(buf) >= 50000: c.executemany(f"insert into {table} values({','.join('?'*len(cols))})", buf); buf = []
    if buf: c.executemany(f"insert into {table} values({','.join('?'*len(cols))})", buf)
    for i in idx:
        if i in cols: c.execute(f"create index if not exists ix_{table}_{i} on {table}({i})")
    c.commit(); return n
def _zcsv(z, name, **kw):
    return csv.DictReader(io.TextIOWrapper(zipfile.ZipFile(z).open(name), encoding="utf-8-sig", errors="ignore"), **kw)

def icij(db, z=f"{RAW}/icij.zip"):
    c = _db(db); out = {}
    out["icij_entities"] = _load(c, "icij_entities", ["node_id", "name", "nkey", "jurisdiction", "countries", "incorporation_date", "status", "source", "service_provider"],
        ((r["node_id"], r["name"], norm(r["name"]), r["jurisdiction_description"], r["countries"], r["incorporation_date"], r["status"], r["sourceID"], r["service_provider"]) for r in _zcsv(z, "nodes-entities.csv")))
    out["icij_intermediaries"] = _load(c, "icij_intermediaries", ["node_id", "name", "nkey", "countries", "status", "source"],
        ((r["node_id"], r["name"], norm(r["name"]), r["countries"], r["status"], r["sourceID"]) for r in _zcsv(z, "nodes-intermediaries.csv") if is_company(r["name"])))
    keep = {r[0] for r in c.execute("select node_id from icij_entities union select node_id from icij_intermediaries")}
    out["icij_rel"] = _load(c, "icij_rel", ["src", "dst", "rel_type", "source"],
        ((r["node_id_start"], r["node_id_end"], r["rel_type"], r["sourceID"]) for r in _zcsv(z, "relationships.csv") if r["node_id_start"] in keep and r["node_id_end"] in keep), idx=("src", "dst"))
    return out

def sanctions(db):
    c = _db(db); rows = []
    for r in csv.reader(open(f"{RAW}/sdn.csv", encoding="latin-1")):
        if len(r) > 3 and r[2].strip() != "individual":
            rows.append(("OFAC_SDN", r[0], r[1], norm(r[1]), r[2].replace("-0-", "entity").strip(), r[3], "", "https://www.treasury.gov/ofac/downloads/sdn.csv"))
    for r in csv.reader(open(f"{RAW}/ofac_alt.csv", encoding="latin-1")):  # aliases of entities
        if len(r) > 3: rows.append(("OFAC_ALT", r[0], r[3], norm(r[3]), "alias", "", "", "https://www.treasury.gov/ofac/downloads/alt.csv"))
    seen = set()
    for r in csv.DictReader(open(f"{RAW}/eu_fsf.csv", encoding="utf-8-sig", errors="ignore"), delimiter=";"):
        if r.get("Entity_SubjectType_ClassificationCode") != "enterprise" or not r.get("NameAlias_WholeName"): continue
        k = (r["Entity_LogicalId"], r["NameAlias_WholeName"])
        if k in seen: continue
        seen.add(k); rows.append(("EU_FSF", r["Entity_LogicalId"], r["NameAlias_WholeName"], norm(r["NameAlias_WholeName"]), "enterprise", r["Entity_Regulation_Programme"], r.get("Address_CountryDescription", ""), "https://webgate.ec.europa.eu/fsd/fsf"))
    ent = {r[1] for r in rows if r[0] == "OFAC_SDN"}
    rows = [r for r in rows if r[0] != "OFAC_ALT" or r[1] in ent]
    return {"sanctions": _load(c, "sanctions", ["list", "uid", "name", "nkey", "type", "program", "country", "source_url"], rows)}

def form_d(db, z=f"{RAW}/formd.zip", q="2026Q3"):
    c = _db(db); sub = {r["ACCESSIONNUMBER"]: r["FILING_DATE"] for r in _zcsv(z, f"{q}_d/FORMDSUBMISSION.tsv", delimiter="\t")}
    off = {r["ACCESSIONNUMBER"]: r for r in _zcsv(z, f"{q}_d/OFFERING.tsv", delimiter="\t")}
    def rows():
        for r in _zcsv(z, f"{q}_d/ISSUERS.tsv", delimiter="\t"):
            o = off.get(r["ACCESSIONNUMBER"], {}); a = r["ACCESSIONNUMBER"]
            yield (a, r["CIK"].lstrip("0"), r["ENTITYNAME"], norm(r["ENTITYNAME"]), r["JURISDICTIONOFINC"], r["ENTITYTYPE"], o.get("INDUSTRYGROUPTYPE"), o.get("INVESTMENTFUNDTYPE"),
                   o.get("TOTALOFFERINGAMOUNT"), o.get("TOTALAMOUNTSOLD"), sub.get(a), f"https://www.sec.gov/Archives/edgar/data/{r['CIK'].lstrip('0')}/{a.replace('-', '')}/")
    return {"formd_issuers": _load(c, "formd_issuers", ["accession", "cik", "name", "nkey", "jurisdiction", "entity_type", "industry", "fund_type", "offering_amt", "sold_amt", "filing_date", "source_url"], rows())}

def f5500(db, y=2024):
    c = _db(db)
    spons = {r["ACK_ID"]: (r["SPONSOR_DFE_NAME"], r["SPONS_DFE_EIN"], r["PLAN_NAME"]) for r in _zcsv(f"{RAW}/f5500_{y}.zip", f"f_5500_{y}_latest.csv")}
    def f(x):
        try: return float(x)
        except: return None
    def rows():
        for r in _zcsv(f"{RAW}/sb{y}.zip", f"F_SCH_SB_{y}_latest.csv"):
            s = spons.get(r["ACK_ID"], ("", r["SB_EIN"], "")); ft, av = f(r["SB_TOT_FNDNG_TGT_AMT"]), f(r["SB_ACTRL_VALUE_AST_AMT"])
            yield (r["ACK_ID"], s[1] or r["SB_EIN"], s[0], norm(s[0]), s[2], r["SB_PLAN_YEAR_BEGIN_DATE"], ft, av, (ft - av) if ft is not None and av is not None else None,
                   f(r["SB_FNDNG_TGT_PRCNT"]), r["SB_PLAN_AT_RISK_IND"], r["SB_TOT_PARTCP_CNT"], f"https://www.efast.dol.gov/  (ACK_ID {r['ACK_ID']}; DOL FOIA F_SCH_SB_{y})")
    return {"pension_sb": _load(c, "pension_sb", ["ack_id", "ein", "sponsor", "nkey", "plan", "plan_year", "funding_target", "actuarial_assets", "shortfall", "funded_pct", "at_risk", "participants", "source_url"], rows())}

def faa(db, z=f"{RAW}/faa.zip"):
    c = _db(db); mdl = {}
    for r in _zcsv(z, "ACFTREF.txt"): mdl[r["CODE"].strip()] = (r["MFR"].strip(), r["MODEL"].strip(), r.get("NO-SEATS", "").strip())
    def rows():
        for r in _zcsv(z, "MASTER.txt"):
            if r["TYPE REGISTRANT"].strip() in ("1", "4", "9"): continue  # individuals / co-owned excluded
            m = mdl.get(r["MFR MDL CODE"].strip(), ("", "", "")); nm = r["NAME"].strip()
            yield ("N" + r["N-NUMBER"].strip(), r["SERIAL NUMBER"].strip(), nm, norm(nm), r["TYPE REGISTRANT"].strip(), m[0], m[1], m[2], r["YEAR MFR"].strip(), r["STATE"].strip(), r["COUNTRY"].strip(), r["STATUS CODE"].strip(), r["CERT ISSUE DATE"].strip(),
                   " | ".join(x.strip() for x in (r.get("OTHER NAMES(1)", ""), r.get("OTHER NAMES(2)", "")) if x and x.strip()), f"https://registry.faa.gov/AircraftInquiry/Search/NNumberResult?nNumberTxt={r['N-NUMBER'].strip()}")
    return {"faa_aircraft": _load(c, "faa_aircraft", ["n_number", "serial", "owner", "nkey", "registrant_type", "mfr", "model", "seats", "year", "state", "country", "status", "cert_date", "other_names", "source_url"], rows())}

def epa(db, z=f"{RAW}/epa_cases.zip"):
    c = _db(db); pen = {}
    for r in _zcsv(z, "CASE_PENALTIES.csv"):
        try: pen[r["CASE_NUMBER"]] = pen.get(r["CASE_NUMBER"], 0) + float(r["FED_PENALTY"] or 0) + float(r["ST_LCL_PENALTY"] or 0) + float(r["COMPLIANCE_ACTION_COST"] or 0)
        except ValueError: pass
    enf = {r["CASE_NUMBER"]: (r["CASE_NAME"], r["FISCAL_YEAR"], r["ACTIVITY_STATUS_DESC"], r["ENF_OUTCOME_DESC"]) for r in _zcsv(z, "CASE_ENFORCEMENTS.csv")}
    def rows():
        for r in _zcsv(z, "CASE_DEFENDANTS.csv"):
            if not is_company(r["DEFENDANT_NAME"]): continue
            e = enf.get(r["CASE_NUMBER"], ("", "", "", ""))
            yield (r["CASE_NUMBER"], r["DEFENDANT_NAME"], norm(r["DEFENDANT_NAME"]), e[0], e[1], e[2], e[3], pen.get(r["CASE_NUMBER"], 0), f"https://echo.epa.gov/enforcement-case-report?id={r['CASE_NUMBER']}")
    return {"epa_cases": _load(c, "epa_cases", ["case_number", "defendant", "nkey", "case_name", "fiscal_year", "status", "outcome", "penalty_and_cost_usd", "source_url"], rows())}

def adv_funds(db, d=f"{RAW}/adv"):
    """Form ADV Schedule D 7.B(1): private funds (GAV), auditors (7B1A23), prime brokers (7B1A24). Latest filing per adviser up to 2024-12-31."""
    c = _db(db); latest = {}
    for r in csv.DictReader(open(f"{d}/IA_ADV_Base_A_20111105_20241231.csv", encoding="latin-1")):
        crd = r.get("1E1") or r["1A"]; dtv = r["DateSubmitted"][:10]
        k = (dtv[6:10] + dtv[0:2] + dtv[3:5]) if "/" in dtv else dtv
        if crd not in latest or k > latest[crd][0]: latest[crd] = (k, r["FilingID"], r["1A"], crd)
    fil = {v[1]: v for v in latest.values()}
    out = {}
    out["adv_funds"] = _load(c, "adv_funds", ["filing_id", "reference_id", "adviser", "adviser_nkey", "crd", "fund", "fund_id", "fund_type", "country", "gav", "filed", "source_url"],
        ((r["FilingID"], r["ReferenceID"], fil[r["FilingID"]][2], norm(fil[r["FilingID"]][2]), fil[r["FilingID"]][3], r["Fund Name"], r["Fund ID"], r["Fund Type"], r["Country"], _f(r["Gross Asset Value"]), fil[r["FilingID"]][0],
          f"https://adviserinfo.sec.gov/firm/summary/{fil[r['FilingID']][3]}") for r in csv.DictReader(open(f"{d}/IA_Schedule_D_7B1_20111105_20241231.csv", encoding="latin-1")) if r["FilingID"] in fil), idx=("filing_id", "adviser_nkey"))
    ref = {(r[0], r[1]) for r in []}
    out["adv_auditors"] = _load(c, "adv_auditors", ["filing_id", "reference_id", "auditor", "country", "pcaob"],
        ((r["FilingID"], r["ReferenceID"], r["Name of Auditing Firm"].strip().upper(), r["Country"], r["PCAOB Registered"]) for r in csv.DictReader(open(f"{d}/IA_Schedule_D_7B1A23_20111105_20241231.csv", encoding="latin-1")) if r["FilingID"] in fil), idx=("filing_id",))
    out["adv_prime_brokers"] = _load(c, "adv_prime_brokers", ["filing_id", "reference_id", "prime_broker", "country", "custodian"],
        ((r["FilingID"], r["ReferenceID"], r["Name of Prime Broker"].strip().upper(), r["Country"], r["Custodian"]) for r in csv.DictReader(open(f"{d}/IA_Schedule_D_7B1A24_20111105_20241231.csv", encoding="latin-1")) if r["FilingID"] in fil), idx=("filing_id",))
    return out

def psc(db, path=f"{RAW}/psc/corporate_psc.jsonl"):
    c = _db(db)
    def rows():
        for l in open(path, encoding="utf-8", errors="ignore"):
            try: j = json.loads(l)
            except ValueError: continue
            d = j.get("data", {}); ident = d.get("identification", {}) or {}
            yield (j.get("company_number"), d.get("name"), norm(d.get("name")), d.get("kind"), ident.get("legal_form"), ident.get("country_registered") or ident.get("place_registered"), ident.get("registration_number"),
                   ";".join(d.get("natures_of_control", [])), d.get("notified_on"), d.get("ceased_on"), f"https://find-and-update.company-information.service.gov.uk/company/{j.get('company_number')}/persons-with-significant-control")
    return {"uk_corporate_psc": _load(c, "uk_corporate_psc", ["company_number", "psc_name", "nkey", "kind", "legal_form", "registered_in", "reg_number", "control", "notified_on", "ceased_on", "source_url"], rows(), idx=("nkey", "company_number"))}
