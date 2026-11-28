import datetime as dt, unittest
import desk, inch11

SUB = {"filings": {"recent": {"form": ["8-K", "8-K"], "filingDate": ["2026-07-01", "2020-01-01"], "items": ["1.03,9.01", "1.03"],
       "accessionNumber": ["0001-26-000001", "0001-20-1"], "primaryDocument": ["a.htm", "b.htm"]}}}
FACTS = {"facts": {"us-gaap": {"LiabilitiesSubjectToCompromise": {"units": {"USD": [{"val": 5e9, "end": "2026-06-30", "accn": "0001-26-2"}]}}}}}

def fake(sub, facts):
    def f(url, headers):
        return sub if "submissions" in url else facts
    return f

class T(unittest.TestCase):
    today = dt.date(2026, 10, 22)
    def test_detects_103_and_lstc(self):
        r = inch11.check("5", fake(SUB, FACTS), {}, today=self.today)
        self.assertTrue(r["in_ch11"])
        self.assertEqual({e[0] for e in r["evidence"]}, {"8-K 1.03", "XBRL LiabilitiesSubjectToCompromise"})
    def test_old_filing_ignored_and_clear(self):
        sub = {"filings": {"recent": {"form": ["8-K"], "filingDate": ["2020-01-01"], "items": ["1.03"], "accessionNumber": ["x"], "primaryDocument": ["y"]}}}
        r = inch11.check("5", fake(sub, {"facts": {}}), {}, today=self.today)
        self.assertEqual(r["status"], "clear")
    def test_error_is_unknown_not_clear(self):
        def boom(url, headers): raise OSError("down")
        self.assertTrue(inch11.check("5", boom, {}, today=self.today)["status"].startswith("unknown"))
    def test_filter_drops_filed(self):
        rows = [{"key": "cik:5", "name": "Filed Co"}, {"key": "cik:6", "name": "Clean Co"}, {"key": "bdc:x", "name": "Private"}]
        def f(url, h):
            return (SUB if "CIK0000000005" in url else {"filings": {"recent": {}}}) if "submissions" in url else {"facts": {}}
        kept = inch11.filter_watchlist(rows, f, {}, today=self.today)
        self.assertEqual([k["name"] for k in kept], ["Clean Co", "Private"])

class Scoring(unittest.TestCase):
    def test_301_text_gating(self):
        self.assertEqual(desk.score_sec_items(["3.01"]), 8)
        self.assertLess(desk.score_sec_items(["3.01"], "minimum bid price requirement notice"), 20)
        self.assertEqual(desk.score_sec_items(["3.01"], "transfer its listing to Nasdaq Capital Market"), 0)
        self.assertGreaterEqual(desk.score_sec_items(["3.01"], "Nasdaq determined to delist; trading suspended"), 20)
    def test_ch7_crosses_flag(self):
        self.assertGreaterEqual(desk.score_court_item({"caseName": "X LLC", "chapter": 7}), 20)



class Exclusions(unittest.TestCase):
    def test_exclusion_file(self):
        import tempfile, os, prefiling
        d = tempfile.mkdtemp(); p = os.path.join(d, "x.csv")
        open(p, "w").write("key,reason,source_url,date\ncik:1334978,acquired by Mubadala Capital,https://x,2026-10-14\n")
        self.assertIn("cik:1334978", prefiling.load_exclusions(p))
        self.assertEqual(prefiling.load_exclusions(os.path.join(d, "missing.csv")), {})

if __name__ == "__main__":
    unittest.main()
