"""TRIAGE OS - worldwide read-only insolvency signal connectors.

Public sources only, companies only (natural persons are dropped at parse time
for GDPR / privacy reasons), every record carries a source URL and date and is
stored as 'unverified'. No outreach, no submissions, GET/POST-search only.

Common procedure taxonomy (PROCEDURES) lets a French 'redressement judiciaire',
a UK administration, a Japanese 民事再生 and an HKEX winding-up petition be
ranked on one scale. Scores are triage priorities, not investment views.
"""
import argparse, csv, datetime as dt, html, json, os, re, time, urllib.parse, urllib.request

import desk

PROCEDURES = {  # common taxonomy -> base priority
    "asset_sale": 45,      # plan de cession, 363-like sale, business/asset sale
    "pre_pack": 45,
    "administration_reorg": 35,  # administration, redressement, sauvegarde, 民事再生, 会社更生
    "scheme_ccaa": 35,     # scheme / restructuring plan / CCAA / moratorium
    "receivership": 35,
    "winding_up_petition": 30,
    "liquidation": 20,
    "listing_distress": 25,  # delisting / suspension / risk warning of a listed issuer
    "closure": 0,          # closed / struck off: no live asset
    "other": 5,
}
LISTED_BONUS = 25
UA = "TRIAGE-OS research (read-only)"

def _get(url, data=None, headers=None, timeout=60, retries=3):
    h = {"User-Agent": "Mozilla/5.0 " + UA}
    h.update(headers or {})
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(1.5 * (i + 1))

def _text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

def make(country, source, ext_id, entity, title, url, date, procedure, listed=False,
         bonus=0, **extra):
    score = min(100, PROCEDURES.get(procedure, 5) + (LISTED_BONUS if listed else 0) + bonus)
    return dict(country=country, source=source, external_id=str(ext_id), entity=entity,
                title=title, url=url, event_date=date, procedure=procedure,
                listed=listed, score=score, **extra)

# --- France: BODACC procédures collectives (open data, Opendatasoft API) ----
BODACC = ("https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/"
          "datasets/annonces-commerciales/records")

def fr_procedure(text):
    t = text.lower()
    if "clôture" in t or "cloture" in t:
        return "closure"
    if "cession" in t:
        return "asset_sale"
    if "redressement" in t or "sauvegarde" in t:
        return "administration_reorg"
    if "liquidation" in t:
        return "liquidation"
    return "other"

def parse_bodacc(rec):
    try:
        pers = json.loads(rec.get("listepersonnes") or "{}").get("personne") or {}
    except ValueError:
        return None
    if isinstance(pers, list):
        pers = pers[0] if pers else {}
    if pers.get("typePersonne") != "pm":   # companies only: drop natural persons
        return None
    try:
        jug = json.loads(rec.get("jugement") or "{}")
    except ValueError:
        jug = {}
    detail = " ".join(filter(None, [jug.get("nature"), jug.get("complementJugement")]))
    proc = fr_procedure(detail)
    name = pers.get("denomination") or rec.get("commercant")
    url = rec.get("url_complete") or (
        "https://www.bodacc.fr/pages/annonces-commerciales-detail/?q.id=id:" + rec["id"])
    return make("FR", "fr_bodacc", rec["id"], name,
                f"{name}: {jug.get('nature') or 'procédure collective'}"[:300], url,
                rec.get("dateparution"), proc, tribunal=rec.get("tribunal"),
                forme=pers.get("formeJuridique"), detail=detail[:600],
                ville=rec.get("ville"))

def fetch_bodacc(since, max_rows=9900, fetch=_get):
    out, offset = [], 0
    where = f"familleavis='collective' and dateparution>=date'{since}'"
    while offset < max_rows:
        q = urllib.parse.urlencode({"where": where, "limit": 100, "offset": offset,
                                    "order_by": "dateparution desc"})
        res = json.loads(fetch(BODACC + "?" + q)).get("results") or []
        out += [s for s in map(parse_bodacc, res) if s]
        if len(res) < 100:
            break
        offset += 100
    return out

# --- UK: The Gazette corporate insolvency notices (open JSON feed) ----------
GAZETTE = "https://www.thegazette.co.uk/insolvency/notice/data.json"

def uk_procedure(category, code):
    c = (category or "").lower()
    if "receiv" in c:
        return "receivership"
    if "administra" in c:
        return "administration_reorg"
    if "arrangement" in c or "moratori" in c or "restructuring" in c or "scheme" in c:
        return "scheme_ccaa"
    if "petition" in c:
        return "winding_up_petition"
    if "strik" in c or "dissol" in c or "final meeting" in c:
        return "closure"
    if "wind" in c or "liquidat" in c or "resolution" in c or "creditors" in c:
        return "liquidation"
    return "other"

def parse_gazette(e):
    code = str(e.get("f:notice-code") or "")
    if not code.startswith("24"):   # 24xx corporate; 25xx are personal insolvency -> drop
        return None
    cat = (e.get("category") or {}).get("@term", "")
    content = _text(e.get("content"))
    m = re.search(r"Company Number:?\s*([A-Z0-9]{6,8})", content, re.I)
    nid = e["id"].rsplit("/", 1)[-1]
    e = dict(e, title=re.sub(r"^(?:/n|\\n|\s)+", "", e.get("title") or "").strip())
    proc = uk_procedure(cat, code)
    return make("UK", "uk_gazette", nid, e.get("title"), f"{e.get('title')}: {cat}"[:300],
                f"https://www.thegazette.co.uk/notice/{nid}", (e.get("published") or "")[:10],
                proc, company_number=m.group(1) if m else None, notice_code=code,
                category=cat, detail=content[:600])

def fetch_gazette(since, max_pages=80, fetch=_get):
    out = []
    for p in range(1, max_pages + 1):
        d = json.loads(fetch(f"{GAZETTE}?results-page-size=100&results-page={p}"))
        ents = d.get("entry") or []
        if isinstance(ents, dict):
            ents = [ents]
        out += [s for s in map(parse_gazette, ents) if s]
        if not ents or (ents[-1].get("published") or "9")[:10] < since:
            break
    return [s for s in out if (s["event_date"] or "") >= since]

# --- UK: Companies House enrichment (free API key required: CH_API_KEY) -----
def companies_house_profile(number, key=None, fetch=None):
    key = key or os.environ.get("CH_API_KEY")
    if not key:
        return None
    url = f"https://api.company-information.service.gov.uk/company/{number}"
    if fetch is None:
        import base64
        auth = base64.b64encode((key + ":").encode()).decode()
        fetch = lambda u: _get(u, headers={"Authorization": "Basic " + auth})
    d = json.loads(fetch(url))
    return {"company_status": d.get("company_status"), "sic_codes": d.get("sic_codes"),
            "has_charges": d.get("has_charges"), "accounts_type":
            ((d.get("accounts") or {}).get("last_accounts") or {}).get("type"),
            "source_url": "https://find-and-update.company-information.service.gov.uk/company/" + number}

# --- Australia: ASX company announcements -----------------------------------
ASX = "https://asx.api.markitdigital.com/asx-research/1.0/markets/announcements"
ASX_TERMS = [("receiver", "receivership"), ("administrator", "administration_reorg"),
             ("voluntary administration", "administration_reorg"),
             ("deed of company arrangement", "scheme_ccaa"), ("scheme of arrangement", "scheme_ccaa"),
             ("liquidat", "liquidation"), ("winding up", "winding_up_petition"),
             ("sale of business", "asset_sale"), ("sale process", "asset_sale"),
             ("removal from official list", "listing_distress"), ("delist", "listing_distress"),
             ("going concern", "listing_distress"), ("default", "listing_distress"),
             ("standstill", "scheme_ccaa"), ("recapitalisation", "administration_reorg")]

def parse_asx(it):
    head = (it.get("headline") or "")
    hl = head.lower()
    for term, proc in ASX_TERMS:
        if term in hl:
            info = (it.get("companyInfo") or [{}])[0]
            sym = it.get("symbol")
            key = it.get("documentKey")
            return make("AU", "au_asx", key, info.get("displayName") or sym, f"{sym}: {head}"[:300],
                        f"https://www.asx.com.au/markets/trade-our-cash-market/announcements.{sym.lower()}"
                        if sym else "https://www.asx.com.au/markets/trade-our-cash-market/todays-announcements",
                        (it.get("date") or "")[:10], proc, listed=True,
                        bonus=10 if it.get("isPriceSensitive") else 0, symbol=sym,
                        document_key=key, pdf=f"https://cdn-api.markitdigital.com/apiman-gateway/ASX/asx-research/1.0/file/{key}",
                        sector=info.get("industry"))
    return None

def fetch_asx(since, max_pages=60, fetch=_get):
    out = []
    for p in range(max_pages):
        items = json.loads(fetch(f"{ASX}?itemsPerPage=100&page={p}"))["data"]["items"]
        out += [s for s in map(parse_asx, items) if s]
        if not items or items[-1]["date"][:10] < since:
            break
    return [s for s in out if s["event_date"] >= since]

# --- Hong Kong / China issuers: HKEXnews title search -----------------------
HKEX = "https://www1.hkexnews.hk/search/titleSearchServlet.do"
HKEX_TERMS = {"WINDING UP": "winding_up_petition", "LIQUIDATOR": "liquidation",
              "RECEIVER": "receivership", "RESTRUCTURING": "administration_reorg",
              "SCHEME OF ARRANGEMENT": "scheme_ccaa", "DELISTING": "listing_distress",
              "DEFAULT": "listing_distress", "DISPOSAL": "asset_sale"}

def parse_hkex(row, term):
    t = (row.get("TITLE") or "") + " " + _text(row.get("LONG_TEXT"))
    proc = HKEX_TERMS[term]
    if term == "DISPOSAL" and "liquidat" not in t.lower() and "receiver" not in t.lower():
        return None   # plain disposals are M&A noise unless distress-linked
    if re.search(r"privati[sz]ation|pre-conditional|share buy-back|redemption|voluntary delisting", t, re.I):
        return None   # M&A, buy-backs, pref redemptions: corporate actions, not distress
    if term == "SCHEME OF ARRANGEMENT" and not re.search(r"debt|creditor|restructur|liquidat", t, re.I):
        return None   # privatisation / M&A schemes are not distress
    d = row.get("DATE_TIME", "")
    iso = f"{d[6:10]}-{d[3:5]}-{d[0:2]}" if len(d) >= 10 else None
    return make("HK", "hk_hkexnews", row["NEWS_ID"], row.get("STOCK_NAME"),
                f"{row.get('STOCK_NAME')} ({row.get('STOCK_CODE')}): {_text(row.get('TITLE'))}"[:300],
                "https://www1.hkexnews.hk" + (row.get("FILE_LINK") or ""), iso, proc, listed=True,
                stock_code=row.get("STOCK_CODE"), headline_category=_text(row.get("LONG_TEXT"))[:300])

def fetch_hkex(since, until, fetch=_get):
    out, seen = [], set()
    for term in HKEX_TERMS:
        q = urllib.parse.urlencode({"sortDir": 0, "sortByOptions": "DateTime", "category": 0,
             "market": "SEHK", "stockId": -1, "documentType": -1, "fromDate": since.replace("-", ""),
             "toDate": until.replace("-", ""), "title": term, "searchType": 0, "t1code": -2,
             "t2Gcode": -2, "t2code": -2, "rowRange": 200, "lang": "E"})
        rows = json.loads(json.loads(fetch(HKEX + "?" + q)).get("result") or "[]")
        for r in rows:
            s = parse_hkex(r, term)
            if s and s["external_id"] not in seen:
                seen.add(s["external_id"]); out.append(s)
    return out

# --- Japan: Teikoku Databank bankruptcy flash (倒産速報) ---------------------
TDB = "https://www.tdb.co.jp/report/bankruptcy/"

def jp_procedure(t):
    if "会社更生" in t or "更生手続" in t or "民事再生" in t or "再生手続" in t:
        return "administration_reorg"
    if "特別清算" in t or "破産" in t:
        return "liquidation"
    return "other"

def jp_debt_oku(t):
    m = re.search(r"負債(?:約)?(?:([\d,]+)億)?(?:([\d,]+)万)?円", t)
    if not m or not (m.group(1) or m.group(2)):
        return None
    return int((m.group(1) or "0").replace(",", "")) + int((m.group(2) or "0").replace(",", "")) / 10000

def parse_tdb(page):
    out = []
    for href, body in re.findall(r'<a[^>]+href="(/report/bankruptcy/flash/\d+/)"[^>]*>(.*?)</a>', page, re.S):
        t = _text(body)
        m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", t)
        name = re.search(r"((?:株式会社|有限会社|合同会社)\S+|\S+(?:株式会社|有限会社|合同会社))", t)
        debt = jp_debt_oku(t)
        bonus = 30 if debt and debt >= 100 else 15 if debt and debt >= 10 else 0
        out.append(make("JP", "jp_tdb", href.strip("/").rsplit("/", 1)[-1],
                        name.group(1) if name else t[:40], t[:300], "https://www.tdb.co.jp" + href,
                        f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None,
                        jp_procedure(t), bonus=bonus, debt_jpy_oku=debt))
    return out

def fetch_tdb(since, fetch=_get):
    return [s for s in parse_tdb(fetch(TDB)) if (s["event_date"] or "") >= since]

# --- storage / ranking ---------------------------------------------------------
def store_all(con, sigs):
    n = 0
    for s in sigs:
        if not (s["url"] or "").startswith("https://") or not s["entity"]:
            continue
        key = f"name:{s['country'].lower()}:{desk.normalize_name(s['entity'])}"
        con.execute("INSERT OR IGNORE INTO entities VALUES (?,?,?,?)", (key, s["entity"], None, desk.now()))
        con.execute("""INSERT INTO signals (source, external_id, title, url, event_date, fetched_at,
            raw_json, entity_key) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(source, external_id) DO UPDATE
            SET title=excluded.title, url=excluded.url, event_date=excluded.event_date,
            fetched_at=excluded.fetched_at, raw_json=excluded.raw_json""",
            ("world:" + s["source"], s["external_id"], s["title"], s["url"], s["event_date"],
             desk.now(), json.dumps(s, ensure_ascii=False), key))
        n += 1
    con.commit()
    return n

def rank_world(con, limit=30, since=None, per_country=None):
    best = {}
    for (raw, key) in con.execute("SELECT raw_json, entity_key FROM signals WHERE source LIKE 'world:%'"):
        s = json.loads(raw)
        if since and (s.get("event_date") or "") < since:
            continue
        if key not in best or s["score"] > best[key]["score"]:
            best[key] = s
    ranked = sorted(best.values(), key=lambda s: (-s["score"], s.get("event_date") or ""))
    if per_country:
        seen = {}
        ranked = [s for s in ranked if seen.setdefault(s["country"], 0) < per_country
                  and not seen.__setitem__(s["country"], seen[s["country"]] + 1)]
    return ranked[:limit]

def export(rows, path):
    cols = ["score", "country", "source", "procedure", "listed", "event_date", "entity", "title", "url", "status"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(cols)
        for s in rows:
            w.writerow([s.get(c, "unverified" if c == "status" else "") for c in cols])

FETCHERS = {"fr_bodacc": fetch_bodacc, "uk_gazette": fetch_gazette, "au_asx": fetch_asx,
            "jp_tdb": fetch_tdb, "hk_hkexnews": None}

def hunt(days=14, db=desk.DB, out=None, only=None):
    until = dt.date.today().isoformat()
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    con, counts = desk.connect(db), {}
    for name in only or FETCHERS:
        try:
            sigs = fetch_hkex(since, until) if name == "hk_hkexnews" else FETCHERS[name](since)
            counts[name] = store_all(con, sigs)
        except Exception as e:  # one source failing must not stop the hunt
            counts[name] = f"error: {e}"[:200]
    rows = rank_world(con, 30, since, per_country=10)
    if out:
        export(rows, out)
    return counts, rows

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--db", default=desk.DB)
    ap.add_argument("--out")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    c, r = hunt(a.days, a.db, a.out, a.only)
    print(json.dumps(c, indent=1))
    for s in r[:10]:
        print(s["score"], s["country"], s["procedure"], s["title"][:90], s["url"])
