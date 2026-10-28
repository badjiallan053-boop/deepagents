"""Pull 8-K item index (1.03, 2.04, 3.01) 2019-2026 from SEC EFTS into JSONL. Public, read-only."""
import json, sys, time, urllib.request, urllib.parse, datetime as dt
UA = {"User-Agent": "TRIAGE-OS research arslane.souici@example.com"}
def get(q, s, e, frm):
    u = "https://efts.sec.gov/LATEST/search-index?" + urllib.parse.urlencode(
        {"q": f'"Item {q}"', "forms": "8-K", "dateRange": "custom", "startdt": s, "enddt": e, "from": frm})
    for i in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
        except Exception: time.sleep(2 + 3 * i)
    return {"hits": {"hits": [], "total": {"value": 0}}}
out = open(sys.argv[1], "a")
for y in range(2019, 2027):
    for m in range(1, 13):
        s = dt.date(y, m, 1); e = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1))
        if s > dt.date(2026, 10, 21): break
        for q in ("1.03", "2.04", "3.01"):
            frm = 0
            while True:
                d = get(q, s.isoformat(), e.isoformat(), frm); hits = d["hits"]["hits"]
                for h in hits:
                    src = h["_source"]
                    out.write(json.dumps({"q": q, "cik": (src.get("ciks") or [""])[0], "name": (src.get("display_names") or [""])[0],
                        "date": src.get("file_date"), "items": src.get("items") or [], "adsh": src.get("adsh")}) + "\n")
                frm += 100; time.sleep(0.12)
                if not hits or frm >= min(d["hits"]["total"]["value"], 10000): break
    out.flush(); print(y, flush=True)
