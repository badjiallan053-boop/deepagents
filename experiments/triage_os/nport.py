"""TRIAGE OS - fund holdings and fund-reported prices from SEC Form N-PORT-P (public).
For each matching debt holding: price = valUSD / principal * 100 (fund's own valuation,
usually a pricing-service mark, Level 2) - a free, honest proxy where TRACE is paywalled.
"""
import re, sqlite3
import auditor

def _t(blk, tag):
    m = re.search(rf"<{tag}>(.*?)</{tag}>", blk, re.S)
    return m.group(1).strip() if m else None

def parse(xml, issuer_re, url):
    pat = re.compile(issuer_re, re.I)
    series = _t(xml, "seriesName") or _t(xml, "regName") or ""
    reg = _t(xml, "regName") or ""
    period = _t(xml, "repPdDate")
    out = []
    for blk in re.findall(r"<invstOrSec>(.*?)</invstOrSec>", xml, re.S):
        name, title = _t(blk, "name") or "", _t(blk, "title") or ""
        if not pat.search(name + " " + title):
            continue
        bal, val = float(_t(blk, "balance") or 0), float(_t(blk, "valUSD") or 0)
        units, cat = _t(blk, "units"), _t(blk, "assetCat")
        mat = _t(blk, "maturityDt")
        cpn = _t(blk, "annualizedRt")
        price = round(100 * val / bal, 2) if units == "PA" and bal > 0 else None
        out.append({"fund": reg, "series": series, "issuer": name, "title": title, "cusip": _t(blk, "cusip"),
                    "balance": bal, "units": units, "value_usd": val, "price": price, "asset_cat": cat,
                    "maturity": mat, "coupon": cpn, "fair_value_level": _t(blk, "fairValLevel"),
                    "period": period, "source_url": url})
    return out

def ensure(con):
    con.execute("""CREATE TABLE IF NOT EXISTS holders(issuer_key text, holder text, holder_type text,
        instrument text, cusip text, units text, balance real, value_usd real, price real, maturity text,
        coupon text, period text, source_url text, status text default 'unverified',
        primary key(issuer_key, holder, instrument, period, source_url))""")

def store(con, key, rows, holder_type="fund (N-PORT)"):
    ensure(con)
    con.executemany("INSERT OR REPLACE INTO holders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'unverified')",
        [(key, (r["series"] or r["fund"]), holder_type, r["title"], r["cusip"], r["units"], r["balance"],
          r["value_usd"], r["price"], r["maturity"], r["coupon"], r["period"], r["source_url"]) for r in rows])
    con.commit()

def hunt(con, key, query, issuer_re, ua, start="2026-05-01", end="2026-10-21", max_docs=40):
    hits = []
    for attempt in range(3):
        try:
            hits = auditor.search(query, "NPORT-P", start, end, ua, max_pages=2); break
        except Exception:
            import time; time.sleep(5 * (attempt + 1))
    hits.sort(key=lambda h: h["_source"].get("file_date", ""), reverse=True)
    n = 0
    for h in hits[:max_docs]:
        u = auditor.filing_url(h)
        try:
            rows = parse(auditor._get(u, ua, timeout=120), issuer_re, u)
        except Exception:
            continue
        store(con, key, rows); n += len(rows)
    return n
