"""Gap-audit prototype ingestors (public, read-only, firms only). 23 Oct 2026.
Sources: UK Gazette insolvency feed, French BODACC (opendatasoft API), SEC EFTS early-distress phrases,
Tokyo Shoko Research monthly bankruptcy list. Records coverage and latency per source.

Pagination / cache (24 Oct 2026):
- UK Gazette Atom: CloudFront may serve a stale or empty copy. Every request sends Cache-Control/
  Pragma: no-cache plus a `_` cache-buster query param, and walks `results-page` until the page is
  empty, shorter than page_size, or the oldest notice falls outside the days window (max_pages cap).
- BODACC OpenDataSoft Explore v2.1: `limit` is capped at 100. Walk `offset` until offset >=
  total_count or a page is empty. The date window is pushed into `where` so we do not scan the
  full multi-million-row corpus. Firms only (typePersonne == "pp" dropped).
"""
import json, re, sys, time, datetime as dt, urllib.request, urllib.parse, gzip
UA = {
    "User-Agent": "TRIAGE-research (public data audit)",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Accept-Encoding": "identity",
}
CORP = re.compile(r"\b(LTD|LIMITED|PLC|LLP|LP|SAS|SARL|SA|SCI|EURL|SNC|GMBH|AG|INC|CORP|株式会社|有限会社)\b|株式会社", re.I)

def get(u, retries=3):
    """HTTP GET with no-cache headers; retries transient SSL/EOF; gunzips if needed."""
    last = None
    for i in range(retries):
        t = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
                status = getattr(r, "status", 200)
                raw = r.read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            body = raw.decode("utf-8", "ignore")
            return body, round(time.time() - t, 2), status
        except Exception as e:
            last = e
            time.sleep(0.5 * (i + 1))
    raise last

def now(): return dt.datetime.now(dt.timezone.utc)

def _parse_day(pub):
    try: return dt.date.fromisoformat(str(pub)[:10])
    except (TypeError, ValueError): return None

def uk_gazette(days=2, page_size=100, max_pages=50):
    """UK Gazette insolvency Atom feed; paginated + cache-busted (see module docstring)."""
    t0 = time.time(); rows = []; raw = 0
    cutoff = now().date() - dt.timedelta(days=days)
    for page in range(1, max_pages + 1):
        bust = int(time.time() * 1000)
        url = (f"https://www.thegazette.co.uk/insolvency/notice/data.feed"
               f"?results-page-size={page_size}&results-page={page}"
               f"&sort-by=latest-date&_={bust}")
        body, _, status = get(url)
        if status == 202 or "challenge.js" in body or "awswaf" in body.lower():
            raise RuntimeError(f"uk_gazette: WAF/empty block (HTTP {status}) on page {page}")
        entries = re.findall(r"<entry>(.*?)</entry>", body, re.S)
        raw += len(entries)
        if not entries:
            break
        oldest = None
        for e in entries:
            title = re.sub(r"\s+", " ", re.search(r"<title>(.*?)</title>", e, re.S).group(1)).strip()
            pub = re.search(r"<published>(.*?)</published>", e).group(1)
            cat = (re.findall(r'term="([^"]+)"', e) or [""])[0]
            link = (re.findall(r"<id>(.*?)</id>", e) or [""])[0]
            d = _parse_day(pub)
            if oldest is None or (d and d < oldest): oldest = d
            if d and d < cutoff: continue
            if CORP.search(title):  # firms only; personal insolvency notices dropped
                rows.append({"src": "uk_gazette", "entity": title, "event": cat, "published": pub, "url": link})
        if oldest is not None and oldest < cutoff:
            break
        if len(entries) < page_size:
            break
        time.sleep(0.2)
    return rows, round(time.time() - t0, 2), raw

def fr_bodacc(days=2, page_size=100, max_pages=200):
    """BODACC collective proceedings; offset-paginated past the 100-row API cap (see module docstring)."""
    page_size = min(int(page_size), 100)  # OpenDataSoft Explore v2.1 hard cap
    t0 = time.time(); rows = []; raw = 0
    cutoff = (now().date() - dt.timedelta(days=days)).isoformat()
    where = f'familleavis="collective" AND dateparution>=date\'{cutoff}\''
    offset = 0; total = None
    for _ in range(max_pages):
        q = urllib.parse.urlencode({"where": where, "order_by": "dateparution desc",
                                    "limit": page_size, "offset": offset})
        body, _, _ = get("https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records?" + q)
        d = json.loads(body)
        if total is None: total = d.get("total_count")
        batch = d.get("results") or []
        raw += len(batch)
        if not batch:
            break
        for r in batch:
            pers = json.loads(r.get("listepersonnes") or "{}") if isinstance(r.get("listepersonnes"), str) else (r.get("listepersonnes") or {})
            p = pers.get("personne", {}) if isinstance(pers, dict) else {}
            if isinstance(p, list): p = p[0] if p else {}
            if p.get("typePersonne") == "pp": continue  # drop natural persons (GDPR)
            j = json.loads(r["jugement"]) if r.get("jugement") else {}
            rows.append({"src": "fr_bodacc", "entity": r.get("commercant"), "event": j.get("nature", "")[:80],
                         "published": r.get("dateparution"), "court": r.get("tribunal"), "url": r.get("url_complete")})
        offset += len(batch)
        if total is not None and offset >= total:
            break
        if len(batch) < page_size:
            break
        time.sleep(0.2)
    return rows, round(time.time() - t0, 2), total if total is not None else raw

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
    body, s, _ = get(f"https://www.tsr-net.co.jp/news/process/{y}/{m}/")
    rows = []
    for h, x in re.findall(r'href="(/data/detail/\d+_\d+\.html)"[^>]*>(.*?)</a>', body, re.S):
        txt = re.sub(r"<[^>]+>|\s+", " ", x).strip()
        rows.append({"src": "jp_tsr", "entity": txt[:120], "published": f"{y}-{m:02d}", "url": "https://www.tsr-net.co.jp" + h})
    return rows, s, len(rows)

def jp_tdb():
    body, s, _ = get("https://www.tdb.co.jp/report/bankruptcy/")
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

def _default_fetchers(days):
    return {
        "uk_gazette": lambda: uk_gazette(days=days)[0],
        "fr_bodacc": lambda: fr_bodacc(days=days)[0],
        "jp_tdb": lambda: jp_tdb()[0],
    }

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
    a = ap.parse_args(argv); fetchers = fetchers or _default_fetchers(a.days); res = {}
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
