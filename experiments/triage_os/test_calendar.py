import sqlite3, tempfile, os, unittest
from item_check import check_items
import claims_agents as ca

CUMULUS = "On October 16, 2026 (the Effective Date), the conditions to the effectiveness of the Plan were satisfied or waived, the Plan became effective and the Company Parties emerged from the Chapter 11 Cases."
LESLIES = "On September 30, 2026 (the “Petition Date”), Leslie's, Inc. filed voluntary petitions under chapter 11. An event of default has occurred and the obligations were accelerated."
CCO = "On October 14, 2026 the Merger was consummated. 3.3 no Default or Event of Default shall exist or result therefrom; change of control."
NOTICE = ("The Preliminary Bid Deadline is September 29, 2026, at 4:00 p.m. and the Bid Deadline is November 9, 2026, at 4:00 p.m. "
          "Sale Hearing: November 18, 2026, at 10:00 a.m. Sale Objection Deadline: November 2, 2026. Auction on November 12, 2026.")


class ItemCheck(unittest.TestCase):
    def test_emergence_is_false_positive(self):
        self.assertEqual(check_items(["1.03"], CUMULUS)[0], "false_positive")

    def test_real_filing_confirmed(self):
        self.assertEqual(check_items(["1.03", "2.04"], LESLIES)[0], "confirmed")

    def test_cco_no_default(self):
        self.assertEqual(check_items(["2.04"], CCO)[0], "false_positive")

    def test_no_text(self):
        self.assertEqual(check_items(["1.03"], "")[0], "unverified")


class Calendar(unittest.TestCase):
    def test_extract_skips_preliminary(self):
        d = ca.extract_dates(NOTICE)
        self.assertEqual(d["bid_deadline"], "2026-11-09")
        self.assertEqual(d["sale_hearing"], "2026-11-18")
        self.assertEqual(d["auction"], "2026-11-12")
        self.assertEqual(d["objection_deadline"], "2026-11-02")

    def test_upsert_requires_source_and_detects_agent(self):
        with tempfile.TemporaryDirectory() as t:
            con = ca.connect(os.path.join(t, "c.db"))
            with self.assertRaises(ValueError):
                ca.upsert(con, {"case_name": "x", "case_no": "1"})
            r = ca.upsert(con, {"case_name": "x", "case_no": "1", "source_url": "https://cases.stretto.com/a"})
            self.assertEqual(r["agent"], "stretto")
            rows = ca.export(con, os.path.join(t, "o.csv"))
            self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
