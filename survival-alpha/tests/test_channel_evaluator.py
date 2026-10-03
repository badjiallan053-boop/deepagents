import math
import unittest

from channel_evaluator import evaluate_outcomes


class ChannelEvaluatorTests(unittest.TestCase):
    def test_promotes_repeatable_positive_sample(self):
        outcomes = [180, 220, 150, -40, 260] * 8
        card = evaluate_outcomes(outcomes, min_samples=20, min_profit_factor=1.3)
        self.assertEqual(card.status, "PROMOTE")
        self.assertGreater(card.profit_factor, 1.3)
        self.assertGreater(card.bootstrap_mean_lower_95_bps, 0)

    def test_rejects_bad_sample(self):
        outcomes = [50, -300, -250, 20, -200] * 8
        card = evaluate_outcomes(outcomes, min_samples=20, min_profit_factor=1.3)
        self.assertEqual(card.status, "REJECT_OR_REWORK")
        self.assertLess(card.mean_bps, 0)

    def test_collects_when_sample_too_small(self):
        card = evaluate_outcomes([100, 80, -20], min_samples=20)
        self.assertEqual(card.status, "COLLECT")

    def test_no_losses_caps_profit_factor_and_stays_json_safe(self):
        import json
        from channel_evaluator import PROFIT_FACTOR_CAP
        card = evaluate_outcomes([100, 200, 300] * 10, min_samples=20, min_profit_factor=1.3)
        self.assertEqual(card.profit_factor, PROFIT_FACTOR_CAP)
        self.assertTrue(card.profit_factor_capped)
        self.assertEqual(card.status, "PROMOTE")  # gate semantics unchanged vs inf
        json.dumps(card.to_dict(), allow_nan=False)

    def test_normal_profit_factor_not_flagged(self):
        card = evaluate_outcomes([100, -50, 200], min_samples=1)
        self.assertFalse(card.profit_factor_capped)
        self.assertAlmostEqual(card.profit_factor, 6.0)


if __name__ == "__main__":
    unittest.main()
