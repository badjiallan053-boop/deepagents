"""Tranche-level capital structures for the top-15 situations. Public issuers: SEC/IR filings. Private borrowers: BDC schedules of investments (bdc_marks)."""
import csv, re, sqlite3
SEC = "https://www.sec.gov/Archives/edgar/data/"
HSSC_Q1 = SEC + "1533758/000110465926059606/hssc-20260331x10q.htm"; SATS_Q2 = SEC + "1415404/000110465926089370/sats-20260630x10q.htm"
DDBS_Q3 = SEC + "1042642/000110465925111701/ddbs-20250930x10q.htm"; SATS_8K = SEC + "1415404/000141540426000048/sats-20261001x8k.htm"
F = ["situation", "issuer", "tranche", "amount_usd_m", "coupon", "maturity", "lien", "guarantors", "covenants", "agent_trustee", "holder", "mark", "as_of", "source_url", "status"]
PUBLIC = [
 ("Hughes 26-90739","Hughes Satellite Systems Corp","Senior Secured Notes",750.0,"5.25%","2026-08-01","1st lien (secured)","HSSC restricted subsidiaries","Limits on debt, liens, sale-leaseback, dividends, investments (10-K)","Trustee per indenture (not stated in 10-Q)","","","2026-03-31",HSSC_Q1,"VERIFIED; $122.7m held by EchoStar affiliates -> $627.3m third-party (SATS 10-Q Q2)"),
 ("Hughes 26-90739","Hughes Satellite Systems Corp","Senior Notes (unsecured)",750.0,"6.625%","2026-08-01","Senior unsecured","HSSC restricted subsidiaries","As above","Not stated","","FV 58.0 (435/750) at 30 Jun 2026","2026-06-30",SATS_Q2,"VERIFIED"),
 ("Hughes 26-90739","Hughes Satellite Systems Corp","Other notes payable",33.9,"n/d","n/d","n/d","","","","","","2026-03-31",HSSC_Q1,"VERIFIED"),
 ("Hughes 26-90739","Hughes Satellite Systems Corp","Intercompany secured loan from EchoStar XXIV",50.0,"n/d","n/d","Secured","","","","EchoStar affiliate","","2026-09-10","https://storage.courtlistener.com/recap/gov.uscourts.txsb.498986/gov.uscourts.txsb.498986.320.0.pdf","VERIFIED (debtor-stated, via Dkt 320)"),
 ("DISH DBS 26-90627","DISH DBS Corp","Senior Notes",2000.0,"7.75%","2026-07-01","Senior unsecured","DISH DBS subsidiaries","Indenture covenants","U.S. Bank Trust (unsecured trustee per 8-K)","","FV 98.9 at 31 Dec 2025","2025-12-31",SATS_Q2,"VERIFIED"),
 ("DISH DBS 26-90627","DISH DBS Corp","Senior Secured Notes",2750.0,"5.25%","2026-12-01","Secured","DISH DBS subsidiaries","","WSFS trustee; U.S. Bank Trust collateral agent (8-K)","","FV 97.2","2025-12-31",SATS_8K,"VERIFIED"),
 ("DISH DBS 26-90627","DISH DBS Corp","Senior Notes",1000.0,"7.375%","2028-07-01","Senior unsecured","","","U.S. Bank Trust","","FV 97.0","2025-12-31",SATS_Q2,"VERIFIED"),
 ("DISH DBS 26-90627","DISH DBS Corp","Senior Secured Notes",2500.0,"5.75%","2028-12-01","Secured","","","WSFS / U.S. Bank Trust","","FV 98.0","2025-12-31",SATS_8K,"VERIFIED"),
 ("DISH DBS 26-90627","DISH DBS Corp","Senior Notes",1500.0,"5.125%","2029-06-01","Senior unsecured","","","U.S. Bank Trust","","FV 88.8","2025-12-31",SATS_Q2,"VERIFIED"),
 ("DISH DBS 26-90627","DBS SubscriberCo","Term Loan",1608.4,"n/d","2029","Secured (SubscriberCo)","","","n/d","","","2025-12-31",SATS_Q2,"CORRECTED (was $1.8bn at issue; $1.608bn at 31 Dec 2025)"),
 ("DISH DBS 26-90627","DBS SubscriberCo","Mandatorily redeemable preferred",178.7,"n/d","2029","Preferred","","","","","","2025-12-31",SATS_Q2,"VERIFIED"),
 ("DISH DBS 26-90627","DISH DBS Corp","Plan outcome: debt reduced ~$4.35bn; effective 2026-10-01",-4350.0,"","","","","","","","","2026-10-01",SATS_8K,"VERIFIED"),
 ("EchoStar parent","EchoStar Corp","Senior Secured Notes",5506.0,"10.75%","2029","Secured","","","","","FV 108.1","2026-06-30",SATS_Q2,"VERIFIED; to be repaid from AT&T proceeds (closing 28 Jul 2026)"),
 ("EchoStar parent","EchoStar Corp","Convertible Secured Notes (CUSIP 278768AB2)",1942.6,"3.875%","2030","Secured","","","","13F: Apollo $969m, Whitebox $319m, Monarch $187m, Sculptor $180m, Silver Point $128m","FV 311","2026-06-30",SATS_Q2,"VERIFIED"),
 ("EchoStar parent","EchoStar Corp","Senior Secured Notes",2372.7,"6.75%","2030","Secured","","","","","FV 101.7","2026-06-30",SATS_Q2,"VERIFIED; to be repaid from AT&T proceeds"),
 ("EchoStar parent","DISH Network","Senior Secured Notes",3500.0,"11.75%","2027-11-15","Secured","","","","","","2026-06-30",SATS_Q2,"VERIFIED; redeemed in full 28 Jul 2026"),
 ("EchoStar parent","DISH Network","Convertible Notes",45.2,"3.375%","2026-08-15","Unsecured","","","","","","2026-06-30",SATS_Q2,"VERIFIED"),
 ("Branicks","Branicks Group AG","Bond 2026 -> extended",405.0,"n/d","2030-09-30","Senior unsecured","","Creditor vote 99%","n/d","","","2026-10-20","https://branicks.com/en/branicks-group-ag-creditors-vote-to-extend-maturity-and-pave-the-way-for-restructuring/","VERIFIED (EUR375m; USD at ~1.08)"),
 ("Branicks","Branicks Group AG","Additional tranche",237.6,"n/d","2028-09-30","n/d","","","","","","2026-10-20","https://branicks.com/en/branicks-group-ag-creditors-vote-to-extend-maturity-and-pave-the-way-for-restructuring/","VERIFIED (EUR220m)"),
 ("BayWa","Kronos EKS AG & Co. KG","Hybrid bond DE000A351PD9 (BayWa-guaranteed)",108.0,"n/d","perpetual","Subordinated hybrid","BayWa AG","98% haircut vote FAILED 12-14 Oct 2026","n/d","","","2026-10-16","https://www.baywa.com/","CORRECTED"),
 ("Agile","Agile Group Holdings","Offshore debt (notes + syndicated loans)",5183.0,"various","various","Senior / loans","Subsidiary guarantors","RSA with 61.5% of syndicated-loan lenders; UK + HK schemes","n/d","","","2026-10-05","https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1005/2026100500001.pdf","CORRECTED (5.183bn)"),
]
def lien(identifier):
    s = identifier.lower()
    for k, v in (("second lien", "2nd lien"), ("first lien", "1st lien"), ("senior secured", "1st lien (senior secured)"), ("subordinated", "Subordinated"), ("revolv", "Revolver"), ("equity", "Equity"), ("preferred", "Preferred")):
        if k in s: return v
    return "n/d"
PRIVATE = ["medallia", "covercraft", "pluralsight", "cornerstone ondemand", "odevo", "loparex", "convey health", "scaled agile", "national dentex"]
def private_rows(db):
    c = sqlite3.connect(db, timeout=120); out = []
    for b in PRIVATE:
        for bdc, bor, ident, par, fv, mark, url in c.execute("select bdc,borrower,identifier,par,fv,mark,source_url from bdc_marks where lower(borrower) like ? and period='2026-06-30' and par>0 order by bdc", (f"%{b}%",)):
            out.append(dict(zip(F, [b.title(), bor, ident.split("|")[1].strip() if "|" in ident else ident, round(par / 1e6, 2), "n/d (SOI)", "n/d (SOI)", lien(ident), "n/d", "n/d (private credit agreement)", "n/d", bdc, mark, "2026-06-30", url, "VERIFIED (BDC 10-Q SOI)"])))
    return out
def build(db, csv_path):
    rows = [dict(zip(F, r)) for r in PUBLIC] + private_rows(db)
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, F); w.writeheader(); w.writerows(rows)
    c = sqlite3.connect(db, timeout=120); c.execute("drop table if exists cap_structures_top15")
    c.execute(f"create table cap_structures_top15({','.join(F)})"); c.executemany(f"insert into cap_structures_top15 values({','.join('?'*len(F))})", [[r[k] for k in F] for r in rows]); c.commit()
    return rows
if __name__ == "__main__":
    r = build("/workspace/triage_os_data/triage.db", "/workspace/triage_os_data/cap_structures_top15.csv")
    print(len(r), len({x["situation"] for x in r}))
