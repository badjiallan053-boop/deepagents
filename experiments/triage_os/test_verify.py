import sqlite3, tempfile, unittest
import verify as v
class T(unittest.TestCase):
    def test_token(self):
        self.assertEqual(v.check_url("x", ["4.35 billion", "October 1"], fetch=lambda u: "reduced by approximately $4.35 billion on October 1, 2026"), ("OK", ""))
        self.assertEqual(v.check_url("x", ["186%"], fetch=lambda u: "coverage 150%")[0], "MISSING")
        def boom(u): raise IOError("403")
        self.assertEqual(v.check_url("x", ["a"], fetch=boom)[0], "ERROR")
    def test_db(self):
        db = tempfile.mktemp(suffix=".db"); c = sqlite3.connect(db)
        c.execute("create table f13_holdings(accession,filer,issuer_key,issuer,cusip,value,shares,putcall,period,source_url,status)")
        c.execute("insert into f13_holdings values('a','F','echostar','ECHOSTAR','x',100e6,1,'','2026Q2','u','')")
        c.execute("create table bdc_marks(bdc,borrower,borrower_key,identifier,period,par,cost,fv,mark,source_url,status)")
        c.execute("insert into bdc_marks values('NCDL','Covercraft','k','i','2026-06-30',1,1,1,7.6,'u','')"); c.commit()
        self.assertEqual(v.f13_total(db, "F"), 100.0); self.assertEqual(v.mark_range(db, "covercraft"), (7.6, 7.6))
        rows = [dict(id="X1", artifact="a", claim="c", status="VERIFIED", url="u", method="m")]
        self.assertEqual(v.save(rows, db), {"VERIFIED": 1}); self.assertIn("**VERIFIED**", v.to_markdown(rows))
if __name__ == "__main__": unittest.main()
