import sqlite3, unittest
import bdc, fts_signals, prefiling, auditor

class T(unittest.TestCase):
    def test_confirm_context(self):
        self.assertTrue(fts_signals.confirm("entered into a cooperation agreement with holders of term loan lenders", "cooperation_agreement"))
        self.assertFalse(fts_signals.confirm("cooperation agreement with Elliott regarding board of directors nominations", "cooperation_agreement"))
        self.assertTrue(fts_signals.confirm("did not make the interest payment and entered the 30-day grace period", "missed_payment"))

    def test_migration(self):
        con = sqlite3.connect(":memory:")
        r = lambda per, fv: {"identifier": "Acme LLC | First lien term loan", "period": per, "fv": fv, "par": 100.0, "cost": 100.0,
                             "mark": fv, "borrower": "Acme LLC", "borrower_key": bdc.norm("Acme LLC")}
        bdc.store(con, "AAA", "https://sec/q1", [r("2026-03-31", 9e7 * 0 + 90.0)])
        bdc.store(con, "AAA", "https://sec/q2", [r("2026-06-30", 60.0)])
        m = bdc.migration(con, min_drop=10, min_fv=0)
        self.assertEqual((m[0]["mark_before"], m[0]["mark_after"], m[0]["drop"]), (90.0, 60.0, 30.0))

    def test_composite_joins_and_rejects(self):
        con = sqlite3.connect(":memory:")
        fts_signals.ensure(con)
        con.execute("CREATE TABLE debt_size(cik text, entity text, debt_usd real, concept text, period text, source_url text)")
        con.execute("CREATE TABLE signals(source text, raw_json text, url text, event_date text)")
        auditor.store(con, [])
        con.execute("INSERT INTO debt_size VALUES ('5','Bigco Inc',6e9,'LongTermDebt','CY2026Q2I','https://f')")
        fts_signals.store(con, [{"entity": "Bigco Inc (BIG) (CIK 0000000005)", "cik": "5", "form": "8-K", "file_date": "2026-10-01",
            "signal": "forbearance", "weight": 35, "phrase": "x", "url": "https://a"},
            {"entity": "Bigco Inc (BIG) (CIK 0000000005)", "cik": "5", "form": "8-K", "file_date": "2026-10-01",
            "signal": "cooperation_agreement", "weight": 40, "phrase": "y", "url": "https://b"}], "now")
        con.execute("CREATE TABLE fts_verified(source_url text, signal text, confirmed int)")
        con.execute("INSERT INTO fts_verified VALUES ('https://b','cooperation_agreement',0)")
        bdc.store(con, "AAA", "https://sec/q2", [{"identifier": "Bigco, Inc. | First lien term loan", "period": "2026-06-30",
            "fv": 50.0, "par": 100.0, "cost": 100.0, "mark": 50.0, "borrower": "Bigco, Inc.", "borrower_key": bdc.norm("Bigco, Inc.")}])
        rows = prefiling.build(con)
        e = [r for r in rows if r["key"] == "cik:5"][0]
        self.assertEqual(set(e["signals"]), {"forbearance", "lender_mark"})   # rejected coop dropped, BDC mark joined
        self.assertEqual(e["score"], min(100, (35 + 37) * 1.5))

if __name__ == "__main__":
    unittest.main()
