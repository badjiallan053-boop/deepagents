"""TRIAGE OS - composite pre-filing distress score per borrower.

Joins: EDGAR full-text distress phrases (fts_hits), auditor changes / going concern
(auditor_flags), 8-K item signals (signals, source='sec'), BDC lender marks, mark
migration and cross-lender spread (bdc_marks), and debt size (debt_size, XBRL frames).
Entities already in Chapter 11 (8-K 1.03) are flagged 'filed', not pre-filing.
Heuristic triage score, not an investment view; every component keeps its URL.
"""
import csv, difflib, json, re
import bdc

SKIP = re.compile(r"\b(fund|trust|bancorp|bank|bancshares|financial corp|capital corp|bdc|lending|"
                  r"credit (?:company|fund|corp)|investment corp|acquisition corp|etf)\b", re.I)

EXHIBIT = re.compile(r"ex[-_]?(?:10|21|4)\b|ex10|ex21|creditagre|exhibit10", re.I)
WEAK = {"missed_payment_mention", "going_concern", "going_concern_10q", "lme"}

def _size_mult(debt):
    if not debt:
        return 0.6
    return 1.5 if debt >= 5e9 else 1.25 if debt >= 5e8 else 0.8 if debt >= 5e7 else 0.6

def build(con, bdc_ciks=()):
    ents = {}
    def ent(key, name):
        return ents.setdefault(key, {"key": key, "name": name, "signals": {}, "evidence": [],
                                      "debt": None, "filed": False, "lender_fv": 0.0})
    def add(e, sig, w, url, date, note=""):
        if w > e["signals"].get(sig, 0):
            e["signals"][sig] = w
        e["evidence"].append((w, date or "", sig, note, url))

    debt = {c: (d, u) for c, d, u in con.execute("SELECT cik, debt_usd, source_url FROM debt_size")}
    con.execute("CREATE TABLE IF NOT EXISTS fts_verified(source_url text, signal text, confirmed int, primary key(source_url, signal))")
    for name, cik, form, date, sig, w, url, ok in con.execute(
            """SELECT h.entity, h.cik, h.form, h.file_date, h.signal, h.weight, h.source_url, v.confirmed
               FROM fts_hits h LEFT JOIN fts_verified v ON v.source_url=h.source_url AND v.signal=h.signal"""):
        if SKIP.search(name) or str(int(cik)) in bdc_ciks:
            continue
        if ok == 0:
            continue          # phrase read in context and rejected (activist / M&A / boilerplate)
        if ok is None and sig in ("cooperation_agreement", "rsa_tsa", "missed_payment", "exchange_offer", "advisor_hired"):
            w = w // 2        # not yet read in context
        if EXHIBIT.search(url.rsplit("/", 1)[-1]) and sig in ("forbearance", "cooperation_agreement", "covenant_waiver", "lme"):
            w = w // 3        # contract boilerplate (credit agreement / subsidiaries exhibit), not an event
        e = ent("cik:" + str(int(cik)), re.sub(r"\s*\([^)]*\)", "", name).strip())
        add(e, sig, w, url, date, form)
    for name, cik, form, date, kind, flags, score, url in con.execute(
            "SELECT entity, cik, form, file_date, kind, flags, score, source_url FROM auditor_flags"):
        if SKIP.search(name):
            continue
        e = ent("cik:" + str(int(cik)), re.sub(r"\s*\([^)]*\)", "", name).strip())
        sig = "auditor_resigned" if "auditor_resigned" in flags else kind
        add(e, sig, min(40, score // 2), url, date, flags)
    for raw, url, date in con.execute("SELECT raw_json, url, event_date FROM signals WHERE source='sec'"):
        r = json.loads(raw)
        if not r.get("cik"):
            continue
        items = [str(i) for i in r.get("items") or []]
        e = ent("cik:" + str(int(r["cik"])), r.get("entity") or r.get("display_name") or "")
        if "1.03" in items:
            e["filed"] = True
        if "2.04" in items:
            add(e, "acceleration_2.04", 40, url, date, "8-K 2.04")
        if "4.02" in items:
            add(e, "non_reliance_4.02", 20, url, date, "8-K 4.02")
    for e in ents.values():
        if e["key"].startswith("cik:"):
            d = debt.get(e["key"][4:])
            if d:
                e["debt"], e["debt_url"] = d

    # private borrowers from BDC marks
    public_by_norm = {bdc.norm(e["name"]): e for e in ents.values() if e["name"]}
    norms = list(public_by_norm)
    marks = bdc.borrower_marks(con)
    by_b = {}
    for a in marks:
        by_b.setdefault(a["key"].split("|")[0], []).append(a)
    mig = {}
    for m in bdc.migration(con, min_drop=10, min_fv=1e6):
        mig.setdefault(m["key"], []).append(m)
    for key, rows in by_b.items():
        if re.match(r"(debt|equity) investments\b", rows[0]["name"], re.I):
            continue   # sector header captured instead of a borrower name
        latest = max(r.get("period", "") for r in rows) if rows and "period" in rows[0] else None
        worst = min(r["mark"] for r in rows)
        fv = sum(r["fv"] for r in rows)
        if worst >= 85 and key not in mig:
            continue
        match = public_by_norm.get(key) or (public_by_norm[difflib.get_close_matches(key, norms, 1, 0.92)[0]]
                                            if len(key) > 6 and difflib.get_close_matches(key, norms, 1, 0.92) else None)
        e = match or ent("bdc:" + key, rows[0]["name"])
        e["lender_fv"] += fv
        if worst < 85:
            r = min(rows, key=lambda r: r["mark"])
            add(e, "lender_mark", round(min(45, (100 - worst) * 0.75)), r["url"], "", f"{r['bdc']} marks {r['identifier'][:60]} at {worst}")
        holders = {r["bdc"] for r in rows}
        if len(holders) >= 2:
            ms = [r["mark"] for r in rows]
            if max(ms) - min(ms) >= 8:
                add(e, "lender_disagreement", 15, rows[0]["url"], "", f"{len(holders)} BDCs, marks {min(ms)}-{max(ms)}")
            if worst < 85:
                add(e, "multi_lender_stress", 10, rows[0]["url"], "", f"{len(holders)} BDC holders")
        for m in mig.get(key, []):
            add(e, "mark_cliff", round(min(35, m["drop"])), m["url"], m["to"],
                f"{m['bdc']} {m['mark_before']}->{m['mark_after']} ({m['from']}->{m['to']})")
    out = []
    for e in ents.values():
        if not e["signals"]:
            continue
        base = sum(sorted(e["signals"].values(), reverse=True)[:5])
        size = e["debt"] or (e["lender_fv"] * 3 if e["lender_fv"] else None)  # BDC hold ~1/3 of a deal [est.]
        strong = [k for k, v in e["signals"].items() if k not in WEAK and v >= 10]
        corroboration = 1.0 if len(strong) >= 2 else 0.6   # one strong signal alone is not enough
        e["score"] = round(min(100, base * _size_mult(size) * corroboration), 1)
        e["n_types"] = len(e["signals"])
        e["evidence"].sort(key=lambda x: (-x[0], x[1]), reverse=False)
        out.append(e)
    return sorted(out, key=lambda e: (e["filed"], -e["score"], -e["n_types"]))

def export(rows, path, n=50):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "score", "entity", "key", "signal_types", "n_types", "debt_usd_m",
                    "bdc_fair_value_usd_m", "already_filed", "evidence_1", "evidence_2", "evidence_3", "status"])
        for i, e in enumerate([r for r in rows if not r["filed"]][:n], 1):
            ev = [f"{s} {note} {u}".strip() for _, _, s, note, u in e["evidence"][:3]]
            w.writerow([i, e["score"], e["name"], e["key"], ";".join(sorted(e["signals"])), e["n_types"],
                        round(e["debt"] / 1e6) if e["debt"] else "", round(e["lender_fv"] / 1e6, 1) if e["lender_fv"] else "",
                        e["filed"], *(ev + ["", "", ""])[:3], "unverified"])

def load_exclusions(path):
    """CSV key,reason,source_url,date - names a human or evidence removed (e.g. acquisition closed)."""
    import os
    if not path or not os.path.exists(path):
        return {}
    return {r["key"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}

def export_filtered(con, path, user_agent, n=50, fetch=None, bdc_ciks=(), exclusions=None):
    """Rebuild, drop names already in Chapter 11 (8-K 1.03 / XBRL LSTC / DIP) and evidenced
    exclusions (acquired, refinanced), export top n."""
    import desk, inch11
    ex = exclusions or {}
    rows = [e for e in build(con, bdc_ciks) if e["key"] not in ex]
    log = []
    kept = inch11.filter_watchlist(rows, fetch or desk.get_json, desk._sec_headers(user_agent), n=n, log=log)
    for e in kept:
        e["filed"] = False
    export(kept, path, n)
    return kept, log

if __name__ == "__main__":
    import argparse, sqlite3
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--user-agent", required=True); ap.add_argument("-n", type=int, default=50)
    ap.add_argument("--exclusions", default=None)
    a = ap.parse_args()
    kept, log = export_filtered(sqlite3.connect(a.db), a.out, a.user_agent, a.n, exclusions=load_exclusions(a.exclusions))
    for name, r in log:
        if r["status"] != "clear":
            print(r["status"], name, r["evidence"][:2])
    print("kept", len(kept))
