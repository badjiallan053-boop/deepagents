import unittest, capstruct as c
class T(unittest.TestCase):
    def test_lien(self):
        self.assertEqual(c.lien("X | Second lien senior secured loan"), "2nd lien")
        self.assertEqual(c.lien("X | First lien 1"), "1st lien")
        self.assertEqual(c.lien("X | Subordinated Debt"), "Subordinated")
    def test_public_shape(self):
        self.assertTrue(all(len(r) == len(c.F) for r in c.PUBLIC))
if __name__ == "__main__": unittest.main()
