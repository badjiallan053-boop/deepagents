"""Directing certificateholder / controlling-class representative per CMBS trust, read from the latest
10-D Exhibit 99.1 (certificate administrator distribution report) on SEC EDGAR. Public, read-only."""
import csv, html, json, os, re, time, urllib.request
UA = {"User-Agent": "TRIAGE-OS research arslane.souici@example.com"}
OUT = os.environ.get("TRIAGE_OUT", "/workspace/triage_os_data")
LABELS = r"(Directing Certificateholder|Directing Holder|Controlling Class Representative|Directing Certificate ?holder)"
STOP = r"(Interest Shortfall|Historical|Supplemental|Page \d|Attention|This report|Certificate|Mortgage Loan|Delinquency|Modified|Specially|Bond|Principal|Collateral|Liquidated|Appraisal|Loan Level|NOI|Advance|Excess|Other|Risk Retention|Operating Advisor|Trustee|Asset Rep|\d{1,2}(?:-\d{1,2})? )"
def get(u):
    time.sleep(0.15); return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8", "ignore")
def text(h): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h)))
def latest_10d(cik):
    d = json.loads(get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"))["filings"]["recent"]
    for f, a, p, dt in zip(d["form"], d["accessionNumber"], d["primaryDocument"], d["filingDate"]):
        if f == "10-D": return a.replace("-", ""), p, dt
def parse(t):
    out = {"directing_holder": None, "label": None}
    for lab, pat in [("Controlling Class Representative", r"The Controlling Class Representative is (.{3,120}?)\.\s"),
                     ("Controlling Class Representative", r"Controlling Class Rep\.\s+(.{3,120}?)\s+-\s"),
                     ("Directing Certificateholder/Holder", LABELS + r"\s+(.{3,120}?)\s+" + STOP)]:
        m = re.search(pat, t)
        if m:
            name = m.group(2) if lab.startswith("Directing") else m.group(1)
            name = re.split(r"\s+(?:There Are No|Interest Shortfall|Reports Available|This report)", name)[0].strip(" :,-.")
            out["directing_holder"] = name; out["label"] = lab if not lab.startswith("Directing") else m.group(1); break
    s = re.search(r"Special Servicer:\s+(.{3,80}?)\s+(?:Special Servicer|Asset|Operating|Trustee)", t) or re.search(r"Special Servicer\s+(.{3,80}?)\s+(?:Current Mortgage|Attention|Mortgage Loan|Certificate|Principal|Historical|Delinquency|Collateral|Bond|Fees|\d{1,2} )", t)
    out["special_servicer"] = s.group(1).strip() if s else None
    c2 = re.search(r"Controlling Class is Class ([A-Z0-9-]+)\.", t)
    if c2: out["controlling_class"] = c2.group(1)
    cc = re.search(r"\s([A-Z][A-Z0-9-]{0,5})\*\s+([0-9A-Z]{9})\s+[\d.]+%\s+([\d,]+\.\d\d)\s+([\d,]+\.\d\d)", t)
    if cc: out.update(controlling_class=cc.group(1), cc_cusip=cc.group(2), cc_original=float(cc.group(3).replace(",", "")), cc_balance=float(cc.group(4).replace(",", "")))
    return out
def run(trusts):
    rows = []
    for name, cik in trusts:
        r = dict(trust=name, cik=cik)
        try:
            acc, p, dt = latest_10d(cik); idx = get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/")
            ex = [h for h in re.findall(r'href="(/Archives/[^"]+\.htm)"', idx) if re.search(r"ex99|ex991|ex-99|exh?_?99", h, re.I)]
            u = "https://www.sec.gov" + ex[0] if ex else f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{p}"
            r.update(parse(text(get(u))), filed=dt, source_url=u)
        except Exception as e: r["error"] = repr(e)[:120]
        rows.append(r); print(r)
    keys = ["trust", "cik", "filed", "label", "directing_holder", "special_servicer", "controlling_class", "cc_cusip", "cc_original", "cc_balance", "source_url", "error"]
    with open(f"{OUT}/cmbs_control/directing_holders.csv", "w", newline="") as f:
        w = csv.DictWriter(f, keys); w.writeheader(); [w.writerow({k: x.get(k) for k in keys}) for x in rows]
    return rows
if __name__ == "__main__":
    ts = {"JPMDB Commercial Mortgage Securities Trust 2016-C4": "1687202"}
    for r in csv.DictReader(open(f"{OUT}/cmbs_fresh_ss_transfers.csv")): ts.setdefault(r["trust"], re.search(r"data/(\d+)/", r["source_url"]).group(1))
    for r in csv.DictReader(open(f"{OUT}/cmbs_trust_stress.csv")):
        m = re.search(r"data/(\d+)/", r.get("url") or "")
        if m: ts.setdefault(r["trust"], m.group(1))
    run(list(ts.items()))
