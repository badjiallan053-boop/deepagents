import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import gate_stats as gs  # noqa: E402


class GateStatsTests(unittest.TestCase):
    def test_no_data_and_min_n(self):
        self.assertEqual(gs.gate_stats([])["status"], "NO_DATA")
        s = gs.gate_stats([10.0] * 29)
        self.assertEqual(s["status"], "COLLECT")
        self.assertTrue(s["profit_factor_capped"])
        self.assertEqual(s["profit_factor"], gs.PF_CAP)

    def test_rows_in_one_cluster_are_one_sample(self):
        vals = [50.0, -10.0] * 100  # 200 rows
        iid = gs.gate_stats(vals)
        self.assertEqual(iid["n_clusters"], 200)
        clustered = gs.gate_stats(vals, ["MintA"] * 100 + ["MintB"] * 100)
        self.assertEqual(clustered["n"], 200)
        self.assertEqual(clustered["n_clusters"], 2)
        self.assertEqual(clustered["status"], "COLLECT")

    def test_research_candidate_and_gate4(self):
        vals = [100.0, -40.0, 60.0] * 20  # 60 rows
        ids = [f"t{i}" for i in range(60)]
        s = gs.gate_stats(vals, ids)
        self.assertEqual(s["status"], "RESEARCH_CANDIDATE")
        self.assertGreater(s["cluster_bootstrap_mean_lower95_bps"], 0)
        big = gs.gate_stats(vals * 5, [f"t{i}" for i in range(300)])
        self.assertEqual(big["status"], "GATE4_ELIGIBLE")

    def test_dominance(self):
        vals = [-10.0] * 40 + [5000.0]
        ids = [f"d{i}" for i in range(41)]
        s = gs.gate_stats(vals, ids)
        self.assertIn(s["status"], ("DOMINATED", "REJECT_OR_REWORK"))
        self.assertLess(s["pf_without_top_cluster"] or 0, 1.3)
        self.assertGreater(s["top_cluster_profit_share"], 0.99)

    def test_cluster_lb_is_wider_than_iid_for_correlated_rows(self):
        vals, ids = [], []
        for c in range(40):
            v = 80.0 if c % 2 else -40.0
            vals += [v] * 10
            ids += [f"day{c}"] * 10
        s = gs.gate_stats(vals, ids)
        self.assertLess(s["cluster_bootstrap_mean_lower95_bps"], s["iid_bootstrap_mean_lower95_bps"])

    def test_exclusions_fail_data_quality(self):
        s = gs.gate_stats([100.0, -10.0] * 40, exclusions={"MARK_FAILED": 10})
        self.assertEqual(s["status"], "DATA_QUALITY")
        self.assertAlmostEqual(s["exclusion_rate"], 10 / 90)

    def test_helpers(self):
        self.assertEqual(gs.utc_day("2026-10-03T23:30:00-02:00"), "2026-10-04")
        self.assertEqual(gs.iso_week("2026-10-04T00:00:00+00:00"), "2026-W40")
        self.assertEqual(gs.capped_profit_factor([]), (None, False))
        self.assertEqual(gs.capped_profit_factor([3.0, -1.0]), (3.0, False))
        with self.assertRaises(ValueError):
            gs.gate_stats([1.0], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
