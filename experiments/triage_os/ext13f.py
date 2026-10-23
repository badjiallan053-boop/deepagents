"""Join SEC Form 13F bulk data (INFOTABLE/COVERPAGE/SUMMARYPAGE) to our names. Public, read-only.
Tables: f13_holdings (filer x our CUSIPs/issuer names), f13_filers (filer name, total 13F value = AUM proxy)."""
import argparse, csv, re, sqlite3, sys
csv.field_size_limit(sys.maxsize)
CUSIPS = {"278768106": "echostar", "644393100": "nfe", "18453H106": "clear_channel_outdoor", "74915M308": "qvc", "G9059U107": "trinseo"}
NAME_RE = re.compile(r"^(FS KKR CAP|GOLUB CAP(ITAL)? BDC|NEW MOUNTAIN FIN|PROSPECT CAP|BLACKSTONE SECD|BLUE OWL CAP(ITAL)? CORP|NUVEEN CHURCHILL|ECHOSTAR|NEW FORTRESS)", re.I)

def norm_firm(s):
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    s = re.sub(r"\b(l ?p|llc|l l c|inc|ltd|limited|corp|corporation|co|group|management|mgmt|capital|partners|advisors|asset|the|lp|llp)\b", " ", s)
    return " ".join(s.split())

def filing_url(cik, acc):
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/" if cik else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&accession={acc}"

def iter_tsv(path):
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        yield from csv.DictReader(f, delimiter="\t")

def load(db, d, period):
    con = sqlite3.connect(db)
    con.execute("create table if not exists f13_filers (accession primary key, filer, filer_norm, period, value_total real, entries int)")
    con.execute("create table if not exists f13_holdings (accession, filer, issuer_key, issuer, cusip, value real, shares real, putcall, period, source_url, status default 'UNVERIFIED')")
    cover = {r["ACCESSION_NUMBER"]: r for r in iter_tsv(f"{d}/COVERPAGE.tsv")}
    summ = {r["ACCESSION_NUMBER"]: r for r in iter_tsv(f"{d}/SUMMARYPAGE.tsv")}
    cik = {r["ACCESSION_NUMBER"]: r.get("CIK", "") for r in iter_tsv(f"{d}/SUBMISSION.tsv")}
    con.execute("delete from f13_filers where period=?", (period,)); con.execute("delete from f13_holdings where period=?", (period,))
    for acc, c in cover.items():
        s = summ.get(acc, {})
        con.execute("insert or replace into f13_filers values (?,?,?,?,?,?)", (acc, c["FILINGMANAGER_NAME"], norm_firm(c["FILINGMANAGER_NAME"]), period,
                    float(s.get("TABLEVALUETOTAL") or 0), int(s.get("TABLEENTRYTOTAL") or 0)))
    n = 0
    for r in iter_tsv(f"{d}/INFOTABLE.tsv"):
        key = CUSIPS.get(r["CUSIP"]) or (NAME_RE.match(r["NAMEOFISSUER"] or "") and norm_firm(r["NAMEOFISSUER"]))
        if not key: continue
        acc = r["ACCESSION_NUMBER"]; filer = cover.get(acc, {}).get("FILINGMANAGER_NAME", "")
        con.execute("insert into f13_holdings (accession,filer,issuer_key,issuer,cusip,value,shares,putcall,period,source_url) values (?,?,?,?,?,?,?,?,?,?)",
                    (acc, filer, key, r["NAMEOFISSUER"], r["CUSIP"], float(r["VALUE"] or 0), float(r["SSHPRNAMT"] or 0), r["PUTCALL"], period,
                     filing_url(cik.get(acc, ""), acc)))
        n += 1
    con.commit(); return n

def firm_lookup(con, firm):
    """Best 13F filer match for a firm name -> (filer, value_total) or None."""
    k = norm_firm(firm.split("(")[0])
    if not k: return None
    row = con.execute("select filer, max(value_total) from f13_filers where filer_norm=? or filer_norm like ? group by filer order by 2 desc limit 1",
                      (k, k + " %")).fetchone()
    return row if row and row[0] else None

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); ap.add_argument("--dir", required=True); ap.add_argument("--period", required=True)
    a = ap.parse_args(); print(load(a.db, a.dir, a.period), "matched 13F rows")
