"""TRIAGE OS local app: stdlib HTTP server + SQLite (read-only). Bind 127.0.0.1 only. Run: python3 server.py [port]"""
import json, os, re, sqlite3, sys, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
DB = os.environ.get("TRIAGE_DB", "/workspace/triage_os_data/triage.db")
HITLOG = os.environ.get("TRIAGE_HITLOG", "/workspace/triage_os_data/hit_log.jsonl")
STATIC = os.path.join(os.path.dirname(__file__), "static")
DIST = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
DIST = os.path.normpath(DIST)
def q(sql, a=()):
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=60); c.row_factory = sqlite3.Row
    try: return [dict(r) for r in c.execute(sql, a)]
    except sqlite3.OperationalError: return []
def nk(s):
    from datasets import norm
    return norm(s)
def badge_for(text):
    """Verification status for a fact from the ledger (substring match on claim id / text)."""
    return None
def stats():
    T = ["icij_entities", "icij_intermediaries", "icij_rel", "sanctions", "formd_issuers", "pension_sb", "faa_aircraft", "epa_cases", "adv_funds", "adv_auditors", "adv_prime_brokers", "uk_corporate_psc", "usaspending_awards", "gleif_l2",
         "bdc_marks", "f13_holdings", "cap_structures_top15", "claims_calendar", "warn_state_notices", "watchlist", "edges2", "verification"]
    out = {}
    for t in T:
        r = q(f"select count(*) n from {t}"); out[t] = r[0]["n"] if r else None
    out["verification_status"] = {r["status"]: r["n"] for r in q("select status,count(*) n from verification group by 1")}
    return out
def search(s):
    s = f"%{s.lower()}%"
    return q("""select name, 'watchlist' kind, reason from watchlist where lower(name) like ? union
                select distinct issuer, 'issuer', situation from cap_structures_top15 where lower(issuer) like ? union
                select distinct filer, 'holder', '13F' from f13_holdings where lower(filer) like ? and issuer_key='echostar' limit 40""", (s, s, s))
def graph(name):
    k = nk(name); N = {}; E = []
    def node(i, label, kind, url=None, status=None):
        N.setdefault(i, {"id": i, "label": label, "kind": kind, "url": url, "status": status}); return i
    root = node("E:" + k, name, "company")
    for r in q("select * from cap_structures_top15 where lower(issuer) like ? or lower(situation) like ?", (f"%{name.lower()}%", f"%{name.lower()}%")):
        t = node(f"T:{r['issuer']}:{r['tranche']}:{r['coupon']}:{r['holder']}", f"{r['tranche']} {r['coupon']} {r['maturity']} ${r['amount_usd_m']}m", "tranche", r["source_url"], r["status"].split(" ")[0])
        E.append({"s": root, "t": t, "label": r["lien"]})
        if r["holder"] and r["holder"] not in ("", "n/d"):
            h = node("H:" + r["holder"][:40], r["holder"][:60], "holder"); E.append({"s": h, "t": t, "label": f"holds (mark {r['mark']})"})
    for r in q("select bdc,borrower,identifier,mark,par,source_url from bdc_marks where period='2026-06-30' and borrower_key in (select borrower_key from bdc_marks where lower(borrower) like ?) limit 40", (f"%{name.lower()}%",)):
        t = node(f"B:{r['bdc']}:{r['identifier']}", f"{r['identifier'].split('|')[1].strip() if '|' in r['identifier'] else r['identifier']} @ {r['mark']}", "tranche", r["source_url"], "VERIFIED")
        E.append({"s": root, "t": t, "label": "borrower"}); h = node("H:" + r["bdc"], r["bdc"], "lender"); E.append({"s": h, "t": t, "label": f"lender ${(r['par'] or 0)/1e6:.1f}m"})
    if "echostar" in k or "dish" in k or "hughes" in k:
        for r in q("select filer, sum(value) v, min(source_url) u from f13_holdings where issuer_key='echostar' group by filer order by v desc limit 12"):
            h = node("H:" + r["filer"], r["filer"], "holder", r["u"], "VERIFIED"); E.append({"s": h, "t": root, "label": f"13F ${r['v']/1e6:.0f}m"})
    for r in q("select * from edges2 where lower(src) like ?", (f"%{name.lower()}%",)):
        kind = {"pension_underfunding": "pension", "gov_contractor": "contract", "environmental_liability": "liability", "uk_psc_subsidiaries": "owner", "offshore_parent_chain": "owner", "offshore_leaks_namesake": "offshore", "sanctions_hit": "sanction", "aircraft_collateral": "asset"}.get(r["type"], "other")
        d = node("X:" + r["edge_id"], r["dst"], kind, r["source_url"], r["status"]); E.append({"s": root, "t": d, "label": r["type"]})
    for r in q("select * from gleif_l2 where lower(query) like ?", (f"%{name.lower()}%",)):
        if r["direct_parent"]: p = node("L:" + r["direct_parent_lei"], f"{r['direct_parent']} ({r['direct_parent_jur']})", "owner", r["source_url"], "VERIFIED"); E.append({"s": p, "t": root, "label": "GLEIF direct parent"})
        if r["ultimate_parent"] and r["ultimate_parent_lei"] != r["direct_parent_lei"]: p = node("L:" + r["ultimate_parent_lei"], f"{r['ultimate_parent']} ({r['ultimate_parent_jur']})", "owner", r["source_url"], "VERIFIED"); E.append({"s": p, "t": root, "label": "GLEIF ultimate parent"})
    for r in q("select src,dst,detail,evidence_url from holdings_graph where edge_type='lei_parent' and lower(src) like ?", (f"%{name.lower()}%",)):
        p = node("L:" + r["dst"], r["dst"], "owner", r["evidence_url"], "VERIFIED"); E.append({"s": p, "t": root, "label": r["detail"][:30]})
    node("P:none", "Patent liens: no public USPTO bulk access this pass", "gap"); E.append({"s": root, "t": "P:none", "label": "patents"})
    return {"nodes": list(N.values()), "edges": E}
SITS = [("hughes", "Hughes Satellite Systems 26-90739", ["hughes"]), ("dish", "DISH DBS 26-90627", ["dish"]), ("echostar", "EchoStar parent", ["echostar"]), ("truefood", "True Food Kitchen (FRC Balance) 26-90806", ["true food", "frc balance"]),
        ("omnis", "Omnis Pleasants 26-11169", ["omnis"]), ("medallia", "Medallia lender takeover", ["medallia"]), ("baywa", "BayWa / Kronos hybrid", ["baywa", "kronos"]), ("branicks", "Branicks bond", ["branicks"]),
        ("zhenro", "Zhenro HK", ["zhenro"]), ("agile", "Agile Group schemes", ["agile"]), ("mm2", "MM2 Asia scheme", ["mm2"]), ("konghwee", "Kong Hwee JM", ["kong hwee"]), ("zentoshin", "Zentoshin bankruptcy", ["zentoshin"]), ("toysrus", "Toys R Us Japan", ["toys"])]
def situations():
    out = []
    for key, title, kws in SITS:
        like = " or ".join(["lower(claim) like ?"] * len(kws)); a = [f"%{x}%" for x in kws]
        ev = [{"date": r["date"], "what": r["event"] + f" ({r['state']})", "url": r["source_url"], "status": r["status"].split(" ")[0]} for r in q("select * from claims_calendar where " + " or ".join(["lower(case_name) like ?"] * len(kws)), a)]
        ev += [{"date": r["next_date"], "what": f"{r['stage']} — next date", "url": r["url"], "status": r["status"]} for r in q("select * from world_situations where " + " or ".join(["lower(entity) like ?"] * len(kws)), a) if r["next_date"]]
        facts = q(f"select claim_id,claim,status,primary_url,checked,fix from verification where {like}", a)
        for f in facts:
            m = re.search(r"(\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* 20\d\d)", f["claim"] + " " + (f["fix"] or ""))
            if m:
                import datetime as dt
                try: ev.append({"date": dt.datetime.strptime(m.group(1)[:6].strip() + " " + m.group(1)[-4:], "%d %b %Y").date().isoformat(), "what": f["claim"][:90], "url": f["primary_url"], "status": f["status"]})
                except ValueError: pass
        out.append({"key": key, "title": title, "timeline": sorted(ev, key=lambda e: e["date"] or ""), "facts": facts})
    return out
def hitlog(n=200):
    from hit_log import verify_chain
    rows = [json.loads(l) for l in open(HITLOG)] if os.path.exists(HITLOG) else []
    ok, bad = verify_chain(HITLOG) if rows else (True, None)
    return {"chain_ok": ok, "broken_at": bad, "count": len(rows), "entries": rows[-n:][::-1]}
def marks_history(borrower):
    k = f"%{borrower.lower()}%"
    rows = q("select bdc, period, avg(mark) mark, sum(par) par, min(source_url) url from (select bdc,period,mark,par,source_url from bdc_marks_hist where lower(borrower) like ? union all select bdc,period,mark,par,source_url from bdc_marks where lower(borrower) like ?) where mark>0 group by bdc, period order by period", (k, k))
    out = {}
    for r in rows: out.setdefault(r["bdc"], []).append(r)
    return out
def cap(situation):
    return q("select * from cap_structures_top15 where situation like ? or issuer like ?", (f"%{situation}%", f"%{situation}%"))
CONTROL = os.environ.get("TRIAGE_CONTROL", "/workspace/triage_os_data/control.json")
SYSTEMIC = os.environ.get("TRIAGE_SYSTEMIC", "/workspace/triage_os_data/systemic.json")
MINING = os.environ.get("TRIAGE_MINING", "/workspace/triage_os_data/mining.json")
def mining():
    return json.load(open(MINING)) if os.path.exists(MINING) else {"events": [], "regime": []}
WORLD = os.environ.get("TRIAGE_WORLD", "/workspace/triage_os_data/world.json")
def world():
    return json.load(open(WORLD)) if os.path.exists(WORLD) else {"situations": [], "buyers": [], "backers": []}
def systemic():
    return json.load(open(SYSTEMIC)) if os.path.exists(SYSTEMIC) else {}
def control():
    return json.load(open(CONTROL)) if os.path.exists(CONTROL) else {"classes": [], "holders": [], "situations": [], "facts": []}
_DIST = None
def distressed():
    global _DIST
    if _DIST is not None: return _DIST
    rows = q("""select borrower_key, borrower, bdc, round(sum(fv)*100.0/sum(par),1) mark, round(min(mark),1) min_mark, round(sum(par)/1e6,1) par_m, round(sum(fv)/1e6,1) fv_m, count(*) tranches, min(source_url) source_url from bdc_marks
                where period='2026-06-30' and mark>0 and borrower not like 'Investment%' and borrower not like 'Portfolio Company%' and borrower not like 'Debt Investments%' and borrower not like 'Total%' and length(borrower_key)>3 and borrower not like 'Senior Secured%' and borrower not like 'First Lien%' and borrower not like 'Second Lien%' and borrower not like 'Subordinated%'
                group by borrower_key, bdc having sum(fv)*100.0/sum(par) between 1 and 75 and count(*)<40 order by sum(par) desc limit 400""")
    hist = {}
    for r in q("""select borrower_key, bdc, period, round(sum(fv)*100.0/nullif(sum(par),0),1) m from (select borrower_key,bdc,period,par,fv from bdc_marks_hist union all select borrower_key,bdc,period,par,fv from bdc_marks)
                  where par>0 group by borrower_key, bdc, period order by period"""):
        hist.setdefault((r["borrower_key"], r["bdc"]), []).append([r["period"], r["m"]])
    for r in rows:
        h = hist.get((r["borrower_key"], r["bdc"]), []); r["hist"] = h
        r["qa"] = "units check" if (r["min_mark"] or 0) < 2 or r["mark"] < 15 else "ok"
        r["chg_q"] = round(h[-1][1] - h[-2][1], 1) if len(h) >= 2 and h[-1][1] is not None and h[-2][1] is not None else None
    _DIST = rows; return rows
ROUTES = {"/api/committee": lambda p: (json.load(open("/workspace/triage_os_data/committee.json")) if os.path.exists("/workspace/triage_os_data/committee.json") else {}), "/api/mining": lambda p: mining(), "/api/world": lambda p: world(), "/api/systemic": lambda p: systemic(), "/api/control": lambda p: control(), "/api/marks": lambda p: marks_history(p.get("borrower", [""])[0]), "/api/cap": lambda p: cap(p.get("situation", [""])[0]), "/api/distressed": lambda p: distressed(),"/api/stats": lambda p: stats(), "/api/search": lambda p: search(p.get("q", [""])[0]), "/api/graph": lambda p: graph(p.get("entity", ["EchoStar Corp"])[0]),
          "/api/situations": lambda p: situations(), "/api/hitlog": lambda p: hitlog(), "/api/verification": lambda p: q("select * from verification order by claim_id"),
          "/api/edges": lambda p: q("select * from edges2 order by status, type, value desc"), "/api/concentration": lambda p: q("select * from fund_service_concentration")}
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); p = urllib.parse.parse_qs(u.query)
        if u.path in ROUTES:
            body = json.dumps(ROUTES[u.path](p), default=str).encode(); ct = "application/json"
        else:
            root = DIST if os.path.isdir(DIST) else STATIC
            rel = u.path.lstrip("/") or "index.html"
            f = os.path.normpath(os.path.join(root, rel))
            if not f.startswith(root) or not os.path.isfile(f): f = os.path.join(root, "index.html")
            body = open(f, "rb").read()
            ct = {".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".pdf": "application/pdf"}.get(os.path.splitext(f)[1], "application/octet-stream")
        self.send_response(200); self.send_header("Content-Type", ct); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
