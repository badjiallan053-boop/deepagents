"""Sale-process calendar from claims-agent dockets (Kroll, Stretto, Epiq, Omni, Verita). Dates are as filed; 'proposed' until the bidding-procedures order is entered."""
import csv, datetime as dt, sqlite3
F = ["case_name", "court", "agent", "event", "date", "time_tz", "state", "source_url", "status"]
ROWS = [
 ("FRC Balance LLC (True Food Kitchen) 26-90806", "S.D. Tex.", "Stretto", "Final DIP hearing", "2026-10-27", "", "scheduled", "https://cases.stretto.com/public/x565/14929/PLEADINGS/1492910062680000000243.pdf", "VERIFIED"),
 ("FRC Balance LLC (True Food Kitchen) 26-90806", "S.D. Tex.", "Stretto", "Bid deadline", "2026-12-10", "17:00 CT", "proposed", "https://cases.stretto.com/public/x565/14929/PLEADINGS/1492910062680000000243.pdf", "VERIFIED"),
 ("FRC Balance LLC (True Food Kitchen) 26-90806", "S.D. Tex.", "Stretto", "Auction", "2026-12-15", "", "proposed", "https://cases.stretto.com/public/x565/14929/PLEADINGS/1492910062680000000243.pdf", "VERIFIED"),
 ("FRC Balance LLC (True Food Kitchen) 26-90806", "S.D. Tex.", "Stretto", "Sale hearing", "2026-12-21", "", "proposed", "https://cases.stretto.com/public/x565/14929/PLEADINGS/1492910062680000000243.pdf", "VERIFIED"),
 ("Omnis Pleasants LLC 26-11169", "D. Del.", "Stretto", "Bid deadline", "2026-11-09", "", "ordered/noticed", "https://cases.stretto.com/public/x914/14816/PLEADINGS/1481609172680000000813.pdf", "VERIFIED"),
 ("Omnis Pleasants LLC 26-11169", "D. Del.", "Stretto", "Auction", "2026-11-12", "", "ordered/noticed", "https://cases.stretto.com/public/x914/14816/PLEADINGS/1481609172680000000813.pdf", "VERIFIED"),
 ("Omnis Pleasants LLC 26-11169", "D. Del.", "Stretto", "Sale hearing", "2026-11-18", "", "ordered/noticed", "https://cases.stretto.com/public/x914/14816/PLEADINGS/1481609172680000000813.pdf", "VERIFIED"),
 ("Hughes Satellite Systems 26-90739", "S.D. Tex.", "Epiq", "Exclusivity / competing-plan hearing", "2026-12-01", "09:00 CT", "scheduled", "https://document.epiq11.com/document/getdocumentbycode?docId=4623687&projectCode=HSQ", "VERIFIED"),
 ("W.D. Pa. case (noticeregistry)", "W.D. Pa.", "n/a", "Bid deadline / auction / sale hearing", "2026-11-06", "", "noticed", "https://noticeregistry.com", "UNVERIFIABLE (secondary; auction 11 Nov, hearing 19 Nov)"),
]
def upcoming(rows, today):
    return sorted([r for r in rows if r[4] >= today], key=lambda r: r[4])
def build(db, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(F); w.writerows(ROWS)
    c = sqlite3.connect(db, timeout=120); c.execute("drop table if exists claims_calendar")
    c.execute(f"create table claims_calendar({','.join(F)})"); c.executemany("insert into claims_calendar values(?,?,?,?,?,?,?,?,?)", ROWS); c.commit()
    return len(ROWS)
if __name__ == "__main__":
    print(build("/workspace/triage_os_data/triage.db", "/workspace/triage_os_data/claims_calendar.csv"))
