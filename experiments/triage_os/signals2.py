"""TRIAGE OS signal pack 2 (public data, read-only, all outputs UNVERIFIED).

forced sellers : bdc_coverage, nport_outflow_stressed, cross_markdown
events         : event_backtest (4.01 auditor change + NT 10-K, covenant waiver, sale-leaseback) vs later 8-K 1.03
insider        : form4_cluster (company-level filing counts only; no individuals)
cmbs           : tenant_distress (ABS-EE largest tenants x watchlist/distress names)
uk             : ch_overdue (Companies House public page 'overdue' flag)
exposure       : exposure_mentions (10-K full-text mentions of a watchlist name as customer/supplier)
trade claims   : top20_claims (CourtListener/RECAP search for top-20 unsecured creditor lists)
"""
import datetime as dt, json, re, sqlite3, statistics, time, urllib.parse, urllib.request
from collections import defaultdict

UA = {"User-Agent": "TRIAGE-OS research arslane.souici@example.com"}
D = dt.date.fromisoformat

def http(url, headers=UA, timeout=60):
    for i in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout).read().decode("utf-8", "replace")
        except Exception as e: err = e; time.sleep(2)
    raise err

def _sig_table(con):
    con.execute("""create table if not exists signals2 (signal, entity, key, value real, detail, source_url, as_of,
                   status default 'UNVERIFIED', primary key(signal, key, as_of))""")

def _put(con, rows):
    _sig_table(con)
    con.executemany("insert or replace into signals2 (signal,entity,key,value,detail,source_url,as_of) values (?,?,?,?,?,?,?)", rows)
    con.commit(); return len(rows)

# ---------- forced sellers ----------
def coverage_from_facts(facts):
    g = facts.get("facts", {}).get("us-gaap", {})
    def last(tag):
        u = g.get(tag, {}).get("units", {})
        vals = [v for k in u for v in u[k] if v.get("form") in ("10-Q", "10-K")]
        return max(vals, key=lambda v: (v["end"], v.get("filed", ""))) if vals else None
    r = last("InvestmentCompanySeniorSecurityIndebtednessAssetCoverageRatio")
    if r: return float(r["val"]) * (100 if float(r["val"]) < 20 else 1), r["end"], "reported"
    eq, debt = last("StockholdersEquity"), last("LongTermDebt") or last("DebtInstrumentCarryingAmount")
    if eq and debt and debt["val"] > 0 and eq["end"] == debt["end"]:
        return round(100 * (1 + eq["val"] / debt["val"]), 1), eq["end"], "derived 1+NAV/debt"
    return None

def bdc_coverage(con, fetch=lambda u: json.loads(http(u)), threshold=170.0):
    ciks = con.execute("select bdc, substr(source_url, 41, instr(substr(source_url,41),'/')-1) from bdc_marks group by bdc").fetchall()
    rows = []
    for t, cik in ciks:
        try: c = coverage_from_facts(fetch(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"))
        except Exception: c = None
        if not c: continue
        cov, end, how = c
        if end < "2025-06-30": continue  # stale fact
        rows.append(("bdc_asset_coverage", t, t, round(cov, 1), f"{'BELOW' if cov < threshold else 'ok'} {threshold:.0f}% ({how}); statutory min 150%",
                     f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json", end))
        time.sleep(0.15)
    return _put(con, rows)

FLOW = re.compile(r'<mon(\d)Flow redemption="([\d.]+)" reinvestment="([\d.]+)" sales="([\d.]+)"')
def parse_flows(xml):
    na = re.search(r"<netAssets>([\d.]+)", xml)
    fl = [(float(r), float(s), float(rv)) for _, r, rv, s in FLOW.findall(xml)]
    if not na or not fl: return None
    red = sum(f[0] for f in fl); inflow = sum(f[1] + f[2] for f in fl)
    return {"net_assets": float(na.group(1)), "net_flow": inflow - red, "net_flow_pct": 100 * (inflow - red) / float(na.group(1))}

def nport_outflow_stressed(con, fetch=http, out_pct=-5.0, px=70.0):
    funds = con.execute("""select holder, source_url, group_concat(distinct issuer_key), sum(value_usd) from holders
        where holder_type like '%N-PORT%' and price is not null and price < ? group by holder, source_url""", (px,)).fetchall()
    rows = []
    for holder, url, keys, val in funds:
        try: f = parse_flows(fetch(url))
        except Exception: f = None
        if not f: continue
        flag = f["net_flow_pct"] <= out_pct
        rows.append(("nport_outflow_stressed", holder, holder, round(f["net_flow_pct"], 2),
                     f"{'FORCED-SELLER RISK' if flag else 'flows ok'}: 3m net flow {f['net_flow']/1e6:.1f}m on NAV {f['net_assets']/1e6:.0f}m; holds stressed {keys} ${val/1e6:.1f}m",
                     url, ""))
        time.sleep(0.15)
    return _put(con, rows)

def _qmarks(con, table):
    m = defaultdict(lambda: defaultdict(dict))
    try:
        for b, k, p, par, fv in con.execute(f"select bdc, borrower_key, period, sum(par), sum(fv) from {table} where par>0 and borrower_key!='' group by 1,2,3"):
            if par >= 1e6: m[k][p][b] = 100 * fv / par
    except sqlite3.OperationalError: pass
    return m

def cross_markdown_events(m, cut=5.0, min_holders=2):
    """(borrower, period) where >=min_holders BDCs cut the mark >=cut pts vs prior quarter."""
    ev = []
    for k, per in m.items():
        ps = sorted(per)
        for i in range(1, len(ps)):
            cuts = {b: per[ps[i - 1]][b] - v for b, v in per[ps[i]].items() if b in per[ps[i - 1]] and per[ps[i - 1]][b] - v >= cut}
            if len(cuts) >= min_holders: ev.append((k, ps[i], cuts, min(per[ps[i]][b] for b in cuts)))
    return ev

def cross_markdown(con):
    m = _qmarks(con, "bdc_marks")
    hist = _qmarks(con, "bdc_marks_hist")
    for k, per in hist.items():
        for p, d in per.items(): m[k].setdefault(p, {}).update(d)
    ev = cross_markdown_events(m)
    # precision: of events with mark still >=60, how many fall <60 at any holder within the next 4 quarters
    n = tp = 0
    for k, p, cuts, lo in ev:
        ps = sorted(m[k]); fut = [q for q in ps if q > p][:4]
        if lo < 60 or not fut: continue
        n += 1; tp += any(min(m[k][q].values()) < 60 for q in fut)
    url = {r[0]: r[1] for r in con.execute("select borrower_key, min(source_url) from bdc_marks group by 1")}
    rows = [("cross_markdown", k, k, round(statistics.mean(c.values()), 1), f"{len(c)} BDCs cut: " + ", ".join(f"{b} -{v:.0f}" for b, v in sorted(c.items())) + f"; lowest now {lo:.0f}",
             url.get(k, ""), p) for k, p, c, lo in ev if p >= "2026-06-30"]
    _put(con, rows)
    return {"events_total": len(ev), "evaluable": n, "fell_below_60_4q": tp, "precision": round(tp / n, 3) if n else None, "current": len(rows)}

# ---------- event backtests vs 8-K 1.03 ----------
def load_jsonl(path, tag=None):
    out = defaultdict(set)
    for line in open(path):
        r = json.loads(line)
        if r.get("cik") and r.get("date") and (tag is None or r.get("tag") == tag): out[r["cik"]].add(r["date"])
    return out

def bankruptcies(items_path):
    bk = defaultdict(set)
    for line in open(items_path):
        r = json.loads(line)
        if "1.03" in r.get("items", []) and r.get("cik"): bk[r["cik"]].add(r["date"])
    return bk

def event_precision(flags, bk, start="2019-01-01", end="2025-04-30", horizon=540):
    n = tp = 0; leads = []
    for cik, ds in flags.items():
        b = sorted(D(x) for x in bk.get(cik, ()))
        fs = [D(x) for x in sorted(ds) if start <= x <= end]
        fs = [f for f in fs if not any(0 <= (f - x).days <= 365 for x in b)]
        if not fs: continue
        n += 1; hit = [x for x in b if 0 < (x - fs[0]).days <= horizon]
        if hit: tp += 1; leads.append((hit[0] - fs[0]).days)
    return {"flagged": n, "ch11_540d": tp, "precision": round(tp / n, 3) if n else None, "median_lead_days": statistics.median(leads) if leads else None}

def combine(a, b, window=365):
    out = defaultdict(set)
    for cik in set(a) & set(b):
        for x in a[cik]:
            if any(abs((D(x) - D(y)).days) <= window for y in b[cik]): out[cik].add(max([x] + [y for y in b[cik] if abs((D(x) - D(y)).days) <= window]))
    return out

def recent_flags(con, name, flags, names, since="2026-04-01", url_tpl="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=8-K"):
    rows = [(name, names.get(c, c), "cik:" + c.lstrip("0"), 1, name, url_tpl.format(cik=c.lstrip("0")), max(d)) for c, d in flags.items() if max(d) >= since]
    return _put(con, rows)

# ---------- insider clusters (company level) ----------
def form4_cluster(con, ciks, fetch=lambda u: json.loads(http(u)), today="2026-10-22", window=90, ratio=2.0):
    rows = []
    for cik, name in ciks:
        try: rec = fetch(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json")["filings"]["recent"]
        except Exception: continue
        dates = [D(d) for f, d in zip(rec["form"], rec["filingDate"]) if f == "4"]
        t = D(today); recent = sum(1 for d in dates if 0 <= (t - d).days <= window)
        prior = sum(1 for d in dates if window < (t - d).days <= window + 365) / (365 / window)
        if recent and recent >= ratio * max(prior, 1):
            rows.append(("form4_cluster", name, f"cik:{int(cik)}", recent, f"{recent} Form 4 filings in {window}d vs {prior:.1f} avg (company-level count; transaction direction not parsed)",
                         f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={int(cik)}&type=4", today))
        time.sleep(0.15)
    return _put(con, rows)

# ---------- CMBS tenant x distress ----------
TEN = re.compile(r"<largestTenant>([^<]+)</largestTenant>|<secondLargestTenant>([^<]+)</secondLargestTenant>|<thirdLargestTenant>([^<]+)</thirdLargestTenant>")
def tenants(xml):
    out = []
    for block in re.split(r"<assets>", xml)[1:]:
        prop = re.search(r"<propertyName>([^<]+)", block); bal = re.search(r"<reportPeriodEndActualBalanceAmount>([\d.]+)", block)
        for m in TEN.finditer(block):
            t = next(x for x in m.groups() if x)
            out.append(((prop.group(1) if prop else ""), t.strip(), float(bal.group(1)) if bal else 0.0))
    return out

def norm(s): return " ".join(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())

def tenant_distress(con, distress_names, fetch=http, max_trusts=60):
    urls = [r[0] for r in con.execute("select distinct source_url from cmbs_loans limit ?", (max_trusts,))]
    AMBIG = {"express", "target", "the", "group", "holdings"}
    dn = {norm(n): n for n in distress_names if len(norm(n)) >= 5 and norm(n) not in AMBIG}
    rows = []
    for u in urls:
        try: ts = tenants(fetch(u))
        except Exception: continue
        trust = con.execute("select trust from cmbs_loans where source_url=? limit 1", (u,)).fetchone()[0]
        for prop, t, bal in ts:
            nt = norm(t)
            hit = next((orig for k, orig in dn.items() if nt.startswith(k) or k.startswith(nt) and len(nt) >= 6), None)
            if hit:
                rows.append(("cmbs_tenant_distress", f"{prop} ({trust})", norm(prop + trust)[:80], round(bal / 1e6, 1), f"tenant '{t}' matches distress name '{hit}'", u, "2026-10-22"))
        time.sleep(0.15)
    return _put(con, rows)

# ---------- UK Companies House public page ----------
def ch_overdue(con, companies, fetch=lambda u: http(u, {"User-Agent": "Mozilla/5.0"})):
    rows = []
    for num, name in companies:
        u = f"https://find-and-update.company-information.service.gov.uk/company/{num}"
        try: h = fetch(u)
        except Exception: continue
        overdue = bool(re.search(r"accounts?\s+(are\s+)?overdue|overdue", h, re.I))
        status = re.search(r'id="company-status"[^>]*>\s*([^<]+)', h)
        rows.append(("uk_late_accounts", name, f"ch:{num}", 1 if overdue else 0,
                     f"{'OVERDUE' if overdue else 'not overdue'}; status {status.group(1).strip() if status else '?'}", u, "2026-10-22"))
        time.sleep(0.5)
    return _put(con, rows)

# ---------- exposure: 10-K mentions ----------
def exposure_mentions(con, names, fetch=lambda u: json.loads(http(u)), since="2025-01-01"):
    rows = []
    for name in names:
        q = urllib.parse.urlencode({"q": f'"{name}" "10%"', "forms": "10-K", "dateRange": "custom", "startdt": since, "enddt": "2026-10-21"})
        try: hits = fetch("https://efts.sec.gov/LATEST/search-index?" + q)["hits"]["hits"]
        except Exception: continue
        for h in hits[:20]:
            s = h["_source"]; filer = (s.get("display_names") or [""])[0]
            if norm(name) in norm(filer): continue  # self-mention
            cik = (s.get("ciks") or [""])[0].lstrip("0"); adsh = s.get("adsh", "")
            rows.append(("exposure_10k_mention", filer, f"{norm(name)}|cik:{cik}", 1, f"10-K mentions '{name}' with a 10% concentration phrase (customer/supplier exposure candidate)",
                         f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/", s.get("file_date")))
        time.sleep(0.15)
    return _put(con, rows)

# ---------- trade claims (RECAP) ----------
def top20_claims(con, cases, fetch=lambda u: json.loads(http(u, {"User-Agent": "TRIAGE-OS-research/0.1"}))):
    rows = []
    for case_name in cases:
        q = urllib.parse.urlencode({"q": f'"largest unsecured" AND caseName:({case_name})', "type": "rd"})
        try: res = fetch("https://www.courtlistener.com/api/rest/v4/search/?" + q).get("results", [])
        except Exception: continue
        for r in res[:10]:
            desc = r.get("description") or ""
            if re.search(r"individual", desc, re.I) or not all(w.lower() in (r.get("caseName") or desc + r.get("absolute_url", "")).lower() for w in case_name.split()[:1]):
                continue  # firms only
            rows.append(("trade_claims_top20", case_name, f"{norm(case_name)}|{r.get('id')}", 1 if r.get("is_available") else 0,
                         f"{(r.get('description') or '')[:120]} | RECAP {'free PDF' if r.get('is_available') else 'not on RECAP'}",
                         "https://www.courtlistener.com" + (r.get("absolute_url") or ""), (r.get("entry_date_filed") or "")[:10]))
    return _put(con, rows)
