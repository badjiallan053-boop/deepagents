import json
import unittest

from sqlalchemy import create_engine, text

from capital_allocator import FirmCapitalAllocator


class CapitalAllocatorTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        with self.engine.begin() as cx:
            cx.execute(text("""
                CREATE TABLE realtime_candidate (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT,
                    source_detail TEXT,
                    strategy_votes_json TEXT,
                    outcome_5m_bps REAL,
                    episode_primary INTEGER NOT NULL DEFAULT 1,
                    firm_primary INTEGER NOT NULL DEFAULT 1
                )
            """))
        self.alloc = FirmCapitalAllocator(self.engine)
        self.alloc.min_samples = 20
        self.alloc.min_profit_factor = 1.3
        self.alloc.nav_lamports = 400_000_000

    def _seed_strategy(self, name, outcomes):
        with self.engine.begin() as cx:
            for out in outcomes:
                cx.execute(text("""
                    INSERT INTO realtime_candidate
                    (source, source_detail, strategy_votes_json, outcome_5m_bps)
                    VALUES ('wallet_buy', '', :votes, :outcome)
                """), {
                    "votes": json.dumps([{"name": name, "passed": True}]),
                    "outcome": out,
                })

    def test_cold_strategy_gets_no_capital(self):
        d = self.alloc.decide(
            source="wallet_buy",
            source_detail="",
            strategy_votes=[{"name": "EDGE", "passed": True}],
        )
        self.assertFalse(d.eligible)
        self.assertEqual(d.requested_lamports, 0)

    def test_promoted_strategy_gets_small_allocation(self):
        self._seed_strategy("EDGE", [180, 220, 150, -40, 260] * 8)
        d = self.alloc.decide(
            source="wallet_buy",
            source_detail="",
            strategy_votes=[{"name": "EDGE", "passed": True}],
        )
        self.assertTrue(d.eligible)
        self.assertGreater(d.requested_lamports, 0)
        self.assertIn("EDGE", d.promoted_strategies)


if __name__ == "__main__":
    unittest.main()
