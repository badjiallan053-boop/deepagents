import os, tempfile, unittest
import master_report as m
class T(unittest.TestCase):
    def test_signals_sorted_sane(self):
        self.assertTrue(all(0 < s[1] < 100 for s in m.SIGNALS))
    def test_scenarios_monotone(self):
        for v in m.SCEN.values(): self.assertEqual(v, sorted(v))
        self.assertTrue(m.SCEN["Conservative"][-1] < m.SCEN["Base"][-1] < m.SCEN["Bull"][-1])
    def test_db_counts_missing(self):
        self.assertEqual(m.db_counts(os.path.join(tempfile.gettempdir(), "nope.db")), {})
if __name__ == "__main__": unittest.main()
