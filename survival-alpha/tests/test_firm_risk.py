import unittest

from sqlalchemy import create_engine, text

from firm_book import ensure_firm_tables
from firm_risk import FirmRiskGovernor


class FirmRiskTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        ensure_firm_tables(self.engine)
        self.risk = FirmRiskGovernor(self.engine)
        self.risk.nav_lamports = 400_000_000
        self.risk.max_open_positions = 2
        self.risk.max_single_position_bps = 1000
        self.risk.max_gross_exposure_bps = 5000
        self.risk.max_source_exposure_bps = 2500
        self.risk.daily_loss_limit_bps = 500

    def test_allows_small_clean_position(self):
        d = self.risk.check(
            mint="MintA", source="telegram", source_detail="@alpha",
            requested_lamports=20_000_000,
        )
        self.assertTrue(d.allowed)

    def test_blocks_duplicate_mint(self):
        with self.engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO firm_portfolio_position
                (candidate_id, opened_at_utc, mint, source, source_detail,
                 allocated_lamports, token_amount, strategy_names_json, status)
                VALUES
                (1, '2026-10-03T00:00:00+00:00', 'MintA', 'telegram', '@alpha',
                 20000000, '100', '[]', 'OPEN')
            """))
        d = self.risk.check(
            mint="MintA", source="telegram", source_detail="@alpha",
            requested_lamports=20_000_000,
        )
        self.assertFalse(d.allowed)
        self.assertIn("duplicate mint exposure", d.reasons)

    def test_blocks_single_position_cap(self):
        d = self.risk.check(
            mint="MintB", source="wallet_buy", requested_lamports=50_000_000,
        )
        self.assertFalse(d.allowed)
        self.assertIn("single-position risk cap", d.reasons)


if __name__ == "__main__":
    unittest.main()
