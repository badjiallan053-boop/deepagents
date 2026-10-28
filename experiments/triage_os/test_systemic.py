import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bdc_tenders

class TenderParse(unittest.TestCase):
    T = ("This is the Final Amendment to the Statement. 1. The Offer expired at 11:59 p.m., Eastern Time, on May 29, 2026. "
         "2. 191,782,834 Shares of the Fund were validly tendered and not withdrawn prior to the expiration of the Offer. The Fund accepted for purchase "
         "93,100,272 Shares on a pro rata basis, representing 5% of the Shares of the Fund outstanding. 3. ... in the amount of $2,201,821,426.")
    def test_prorated(self):
        p = bdc_tenders.parse(self.T)
        self.assertEqual(p["tendered_shares"], 191782834); self.assertEqual(p["purchased_shares"], 93100272)
        self.assertEqual(p["expired"], "May 29, 2026"); self.assertTrue(p["prorated"]); self.assertEqual(p["purchase_usd"], 2201821426)
    def test_full_fill(self):
        t = ("Final Amendment. 2. 31,791,045 Shares of the Fund were validly tendered and not withdrawn. The Fund accepted for purchase 100% of the Shares")
        p = bdc_tenders.parse(t); self.assertEqual(p["purchased_shares"], p["tendered_shares"])
    def test_not_final(self):
        self.assertEqual(bdc_tenders.parse("Amendment No. 1 to file a written communication"), {})

if __name__ == "__main__": unittest.main()
