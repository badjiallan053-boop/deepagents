import sqlite3, unittest
import bdc, auditor

def ctx(cid, ident, d="2026-06-30"):
    return (f'<xbrli:context id="{cid}"><xbrli:entity><xbrli:segment><xbrldi:typedMember dimension="us-gaap:InvestmentIdentifierAxis">'
            f'<us-gaap:limitedToken.domain>{ident}</us-gaap:limitedToken.domain></xbrldi:typedMember></xbrli:segment></xbrli:entity>'
            f'<xbrli:period><xbrli:instant>{d}</xbrli:instant></xbrli:period></xbrli:context>')
def fact(name, cid, v, scale="3"):
    return f'<ix:nonFraction name="us-gaap:{name}" contextRef="{cid}" scale="{scale}" decimals="-3">{v}</ix:nonFraction>'

DOC = "".join([ctx("c1", "Acme Buyer, LLC | First lien senior secured loan"), ctx("c2", "Acme Buyer, LLC | Common equity"),
               ctx("c3", "Acme Buyer, LLC | First lien senior secured loan", "2025-12-31"),
               ctx("c4", "Acme Buyer, LLC | First lien senior secured revolving loan"),
               fact("InvestmentOwnedAtFairValue", "c1", "7,000"), fact("InvestmentOwnedBalancePrincipalAmount", "c1", "10,000"),
               fact("InvestmentOwnedAtCost", "c1", "9,900"), fact("InvestmentOwnedAtFairValue", "c2", "500"),
               fact("InvestmentOwnedAtCost", "c2", "1,000"), fact("InvestmentOwnedAtFairValue", "c3", "9,500"),
               fact("InvestmentOwnedAtFairValue", "c4", "10"), fact("InvestmentOwnedBalancePrincipalAmount", "c4", "100")])

class TestBDC(unittest.TestCase):
    def test_parse_current_period_debt_only(self):
        rows = bdc.parse(DOC)
        marks = {r["identifier"]: r["mark"] for r in rows}
        self.assertEqual(marks["Acme Buyer, LLC | First lien senior secured loan"], 70.0)
        self.assertNotIn("Acme Buyer, LLC | Common equity", marks)
        self.assertTrue(all(r["period"] == "2026-06-30" for r in rows))

    def test_fx_par_falls_back_to_cost(self):
        self.assertEqual(bdc.fair_mark(90, 1000, 100), 90.0)   # par in SEK, FV/cost in USD
        self.assertEqual(bdc.fair_mark(90, 100, 99), 90.0)

    def test_stress_and_divergence(self):
        con = sqlite3.connect(":memory:")
        bdc.store(con, "AAA", "https://sec/a", bdc.parse(DOC))
        other = DOC.replace(">7,000<", ">9,800<")
        bdc.store(con, "BBB", "https://sec/b", bdc.parse(other))
        s = bdc.stressed(con, min_fv=0)
        self.assertEqual([(a["bdc"], a["mark"]) for a in s], [("AAA", 70.0)])  # revolver ignored
        d = bdc.divergence(con)
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["gap"], 28.0)

    def test_lien_bucket(self):
        self.assertEqual(bdc.lien("X | Second Lien Term Loan"), "junior")
        self.assertEqual(bdc.lien("X | First lien senior secured loan"), "senior")

class TestAuditor(unittest.TestCase):
    def test_classify(self):
        f = auditor.classify_401("On Oct 1 the firm resigned. Its report contained a going concern paragraph. "
                                 "During the period there were no disagreements and no reportable events.")
        self.assertIn("auditor_resigned", f)
        self.assertIn("going_concern_in_prior_reports", f)
        self.assertNotIn("disagreement_mentioned", f)
        self.assertNotIn("reportable_event", f)
        self.assertGreaterEqual(auditor.score(f), 65)

    def test_url_and_store(self):
        hit = {"_id": "0001-26-000006:x.htm", "_source": {"ciks": ["0000000123"], "display_names": ["Foo Inc  (FOO)  (CIK 0000000123)"],
               "form": "8-K", "file_date": "2026-10-06"}}
        self.assertEqual(auditor.filing_url(hit), "https://www.sec.gov/Archives/edgar/data/123/000126000006/x.htm")
        con = sqlite3.connect(":memory:")
        auditor.store(con, [auditor.row(hit, "auditor_change", ["auditor_resigned"])])
        self.assertEqual(con.execute("select score from auditor_flags").fetchone()[0], 40)

if __name__ == "__main__":
    unittest.main()
