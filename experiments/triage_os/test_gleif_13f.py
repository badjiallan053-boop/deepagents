import os, sqlite3, tempfile, unittest
import gleif, ext13f

class T(unittest.TestCase):
    def test_same_entity(self):
        self.assertTrue(gleif.same_entity("Odevo AB", "Odevo AB"))
        self.assertTrue(gleif.same_entity("Branicks Group", "BRANICKS Group AG"))
        self.assertFalse(gleif.same_entity("LVGEM", "LEGEM"))
        self.assertFalse(gleif.same_entity("Medallia", "MEDALIA"))
    def test_run_with_fake_fetch(self):
        def fetch(url):
            if "fuzzycompletions" in url: return {"data": [{"attributes": {"value": "ODEVO AB"}, "relationships": {"lei-records": {"data": {"id": "L1"}}}}]}
            if url.endswith("direct-parent"): return {"data": {"id": "P1", "attributes": {"entity": {"legalName": {"name": "Parent AB"}, "legalAddress": {"country": "SE"}}}}}
            return {}
        db = os.path.join(tempfile.mkdtemp(), "t.db")
        self.assertEqual(gleif.run(db, ["Odevo AB"], fetch=fetch, pause=0), 1)
        self.assertEqual(sqlite3.connect(db).execute("select dst from holdings_graph").fetchone()[0], "Parent AB")
    def test_13f_norm_and_load(self):
        self.assertEqual(ext13f.norm_firm("Silver Point Capital L.P."), "silver point")
        d = tempfile.mkdtemp()
        open(f"{d}/COVERPAGE.tsv","w").write("ACCESSION_NUMBER\tFILINGMANAGER_NAME\nA1\tWhitebox Advisors LLC\n")
        open(f"{d}/SUMMARYPAGE.tsv","w").write("ACCESSION_NUMBER\tTABLEVALUETOTAL\tTABLEENTRYTOTAL\nA1\t1000\t2\n")
        open(f"{d}/SUBMISSION.tsv","w").write("ACCESSION_NUMBER\tCIK\nA1\t0000123\n")
        open(f"{d}/INFOTABLE.tsv","w").write("ACCESSION_NUMBER\tNAMEOFISSUER\tCUSIP\tVALUE\tSSHPRNAMT\tPUTCALL\nA1\tECHOSTAR CORP\t278768106\t500\t10\t\nA1\tAPPLE INC\t037833100\t500\t10\t\n")
        db = os.path.join(d, "t.db"); self.assertEqual(ext13f.load(db, d, "Q"), 1)
        c = sqlite3.connect(db)
        self.assertEqual(ext13f.firm_lookup(c, "Whitebox Advisors")[0], "Whitebox Advisors LLC")
        self.assertIn("/edgar/data/123/A1/", c.execute("select source_url from f13_holdings").fetchone()[0])
if __name__ == "__main__": unittest.main()
