import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("backtest", Path(__file__).with_name("backtest.py"))
bt = importlib.util.module_from_spec(spec); spec.loader.exec_module(bt)
FIX = Path(__file__).with_name("fixtures")

def rd():
    return json.loads((FIX / "courtlistener_rd_sale_orders.json").read_text())

META = {"71457446": {"caseName": "575 RIVER ROAD EDGEWATER LLC", "dateFiled": "2025-09-25", "chapter": "11", "court_id": "njb",
                     "docket_absolute_url": "/docket/71457446/575-river-road-edgewater-llc/"}}

def cl_fetch(url, headers):
    if "type=rd" in url:
        return rd()
    for k, m in META.items():
        if k in url and "docket_id" in url:
            return {"results": [dict(m, docket_id=int(k))]}
    return {"results": []}

class GroundTruth(unittest.TestCase):
    def test_sale_order_filter(self):
        self.assertTrue(bt.is_sale_order("Order Approving the Sale of Assets Free and Clear"))
        self.assertTrue(bt.is_sale_order("Agreed Order Granting Motion of Debtor for an Order Approving the Sale"))
        self.assertFalse(bt.is_sale_order("Objection to the Debtors Motion for Entry of an Order (A) Approving Bidding Procedures"))
        self.assertFalse(bt.is_sale_order("Transmittal of Record on Appeal (related document:2878 ORDER APPROVING THE SALE"))
        self.assertFalse(bt.is_sale_order("Notice of Filing of Proposed Purchase and Sale Agreement"))

    def test_group_keeps_earliest_order_per_docket(self):
        g = bt.group_sale_orders(rd()["results"])
        self.assertEqual(g["70147736"]["sale_order_date"], "2025-10-15")
        self.assertNotIn("72236458", g)  # objection only

    def test_collect_requires_docket_meta(self):
        cases = bt.collect_sale_orders("2024-10-01", "2026-04-30", fetch=cl_fetch, max_pages=1)
        self.assertEqual([c["docket_id"] for c in cases], ["71457446"])
        self.assertEqual(cases[0]["petition_date"], "2025-09-25")

class Replay(unittest.TestCase):
    def test_lead_time_and_hit_rate(self):
        cases = [dict(docket_id="1", case_name="Acme LLC", petition_date="2025-01-01", sale_order_date="2025-03-02", chapter="11", docket_meta={}),
                 dict(docket_id="2", case_name="Bob Smith", petition_date="2025-01-01", sale_order_date="2025-02-01", chapter=None, docket_meta={})]
        sec = lambda c: {"date": "2024-12-01", "items": ["1.03"]} if c["docket_id"] == "1" else None
        rows = bt.replay(cases, sec)
        self.assertEqual(rows[0]["lead_days"], 91)       # SEC flag before petition
        self.assertEqual(rows[0]["sec_lead_days"], 91)
        self.assertIsNone(rows[1]["first_flag"])          # no chapter, no SEC -> missed
        s = bt.summarize(rows)
        self.assertEqual(s["hit_rate_any"], 0.5)
        self.assertEqual(s["hit_rate_sec"], 0.5)
        self.assertEqual(s["median_lead_days_any"], 91)

    def test_sec_first_flag_requires_name_match_and_score(self):
        hits = {"hits": {"hits": [
            {"_source": {"display_names": ["Acme Corp  (ACM)  (CIK 1)"], "file_date": "2025-02-01", "items": ["1.03"]}},
            {"_source": {"display_names": ["Acme Corp  (ACM)  (CIK 1)"], "file_date": "2025-01-01", "items": ["5.02"]}},
            {"_source": {"display_names": ["Other Co  (O)  (CIK 2)"], "file_date": "2024-06-01", "items": ["1.03"]}}]}}
        f = bt.sec_first_flag("Acme Corp.", "2025-06-01", lambda u, h: hits, "T t@example.com")
        self.assertEqual(f["date"], "2025-02-01")

class FalsePositives(unittest.TestCase):
    def test_fp_rate(self):
        def fetch(url, headers):
            if "Broken" in url:
                raise OSError("timeout")
            if "type=rd" in url:
                return {"results": [{"docket_id": 5, "description": "Order Approving the Sale of substantially all assets"},
                                    {"docket_id": 6, "description": "Objection to sale"}]}
            return {"results": [{"docket_id": 5, "caseName": "Acme, Inc."}]}
        flags = [{"entity": "Acme Inc", "date": "2025-01-01"}, {"entity": "Zed Inc", "date": "2025-01-01"},
                 {"entity": "Broken Inc", "date": "2025-01-01"}]
        orig = bt.sale_order_names
        bt_batch = lambda names, a, b, f: orig(names, a, b, f, batch=1)
        bt.sale_order_names = bt_batch
        try:
            rows, m = bt.false_positive_rate(flags, fetch)
        finally:
            bt.sale_order_names = orig
        self.assertEqual(m["n_checked"], 2)
        self.assertEqual(m["fp_rate_no_363"], 0.5)

class Labels(unittest.TestCase):
    def test_label_sec(self):
        self.assertEqual(bt.label_sec(["1.03"], "the Company filed voluntary petitions under chapter 11")[0], "true_distress")
        self.assertEqual(bt.label_sec(["1.03"], "the Company emerged from chapter 11; the plan became effective")[0], "false_positive")
        self.assertEqual(bt.label_sec(["3.01"], "Nasdaq notified the Company it did not meet the minimum bid price requirement")[0], "unclear")
        self.assertEqual(bt.label_sec(["3.01"], "in connection with the merger the Company will voluntarily delist")[0], "false_positive")
        self.assertEqual(bt.label_sec(["3.01"], "substantial doubt about ability to continue as a going concern")[0], "true_distress")
        self.assertEqual(bt.label_sec(["2.06"], "")[0], "unclear")

    def test_label_court(self):
        self.assertEqual(bt.label_court({"caseName": "BNG Industries LLC", "chapter": "11"})[0], "true_distress")
        self.assertEqual(bt.label_court({"caseName": "Victoria A Campbell", "chapter": "11"})[0], "false_positive")
        self.assertEqual(bt.label_court({"caseName": "SEC v. Doe", "chapter": None})[0], "unclear")

    def test_label_all_and_precision(self):
        desk = bt.desk
        with tempfile.TemporaryDirectory() as d, desk.connect(Path(d) / "t.db") as con:
            desk.store(con, "sec", "a1", "X 8-K", "https://www.sec.gov/a", "2026-10-01", {"entity": "X Inc", "cik": "1", "items": ["1.03"]})
            desk.store(con, "sec", "a2", "Y 8-K", "https://www.sec.gov/b", "2026-10-01", {"entity": "Y Inc", "cik": "2", "items": ["3.01"]})
            desk.store(con, "courtlistener", "9", "Jane Roe", "https://www.courtlistener.com/docket/9/", "2026-10-01", {"caseName": "Jane Roe", "chapter": "11"})
            texts = {"https://www.sec.gov/a": "<p>filed voluntary petitions under Chapter 11</p>",
                     "https://www.sec.gov/b": "<p>minimum bid price requirement</p>"}
            p = bt.label_all(con, lambda u: texts[u])
            self.assertEqual(p["ALL"]["n"], 3)
            self.assertEqual(p["ALL"]["precision_decided"], 0.5)
            self.assertEqual(p["sec_1.03"]["precision_decided"], 1.0)
            self.assertEqual(con.execute("select count(*) from labels").fetchone()[0], 3)

if __name__ == "__main__":
    unittest.main()
