import unittest, datasets as d
class T(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(d.norm("Covercraft Parent III, Inc."), "covercraft")
        self.assertEqual(d.norm("Loparex Midco B.V."), "loparex")
        self.assertEqual(d.norm("Hughes Satellite Systems Corp"), "hughes satellite systems")
    def test_company_filter(self):
        self.assertTrue(d.is_company("ACME HOLDINGS LTD")); self.assertTrue(d.is_company("Orion House Services (HK) Limited"))
        self.assertFalse(d.is_company("MICHAEL PAPAGEORGE, MR.")); self.assertFalse(d.is_company("BENE MARY D"))
if __name__ == "__main__": unittest.main()
