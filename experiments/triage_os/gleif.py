"""GLEIF LEI lookup + direct/ultimate parent links (public API, no key). Stores lei_entities and adds lei_parent edges."""
import json, sqlite3, sys, time, urllib.parse, urllib.request
API = "https://api.gleif.org/api/v1"
def get_json(url):
    try: return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/vnd.api+json"}), timeout=30))
    except Exception: return {}
import difflib, re
def _n(s): return " ".join(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())
def same_entity(query, legal):
    q, l = _n(query), _n(legal)
    return l.startswith(q) or difflib.SequenceMatcher(None, q, l[:len(q) + 4]).ratio() >= 0.97

def lookup(name, fetch=get_json):
    d = fetch(f"{API}/fuzzycompletions?field=entity.legalName&q={urllib.parse.quote(name)}").get("data", [])
    for x in d:
        lei = (x.get("relationships", {}).get("lei-records", {}).get("data") or {}).get("id")
        if lei and same_entity(name, x["attributes"]["value"]): return lei, x["attributes"]["value"]
    return None, None
def parents(lei, fetch=get_json):
    out = {}
    for rel in ("direct-parent", "ultimate-parent"):
        d = fetch(f"{API}/lei-records/{lei}/{rel}").get("data")
        if d: out[rel] = (d["id"], d["attributes"]["entity"]["legalName"]["name"], d["attributes"]["entity"]["legalAddress"].get("country"))
    return out
def run(db, names, fetch=get_json, pause=0.3):
    con = sqlite3.connect(db)
    con.execute("create table if not exists lei_entities (query, lei, legal_name, direct_parent_lei, direct_parent, ultimate_parent_lei, ultimate_parent, source_url, status default 'UNVERIFIED', primary key(query))")
    con.execute("create table if not exists holdings_graph (edge_type, src, dst, issuer_key, weight real, detail, evidence_url, period, status default 'UNVERIFIED')")
    con.execute("delete from holdings_graph where edge_type='lei_parent'"); con.execute("delete from lei_entities")
    n = 0
    for q in names:
        lei, legal = lookup(q, fetch)
        if not lei: continue
        p = parents(lei, fetch); dp = p.get("direct-parent", (None, None, None)); up = p.get("ultimate-parent", (None, None, None))
        url = f"https://search.gleif.org/#/record/{lei}"
        con.execute("insert or replace into lei_entities (query,lei,legal_name,direct_parent_lei,direct_parent,ultimate_parent_lei,ultimate_parent,source_url) values (?,?,?,?,?,?,?,?)",
                    (q, lei, legal, dp[0], dp[1], up[0], up[1], url))
        for kind, par in (("direct", dp), ("ultimate", up)):
            if par[0]:
                con.execute("insert into holdings_graph (edge_type,src,dst,issuer_key,weight,detail,evidence_url,period) values ('lei_parent',?,?,?,?,?,?,?)",
                            (legal, par[1], q.lower(), 1.0, f"{kind} parent {par[0]} ({par[2]})", url, "2026-10-22"))
                n += 1
        time.sleep(pause)
    con.commit(); return n
if __name__ == "__main__":
    print(run(sys.argv[1], sys.argv[2:]), "parent edges")
