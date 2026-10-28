import csv, os, tempfile, unittest
import buyers

class T(unittest.TestCase):
    def test_build(self):
        out = os.path.join(tempfile.mkdtemp(), "b.csv"); rows = buyers.build(None, out)
        self.assertGreaterEqual(len(rows), 140)
        self.assertEqual(len({r["firm"] for r in rows}), len(rows))
        self.assertTrue(all(r["type"] in buyers.TYPES and r["evidence_url"].startswith("https://") for r in rows))
        self.assertEqual([r["rank"] for r in rows], list(range(1, len(rows)+1)))
        self.assertEqual(len(list(csv.DictReader(open(out)))), len(rows))
    def test_evidence_rerank(self):
        import sqlite3
        d = tempfile.mkdtemp(); db = os.path.join(d, "t.db"); c = sqlite3.connect(db)
        c.execute("create table f13_filers (accession, filer, filer_norm, period, value_total real, entries int)")
        c.execute("create table f13_holdings (accession, filer, issuer_key, issuer, cusip, value real, shares real, putcall, period, source_url, status)")
        c.execute("insert into f13_filers values ('a','Whitebox Advisors LLC','whitebox',  'Q', 5e9, 10)")
        c.execute("insert into f13_holdings values ('a','WHITEBOX ADVISORS LLC','echostar','E','c',3.2e8,1,'','Q','https://www.sec.gov/x','')")
        c.commit(); rows = buyers.build(db, os.path.join(d, "b.csv"), {"apollo.com": 75})
        top = rows[0]
        self.assertEqual(top["firm"], "Whitebox Advisors"); self.assertIn("echostar", top["db_match"]); self.assertEqual(top["evidence_url"], "https://www.sec.gov/x")
        ap = next(r for r in rows if r["firm"] == "Apollo Global Management")
        self.assertIn("75", ap["data_buying_evidence"])
        self.assertEqual(len({(r["score"], r["firm"]) for r in rows}), len(rows))

if __name__ == "__main__": unittest.main()
