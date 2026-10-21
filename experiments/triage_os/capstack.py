"""TRIAGE OS - capital structure rows from a public issuer's 10-Q/10-K inline XBRL
(debt facts dimensioned by DebtInstrumentAxis / LongtermDebtTypeAxis / ShortTermDebtTypeAxis).
Private borrowers: tranches from BDC schedules (bdc_marks). Every row keeps its source URL."""
import html, re, sqlite3
import bdc

AXES = ("us-gaap:DebtInstrumentAxis", "us-gaap:LongtermDebtTypeAxis", "us-gaap:ShortTermDebtTypeAxis",
        "us-gaap:LineOfCreditFacilityAxis")
CONCEPTS = {"DebtInstrumentFaceAmount": "face", "LongTermDebt": "carrying", "DebtInstrumentCarryingAmount": "carrying",
            "LongTermDebtGross": "carrying", "SecuredDebt": "carrying", "SeniorNotes": "carrying",
            "LineOfCreditFacilityMaximumBorrowingCapacity": "commitment", "LongTermLineOfCredit": "carrying",
            "DebtInstrumentInterestRateStatedPercentage": "coupon", "DebtInstrumentBasisSpreadOnVariableRate1": "spread",
            "DebtInstrumentMaturityDate": "maturity", "DebtInstrumentFairValue": "fair_value",
            "LongTermDebtFairValue": "fair_value"}
CTX = re.compile(r'<xbrli:context id="([^"]+)">(.*?)</xbrli:context>', re.S)
MEM = re.compile(r'<xbrldi:explicitMember dimension="([^"]+)">([^<]+)</xbrldi:explicitMember>')
FACT = re.compile(r'<ix:(nonFraction|nonNumeric)([^>]*)>(.*?)</ix:\1>', re.S)
ATTR = re.compile(r'(\w+)="([^"]*)"')

def member_label(m):
    m = m.split(":")[-1]
    m = re.sub(r"Member$", "", m)
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", m).replace("Percent", "%").strip()

def _concept_kind(c):
    if re.search(r"DebtDefault", c):
        return "default_amount"
    if re.search(r"DebtorInPossessionFinancingAmountArranged", c):
        return "dip"
    if re.search(r"^LongTermDebt(?!Current|Noncurrent|FairValue)|DebtInstrumentNetOf|LongTermDebtExcluding", c):
        return "carrying"
    return None

def parse(doc):
    ctx = {}
    for cid, body in CTX.findall(doc):
        mems = MEM.findall(body)
        tr = [v for d, v in mems if d in AXES]
        other = [d for d, v in mems if d not in AXES and d != "dei:LegalEntityAxis"]
        if tr and not other:
            inst = re.search(r"<xbrli:(?:instant|endDate)>([\d-]+)<", body)
            ctx[cid] = (tr[0], inst.group(1) if inst else None)
    if not ctx:
        return []
    latest = max(d for _, d in ctx.values() if d)
    rows = {}
    for kind, a_s, text in FACT.findall(doc):
        a = dict(ATTR.findall(a_s))
        concept = a.get("name", "").split(":")[-1]
        c = a.get("contextRef")
        key = CONCEPTS.get(concept) or _concept_kind(concept)
        if not key or c not in ctx or ctx[c][1] != latest:
            continue
        t = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
        if kind == "nonFraction":
            try:
                v = float(t.replace(",", "") or 0) * 10 ** int(a.get("scale", "0") or 0)
            except ValueError:
                continue
            if a.get("sign") == "-":
                v = -v
        else:
            v = t
        r = rows.setdefault(ctx[c][0], {"member": ctx[c][0], "tranche": member_label(ctx[c][0]), "as_of": latest})
        r.setdefault(key, v)
        if key == "default_amount":
            r["in_default"] = True
    return list(rows.values())

def ensure(con):
    con.execute("""CREATE TABLE IF NOT EXISTS cap_structure(issuer_key text, issuer text, tranche text,
        lien text, amount_usd real, amount_kind text, coupon text, maturity text, mark_or_price real,
        as_of text, source text, source_url text, status text default 'unverified',
        primary key(issuer_key, tranche, as_of, source))""")

def lien_of(name):
    n = name.lower()
    if re.search(r"second|2nd|junior|subordinat|unsecured|convertible|exchangeable|senior notes|notes", n) and "secured" not in n:
        return "unsecured/junior" if not re.search(r"second|2nd", n) else "second lien"
    if re.search(r"revolv|term loan|first lien|secured|abl|1st", n):
        return "senior secured"
    return "unknown"

def store_public(con, key, issuer, rows, url):
    ensure(con)
    for r in rows:
        amt, kind = next(((r[k], k) for k in ("face", "carrying", "default_amount", "dip", "commitment") if isinstance(r.get(k), float)), (None, None))
        cpn = r.get("coupon")
        cpn = f"{cpn * 100:.3f}%" if isinstance(cpn, float) and cpn < 1 else (f"{cpn}%" if isinstance(cpn, float) else cpn)
        if r.get("spread") is not None and isinstance(r["spread"], float):
            cpn = (cpn + " / " if cpn else "") + f"SOFR+{r['spread'] * 100:.2f}%"
        fvp = round(100 * r["fair_value"] / amt, 1) if isinstance(r.get("fair_value"), float) and amt else None
        con.execute("INSERT OR REPLACE INTO cap_structure VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'unverified')",
            (key, issuer, r["tranche"], lien_of(r["tranche"]), amt, kind, cpn, r.get("maturity"), fvp,
             r["as_of"], "10-Q/10-K iXBRL", url))
    con.commit()

def store_private(con, key, name_like):
    ensure(con)
    n = 0
    for bdcname, ident, period, par, cost, fv, url in con.execute(
            "SELECT bdc, identifier, period, par, cost, fv, source_url FROM bdc_marks WHERE lower(borrower) LIKE ?", (name_like,)):
        m = bdc.fair_mark(fv, par, cost)
        con.execute("INSERT OR REPLACE INTO cap_structure VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'unverified')",
            (key, ident.split("|")[0].strip(), f"{bdcname}: {ident[:160]}", bdc.lien(ident) if not bdc.UNFUNDED.search(ident) else "revolver/DDTL",
             par or cost, "par" if par else "cost", None, None, m, period, "BDC schedule", url))
        n += 1
    con.commit()
    return n
