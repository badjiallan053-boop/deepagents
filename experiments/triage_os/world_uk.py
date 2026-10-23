"""UK: Companies House Free Company Data Product (full register snapshot). Late accounts, outstanding charges,
insolvency statuses. Writes uk_ch_flags (larger companies only: FULL/GROUP/MEDIUM accounts) and summary counts."""
import csv, io, zipfile, sqlite3, os, datetime, collections
Z = "/workspace/triage_os_data/world/ch_basic.zip"; DB = os.environ.get("TRIAGE_DB", "/workspace/triage_os_data/triage.db")
SNAP = datetime.date(2026, 10, 1)
def d(s):
    try: return datetime.datetime.strptime(s.strip(), "%d/%m/%Y").date()
    except Exception: return None
if __name__ == "__main__":
    zf = zipfile.ZipFile(Z); fn = zf.namelist()[0]
    rdr = csv.reader(io.TextIOWrapper(zf.open(fn), encoding="utf-8", errors="ignore"))
    hdr = [h.strip() for h in next(rdr)]; ix = {h: i for i, h in enumerate(hdr)}
    S = collections.Counter(); keep = []
    for r in rdr:
        if len(r) < len(hdr): continue
        S["rows"] += 1
        st = r[ix["CompanyStatus"]]; S["status:" + st] += 1
        cat = r[ix["Accounts.AccountCategory"]]; due = d(r[ix["Accounts.NextDueDate"]])
        late = st == "Active" and due and due < SNAP
        if late: S["late_active"] += 1
        big = cat in ("FULL", "GROUP", "MEDIUM")
        if late and big: S["late_big"] += 1
        out = int(r[ix["Mortgages.NumMortOutstanding"]] or 0)
        if out: S["with_outstanding_charges"] += 1
        if big and (late or st in ("Liquidation", "In Administration", "Administration Order", "Voluntary Arrangement", "Receivership Action", "Live but Receiver Manager on at least one charge")):
            keep.append((r[ix["CompanyNumber"]], r[ix["CompanyName"]], st, cat, r[ix["Accounts.NextDueDate"]], r[ix["Accounts.LastMadeUpDate"]], out, r[ix["SICCode.SicText_1"]], r[ix["RegAddress.PostTown"]], (SNAP - due).days if due else None))
    con = sqlite3.connect(DB, timeout=300)
    con.execute("drop table if exists uk_ch_flags"); con.execute("create table uk_ch_flags (number, name, status, acct_cat, next_due, last_made_up, charges_outstanding, sic, town, days_overdue)")
    con.executemany("insert into uk_ch_flags values (?,?,?,?,?,?,?,?,?,?)", keep)
    con.execute("create table if not exists dataset_counts (dataset, rows, note, source_url)"); con.execute("delete from dataset_counts where dataset like 'uk_ch%'")
    u = "https://download.companieshouse.gov.uk/en_output.html"
    con.executemany("insert into dataset_counts values (?,?,?,?)", [("uk_ch_register", S["rows"], "BasicCompanyData snapshot 2026-10-01", u), ("uk_ch_late_active", S["late_active"], "active, accounts past due", u),
        ("uk_ch_late_big", S["late_big"], "active FULL/GROUP/MEDIUM filers, accounts past due", u), ("uk_ch_charges", S["with_outstanding_charges"], "companies with >=1 outstanding charge", u), ("uk_ch_flags", len(keep), "large filers late or in insolvency status", u)])
    con.commit(); print(dict(S.most_common(25)), len(keep))
