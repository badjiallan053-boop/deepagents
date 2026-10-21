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


if __name__ == "__main__":
    unittest.main()
