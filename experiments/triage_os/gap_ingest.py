"""Gap-audit prototype ingestors (public, read-only, firms only). 23 Oct 2026.
Sources: UK Gazette insolvency feed, French BODACC (opendatasoft API), SEC EFTS early-distress phrases,
Tokyo Shoko Research monthly bankruptcy list. Records coverage and latency per source."""
import json, re, sys, time, datetime as dt, urllib.request, urllib.parse
UA = {"User-Agent": "TRIAGE-research (public data audit)"}
CORP = re.compile(r"\b(LTD|LIMITED|PLC|LLP|LP|SAS|SARL|SA|SCI|EURL|SNC|GMBH|AG|INC|CORP|株式会社|有限会社)\b|株式会社", re.I)
def get(u):
    t = time.time(); r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40).read()
    return r.decode("utf-8", "ignore"), round(time.time() - t, 2)
def now(): return dt.datetime.now(dt.timezone.utc)

def uk_gazette(n=100):
    body, s = get(f"https://www.thegazette.co.uk/insolvency/notice/data.feed?results-page-size={n}&sort-by=latest-date")
    rows = []
    for e in re.findall(r"<entry>(.*?)</entry>", body, re.S):
        title = re.sub(r"\s+", " ", re.search(r"<title>(.*?)</title>", e, re.S).group(1)).strip()
        pub = re.search(r"<published>(.*?)</published>", e).group(1)
        cat = (re.findall(r'term="([^"]+)"', e) or [""])[0]
        link = (re.findall(r'<id>(.*?)</id>', e) or [""])[0]
        if CORP.search(title):  # firms only; personal insolvency notices dropped
            rows.append({"src": "uk_gazette", "entity": title, "event": cat, "published": pub, "url": link})
    return rows, s, len(re.findall(r"<entry>", body))

def fr_bodacc(n=100):
    q = urllib.parse.urlencode({"where": 'familleavis="collective"', "order_by": "dateparution desc", "limit": n})
    body, s = get("https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records?" + q)
    d = json.loads(body); rows = []
    for r in d["results"]:
        pers = json.loads(r.get("listepersonnes") or "{}") if isinstance(r.get("listepersonnes"), str) else (r.get("listepersonnes") or {})
        p = pers.get("personne", {}) if isinstance(pers, dict) else {}
        if isinstance(p, list): p = p[0] if p else {}
        if p.get("typePersonne") == "pp": continue  # drop natural persons (GDPR)
        j = json.loads(r["jugement"]) if r.get("jugement") else {}
        rows.append({"src": "fr_bodacc", "entity": r.get("commercant"), "event": j.get("nature", "")[:80], "published": r.get("dateparution"),
                     "court": r.get("tribunal"), "url": r.get("url_complete")})
    return rows, s, d.get("total_count")

PHRASES = ['"forbearance agreement"', '"substantial doubt" "going concern"', '"waiver and amendment" "credit agreement"', '"restructuring support agreement"', '"grace period" "interest payment"']
def sec_efts(start, end):
    rows = []; t0 = time.time()
    for p in PHRASES:
        q = urllib.parse.urlencode({"q": p, "dateRange": "custom", "startdt": start, "enddt": end, "forms": "8-K,10-Q,6-K"})
        d = json.loads(get("https://efts.sec.gov/LATEST/search-index?" + q)[0])
        for h in d["hits"]["hits"]:
            s = h["_source"]; rows.append({"src": "sec_efts", "phrase": p, "entity": s["display_names"][0], "event": s["form"], "published": s["file_date"],
                                           "url": f"https://www.sec.gov/Archives/edgar/data/{s['ciks'][0].lstrip('0')}/{h['_id'].split(':')[0].replace('-','')}/{h['_id'].split(':')[1]}"})
        time.sleep(0.3)
    return rows, round(time.time() - t0, 2), len(rows)

def jp_tsr(y, m):
    body, s = get(f"https://www.tsr-net.co.jp/news/process/{y}/{m}/")
    rows = []
    for h, x in re.findall(r'href="(/data/detail/\d+_\d+\.html)"[^>]*>(.*?)</a>', body, re.S):
        txt = re.sub(r"<[^>]+>|\s+", " ", x).strip()
        rows.append({"src": "jp_tsr", "entity": txt[:120], "published": f"{y}-{m:02d}", "url": "https://www.tsr-net.co.jp" + h})
    return rows, s, len(rows)

def jp_tdb():
    body, s = get("https://www.tdb.co.jp/report/bankruptcy/")
    rows = []
    for h, x in re.findall(r'href="(/report/bankruptcy/flash/\d+/)"(.*?)</a>', body, re.S):
        txt = re.sub(r"<[^>]+>|\s+", " ", x).strip()
        alt = re.findall(r'alt="([^"]+)"', x)
        rows.append({"src": "jp_tdb_flash", "entity": (alt[0] if alt else txt)[:120], "detail": txt[:200], "url": "https://www.tdb.co.jp" + h})
    seen = set(); rows = [r for r in rows if not (r["url"] in seen or seen.add(r["url"]))]
    return rows, s, len(rows)


# ---- CLI: last-N-days ingest into triage.db with dedupe (src,url) ----
import os, sqlite3, argparse
DEFAULT_DB = os.environ.get("TRIAGE_DB", "/workspace/triage_os_data/triage.db")
FETCHERS = {"uk_gazette": lambda: uk_gazette(100)[0], "fr_bodacc": lambda: fr_bodacc(100)[0], "jp_tdb": lambda: jp_tdb()[0]}

def _in_window(pub, days, today=None):
    if not pub: return True  # undated (TDB flash): keep, dedupe handles repeats
    try: d = dt.date.fromisoformat(str(pub)[:10])
    except ValueError: return True
    today = today or now().date()
    return (today - d).days <= days

def store(rows, db, days, today=None):
    c = sqlite3.connect(db)
    c.execute("""CREATE TABLE IF NOT EXISTS gap_entities(src TEXT, entity TEXT, event TEXT, published TEXT,
                 court TEXT, url TEXT, detail TEXT, ingested_utc TEXT, UNIQUE(src, url))""")
    new = 0
    for r in rows:
        if not r.get("url") or not r.get("entity") or not _in_window(r.get("published"), days, today): continue
        cur = c.execute("INSERT OR IGNORE INTO gap_entities VALUES(?,?,?,?,?,?,?,?)",
                        (r["src"], r["entity"], r.get("event"), r.get("published"), r.get("court"), r["url"], r.get("detail"), now().isoformat()))
        new += cur.rowcount
    c.commit(); c.close(); return new

def cli(argv=None, fetchers=None):
    ap = argparse.ArgumentParser(description="Ingest UK Gazette / BODACC (firms only) / TDB into triage.db")
    ap.add_argument("--days", type=int, default=2); ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--sources", default="uk_gazette,fr_bodacc,jp_tdb")
    a = ap.parse_args(argv); fetchers = fetchers or FETCHERS; res = {}
    for name in a.sources.split(","):
        try: res[name] = store(fetchers[name](), a.db, a.days)
        except Exception as e: res[name] = "error: " + repr(e)[:150]
    print(json.dumps(res)); return res

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1].startswith("--"):
    cli(); sys.exit(0)
if __name__ == "__main__":
    out = {"run_at_utc": now().isoformat(), "sources": {}}
    for name, fn in [("uk_gazette", lambda: uk_gazette()), ("fr_bodacc", lambda: fr_bodacc()),
                     ("sec_efts", lambda: sec_efts("2026-10-09", "2026-10-23")), ("jp_tsr", lambda: jp_tsr(2026, 10)), ("jp_tdb", jp_tdb)]:
        try:
            rows, secs, raw = fn(); out["sources"][name] = {"fetch_s": secs, "raw": raw, "firm_rows": len(rows), "rows": rows}
        except Exception as e:
            out["sources"][name] = {"error": repr(e)[:200]}
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "/workspace/triage_os_data/gap_ingest.json", "w"), ensure_ascii=False, indent=1)
    for k, v in out["sources"].items(): print(k, {a: b for a, b in v.items() if a != "rows"})
