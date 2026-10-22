import os, sqlite3, tempfile, unittest
import holdings_graph as hg

class T(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "t.db"); c = sqlite3.connect(self.db)
        c.execute("create table bdc_marks (bdc,borrower,borrower_key,identifier,period,par,cost,fv,mark,source_url,status)")
        c.executemany("insert into bdc_marks values (?,?,?,?,?,?,?,?,?,?,?)", [
            ("A","X","x","",'2026-06-30',2e6,2e6,1.0e6,50,"u1",""), ("B","X","x","",'2026-06-30',3e6,3e6,2.7e6,90,"u2",""),
            ("A","Y","y","",'2026-06-30',2e6,2e6,1.9e6,95,"u3",""), ("B","Y","y","",'2026-06-30',2e6,2e6,1.9e6,95,"u4","")])
        c.execute("create table holders (issuer_key,holder,holder_type,instrument,cusip,units,balance,value_usd,price,maturity,coupon,period,source_url,status)")
        c.executemany("insert into holders values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            ("i","F","","TL","c1","",0,1e6,60,"","","p","u",""), ("i","F","","Notes","c2","",0,1e6,80,"","","p","u","")])
        c.execute("create table cmbs_loans (trust,propertyName,propertyCity,reportPeriodEndActualBalanceAmount,stress_score,mostRecentSpecialServicerTransferDate,source_url)")
        c.executemany("insert into cmbs_loans values (?,?,?,?,?,?,?)", [("T1","Mall","Fresno","5e7",40,"2026-09-01","u"),("T2","Mall ","Fresno","5e7",40,"","u")])
        c.commit(); c.close()
    def test_f13_and_preserve_lei(self):
        c = sqlite3.connect(self.db)
        c.execute("create table f13_holdings (accession, filer, issuer_key, issuer, cusip, value real, shares real, putcall, period, source_url, status)")
        c.executemany("insert into f13_holdings values (?,?,?,?,?,?,?,?,?,?,?)", [("a","W","echostar","E","c",5e6,1,"","Q","u",""),("b","W","echostar","E","c",3e6,1,"","Q","u",""),("c","S","echostar","E","c",5e5,1,"","Q","u","")])
        c.execute(hg.DDL); c.execute("insert into holdings_graph (edge_type,src,dst) values ('lei_parent','x','y')"); c.commit()
        hg.build(self.db)
        f = c.execute("select src,weight from holdings_graph where edge_type='f13_holder'").fetchall()
        self.assertEqual(f, [("W", 5.0)])
        self.assertEqual(c.execute("select count(*) from holdings_graph where edge_type='lei_parent'").fetchone()[0], 1)

    def test_build(self):
        hg.build(self.db); c = sqlite3.connect(self.db)
        types = {r[0]: r[1] for r in c.execute("select edge_type,count(*) from holdings_graph group by 1")}
        self.assertEqual(types, {"mark_dispersion":1, "crossholder":1, "forced_seller":1, "cre_pari_passu":1})
        gap = c.execute("select weight from holdings_graph where edge_type='mark_dispersion'").fetchone()[0]
        self.assertEqual(gap, 40.0)
if __name__ == "__main__": unittest.main()
