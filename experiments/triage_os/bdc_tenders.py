"""Non-traded BDC tender-offer results from EDGAR SC TO-I/A final amendments (Rule 13e-4(c)(4)), public."""
import json, re, time, html, sqlite3, os, urllib.request
UA = {"User-Agent": "TRIAGE-OS research arslane.souici@example.com"}
DB = os.environ.get("TRIAGE_DB", "/workspace/triage_os_data/triage.db")
FUNDS = {"BCRED": 1803498, "HLEND": 1838126, "OCIC": 1812554, "ASIF": 1918712, "GCRED": 1930087, "ADS": 1837532, "NHPIF": 1851322}
def get(u):
    time.sleep(0.15); return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8", "ignore")
def text(h): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h)))
def num(x): return float(x.replace(",", ""))
def parse(t):
    out = {}
    if not re.search(r"[Ff]inal [Aa]mendment", t): return out
    m = re.search(r"Offer expired at [^,]*, (?:Eastern|New York City) Time, on ([A-Z][a-z]+ \d+, \d{4})", t); out["expired"] = m.group(1) if m else None
    m = re.search(r"(\d[\d,]{4,}(?:\.\d+)?) (?:Shares|shares|Common Shares|common shares)[^.]{0,60}?(?:validly|properly) tendered", t)
    if m: out["tendered_shares"] = num(m.group(1))
    m = re.search(r"accepted for purchase (\d[\d,]{4,}(?:\.\d+)?) (?:Shares|shares)", t)
    if m: out["purchased_shares"] = num(m.group(1))
    elif re.search(r"accepted for purchase 100% of the", t) and "tendered_shares" in out: out["purchased_shares"] = out["tendered_shares"]
    m = re.search(r"representing (\d+(?:\.\d+)?)% of the (?:Shares|shares)", t); out["cap_pct"] = float(m.group(1)) if m else None
    m = re.search(r"in the amount of \$(\d[\d,]+(?:\.\d+)?)", t)
    if m: out["purchase_usd"] = num(m.group(1))
    out["prorated"] = bool(re.search(r"pro rata", t))
    return out
if __name__ == "__main__":
    rows = []
    for tk, cik in FUNDS.items():
        s = json.loads(get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")); r = s["filings"]["recent"]
        for f, a, d, doc in zip(r["form"], r["accessionNumber"], r["filingDate"], r["primaryDocument"]):
            if f == "SC TO-I/A" and d >= "2025-01-01":
                u = f"https://www.sec.gov/Archives/edgar/data/{cik}/{a.replace('-','')}/{doc}"
                try: p = parse(text(get(u)))
                except Exception: continue
                if "tendered_shares" in p:
                    rows.append((tk, s["name"], d, a, u, p.get("expired"), p.get("tendered_shares"), p.get("purchased_shares"), p.get("purchase_usd"), int(p["prorated"]), p.get("cap_pct")))
                    print(tk, d, p, flush=True)
    con = sqlite3.connect(DB); con.execute("drop table if exists bdc_tenders")
    con.execute("create table bdc_tenders (ticker, fund, filed, accession, url, expired, tendered_shares, purchased_shares, nav_usd_accepted, prorated, cap_pct)")
    con.executemany("insert into bdc_tenders values (?,?,?,?,?,?,?,?,?,?,?)", rows); con.commit(); print(len(rows))
