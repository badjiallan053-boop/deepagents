import sqlite3, unittest
import warn_apify

class T(unittest.TestCase):
    def test_both_shapes_and_dedupe(self):
        a = {"source_state": "NY", "employer_name": "Acme LLC", "notice_date": "2026-09-01", "affected_workers": 120,
             "employer_address": "1 Main", "source_url": "https://dol.ny.gov/warn-dashboard"}
        b = {"companyName": "Beta Inc", "noticeDate": "2026-08-01", "employeesAffected": 5,
             "location": {"state": "CA", "address": "2 Elm"}, "sourceUrl": "https://edd.ca.gov/x.xlsx"}
        con = sqlite3.connect(":memory:")
        self.assertEqual(warn_apify.store(con, [a, b, {"companyName": ""}], "t"), 2)
        self.assertEqual(warn_apify.store(con, [a], "t"), 0)
        self.assertEqual(con.execute("select state, employees from warn_notices where company='Acme LLC'").fetchone(), ("NY", 120))

if __name__ == "__main__":
    unittest.main()
