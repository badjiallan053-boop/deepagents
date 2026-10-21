"""TRIAGE OS - BDC schedule-of-investments marks (SEC inline XBRL), read-only.

BDCs must mark every private loan at fair value each quarter and tag each line
(us-gaap:InvestmentIdentifierAxis) in inline XBRL. Two pre-default signals:
  * stress: a debt position marked < 80% of par (or cost when par is missing)
  * divergence: two or more BDCs holding the same borrower with marks >= 10 pts apart
Marks are the managers' own Level-3 estimates, not market prices: unverified.
"""
import html, re, sqlite3, statistics

FACTS = {"us-gaap:InvestmentOwnedAtFairValue": "fv", "us-gaap:InvestmentOwnedAtCost": "cost",
         "us-gaap:InvestmentOwnedBalancePrincipalAmount": "par"}
EQUITY = re.compile(r"\b(equity|shares?|units?|warrants?|common|preferred|membership|partnership interest|lp interest|class [a-z] )", re.I)
CTX = re.compile(r'<xbrli:context id="([^"]+)">(.*?)</xbrli:context>', re.S)
TYPED = re.compile(r'dimension="us-gaap:InvestmentIdentifierAxis"><[^>]+>(.*?)</', re.S)
INSTANT = re.compile(r"<xbrli:instant>(\d{4}-\d{2}-\d{2})</xbrli:instant>")
FACT = re.compile(r'<ix:nonFraction([^>]*)>(.*?)</ix:nonFraction>', re.S)
ATTR = re.compile(r'(\w+)="([^"]*)"')
_SUF = {"inc", "llc", "lp", "corp", "corporation", "co", "ltd", "limited", "holdings", "holding",
        "holdco", "intermediate", "parent", "buyer", "borrower", "acquisition", "acquisitionco",
        "midco", "topco", "bidco", "opco", "the", "group", "l", "p", "and"}

def borrower_of(identifier):
    return html.unescape(identifier).split("|")[0].strip()

def norm(name):
    w = re.sub(r"[^a-z0-9 ]+", " ", name.lower().replace("&", " ")).split()
    core = [x for x in w if x not in _SUF and not re.fullmatch(r"(i|ii|iii|iv|v|\d+)", x)]
    return " ".join(core or w)

def _num(attrs, text):
    t = re.sub(r"<[^>]+>", "", text).strip().replace(",", "")
    if t in ("", "-", "—", "–"):
        return 0.0
    try:
        v = float(t) * 10 ** int(attrs.get("scale", "0") or 0)
    except ValueError:
        return None
    return -v if attrs.get("sign") == "-" else v

def parse(doc, period=None):
    ctx = {}
    for cid, body in CTX.findall(doc):
        m, i = TYPED.search(body), INSTANT.search(body)
        if m and i and "explicitMember" not in body:
            ctx[cid] = (html.unescape(m.group(1)).strip(), i.group(1))
    if not ctx:
        return []
    period = period or max(d for _, d in ctx.values())
    pos = {}
    for attrs_s, text in FACT.findall(doc):
        a = dict(ATTR.findall(attrs_s))
        key, c = FACTS.get(a.get("name")), a.get("contextRef")
        if key and c in ctx and ctx[c][1] == period:
            v = _num(a, text)
            if v is not None:
                pos.setdefault(c, {"identifier": ctx[c][0], "period": period})[key] = v
    out = []
    for p in pos.values():
        if EQUITY.search(p["identifier"]) or not p.get("fv"):
            continue
        base = p.get("par") or p.get("cost")
        if not base or base <= 0:
            continue
        p["mark"] = round(100 * p["fv"] / base, 1)
        p["borrower"] = borrower_of(p["identifier"])
        p["borrower_key"] = norm(p["borrower"])
        out.append(p)
    return out

def store(con, bdc, filing_url, rows):
    con.execute("""CREATE TABLE IF NOT EXISTS bdc_marks(bdc text, borrower text, borrower_key text,
        identifier text, period text, par real, cost real, fv real, mark real, source_url text,
        status text default 'unverified', primary key(bdc, identifier, period))""")
    con.executemany("INSERT OR REPLACE INTO bdc_marks VALUES (?,?,?,?,?,?,?,?,?,?, 'unverified')",
        [(bdc, r["borrower"], r["borrower_key"], r["identifier"], r["period"], r.get("par"),
          r.get("cost"), r["fv"], r["mark"], filing_url) for r in rows])
    con.commit()

JUNIOR = re.compile(r"second|2nd|junior|subordinat|last[ -]out|second[ -]out|mezz|unsecured", re.I)

def lien(identifier):
    return "junior" if JUNIOR.search(identifier) else "senior"

def fair_mark(fv, par, cost):
    """Mark vs par; falls back to cost when par looks like a foreign-currency amount
    (par/cost far from 1 means par is in SEK/EUR/... while fair value is in USD)."""
    if par and cost and not (0.8 <= par / cost <= 1.25):
        par = None
    base = par or cost
    return round(100 * fv / base, 1) if base and base > 0 else None

UNFUNDED = re.compile(r"revolv|delayed[ -]draw|\bddtl?\b|unfunded|letter of credit", re.I)

def borrower_marks(con):
    """One mark per (bdc, borrower): its largest funded debt position (term loan / bond),
    so a first-lien term loan is compared with a first-lien term loan, not a revolver."""
    best = {}
    for bdc, key, name, ident, fv, par, cost, url in con.execute(
            "SELECT bdc, borrower_key, borrower, identifier, fv, par, cost, source_url FROM bdc_marks"):
        if UNFUNDED.search(ident):
            continue
        mark = fair_mark(fv, par, cost)
        if mark is None:
            continue
        key = key + "|" + lien(ident)
        if mark > 115:      # par/cost tagging mismatch, not a real mark
            continue
        cur = best.get((bdc, key))
        if not cur or fv > cur["fv"]:
            best[(bdc, key)] = {"bdc": bdc, "key": key, "name": name, "identifier": ident,
                                "fv": fv, "mark": mark, "url": url}
    return list(best.values())

def stressed(con, below=80, min_fv=1e6):
    return sorted([a for a in borrower_marks(con) if a["mark"] is not None and a["mark"] < below
                   and a["fv"] >= min_fv], key=lambda a: a["mark"])

def divergence(con, min_gap=8):
    by = {}
    for a in borrower_marks(con):
        if a["mark"] is not None and a["fv"] > 0 and a["mark"] <= 102:  # >102 = FX/par tagging noise
            by.setdefault(a["key"], []).append(a)
    out = []
    for key, rows in by.items():
        if len({r["bdc"] for r in rows}) < 2:
            continue
        marks = [r["mark"] for r in rows]
        gap = max(marks) - min(marks)
        if gap >= min_gap:
            out.append({"key": key, "name": rows[0]["name"], "gap": round(gap, 1),
                        "median": statistics.median(marks),
                        "holders": sorted(((r["bdc"], r["mark"], r["url"], r["identifier"]) for r in rows), key=lambda x: x[1])})
    return sorted(out, key=lambda d: -d["gap"])
