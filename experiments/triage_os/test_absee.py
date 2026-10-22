import sqlite3, unittest
import absee

XML = """<assetData xmlns="http://www.sec.gov/edgar/document/absee/cmbs/assetdata"><assets>
<assetNumber>1</assetNumber><maturityDate>06-06-2027</maturityDate><paymentStatusLoanCode>0</paymentStatusLoanCode>
<mostRecentSpecialServicerTransferDate>05-01-2026</mostRecentSpecialServicerTransferDate>
<property><propertyName>Hotel X</propertyName><propertyTypeCode>LO</propertyTypeCode>
<mostRecentDebtServiceCoverageNetOperatingIncomePercentage>.4052</mostRecentDebtServiceCoverageNetOperatingIncomePercentage></property>
</assets><assets><assetNumber>2</assetNumber><maturityDate>06-06-2034</maturityDate><paymentStatusLoanCode>0</paymentStatusLoanCode>
<property><mostRecentDebtServiceCoverageNetOperatingIncomePercentage>1.9</mostRecentDebtServiceCoverageNetOperatingIncomePercentage></property></assets></assetData>"""


class T(unittest.TestCase):
    def test_parse_and_stress(self):
        rows = absee.parse(XML, "T", "1", "a", "u", "2026-10-22")
        self.assertEqual(rows[0]["maturityDate"], "2027-06-06")
        self.assertEqual(rows[0]["stress_score"], 70)
        self.assertIn("special servicing", rows[0]["stress_reasons"])
        self.assertEqual(rows[1]["stress_score"], 0)
        con = sqlite3.connect(":memory:")
        self.assertEqual(absee.store(con, rows), 2)





class Rollup(unittest.TestCase):
    def test_trust_rollup(self):
        import sqlite3
        con = sqlite3.connect(":memory:")
        base = {c: "" for c in absee.COLS}
        r1 = dict(base, trust="T", accession="a", assetNumber="1", reportPeriodEndActualBalanceAmount="100",
                  mostRecentSpecialServicerTransferDate="2026-09-01", paymentStatusLoanCode="3")
        r2 = dict(base, trust="T", accession="a", assetNumber="2", reportPeriodEndActualBalanceAmount="300", paymentStatusLoanCode="0")
        absee.store(con, [r1, r2])
        r = absee.trust_rollup(con, asof="2026-10-22")[0]
        self.assertEqual((r["ss_pct"], r["dq_pct"], r["fresh_ss"]), (25.0, 25.0, 1))

if __name__ == "__main__":
    unittest.main()
