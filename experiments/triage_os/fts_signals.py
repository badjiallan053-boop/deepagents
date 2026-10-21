"""TRIAGE OS - EDGAR full-text pre-filing distress phrases (read-only, public).
Each phrase maps to a signal type with a weight; hits stored with filing URL + date."""
import re, sqlite3
import auditor

PHRASES = {  # phrase -> (signal type, weight, forms)
    '"forbearance agreement"': ("forbearance", 35, "8-K,10-Q,10-K"),
    '"cooperation agreement" lenders': ("cooperation_agreement", 40, "8-K,10-Q,SC 13D"),
    '"transaction support agreement"': ("rsa_tsa", 45, "8-K"),
    '"restructuring support agreement"': ("rsa_tsa", 45, "8-K"),
    '"waiver and amendment"': ("covenant_waiver", 20, "8-K,10-Q"),
    '"grace period" "interest payment"': ("missed_payment", 40, "8-K"),
    '"did not make the interest payment"': ("missed_payment", 45, "8-K,10-Q"),
    '"elected not to make" "interest payment"': ("missed_payment", 45, "8-K,10-Q"),
    '"restructuring advisor"': ("advisor_hired", 30, "8-K,10-Q"),
    '"liability management"': ("lme", 25, "8-K,10-Q"),
    '"exchange offer" "consent solicitation"': ("exchange_offer", 25, "8-K"),
    '"substantial doubt" "going concern"': ("going_concern", 25, "10-Q,10-K"),
}
ADVISORS = re.compile(r"kirkland|pjt|houlihan|evercore|lazard|moelis|alvarez|ftI|alixpartners|perella|guggenheim|ducera|centerview", re.I)

def ensure(con):
    con.execute("""CREATE TABLE IF NOT EXISTS fts_hits(entity text, cik text, form text, file_date text,
        signal text, weight int, phrase text, source_url text, retrieved_at text,
        status text default 'unverified', primary key(source_url, signal))""")

def to_rows(hits, phrase):
    sig, w, _ = PHRASES[phrase]
    out = []
    for h in hits:
        s = h["_source"]
        if not s.get("ciks"):
            continue
        out.append({"entity": re.sub(r"\s*\(CIK.*", "", s["display_names"][0]).strip(),
                    "cik": s["ciks"][0], "form": s["form"], "file_date": s["file_date"],
                    "signal": sig, "weight": w, "phrase": phrase, "url": auditor.filing_url(h)})
    return out

def store(con, rows, now):
    ensure(con)
    con.executemany("INSERT OR IGNORE INTO fts_hits VALUES (?,?,?,?,?,?,?,?,?,'unverified')",
        [(r["entity"], r["cik"], r["form"], r["file_date"], r["signal"], r["weight"], r["phrase"],
          r["url"], now) for r in rows])
    con.commit()

def hunt(con, start, end, ua, now, phrases=None, max_pages=10):
    counts = {}
    for p in phrases or PHRASES:
        try:
            rows = to_rows(auditor.search(p, PHRASES[p][2], start, end, ua, max_pages=max_pages), p)
        except Exception as e:
            counts[p] = f"error {e}"; continue
        store(con, rows, now); counts[p] = len(rows)
    return counts

CONTEXT = {
    "cooperation_agreement": (r"cooperation agreement", r"lender|noteholder|creditor|bondholder|term loan|indenture"),
    "rsa_tsa": (r"(restructuring|transaction) support agreement", r"chapter 11|noteholder|lender|creditor|restructur|prepackaged"),
    "forbearance": (r"forbearance agreement", r"lender|default|credit agreement|noteholder"),
    "missed_payment": (r"interest payment", r"grace period|did not make|elected not to|forbearance|event of default"),
    "advisor_hired": (r"restructuring advis", r"retain|engage|hired"),
    "exchange_offer": (r"exchange offer", r"distress|liquidity|restructur|discount|below par|support agreement"),
}
NEGATE_ACTIVIST = re.compile(r"board of directors|nominat|standstill|activist|director appointment", re.I)

def confirm(text, signal, window=400):
    """True if the phrase sits next to creditor/distress context (not activist or M&A usage)."""
    if signal not in CONTEXT:
        return True
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))
    head, ctx = CONTEXT[signal]
    for m in re.finditer(head, t, re.I):
        w = t[max(0, m.start() - window): m.end() + window]
        if re.search(ctx, w, re.I) and not (signal == "cooperation_agreement" and NEGATE_ACTIVIST.search(w)):
            return True
    return False

def verify(con, ua, signals=tuple(CONTEXT)):
    con.execute("CREATE TABLE IF NOT EXISTS fts_verified(source_url text, signal text, confirmed int, primary key(source_url, signal))")
    done = {(u, s) for u, s in con.execute("SELECT source_url, signal FROM fts_verified")}
    todo = [(u, s) for u, s in con.execute("SELECT source_url, signal FROM fts_hits WHERE signal IN (%s)" %
            ",".join("?" * len(signals)), signals) if (u, s) not in done]
    for u, s in todo:
        try:
            ok = confirm(auditor._get(u, ua, timeout=90), s)
        except Exception:
            continue
        con.execute("INSERT OR REPLACE INTO fts_verified VALUES (?,?,?)", (u, s, int(ok)))
        con.commit()
    return con.execute("SELECT signal, sum(confirmed), count(*) FROM fts_verified GROUP BY 1").fetchall()
