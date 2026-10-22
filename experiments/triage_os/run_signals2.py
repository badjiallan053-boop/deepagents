"""Run signal pack 2 against triage.db and write signals2_summary.json. Public, read-only."""
import csv, json, re, sqlite3, sys, urllib.parse
import signals2 as s
db, d = sys.argv[1], sys.argv[2]
con = sqlite3.connect(db, timeout=120); out = {}
out["bdc_coverage_rows"] = s.bdc_coverage(con)
out["nport_rows"] = s.nport_outflow_stressed(con)
out["cross_markdown"] = s.cross_markdown(con)
bk = s.bankruptcies(f"{d}/bt/8k_items.jsonl")
a401 = s.load_jsonl(f"{d}/bt/s2_401.jsonl"); nt = s.load_jsonl(f"{d}/bt/s2_nt10k.jsonl")
wv = s.load_jsonl(f"{d}/bt/s2_waiver.jsonl"); slb = s.load_jsonl(f"{d}/bt/s2_slb.jsonl")
names = {}
for f in ("s2_401", "s2_nt10k", "s2_waiver", "s2_slb"):
    for line in open(f"{d}/bt/{f}.jsonl"):
        r = json.loads(line); names[r["cik"]] = r["name"]
slb_cluster = {c: v for c, v in slb.items() if len(v) >= 2}
combo = s.combine(a401, nt)
out["backtest"] = {"auditor_change_4.01": s.event_precision(a401, bk), "nt_10k": s.event_precision(nt, bk),
                   "4.01 + NT 10-K within 365d": s.event_precision(combo, bk), "covenant_waiver_8k": s.event_precision(wv, bk),
                   "sale_leaseback_8k": s.event_precision(slb, bk), "sale_leaseback_cluster_2+": s.event_precision(slb_cluster, bk)}
for nm, fl in (("auditor_change_plus_nt10k", combo), ("covenant_waiver_8k", wv), ("sale_leaseback_cluster", slb_cluster)):
    s.recent_flags(con, nm, fl, names)
wl = [(r["key"].split(":")[1], r["entity"]) for r in csv.DictReader(open(f"{d}/prefiling_watchlist.csv")) if r["key"].startswith("cik:")]
out["form4_rows"] = s.form4_cluster(con, wl)
corp = re.compile(r"\b(inc|llc|corp|corporation|ltd|holdings|company|co\.|lp|group)\b", re.I)
dn = {t for (t,) in con.execute("select title from signals where source='courtlistener'") if t and corp.search(t)}
dn |= {e for _, e in wl}
dn |= {b for (b,) in con.execute("select distinct borrower from bdc_marks where period='2026-06-30' and mark<60 and mark>0")}
dn |= {"True Food Kitchen", "Barista Parlor", "Chain Reaction Cycles", "Hughes Network", "DISH Network", "QVC", "Joann", "Big Lots", "Party City", "Rite Aid", "At Home", "Hooters", "TGI Fridays", "Red Lobster", "Express", "Conn's", "Bowlero"}
out["tenant_rows"] = s.tenant_distress(con, sorted(dn))
# UK: resolve company numbers from the public search page
uk = []
for nm in ["TG JONES RETAIL UK LIMITED", "IGUANAS", "WHSMITH", "POLLEN ESTATE", "CLINTON CARDS"]:
    try:
        h = s.http("https://find-and-update.company-information.service.gov.uk/search/companies?q=" + urllib.parse.quote(nm), {"User-Agent": "Mozilla/5.0"})
        m = re.search(r'href="/company/([A-Z0-9]{8})"[^>]*>\s*(?:<[^>]+>\s*)*([^<]+)', h)
        if m: uk.append((m.group(1), m.group(2).strip()))
    except Exception as e:
        out.setdefault("uk_errors", []).append(str(e)[:80])
out["uk_rows"] = s.ch_overdue(con, uk); out["uk_companies"] = uk
out["exposure_rows"] = s.exposure_mentions(con, ["EchoStar", "Hughes Network", "New Fortress Energy", "Clear Channel Outdoor", "QVC", "Trinseo", "Medallia", "Peraton"])
out["trade_claims_rows"] = s.top20_claims(con, ["Hughes Satellite", "DISH DBS", "True Food Kitchen", "Barista Parlor", "Chain Reaction Cycles"])
json.dump(out, open(f"{d}/signals2_summary.json", "w"), indent=1, default=str); print(json.dumps(out, indent=1, default=str))
