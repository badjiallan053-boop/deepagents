"""API-backed public datasets for the watchlist: USASpending (federal contracts) and GLEIF level-2 parent chains."""
import json, sqlite3, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datasets import norm
UA = {"User-Agent": "TRIAGE-OS research arslane.souici@example.com", "Content-Type": "application/json"}
def _get(url, data=None, tries=3):
    for i in range(tries):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=25).read())
        except Exception as e:
            if i == tries - 1: return {"error": str(e)}
            time.sleep(2 * (i + 1))
def usaspending_one(name):
    body = json.dumps({"filters": {"recipient_search_text": [name], "award_type_codes": ["A", "B", "C", "D"], "time_period": [{"start_date": "2024-10-01", "end_date": "2026-09-30"}]},
                       "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "End Date", "generated_internal_id"], "limit": 100, "sort": "Award Amount", "order": "desc"}).encode()
    j = _get("https://api.usaspending.gov/api/v2/search/spending_by_award/", body)
    k = norm(name)
    return [(k, name, r["Recipient Name"], r["Award ID"], r.get("Award Amount") or 0, r.get("Awarding Agency"), r.get("End Date"), f"https://www.usaspending.gov/award/{r['generated_internal_id']}")
            for r in j.get("results", []) if norm(r["Recipient Name"]) == k]
def usaspending(db, names, workers=6):
    c = sqlite3.connect(db, timeout=120)
    c.execute("create table if not exists usaspending_awards(nkey,query,recipient,award_id,amount,agency,end_date,source_url)")
    with ThreadPoolExecutor(workers) as ex:
        for rows in ex.map(usaspending_one, names):
            if rows: c.executemany("insert into usaspending_awards values(?,?,?,?,?,?,?,?)", rows); c.commit()
    return c.execute("select count(*) from usaspending_awards").fetchone()[0]
def gleif_one(name):
    q = urllib.parse.quote(name); j = _get(f"https://api.gleif.org/api/v1/lei-records?filter[fulltext]={q}&page[size]=5")
    k = norm(name); out = []
    for r in j.get("data", []):
        ln = r["attributes"]["entity"]["legalName"]["name"]
        if norm(ln) != k: continue
        lei = r["id"]; row = [k, name, lei, ln, r["attributes"]["entity"]["jurisdiction"]]
        for rel in ("direct-parent", "ultimate-parent"):
            p = _get(f"https://api.gleif.org/api/v1/lei-records/{lei}/{rel}")
            d = p.get("data") if isinstance(p.get("data"), dict) else None
            row += [d["id"], d["attributes"]["entity"]["legalName"]["name"], d["attributes"]["entity"]["jurisdiction"]] if d else ["", "", ""]
        row.append(f"https://search.gleif.org/#/record/{lei}"); out.append(tuple(row)); break
    time.sleep(1.0); return out
def gleif(db, names, workers=2):
    c = sqlite3.connect(db, timeout=120)
    c.execute("create table if not exists gleif_l2(nkey,query,lei,legal_name,jurisdiction,direct_parent_lei,direct_parent,direct_parent_jur,ultimate_parent_lei,ultimate_parent,ultimate_parent_jur,source_url)")
    with ThreadPoolExecutor(workers) as ex:
        for rows in ex.map(gleif_one, names):
            if rows: c.executemany("insert into gleif_l2 values(?,?,?,?,?,?,?,?,?,?,?,?)", rows); c.commit()
    return c.execute("select count(*) from gleif_l2").fetchone()[0]
if __name__ == "__main__":
    import sys
    db = "/workspace/triage_os_data/triage.db"; c = sqlite3.connect(db)
    q = {"usa": "select name from watchlist where source in ('cap_structure','world') or (source='bdc_marks' and cast(substr(reason, instr(reason,'mark ')+5) as real)<60) or (source='signal' and reason in ('auditor_change_plus_nt10k','trade_claims_top20'))",
         "gleif": "select name from watchlist where source in ('cap_structure','world') or (source='bdc_marks' and cast(substr(reason, instr(reason,'mark ')+5) as real)<50)"}
    names = [r[0].split("  (")[0] for r in c.execute(q[sys.argv[1]])]
    print(len(names), flush=True)
    if sys.argv[1] == "usa": print("usaspending", usaspending(db, names))
    else: print("gleif", gleif(db, names))
