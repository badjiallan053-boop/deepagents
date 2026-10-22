import unittest, claims_calendar as c
class T(unittest.TestCase):
    def test_upcoming_sorted(self):
        u = c.upcoming(c.ROWS, "2026-11-01"); self.assertEqual(u[0][4], "2026-11-06"); self.assertTrue(all(r[4] >= "2026-11-01" for r in u))
    def test_shape(self): self.assertTrue(all(len(r) == len(c.F) for r in c.ROWS))
if __name__ == "__main__": unittest.main()
