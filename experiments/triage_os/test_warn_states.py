import os, sqlite3, tempfile, unittest, datetime as dt
import openpyxl, warn_states as w
MD = """| **Aetos Systems, Inc.**  <br>Space Commerce Way  <br>  <br>MERRITT ISLAND, FL, 32953 | 10-16-26 | 12-01-26  <br>_thru_  <br>12-31-26 | 126 | Professional, Scientific, and Technical Services |     |
| **Grunt Style, LLC**  <br>4267 Legendary Drive  <br>  <br>DESTIN, FL, 32541 | 10-02-26 | 11-30-26  <br>_thru_  <br>11-30-26 | 8   | Retail Trade |     |"""
def xl(rows):
    p = tempfile.mktemp(suffix=".xlsx"); wb = openpyxl.Workbook(); ws = wb.active
    for r in rows: ws.append(r)
    wb.save(p); return p
class T(unittest.TestCase):
    def test_fl(self):
        r = w.parse_fl_markdown(MD)
        self.assertEqual(len(r), 2); self.assertEqual(r[0]["employees"], 126); self.assertEqual(r[0]["notice_date"], "2026-10-16"); self.assertEqual(r[0]["city"], "Merritt Island")
    def test_nj(self):
        p = xl([["Company","City","Month Posted","Effective Date","Workforce Affected"],["Acme","Newark","March",dt.datetime(2026,5,1),"1,200"]])
        r = w.parse_nj(p)[0]; self.assertEqual((r["notice_date"], r["effective_date"], r["employees"]), ("2026-03-01","2026-05-01",1200))
    def test_il(self):
        p = xl([["Location Name","Location City","Initial Date Reported","Impact Date","Expected Layoff","Revised Layoff","Causes","Reason"],["X Co","Cary",dt.datetime(2026,1,2),None,100,90,"Bankruptcy","Plant Closure"]])
        r = w.parse_il(p)[0]; self.assertEqual(r["employees"], 90); self.assertIn("Bankruptcy", r["reason"])
    def test_tx(self):
        p = xl([["NOTICE_DATE","JOB_SITE_NAME","CITY_NAME","LAYOFF_DATE","TOTAL_LAYOFF_NUMBER"],["1/5/2026","Y Inc","Austin","3/1/2026",50]])
        r = w.parse_tx(p)[0]; self.assertEqual((r["company"], r["notice_date"], r["employees"]), ("Y Inc","2026-01-05",50))
    def test_ingest_dedup(self):
        db = tempfile.mktemp(suffix=".db"); rows = w.parse_fl_markdown(MD)
        self.assertEqual(w.ingest(rows, db), 2); self.assertEqual(w.ingest(rows, db), 0)
if __name__ == "__main__": unittest.main()
