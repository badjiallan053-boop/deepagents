"""Generic SEC EFTS monthly puller -> JSONL (cik, name, date, form, items, adsh). Public, read-only.
usage: efts_pull.py OUT.jsonl TAG 'QUERY' FORMS [start_year]"""
import json, sys, time, urllib.request, urllib.parse, datetime as dt
UA = {"User-Agent": "TRIAGE-OS research arslane.souici@example.com"}
def get(q, forms, s, e, frm):
    u = "https://efts.sec.gov/LATEST/search-index?" + urllib.parse.urlencode(
        {"q": q, "forms": forms, "dateRange": "custom", "startdt": s, "enddt": e, "from": frm})
    for i in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
        except Exception: time.sleep(2 + 3 * i)
    return {"hits": {"hits": [], "total": {"value": 0}}}
def main(out, tag, q, forms, y0=2019):
    f = open(out, "a")
    for y in range(int(y0), 2027):
        for m in range(1, 13):
            s = dt.date(y, m, 1); e = dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)
            if s > dt.date(2026, 10, 21): break
            frm = 0
            while True:
                d = get(q, forms, s.isoformat(), e.isoformat(), frm); hits = d["hits"]["hits"]
                for h in hits:
                    src = h["_source"]
                    f.write(json.dumps({"tag": tag, "cik": (src.get("ciks") or [""])[0], "name": (src.get("display_names") or [""])[0],
                        "date": src.get("file_date"), "form": src.get("form") or src.get("root_forms"), "items": src.get("items") or [], "adsh": src.get("adsh")}) + "\n")
                frm += 100; time.sleep(0.12)
                if not hits or frm >= min(d["hits"]["total"]["value"], 10000): break
        f.flush(); print(tag, y, flush=True)
if __name__ == "__main__": main(*sys.argv[1:])
