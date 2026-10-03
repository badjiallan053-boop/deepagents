import unittest

from elite_signals import MicrostructureSnapshot
from strategy_tournament import evaluate_tournament


class StrategyTournamentTests(unittest.TestCase):
    def _micro(self):
        return MicrostructureSnapshot(
            tx_count=30,
            buy_count=18,
            sell_count=8,
            unique_buyers=12,
            unique_sellers=6,
            buy_sell_ratio=18/26,
            flow_imbalance=10/26,
            same_slot_buy_share=0.2,
            top_buyer_amount_share=0.15,
            total_fee_lamports=100000,
            median_fee_lamports=3000,
            mint_authority_enabled=False,
            freeze_authority_enabled=False,
            top10_account_concentration=0.25,
        )

    def test_telegram_edge_requires_prior(self):
        votes = evaluate_tournament(
            source="telegram",
            micro=self._micro(),
            roundtrip_bps=-120,
            drift_500_bps=-40,
            organic_score=70,
            source_count=2,
            independent_wallet_count=1,
            telegram_channel_samples=25,
            telegram_channel_profit_factor=1.7,
            telegram_channel_ci_lower_bps=30,
        )
        tg = next(v for v in votes if v.name == "TELEGRAM_CHANNEL_EDGE")
        self.assertTrue(tg.passed)

    def test_telegram_cold_start_does_not_pass(self):
        votes = evaluate_tournament(
            source="telegram",
            micro=self._micro(),
            roundtrip_bps=-120,
            drift_500_bps=-40,
            organic_score=70,
            source_count=2,
            independent_wallet_count=1,
            telegram_channel_samples=3,
            telegram_channel_profit_factor=5.0,
            telegram_channel_ci_lower_bps=100,
        )
        tg = next(v for v in votes if v.name == "TELEGRAM_CHANNEL_EDGE")
        self.assertFalse(tg.passed)


if __name__ == "__main__":
    unittest.main()
