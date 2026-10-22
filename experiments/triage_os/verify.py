"""Claim verification ledger. Each claim -> VERIFIED / CORRECTED / UNVERIFIABLE with primary URL and check date.
Automated checks: (a) fetch a primary URL and require tokens; (b) recompute from SEC-derived DB tables.
Research results (web) are recorded with the primary URL found and the method."""
import datetime as dt, re, sqlite3, urllib.request, html as _h

UA = "TRIAGE-OS research arslane.souici@example.com"
TODAY = dt.date.today().isoformat()

def fetch_text(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req, timeout=timeout).read()
    if data[:4] == b"%PDF":
        import subprocess
        return re.sub(r"\s+", " ", subprocess.run(["pdftotext", "-", "-"], input=data, capture_output=True).stdout.decode("utf-8", "ignore"))
    raw = data.decode("utf-8", "ignore")
    return re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", " ", raw)))

def token_check(text, tokens):
    t = text.lower()
    return [k for k in tokens if k.lower() not in t]

def check_url(url, tokens, fetch=fetch_text):
    try:
        missing = token_check(fetch(url), tokens)
    except Exception as e:  # network / block
        return "ERROR", str(e)[:120]
    return ("OK", "") if not missing else ("MISSING", ";".join(missing))

def _f13_latest(db, filer, issuer_key):
    """Sum all lines of the filer's latest accession (one filing can list a CUSIP once per sub-manager)."""
    c = sqlite3.connect(db, timeout=120)
    rows = c.execute("select accession,cusip,putcall,value from f13_holdings where filer=? and issuer_key=?", (filer, issuer_key)).fetchall()
    if not rows: return {}
    acc = max(r[0] for r in rows); out = {}
    for a, cusip, pc, val in rows:
        if a == acc: out[(cusip, pc)] = out.get((cusip, pc), 0) + val
    return out

def f13_total(db, filer, issuer_key="echostar"):
    return round(sum(_f13_latest(db, filer, issuer_key).values()) / 1e6, 1)

def f13_breakdown(db, filer, issuer_key="echostar"):
    return "; ".join(f"{k[0]}{' '+k[1] if k[1] else ''} ${v/1e6:.1f}m" for k, v in sorted(_f13_latest(db, filer, issuer_key).items()))

def mark_range(db, borrower_like, bdc=None, period="2026-06-30"):
    c = sqlite3.connect(db, timeout=120)
    q = "select min(mark),max(mark) from bdc_marks where lower(borrower) like ? and period=? and mark>0"
    a = [f"%{borrower_like.lower()}%", period]
    if bdc: q += " and bdc=?"; a.append(bdc)
    return c.execute(q, a).fetchone()

def save(rows, db):
    c = sqlite3.connect(db, timeout=120)
    c.execute("create table if not exists verification(claim_id primary key, artifact, claim, status, primary_url, checked, method, fix)")
    c.executemany("insert or replace into verification values(?,?,?,?,?,?,?,?)",
                  [(r["id"], r["artifact"], r["claim"], r["status"], r["url"], r.get("checked", TODAY), r["method"], r.get("fix", "")) for r in rows])
    c.commit()
    return dict(c.execute("select status,count(*) from verification group by status").fetchall())

def to_markdown(rows):
    out = ["| ID | Artifact | Claim | Status | Primary source | Checked | Method | Fix / note |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append("| {id} | {artifact} | {claim} | **{status}** | {url} | {c} | {method} | {fix} |".format(c=r.get("checked", TODAY), fix=r.get("fix", ""), **{k: str(v).replace("|", "/") for k, v in r.items() if k not in ("checked", "fix")}))
    return "\n".join(out)
