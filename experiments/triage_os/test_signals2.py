import json, os, sqlite3, tempfile, unittest
import signals2 as s

def db():
    p = os.path.join(tempfile.mkdtemp(), "t.db"); c = sqlite3.connect(p)
    c.execute("create table bdc_marks (bdc,borrower,borrower_key,identifier,period,par,cost,fv,mark,source_url,status)")
    c.executemany("insert into bdc_marks values (?,?,?,?,?,?,?,?,?,?,?)", [
        ("A","X","x","","2026-03-31",2e6,0,1.9e6,0,"https://www.sec.gov/Archives/edgar/data/111/a.htm",""),
        ("B","X","x","","2026-03-31",2e6,0,1.8e6,0,"https://www.sec.gov/Archives/edgar/data/222/b.htm",""),
        ("A","X","x","","2026-06-30",2e6,0,1.6e6,0,"https://www.sec.gov/Archives/edgar/data/111/a.htm",""),
        ("B","X","x","","2026-06-30",2e6,0,1.5e6,0,"https://www.sec.gov/Archives/edgar/data/222/b.htm","")])
    c.commit(); return c

class T(unittest.TestCase):
    def test_coverage(self):
        f = {"facts": {"us-gaap": {"InvestmentCompanySeniorSecurityIndebtednessAssetCoverageRatio": {"units": {"pure": [{"end": "2026-06-30", "val": 1.62, "form": "10-Q"}]}}}}}
        self.assertEqual(s.coverage_from_facts(f)[0], 162.0)
        f2 = {"facts": {"us-gaap": {"StockholdersEquity": {"units": {"USD": [{"end": "2026-06-30", "val": 100, "form": "10-Q"}]}},
                                    "LongTermDebt": {"units": {"USD": [{"end": "2026-06-30", "val": 125, "form": "10-Q"}]}}}}}
        self.assertEqual(s.coverage_from_facts(f2)[0], 180.0)
        c = db(); n = s.bdc_coverage(c, fetch=lambda u: f)
        self.assertEqual(n, 2); self.assertIn("BELOW", c.execute("select detail from signals2").fetchone()[0])
    def test_flows(self):
        x = '<netAssets>1000</netAssets><mon1Flow redemption="80" reinvestment="0" sales="10"/><mon2Flow redemption="0" reinvestment="0" sales="0"/>'
        self.assertAlmostEqual(s.parse_flows(x)["net_flow_pct"], -7.0)
    def test_cross_markdown(self):
        c = db(); r = s.cross_markdown(c)
        self.assertEqual(r["events_total"], 1); self.assertEqual(r["current"], 1)
        self.assertIn("2 BDCs cut", c.execute("select detail from signals2 where signal='cross_markdown'").fetchone()[0])
    def test_event_precision_and_combine(self):
        flags = {"1": {"2020-01-01"}, "2": {"2020-01-01"}}; bk = {"1": {"2020-06-01"}}
        r = s.event_precision(flags, bk); self.assertEqual((r["flagged"], r["ch11_540d"], r["median_lead_days"]), (2, 1, 152))
        self.assertEqual(dict(s.combine({"1": {"2020-01-01"}}, {"1": {"2020-03-01"}, "2": {"2020-01-01"}})), {"1": {"2020-03-01"}})
    def test_tenants_and_distress(self):
        x = "<assets><propertyName>Mall</propertyName><reportPeriodEndActualBalanceAmount>5000000</reportPeriodEndActualBalanceAmount><largestTenant>True Food Kitchen</largestTenant></assets>"
        self.assertEqual(s.tenants(x), [("Mall", "True Food Kitchen", 5e6)])
        c = db(); c.execute("create table cmbs_loans (trust, source_url)"); c.execute("insert into cmbs_loans values ('T1','u')")
        self.assertEqual(s.tenant_distress(c, ["True Food Kitchen"], fetch=lambda u: x), 1)
    def test_form4_cluster_company_level(self):
        rec = {"filings": {"recent": {"form": ["4"] * 6 + ["4"], "filingDate": ["2026-10-01"] * 6 + ["2026-01-01"]}}}
        c = db(); self.assertEqual(s.form4_cluster(c, [("123", "Co")], fetch=lambda u: rec), 1)
        self.assertIn("company-level", c.execute("select detail from signals2").fetchone()[0])
    def test_ch_overdue(self):
        c = db(); s.ch_overdue(c, [("01234567", "Co Ltd")], fetch=lambda u: '<dd id="company-status"> Active </dd> Accounts overdue')
        self.assertEqual(c.execute("select value from signals2").fetchone()[0], 1)
if __name__ == "__main__": unittest.main()
