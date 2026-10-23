import csv, json, tempfile, unittest
from pathlib import Path
from archive import build
import capstack, nport

class TestArchive(unittest.TestCase):
    def test_publish_hash_immutable_and_score(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "w.csv"
            p.write_text("rank,score,entity,signal_types,evidence_1\n1,90,Acme Corp,rsa_tsa,x https://sec/a\n")
            site = Path(d) / "site"
            m = build.publish(p, site, 1, "2026-10-22T00:00:00+00:00")
            self.assertEqual(m["snapshots"][0]["sha256"], build.sha256(p))
            build.publish(p, site, 1)                 # idempotent
            p.write_text(p.read_text() + "2,50,Other,x,y\n")
            with self.assertRaises(ValueError):
                build.publish(p, site, 1)             # immutable
            (site / "outcomes.csv").write_text("entity,outcome,outcome_date,source_url\nAcme Corp,Chapter 11,2026-12-01,https://court/x\n")
            res = build.score(site, build.load_manifest(site))
            self.assertEqual(res[0]["lead_days"], 40)
            build.render(site, build.load_manifest(site))
            self.assertIn("1 of 1", (site / "scoring.html").read_text())

class TestCapNport(unittest.TestCase):
    def test_nport_parse_price(self):
        xml = ("<seriesName>Loan Fund</seriesName><repPdDate>2026-07-31</repPdDate><invstOrSec><name>New Fortress Energy Inc</name>"
               "<title>NFE TERM B 10/30/2028</title><cusip>X</cusip><balance>1000000</balance><units>PA</units><valUSD>596000</valUSD>"
               "<assetCat>LON</assetCat><maturityDt>2028-10-30</maturityDt></invstOrSec>"
               "<invstOrSec><name>Other Co</name><title>t</title><balance>1</balance><units>PA</units><valUSD>1</valUSD></invstOrSec>")
        r = nport.parse(xml, r"new fortress", "https://sec/x")
        self.assertEqual(len(r), 1); self.assertEqual(r[0]["price"], 59.6); self.assertEqual(r[0]["period"], "2026-07-31")

    def test_lien(self):
        self.assertEqual(capstack.lien_of("Senior Secured Notes due 2029"), "senior secured")
        self.assertEqual(capstack.lien_of("Term Loan B"), "senior secured")
        self.assertEqual(capstack.member_label("sats:SeniorNotes11.75PercentDue2027Member"), "Senior Notes11.75 % Due2027")

if __name__ == "__main__":
    unittest.main()
