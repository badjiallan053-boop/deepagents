"""UK director/PDMR dealings from Investegate company pages (no captcha path; ~1 req/s), 2020-2026, FTSE 100 sample.
Each 'Director/PDMR Shareholding' RNS is opened and the MAR Article 19 notification parsed: PDMR name and nature of transaction.
Purchase = 'purchase'/'acquisition of ... shares'/'buy' and NOT vesting/award/exercise/dividend reinvestment/sale.
Cluster: >=2 distinct PDMRs with purchase notices within 30 days. Entry next close after the announcement date; 60d excess vs ISF.L; 30bp + 50bp stamp duty.
"""
import os, re, json, time, datetime, subprocess, html
D = "/workspace/triage_os_data/edge/uk"; OUT = f"{D}/pdmr.json"
EPICS = "AZN SHEL HSBA ULVR BP. RIO GSK REL DGE BATS LSEG GLEN AAL NG. CPG BA. LLOY BARC VOD PRU TSCO RKT IMB SSE EXPN AHT NWG LGEN AV. SGE BT.A WPP HLN III ENT INF SMIN IHG BRBY JD. KGF SBRY MNG PSON RR. ITRK SPX AUTO ABF BNZL WTB".split()
def get(u):
    c = f"{D}/cache_{re.sub(r'[^A-Za-z0-9]', '_', u)[-150:]}"
    if os.path.exists(c): return open(c, errors="ignore").read()
    time.sleep(0.8); t = subprocess.run(["curl", "-s", "-m", "40", "-A", "Mozilla/5.0 (research; contact badjiallan053@gmail.com)", u], capture_output=True, text=True).stdout
    open(c, "w").write(t); return t
def company(epic):
    code = epic.rstrip(".").replace(".", ""); out = []
    for page in range(1, 80):
        t = get(f"https://www.investegate.co.uk/company/{epic.rstrip('.')}?page={page}")
        rows = []
        for tr in t.split("<tr")[1:]:
            m1 = re.search(r'(\d{2} \w{3} \d{4})', tr); m2 = re.search(r'href="(https?://www\.investegate\.co\.uk/announcement/rns/[^"]*pdmr[^"]*)"', tr)
            if m1 and m2: rows.append((m1.group(1), m2.group(1)))
        dates = re.findall(r'(\d{2} \w{3} \d{4})', t)
        out += rows
        if not dates or datetime.datetime.strptime(dates[-1], "%d %b %Y").date() < datetime.date(2020, 1, 1): break
    return out
def parse(u):
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", get(u))))
    nat = " ".join(re.findall(r"Nature of the transaction (.{0,160})", t, re.I)).lower()
    name = re.search(r"\bName\s+(?:of PDMR\s+)?([A-Z][A-Za-z.'\- ]{3,40}?)\s+(?:2\b|Reason)", t)
    buy = bool(re.search(r"purchase|acquisition of|market buy|bought", nat)) and not re.search(r"vest|award|exercise|reinvest|sale|disposal|sold|transfer|grant|sharesave|dividend", nat)
    return dict(buy=buy, pdmr=name.group(1).strip() if name else None, nature=nat[:120])
import threading, concurrent.futures as cf
LK = threading.Lock()
def one(e, res):
        items = []
        for d, u in company(e):
            dd = datetime.datetime.strptime(d, "%d %b %Y").date()
            if dd < datetime.date(2020, 1, 1): continue
            p = parse(u); items.append(dict(date=dd.isoformat(), url=u, **p))
        with LK: res[e] = items; json.dump(res, open(OUT, "w")); print(e, len(items), sum(i["buy"] for i in items), flush=True)
def run():
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    with cf.ThreadPoolExecutor(4) as ex: list(ex.map(lambda e: one(e, res), [e for e in EPICS if e not in res]))
if __name__ == "__main__": run()
