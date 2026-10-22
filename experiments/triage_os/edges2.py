"""Second-generation edges joining watchlist (distressed) entities to ownership, asset, liability and holder datasets.
Match quality: EIN (exact identifier) > LEI > strict-name (normalised key with >=2 tokens or a distinctive >=7-char token)."""
import re, sqlite3
GENERIC = set("investment investments capital partners global international national american united services solutions systems technologies technology health healthcare energy power group alpha beta delta omega project team alta lifestyle rising tide plasma zeus fuse safety windows lightning precisely".split())
OFFSHORE = {"KY": "Cayman Islands", "VG": "British Virgin Islands", "JE": "Jersey", "GG": "Guernsey", "BM": "Bermuda", "LU": "Luxembourg", "IE": "Ireland", "NL": "Netherlands", "IM": "Isle of Man", "PA": "Panama", "BS": "Bahamas", "SC": "Seychelles"}
LEGAL = re.compile(r"\b(inc|incorporated|llc|ltd|limited|corp|corporation|co|company|plc|sa|ag|gmbh|lp|llp|the)\b")
def tight(s): return re.sub(r"\s+", " ", LEGAL.sub(" ", re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower().replace(".", "")))).strip()
def strict(k):
    t = k.split()
    if not t: return False
    if len(t) >= 2: return not all(x in GENERIC for x in t)
    return len(t[0]) >= 7 and t[0] not in GENERIC
SPV = re.compile(r"\b(midco|topco|holdco|bidco|parent|intermediate|buyer|acquisition|borrower|purchaser|merger sub|b\.?v\.?|s\.?a\.? ?r\.?l\.?|s\.?à r\.?l\.?|ltd\.?|limited|cayman|luxembourg|jersey|lp)\b", re.I)
def spv_tags(name): return sorted({m.lower().replace(".", "").replace(" ", "") for m in SPV.findall(name or "")})
def build(db):
    c = sqlite3.connect(db, timeout=120); E = []
    def add(t, src, dst, detail, value, match, url): E.append((f"{t}-{len(E)+1:04d}", t, src, dst, detail, value, match, url, "UNVERIFIED"))
    # 1 pension underfunding (EIN join)
    for n, why, sp, plan, ft, av, sh, pct, risk, part, ack in c.execute("select w.name,w.reason,p.sponsor,p.plan,p.funding_target,p.actuarial_assets,p.shortfall,p.funded_pct,p.at_risk,p.participants,p.ack_id from pension_sb p join watchlist w on p.ein=w.ein and w.ein!='' where p.shortfall>0"):
        add("pension_underfunding", n, plan, f"{why}; funding target ${ft/1e6:.1f}m vs assets ${av/1e6:.1f}m; funded {pct}%; at-risk={risk or 'n'}; participants {part}; ACK {ack}", sh, "EIN", f"https://www.efast.dol.gov/5500search/ (ACK_ID {ack}); DOL FOIA F_SCH_SB_2024")
    # 2 government contractors (exact normalised recipient)
    for n, why, rec, amt, cnt, ag, url in c.execute("select w.name,w.reason,u.recipient,sum(u.amount),count(distinct u.award_id),group_concat(distinct u.agency),(select source_url from usaspending_awards x where x.nkey=w.nkey order by amount desc limit 1) from (select distinct nkey,recipient,award_id,amount,agency,source_url from usaspending_awards) u join watchlist w on u.nkey=w.nkey group by w.nkey"):
        if strict(re.sub(r'[^a-z ]', '', rec.lower())) or True: add("gov_contractor", n, rec, f"{why}; {cnt} contract awards with activity FY25-26 (lifetime award values); agencies: {ag}", amt, "exact-name", url)
    # 3 aircraft collateral
    for n, why, k, cnt, mdl, url in c.execute("select w.name,w.reason,w.nkey,count(*),group_concat(distinct f.mfr||' '||f.model),min(f.source_url) from faa_aircraft f join watchlist w on f.nkey=w.nkey group by w.nkey"):
        if strict(k): add("aircraft_collateral", n, f"{cnt} aircraft", f"{why}; {mdl[:200]}", cnt, "strict-name", url)
    # 4 environmental liabilities
    for n, why, k, cnt, pen, url in c.execute("select w.name,w.reason,w.nkey,count(distinct e.case_number),sum(e.penalty_and_cost_usd),min(e.source_url) from epa_cases e join watchlist w on e.nkey=w.nkey group by w.nkey"):
        if strict(k): add("environmental_liability", n, f"{cnt} EPA cases", f"{why}; penalties+compliance cost ${pen/1e6:.2f}m", pen, "strict-name", url)
    # 5 offshore chains: GLEIF parents in offshore jurisdictions; ICIJ strict matches
    for n, lei, dp, dpj, up, upj, url in c.execute("select query,lei,direct_parent,direct_parent_jur,ultimate_parent,ultimate_parent_jur,source_url from gleif_l2"):
        for p, j in ((dp, dpj), (up, upj)):
            if p and (j or "")[:2] in OFFSHORE: add("offshore_parent_chain", n, p, f"GLEIF L2 parent in {OFFSHORE[j[:2]]} ({j}); LEI {lei}", 1, "LEI", url)
    for n, why, k, en, jur, srcs, nid in c.execute("select w.name,w.reason,w.nkey,e.name,e.jurisdiction,e.source,e.node_id from icij_entities e join watchlist w on e.nkey=w.nkey"):
        if strict(k) and len(k) >= 10: add("offshore_leaks_namesake", n, en, f"{why}; ICIJ {srcs} entity in {jur} (name match only - not proof of link)", 0, "strict-name", f"https://offshoreleaks.icij.org/nodes/{nid}")
    # 6 UK subsidiaries via corporate PSC (watchlist entity is the registered corporate PSC)
    for n, why, k, cnt, nums in c.execute("select w.name,w.reason,w.nkey,count(distinct p.company_number),group_concat(distinct p.company_number) from uk_corporate_psc p join watchlist w on p.nkey=w.nkey where p.ceased_on is null group by w.nkey"):
        if strict(k): add("uk_psc_subsidiaries", n, f"{cnt} UK companies", f"{why}; controls UK cos {nums[:120]}", cnt, "strict-name", f"https://find-and-update.company-information.service.gov.uk/company/{nums.split(',')[0]}/persons-with-significant-control")
    # 7 sanctions screen: tight name equality (only legal-form suffixes removed) for watchlist, EchoStar 13F holders, ADV advisers
    S = {}
    for sn, lst, prog in c.execute("select name,list,program from sanctions"): S.setdefault(tight(sn), (sn, lst, prog))
    cands = [(n, "watchlist") for (n,) in c.execute("select name from watchlist")] + [(n, "13F") for (n,) in c.execute("select distinct filer from f13_holdings")] + [(n, "ADV") for (n,) in c.execute("select distinct adviser from adv_funds")]
    for n, src in cands:
        k = tight(n)
        if len(k) >= 6 and k in S: add("sanctions_hit", n, S[k][0], f"{src} name equals {S[k][1]} {S[k][2]}", 1, "tight-name", "https://sanctionssearch.ofac.treas.gov/")
    # 8 fund-level service-provider concentration among EchoStar 13F holders (Form ADV 7.B.1, filed <= 2024-12-31)
    try:
        for adv, crd, filed, kind, prov, gav, n, share, tot, nf in c.execute("select * from fund_service_concentration where share_of_gav>=0.7"):
            add("fund_service_concentration", adv, prov, f"{kind}: {share:.0%} of ${tot}bn private-fund GAV ({n} of {nf} funds); ADV filed {filed}", share, "CRD", f"https://adviserinfo.sec.gov/firm/summary/{crd}")
    except sqlite3.OperationalError: pass
    c.execute("drop table if exists edges2"); c.execute("create table edges2(edge_id primary key,type,src,dst,detail,value,match,source_url,status)")
    c.executemany("insert into edges2 values(?,?,?,?,?,?,?,?,?)", E); c.commit()
    return dict(c.execute("select type,count(*) from edges2 group by 1").fetchall())
def fund_concentration(db, advisers):
    """Share of each adviser's private-fund GAV by auditor and prime broker (Form ADV Sch. D 7.B.1 items 23/24; latest filing <= 2024-12-31)."""
    c = sqlite3.connect(db, timeout=120); rows = []
    for a in advisers:
        tot = c.execute("select sum(gav),count(*),min(adviser),min(crd),min(filed) from adv_funds where adviser like ?", (a,)).fetchone()
        if not tot[0]: continue
        for kind, t, col in (("auditor", "adv_auditors", "auditor"), ("prime_broker", "adv_prime_brokers", "prime_broker")):
            for name, gav, n in c.execute(f"select x.{col}, sum(f.gav), count(*) from adv_funds f join (select distinct filing_id,reference_id,{col} from {t}) x on x.filing_id=f.filing_id and x.reference_id=f.reference_id where f.adviser like ? group by 1 order by 2 desc limit 3", (a,)):
                rows.append((tot[2], tot[3], tot[4], kind, name, round(gav / 1e9, 2), n, round(gav / tot[0], 3), round(tot[0] / 1e9, 2), tot[1]))
    c.execute("drop table if exists fund_service_concentration")
    c.execute("create table fund_service_concentration(adviser,crd,filed,kind,provider,gav_bn,funds,share_of_gav,adviser_gav_bn,adviser_funds)")
    c.executemany("insert into fund_service_concentration values(?,?,?,?,?,?,?,?,?,?)", rows); c.commit(); return rows
def global_concentration(db):
    c = sqlite3.connect(db, timeout=120); out = {}
    for kind, t, col in (("auditor", "adv_auditors", "auditor"), ("prime_broker", "adv_prime_brokers", "prime_broker")):
        tot = c.execute(f"select sum(f.gav) from adv_funds f where exists(select 1 from {t} x where x.filing_id=f.filing_id and x.reference_id=f.reference_id) and f.fund_type='Hedge Fund'").fetchone()[0]
        top = c.execute(f"select x.{col}, sum(f.gav) g from adv_funds f join (select distinct filing_id,reference_id,{col} from {t}) x on x.filing_id=f.filing_id and x.reference_id=f.reference_id where f.fund_type='Hedge Fund' group by 1 order by g desc limit 6").fetchall()
        out[kind] = [(n, round(g / tot, 3)) for n, g in top]
    return out
if __name__ == "__main__": print(build("/workspace/triage_os_data/triage.db"))

def spv_stats(db):
    """SPV naming patterns in BDC borrower names (30 Jun 2026) - Delaware-style holdco/midco/bidco chains and offshore suffixes."""
    c = sqlite3.connect(db, timeout=120); from collections import Counter
    tags = Counter(); dist = Counter(); n = 0; nd = 0
    for bor, m in c.execute("select borrower,min(mark) from bdc_marks where period='2026-06-30' and mark>0 group by borrower_key"):
        t = spv_tags(bor); n += 1; tags.update(t)
        if m < 80: nd += 1; dist.update(t)
    c.execute("drop table if exists spv_patterns"); c.execute("create table spv_patterns(tag,borrowers,distressed_borrowers,share_all,share_distressed)")
    c.executemany("insert into spv_patterns values(?,?,?,?,?)", [(k, tags[k], dist[k], round(tags[k] / n, 4), round(dist[k] / nd, 4) if nd else None) for k in tags]); c.commit()
    return n, nd, tags.most_common(12)
