"""Aggregate one N-PORT quarterly dataset (all registered funds): latest filing per series, holdings by asset class,
Level-3 share, CMBS and private-loan exposure, and the fund-overlap ('forced seller') map for distressed issuers."""
import csv, sys, os, re, sqlite3, collections, datetime
csv.field_size_limit(10**9)
D = sys.argv[1] if len(sys.argv) > 1 else "/workspace/triage_os_data/systemic"
DB = os.environ.get("TRIAGE_DB", "/workspace/triage_os_data/triage.db")
WATCH = ["ECHOSTAR", "HUGHES SATELLITE", "DISH DBS", "DISH NETWORK", "BRANICKS", "BAYWA", "MULTI-COLOR", "LOPAREX", "MEDALLIA", "XPLORE"]
CMBS = re.compile(r"(BENCHMARK|BANK5?|BMO|JPMDB|JPMBB|JPMCC|WFCM|WELLS FARGO COMMERCIAL|MORGAN STANLEY CAPITAL I|MSBAM|CGCMT|CITIGROUP COMMERCIAL|COMM 20|GS MORTGAGE SECURITIES|CSAIL|CFCRE|UBS COMMERCIAL|DBJPM|BBCMS|BX TRUST|BX COMMERCIAL|COMMERCIAL MORTGAGE)", re.I)
def rd(fn): return csv.DictReader(open(os.path.join(D, fn), newline="", errors="ignore"), delimiter="\t", quoting=csv.QUOTE_NONE)
def dt(s):
    try: return datetime.datetime.strptime(s, "%d-%b-%Y")
    except Exception: return datetime.datetime(1900, 1, 1)
sub = {r["ACCESSION_NUMBER"]: dt(r["REPORT_DATE"]) for r in rd("SUBMISSION.tsv")}
reg = {r["ACCESSION_NUMBER"]: r["REGISTRANT_NAME"] for r in rd("REGISTRANT.tsv")}
best = {}
for r in rd("FUND_REPORTED_INFO.tsv"):
    a, s = r["ACCESSION_NUMBER"], r["SERIES_ID"] or r["ACCESSION_NUMBER"]
    try: na = float(r["NET_ASSETS"] or 0)
    except ValueError: na = 0
    if s not in best or sub.get(a, datetime.datetime(1900,1,1)) > best[s][1]: best[s] = (a, sub.get(a, datetime.datetime(1900,1,1)), r["SERIES_NAME"], na)
keep = {v[0]: (k, v[2], v[3]) for k, v in best.items()}
agg = collections.defaultdict(float); lvl3 = 0.0; tot = 0.0; n = 0; nk = 0
cmbs = collections.defaultdict(lambda: [0.0, set()]); loans = collections.defaultdict(float); watch = []
for r in rd("FUND_REPORTED_HOLDING.tsv"):
    n += 1
    a = r["ACCESSION_NUMBER"]
    if a not in keep: continue
    nk += 1
    try: v = float(r["PERCENTAGE"] or 0) / 100.0 * keep[a][2]   # % of NAV x NAV: robust to currency/unit errors in CURRENCY_VALUE
    except ValueError: continue
    if abs(v) > 2 * keep[a][2]: continue
    if r["PAYOFF_PROFILE"] == "Short": continue
    cat = r["ASSET_CAT"] or "NA"; agg[(cat, r["ISSUER_TYPE"] or "NA")] += v; tot += v
    if r["FAIR_VALUE_LEVEL"] == "3": lvl3 += v
    if cat == "ABS-MBS" and CMBS.search(r["ISSUER_NAME"] + " " + r["ISSUER_TITLE"]):
        c = cmbs[keep[a][1]]; c[0] += v
    if cat == "LON": loans[keep[a][1]] += v
    nm = (r["ISSUER_NAME"] + " " + r["ISSUER_TITLE"]).upper()
    for w in WATCH:
        if w in nm:
            watch.append((w, r["ISSUER_NAME"], r["ISSUER_TITLE"], r["ISSUER_CUSIP"], keep[a][1], reg.get(a, ""), v, float(r["PERCENTAGE"] or 0) * 100, r["FAIR_VALUE_LEVEL"], a)); break
con = sqlite3.connect(DB)
con.execute("drop table if exists nport_asset_mix"); con.execute("create table nport_asset_mix (asset_cat, issuer_type, value_usd)")
con.executemany("insert into nport_asset_mix values (?,?,?)", [(k[0], k[1], v) for k, v in agg.items()])
con.execute("drop table if exists nport_funds"); con.execute("create table nport_funds (series_id, accession, series_name, net_assets, cmbs_usd, loans_usd)")
con.executemany("insert into nport_funds values (?,?,?,?,?,?)", [(v[0], a, v[1], v[2], cmbs[v[1]][0] if v[1] in cmbs else 0, loans.get(v[1], 0)) for a, v in keep.items()])
con.execute("drop table if exists nport_watch"); con.execute("create table nport_watch (watch, issuer, title, cusip, fund, registrant, value_usd, pct_nav, fv_level, accession)")
con.executemany("insert into nport_watch values (?,?,?,?,?,?,?,?,?,?)", watch)
con.execute("create table if not exists dataset_counts (dataset, rows, note, source_url)")
con.execute("delete from dataset_counts where dataset like 'nport%'")
u = "https://www.sec.gov/files/dera/data/form-n-port-data-sets/2026q3_nport.zip"
con.executemany("insert into dataset_counts values (?,?,?,?)", [("nport_2026q3_holdings_raw", n, "all holding rows in FUND_REPORTED_HOLDING", u), ("nport_2026q3_holdings_latest", nk, "rows in latest filing per series", u), ("nport_2026q3_series", len(keep), "fund series", u)])
con.commit()
print("rows", n, "kept", nk, "series", len(keep), "total $bn", round(tot/1e9), "level3 $bn", round(lvl3/1e9,1), "cmbs funds", len(cmbs), "watch rows", len(watch))
