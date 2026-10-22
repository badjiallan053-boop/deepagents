"""Curated non-US special situations (public sources, all UNVERIFIED).

Loads into table world_situations in triage.db. Read-only research; no individuals named.
"""
import argparse, sqlite3

SITUATIONS = [
 # (key, country, entity, type, stage, next_date, score, url, src_date, note)
 ("baywa_hybrid","DE","BayWa / Kronos EKS EUR100m hybrid","bond restructuring","vote failed","2026-11-30",88,"https://www.boersen-zeitung.de/unternehmen-branchen/baywa-scheitert-vorerst-mit-restrukturierung-von-anleihe","2026-10-21","98% haircut proposal failed vote; second vote/StaRUG route likely"),
 ("branicks","DE","Branicks Group EUR400m bond","SchVG extension","creditor vote passed","2027-03-31",84,"https://branicks.com/en/branicks-group-ag-creditors-vote-to-extend-maturity-and-pave-the-way-for-restructuring/","2026-10-20","99% creditor approval; shareholder vote risk flagged with insolvency warning"),
 ("zhenro_hk","HK","Zhenro Properties HK subsidiary","winding-up petition","hearing","2026-11-09",82,"https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1020/2026102000255.pdf","2026-10-20","Petition hearing 9 Nov 2026"),
 ("agile","HK/UK","Agile Group USD5.1bn offshore debt","scheme/plan","parallel UK+HK proceedings",None,80,"https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1005/2026100500001.pdf","2026-10-05","Parallel UK plan and HK scheme"),
 ("mm2_asia","SG","MM2 Asia","scheme of arrangement","creditor meetings","2026-11-04",78,"https://www.sgpbusiness.com/","2026-10-15","Scheme creditor meetings 4 Nov"),
 ("kong_hwee","SG","Kong Hwee Iron Works","judicial management","application","2026-11-16",72,"https://www.sgpbusiness.com/","2026-10-15","JM application hearing 16 Nov"),
 ("agwest","CA","AgWest Ltd.","CCAA","monitor A&M",None,74,"https://ised-isde.canada.ca/site/office-superintendent-bankruptcy/en/ccaa-records-2021-to-present","2026-10-13","CCAA hearing 13 Oct; sale process expected"),
 ("rath","AT","Rath AG","lender agreement","amend & extend","2029-12-31",70,"https://live.deutsche-boerse.com/","2026-10-16","Financing extended to 2029; Meissen/Budapest closures"),
 ("zentoshin","JP","Zentoshin","bankruptcy/fraud","filed",None,76,"https://www.tsr-net.co.jp/news/","2026-10-08","JPY115.2bn liabilities, 60+ bank creditors, accounting fraud"),
 ("toshin_hd","JP","Toshin Holdings","corporate reorganisation","filed",None,68,"https://www.tsr-net.co.jp/news/","2026-10-08","JPY16.0bn liabilities"),
 ("gaia_funding","JP","Gaia Funding","bankruptcy","filed",None,62,"https://www.tsr-net.co.jp/news/","2026-10-21","JPY5.76bn; lending-fund investors exposed"),
 ("qpm","AU","QPM Energy","voluntary administration + receivership","sale process",None,72,"https://www.asx.com.au/markets/trade-our-cash-market/announcements","2026-07-07","Receivers appointed by secured lenders"),
 ("finexia_sb","AU","Finexia / Shared Beginnings","voluntary administration","appointed",None,58,"https://www.asx.com.au/markets/trade-our-cash-market/announcements","2026-10-19","Subsidiary in VA"),
 ("tg_jones","UK","TG Jones (ex-WHSmith high street)","Part 26A plan","sanctioned",None,60,"https://www.mills-reeve.com/publications/the-tg-jones-restructuring-plan-is-approved/","2026-10-19","[2026] EWHC 2079 (Ch); landlord compromise; watch post-plan liquidity"),
 ("iguanas","UK","Iguanas","Part 26A plan","sanctioned (cram-down)",None,55,"https://www.lexisnexis.co.uk/","2026-10-15","Cross-class cram-down"),
 ("lvgem","HK","LVGEM (China) Real Estate","scheme + petition","RSA signed","2027-04-06",66,"https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1005/2026100500079.pdf","2026-10-05","Petition adjourned to 6 Apr 2027"),
 ("redsun","HK","Redsun Properties","winding-up petition","adjourned","2027-04-12",60,"https://www.hkexnews.hk/","2026-10-01","Petition adjourned to 12 Apr 2027"),
 ("china_sce","HK","China SCE","offshore restructuring","effective date",None,57,"https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1021/2026102100751.pdf","2026-10-21","Post-reorg new notes trading"),
 ("maxeda","NL","Maxeda DIY","WHOA (possible)","negotiation",None,64,"https://www.octus.com/","2026-10-01","WHOA likely absent consensual deal"),
 ("vpower","HK","VPower Group","restructuring","update",None,52,"https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1021/2026102100581.pdf","2026-10-21","Restructuring update announcement"),
 ("toysrus_jp","JP","Toys R Us Japan","civil rehabilitation","commencement order",None,74,"https://www.tdb.co.jp/report/bankruptcy/flash/5266/","2026-10-06","JPY13.2bn liabilities; largest toy-retailer failure; sponsor search"),
 ("infinities_tech","HK","Infinities Tech (01961)","winding-up petition","petition filed",None,56,"https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1021/2026102100332.pdf","2026-10-21","Fresh petition"),
]

COLS = "key,country,entity,type,stage,next_date,score,url,src_date,note"

def store(db):
    con = sqlite3.connect(db)
    con.execute(f"create table if not exists world_situations ({COLS}, status default 'UNVERIFIED', primary key(key))")
    con.executemany(f"insert or replace into world_situations ({COLS}) values (?,?,?,?,?,?,?,?,?,?)", SITUATIONS)
    con.commit()
    n = con.execute("select count(*) from world_situations").fetchone()[0]
    con.close()
    return n

def top(db, n=20):
    con = sqlite3.connect(db)
    rows = con.execute("select key,country,entity,stage,next_date,score,url,src_date from world_situations order by score desc limit ?", (n,)).fetchall()
    con.close()
    return rows

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True)
    a = ap.parse_args(); print(store(a.db), "situations")
