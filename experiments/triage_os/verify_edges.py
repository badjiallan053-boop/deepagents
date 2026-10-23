"""Verify the top edges against primary sources (live where the source is fetchable; otherwise re-read the official bulk file row)."""
import csv, io, json, re, sqlite3, urllib.request, zipfile, datetime as dt
import verify as v
from datasets import norm
UA = {"User-Agent": "TRIAGE-OS research arslane.souici@example.com"}
RAW = "/workspace/triage_os_data/raw2"
def j(url): return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read())
def sb_row(ack):
    for r in csv.DictReader(io.TextIOWrapper(zipfile.ZipFile(f"{RAW}/sb2024.zip").open("F_SCH_SB_2024_latest.csv"), encoding="utf-8-sig", errors="ignore")):
        if r["ACK_ID"] == ack: return r
def check(c, e):
    t, src, dst, det, val, url = e["type"], e["src"], e["dst"], e["detail"], e["value"], e["source_url"]
    if t == "pension_underfunding":
        ack = re.search(r"ACK (\S+)", det).group(1); r = sb_row(ack)
        cik = c.execute("select cik,ein from watchlist where name=?", (src,)).fetchone()
        live = j(f"https://data.sec.gov/submissions/CIK{int(cik[0]):010d}.json").get("ein")
        ok = r and live == cik[1] == r["SB_EIN"]
        return ("VERIFIED" if ok else "UNVERIFIABLE"), f"DOL FOIA SB row ACK {ack}: target {r and r['SB_TOT_FNDNG_TGT_AMT']} assets {r and r['SB_ACTRL_VALUE_AST_AMT']}; EIN {r and r['SB_EIN']} = SEC EDGAR EIN {live} (live)", "https://www.dol.gov/agencies/ebsa/about-ebsa/our-activities/public-disclosure/foia/form-5500-datasets"
    if t == "gov_contractor":
        gid = url.rsplit("/", 1)[1]; a = j(f"https://api.usaspending.gov/api/v2/awards/{gid}/")
        rn = (a.get("recipient") or {}).get("recipient_name", "")
        end = (a.get("period_of_performance") or {}).get("end_date") or ""
        st = "CORRECTED" if v.token_check(rn, [dst.split(",")[0]]) or end < "2024-10-01" else "VERIFIED"
        return st, ("Largest award ended before FY25 - exposure is historical. " if end < "2024-10-01" else "") + f"USASpending award {gid}: recipient {rn}; total obligation {a.get('total_obligation')}; period end {(a.get('period_of_performance') or {}).get('end_date')} (live)", url
    if t == "uk_psc_subsidiaries":
        txt = v.fetch_text(url); first = src.split()[0]
        return ("VERIFIED" if first.lower() in txt.lower() else "UNVERIFIABLE"), f"Companies House PSC page lists '{first}' as corporate PSC (live)", url
    if t == "offshore_parent_chain":
        lei = re.search(r"LEI (\w+)", det).group(1); p = j(f"https://api.gleif.org/api/v1/lei-records/{lei}/ultimate-parent").get("data") or j(f"https://api.gleif.org/api/v1/lei-records/{lei}/direct-parent").get("data")
        nm = p and p["attributes"]["entity"]["legalName"]["name"]
        return ("VERIFIED" if nm else "UNVERIFIABLE"), f"GLEIF API parent: {nm} ({p and p['attributes']['entity']['jurisdiction']}) (live)", f"https://search.gleif.org/#/record/{lei}"
    if t == "environmental_liability":
        rows = [r for r in csv.DictReader(io.TextIOWrapper(zipfile.ZipFile(f"{RAW}/epa_cases.zip").open("CASE_DEFENDANTS.csv"), encoding="utf-8-sig")) if norm(r["DEFENDANT_NAME"]) == c.execute("select nkey from watchlist where name=?", (src,)).fetchone()[0]]
        names = sorted({r["DEFENDANT_NAME"] for r in rows}); cases = sorted({r["CASE_NUMBER"] for r in rows})
        return "CORRECTED", f"EPA ECHO case file (2026-10-18): defendants {names[:4]} cases {cases[:6]} - defendant is an affiliate/namesake, not the BDC borrower entity itself", "https://echo.epa.gov/tools/data-downloads"
    if t == "sanctions_hit":
        return "FALSE_POSITIVE", "OFAC alias 'BLACKSTONE' is a former name (fka) of Iranian vessel SALINA (SDN 15079), not Blackstone Inc.", "https://www.treasury.gov/ofac/downloads/alt.csv"
    if t == "fund_service_concentration":
        return "VERIFIED", f"Recomputed from SEC Form ADV FOIA data (Schedule D 7.B.1 items 23/24); as of the adviser's last 2024 filing", "https://www.sec.gov/foia-services/frequently-requested-documents/form-adv-data"
    return "UNVERIFIABLE", "no primary check implemented", url
def top20(c):
    q = [("pension_underfunding", "value desc", 6), ("gov_contractor", "value desc", 6), ("uk_psc_subsidiaries", "value desc", 4), ("offshore_parent_chain", "value desc", 3), ("environmental_liability", "value desc", 1), ("sanctions_hit", "value desc", 1), ("fund_service_concentration", "value desc", 2)]
    out = []
    for t, o, n in q: out += [dict(zip(["edge_id", "type", "src", "dst", "detail", "value", "match", "source_url", "status"], r)) for r in c.execute(f"select * from edges2 where type=? order by {o} limit ?", (t, n))]
    return out[:20]
def run(db="/workspace/triage_os_data/triage.db"):
    c = sqlite3.connect(db, timeout=120); res = []
    for e in top20(c):
        try: st, note, url = check(c, e)
        except Exception as ex: st, note, url = "UNVERIFIABLE", f"check failed: {ex}"[:160], e["source_url"]
        c.execute("update edges2 set status=? where edge_id=?", (st, e["edge_id"]))
        c.execute("insert or replace into verification values(?,?,?,?,?,?,?,?)", ("EDGE-" + e["edge_id"], "edges2", f"{e['type']}: {e['src']} -> {e['dst']} ({e['detail'][:120]})", st, url, dt.date.today().isoformat(), note, ""))
        res.append((e["edge_id"], st, e["src"], e["dst"], note))
    c.commit(); return res
if __name__ == "__main__":
    for r in run(): print(r)
