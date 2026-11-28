"""Read-only ingestion of SEC ABS-EE (EX-102) CMBS loan-level data.

Flags stress: special servicer transfer, payment status, low DSCR, near maturity, workout strategy.
"""
import re
import sqlite3
import xml.etree.ElementTree as ET

FIELDS = ["assetNumber", "originatorName", "maturityDate", "reportPeriodEndActualBalanceAmount",
          "paymentStatusLoanCode", "mostRecentSpecialServicerTransferDate", "workoutStrategyCode",
          "modifiedIndicator", "reportingPeriodEndDate"]
PFIELDS = ["propertyName", "propertyCity", "propertyState", "propertyTypeCode",
           "mostRecentDebtServiceCoverageNetOperatingIncomePercentage", "mostRecentPhysicalOccupancyPercentage",
           "mostRecentValuationAmount", "mostRecentValuationDate"]
COLS = ["trust", "cik", "accession"] + FIELDS + PFIELDS + ["stress_score", "stress_reasons", "source_url", "retrieved_at"]


def _strip(xml):
    return re.sub(r'\sxmlns(:\w+)?="[^"]+"', "", xml, count=5)


def _txt(node, tag):
    e = node.find(".//" + tag)
    return e.text.strip() if e is not None and e.text else ""


def _mdy(s):
    m = re.match(r"(\d\d)-(\d\d)-(\d{4})", s or "")
    return f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else s


def stress(row, asof="2026-10-22"):
    reasons = []
    if row["mostRecentSpecialServicerTransferDate"]:
        reasons.append("special servicing")
    if row["paymentStatusLoanCode"] not in ("", "0", "A", "B"):
        reasons.append(f"payment status {row['paymentStatusLoanCode']}")
    try:
        d = float(row["mostRecentDebtServiceCoverageNetOperatingIncomePercentage"] or "nan")
        if d == d and d < 1.0:
            reasons.append(f"DSCR {d:.2f}")
    except ValueError:
        pass
    mat = row["maturityDate"]
    if mat and mat <= "2027-12-31":
        reasons.append(f"maturity {mat}")
    if row["workoutStrategyCode"]:
        reasons.append(f"workout {row['workoutStrategyCode']}")
    w = {"special servicing": 40, "payment": 30, "DSCR": 20, "maturity": 10, "workout": 20}
    score = sum(v for k, v in w.items() if any(r.startswith(k) for r in reasons))
    return score, "; ".join(reasons)


def parse(xml, trust, cik, accession, source_url, retrieved_at):
    root = ET.fromstring(_strip(xml))
    out = []
    for a in root.iter("assets"):
        row = {f: _txt(a, f) for f in FIELDS}
        prop = a.find("property")
        row.update({f: _txt(prop, f) if prop is not None else "" for f in PFIELDS})
        for k in ("maturityDate", "mostRecentSpecialServicerTransferDate", "reportingPeriodEndDate", "mostRecentValuationDate"):
            row[k] = _mdy(row[k])
        row["stress_score"], row["stress_reasons"] = stress(row)
        row.update(trust=trust, cik=cik, accession=accession, source_url=source_url, retrieved_at=retrieved_at)
        out.append(row)
    return out


def store(con, rows):
    con.execute("create table if not exists cmbs_loans (" + ",".join(c + " text" for c in COLS) +
                ", primary key(accession, assetNumber))")
    con.executemany(f"insert or replace into cmbs_loans values ({','.join('?' * len(COLS))})",
                    [[r[c] for c in COLS] for r in rows])
    return len(rows)


# --- wider coverage: discover recent CMBS ABS-EE filings and roll up per trust ---------
def discover(ua, start, end, fetch_json, max_pages=10):
    """EDGAR full-text search for ABS-EE filings; returns [(entity, cik, accession)] newest first."""
    import urllib.parse
    seen, out = set(), []
    for page in range(max_pages):
        q = urllib.parse.urlencode({"q": '"mortgage trust"', "forms": "ABS-EE", "startdt": start, "enddt": end, "from": page * 100})
        hits = fetch_json(f"https://efts.sec.gov/LATEST/search-index?{q}", {"User-Agent": ua}).get("hits", {}).get("hits", [])
        if not hits:
            break
        for h in hits:
            s = h["_source"]
            acc = h["_id"].split(":")[0]
            cik = str(int(s["ciks"][0]))
            if acc in seen:
                continue
            seen.add(acc)
            out.append((s["display_names"][0], cik, acc, s.get("file_date", "")))
    return sorted(out, key=lambda x: x[3], reverse=True)


def trust_rollup(con, asof="2026-10-22", fresh_days=120):
    """Per trust: loans, balance, share of balance in special servicing / delinquent, and fresh SS transfers."""
    import datetime as dt
    cutoff = (dt.date.fromisoformat(asof) - dt.timedelta(days=fresh_days)).isoformat()
    rows = con.execute("""select trust, count(*), sum(cast(reportPeriodEndActualBalanceAmount as real)),
        sum(case when mostRecentSpecialServicerTransferDate<>'' then cast(reportPeriodEndActualBalanceAmount as real) else 0 end),
        sum(case when paymentStatusLoanCode not in ('','0','A','B') then cast(reportPeriodEndActualBalanceAmount as real) else 0 end),
        sum(case when mostRecentSpecialServicerTransferDate>=? then 1 else 0 end), max(source_url)
        from cmbs_loans group by trust""", (cutoff,)).fetchall()
    out = []
    for t, n, bal, ss, dq, fresh, url in rows:
        bal = bal or 0
        out.append({"trust": t, "loans": n, "balance_m": round(bal / 1e6, 1),
                    "ss_pct": round(100 * (ss or 0) / bal, 1) if bal else 0.0,
                    "dq_pct": round(100 * (dq or 0) / bal, 1) if bal else 0.0, "fresh_ss": fresh, "url": url})
    return sorted(out, key=lambda r: (-r["ss_pct"], -r["dq_pct"]))
