"""France: BODACC procédures collectives (bulk export) -> opening judgments of sauvegarde / redressement / liquidation,
enriched with turnover from the public recherche-entreprises.api.gouv.fr (INSEE/INPI data). Filter: revenue > EUR10m."""
import csv, json, re, sqlite3, time, os, sys, urllib.request, urllib.parse
D = "/workspace/triage_os_data/world"; DB = os.environ.get("TRIAGE_DB", "/workspace/triage_os_data/triage.db")
csv.field_size_limit(10**8)
def proc(j):
    t = (j or "").lower()
    if "sauvegarde" in t: return "sauvegarde"
    if "redressement" in t: return "redressement"
    if "liquidation" in t: return "liquidation"
    return None
def opening(j):
    t = (j or "").lower()
    return any(k in t for k in ("ouverture", "prononce la liquidation", "conversion", "plan de sauvegarde accéléré", "sauvegarde accélérée"))
def rows():
    out = {}
    for r in csv.DictReader(open(f"{D}/bodacc_pc.csv", encoding="utf-8-sig"), delimiter=";"):
        p = proc(r["jugement"])
        if not p or not opening(r["jugement"]): continue
        siren = (r["registre"] or "").split(",")[0].replace(" ", "")
        if not re.fullmatch(r"\d{9}", siren): continue
        try: jd = json.loads(r["jugement"]).get("date", "")
        except Exception: jd = ""
        prev = out.get(siren)
        rank = {"liquidation": 3, "redressement": 2, "sauvegarde": 1}[p]
        if not prev or rank >= prev["rank"]:
            out[siren] = dict(siren=siren, name=r["commercant"], proc=p, rank=rank, date=jd or r["dateparution"], tribunal=r["tribunal"], dept=r["numerodepartement"], url=r["url_complete"])
    return out
def fin(siren):
    u = "https://recherche-entreprises.api.gouv.fr/search?q=" + siren
    for i in range(4):
        try:
            j = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "TRIAGE-OS research"}), timeout=30).read())
            res = [x for x in j.get("results", []) if x.get("siren") == siren]
            if not res: return None
            x = res[0]; f = x.get("finances") or {}
            yr = max(f) if f else None
            return dict(ca=(f[yr] or {}).get("ca") if yr else None, yr=yr, effectif=x.get("tranche_effectif_salarie"), naf=x.get("activite_principale"), cat=x.get("categorie_entreprise"))
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(2 + i * 2); continue
            return None
        except Exception: time.sleep(1)
    return None
if __name__ == "__main__":
    R = rows(); print("openings (unique SIREN):", len(R), {p: sum(1 for v in R.values() if v["proc"] == p) for p in ("sauvegarde", "redressement", "liquidation")}, flush=True)
    con = sqlite3.connect(DB, timeout=300)
    con.execute("create table if not exists fr_bodacc (siren primary key, name, proc, date, tribunal, dept, url, ca, ca_year, effectif, naf, cat)")
    done = {r[0] for r in con.execute("select siren from fr_bodacc")}
    # enrich: sauvegarde/redressement all; liquidation only if company category is not micro (checked after lookup)
    todo = [v for k, v in R.items() if k not in done and (v["proc"] != "liquidation" or "--all" in sys.argv)]
    todo.sort(key=lambda v: v["rank"])  # sauvegarde first
    from concurrent.futures import ThreadPoolExecutor
    def job(v): return v, (fin(v["siren"]) or {})
    with ThreadPoolExecutor(6) as ex:
        for i, (v, f) in enumerate(ex.map(job, todo)):
            con.execute("insert or replace into fr_bodacc values (?,?,?,?,?,?,?,?,?,?,?,?)", (v["siren"], v["name"], v["proc"], v["date"], v["tribunal"], v["dept"], v["url"], f.get("ca"), f.get("yr"), f.get("effectif"), f.get("naf"), f.get("cat")))
            if i % 100 == 0: con.commit(); print(i, len(todo), flush=True)
    con.commit(); print("done")
