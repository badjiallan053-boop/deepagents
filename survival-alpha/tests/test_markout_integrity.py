import asyncio
import os
import unittest
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import create_engine, text

from firm_book import (
    MARK_FAILED, MISSED, NO_ROUTE, SOLD, TRANSIENT, UNSELLABLE,
    FirmPortfolioBook, classify_quote_exception,
)
from realtime_engine import CandidateEvent, RealtimeEngine, ensure_realtime_tables

T0 = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)

_TABLES = ("candidate_markout", "markout_attempt", "firm_portfolio_position",
           "realtime_candidate", "paper_position", "watch_wallet")


def _engine():
    """SQLite by default; set SA_TEST_DATABASE_URL to run against a throwaway Postgres."""
    url = os.getenv("SA_TEST_DATABASE_URL", "")
    if not url:
        return create_engine("sqlite:///:memory:")
    engine = create_engine(url)
    with engine.begin() as cx:
        for t in _TABLES:
            cx.execute(text(f"DROP TABLE IF EXISTS {t}"))
    return engine
E0 = T0.timestamp()


def _http_error(code: int) -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "https://api.jup.ag/swap/v2/order")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(code, request=req))


class ScriptedQuotes:
    """Each call pops the next scripted result: an int value or an exception."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = 0

    async def __call__(self, mint, amount):
        self.calls += 1
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, BaseException):
            raise item
        return {"outAmount": str(item)}


class MarkoutIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()
        ensure_realtime_tables(self.engine)
        self.book = FirmPortfolioBook(self.engine)
        self.book.markout_horizons = (30, 120, 300, 900)
        self.book.retry_window_secs = 60.0
        self.book.retry_base_secs = 2.0
        self.book.retry_max_backoff_secs = 20.0
        self.book.late_tolerance_frac = 0.20
        self.book.late_tolerance_min_secs = 5.0

    def _candidate(self, created=T0, primary=1, mint="MintA"):
        with self.engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO realtime_candidate
                (created_at_utc, updated_at_utc, mint, source, notional_lamports,
                 buy_out_amount, decision, episode_primary)
                VALUES (:c, :c, :m, 'jupiter_organic', 40000000, '1000', 'REJECT', :p)
            """), {"c": created.isoformat(), "m": mint, "p": primary})
            return int(cx.execute(text("SELECT MAX(id) FROM realtime_candidate")).scalar_one())

    def _mark(self, quotes, at_secs):
        asyncio.run(self.book.mark_candidate_horizons(quotes, now_epoch=E0 + at_secs))

    def _markouts(self, cid):
        with self.engine.begin() as cx:
            return {
                int(r["horizon_seconds"]): dict(r)
                for r in cx.execute(text(
                    "SELECT * FROM candidate_markout WHERE candidate_id=:id"
                ), {"id": cid}).mappings().all()
            }

    def _attempt(self, cid, h):
        with self.engine.begin() as cx:
            return cx.execute(text(
                "SELECT * FROM markout_attempt WHERE candidate_id=:id AND horizon_seconds=:h"
            ), {"id": cid, "h": h}).mappings().first()

    def _candidate_row(self, cid):
        with self.engine.begin() as cx:
            return cx.execute(text(
                "SELECT * FROM realtime_candidate WHERE id=:id"
            ), {"id": cid}).mappings().first()

    def test_schema_created_and_idempotent(self):
        # Regression: on Postgres a failing ALTER inside the CREATE transaction
        # used to roll back realtime_candidate/paper_position/watch_wallet.
        from sqlalchemy import inspect
        ensure_realtime_tables(self.engine)
        FirmPortfolioBook(self.engine)
        names = set(inspect(self.engine).get_table_names())
        for t in ("realtime_candidate", "paper_position", "watch_wallet",
                  "candidate_markout", "markout_attempt"):
            self.assertIn(t, names)

    # (3) one quote per horizon, observed age stored
    def test_each_horizon_gets_its_own_quote(self):
        cid = self._candidate()
        quotes = ScriptedQuotes(44_000_000, 30_000_000)
        self._mark(quotes, 31)
        self.assertEqual(set(self._markouts(cid)), {30})
        self._mark(quotes, 121)
        m = self._markouts(cid)
        self.assertEqual(set(m), {30, 120})
        self.assertAlmostEqual(m[30]["pnl_bps"], 1000.0)
        self.assertAlmostEqual(m[120]["pnl_bps"], -2500.0)
        self.assertAlmostEqual(m[30]["observed_age_seconds"], 31.0)
        self.assertEqual(m[30]["late"], 0)
        self.assertEqual(m[30]["status"], SOLD)
        self.assertEqual(quotes.calls, 2)

    def test_late_quote_is_flagged_and_not_reused_for_earlier_horizons(self):
        cid = self._candidate()
        quotes = ScriptedQuotes(40_000_000)
        self._mark(quotes, 170)  # 30s window closed; 120s still in its retry window
        m = self._markouts(cid)
        self.assertEqual(set(m), {120})
        self.assertEqual(m[120]["late"], 1)
        self.assertAlmostEqual(m[120]["lateness_seconds"], 50.0)
        self.assertEqual(self._attempt(cid, 30)["status"], MISSED)
        self.assertEqual(quotes.calls, 1)

    def test_late_five_minute_markout_does_not_set_outcome(self):
        cid = self._candidate()
        self._mark(ScriptedQuotes(48_000_000), 340)  # tol for 300s is 60s
        self.assertEqual(self._markouts(cid)[300]["late"], 0)
        cid2 = self._candidate(created=T0 + timedelta(seconds=0), mint="MintB")
        with self.engine.begin() as cx:
            cx.execute(text("DELETE FROM markout_attempt WHERE candidate_id=:id"), {"id": cid2})
        self.book.retry_window_secs = 120.0
        self._mark(ScriptedQuotes(48_000_000), 370)
        row = self._candidate_row(cid2)
        self.assertEqual(self._markouts(cid2)[300]["late"], 1)
        self.assertIsNone(row["outcome_5m_bps"])
        self.assertEqual(row["outcome_5m_status"], "LATE")

    # (2) transient errors are retried with backoff, not booked as losses
    def test_rate_limit_is_retried_then_sold(self):
        cid = self._candidate()
        quotes = ScriptedQuotes(_http_error(429), 50_000_000)
        self._mark(quotes, 300)
        self.assertNotIn(300, self._markouts(cid))
        att = self._attempt(cid, 300)
        self.assertEqual(att["status"], "PENDING")
        self.assertEqual(att["last_kind"], TRANSIENT)
        self._mark(quotes, 301)  # backoff not elapsed: no new quote
        self.assertEqual(quotes.calls, 1)  # 30s/120s windows closed (MISSED), 900s not due
        self._mark(quotes, 303)
        m = self._markouts(cid)[300]
        self.assertEqual(m["status"], SOLD)
        self.assertAlmostEqual(m["pnl_bps"], 2500.0)
        row = self._candidate_row(cid)
        self.assertAlmostEqual(row["outcome_5m_bps"], 2500.0)
        self.assertEqual(row["outcome_5m_status"], SOLD)

    def test_persistent_transient_errors_end_as_mark_failed_not_minus_100(self):
        cid = self._candidate()
        quotes = ScriptedQuotes(httpx.ReadTimeout("slow"))
        for t in range(300, 420, 3):
            self._mark(quotes, t)
        self.assertNotIn(300, self._markouts(cid))
        self.assertEqual(self._attempt(cid, 300)["status"], MARK_FAILED)
        row = self._candidate_row(cid)
        self.assertIsNone(row["outcome_5m_bps"])
        self.assertEqual(row["outcome_5m_status"], MARK_FAILED)

    # (1) no-route past the retry window is -100%
    def test_persistent_no_route_is_unsellable_at_first_observed_age(self):
        cid = self._candidate()
        quotes = ScriptedQuotes(_http_error(400))
        for t in range(300, 420, 3):
            self._mark(quotes, t)
        m = self._markouts(cid)[300]
        self.assertEqual(m["status"], UNSELLABLE)
        self.assertEqual(m["sellable"], 0)
        self.assertAlmostEqual(m["pnl_bps"], -10_000.0)
        self.assertAlmostEqual(m["observed_age_seconds"], 300.0)
        self.assertEqual(m["late"], 0)
        row = self._candidate_row(cid)
        self.assertAlmostEqual(row["outcome_5m_bps"], -10_000.0)
        self.assertEqual(row["outcome_5m_status"], UNSELLABLE)

    def test_zero_out_amount_counts_as_no_route(self):
        cid = self._candidate()
        quotes = ScriptedQuotes(0)
        for t in range(30, 100, 3):
            self._mark(quotes, t)
        self.assertEqual(self._markouts(cid)[30]["status"], UNSELLABLE)

    def test_temporary_no_route_then_sold_is_sold(self):
        cid = self._candidate()
        quotes = ScriptedQuotes(_http_error(404), 20_000_000)
        self._mark(quotes, 30)
        self._mark(quotes, 33)
        m = self._markouts(cid)[30]
        self.assertEqual(m["status"], SOLD)
        self.assertAlmostEqual(m["pnl_bps"], -5000.0)

    def test_failed_rows_never_block_newer_candidates(self):
        old_ids = [self._candidate(mint=f"Old{i}") for i in range(520)]
        new_id = self._candidate(created=T0 + timedelta(seconds=5000), mint="Fresh")
        quotes = ScriptedQuotes(42_000_000)
        self._mark(quotes, 5031)
        self._mark(quotes, 5031)
        self.assertEqual(set(self._markouts(new_id)), {30})
        self.assertEqual(self._attempt(old_ids[0], 300)["status"], MISSED)
        self.assertEqual(quotes.calls, 1)  # windows long gone: no quotes wasted on them

    def test_non_primary_rows_are_not_marked(self):
        cid = self._candidate(primary=0)
        quotes = ScriptedQuotes(42_000_000)
        self._mark(quotes, 31)
        self.assertEqual(self._markouts(cid), {})
        self.assertEqual(quotes.calls, 0)

    def test_classification(self):
        for code in (429, 500, 502, 503, 401, 403, 408):
            self.assertEqual(classify_quote_exception(_http_error(code)), TRANSIENT, code)
        for code in (400, 404, 422):
            self.assertEqual(classify_quote_exception(_http_error(code)), NO_ROUTE, code)
        self.assertEqual(classify_quote_exception(httpx.ConnectTimeout("t")), TRANSIENT)
        self.assertEqual(classify_quote_exception(httpx.ConnectError("c")), TRANSIENT)
        self.assertEqual(classify_quote_exception(KeyError("x")), TRANSIENT)


class EpisodeDedupeTests(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        for k in ("REALTIME_ENABLED", "JUPITER_API_KEY", "HELIUS_API_KEY", "HELIUS_RPC_URL",
                  "SOLANA_RPC_URL", "PUMPPORTAL_API_KEY"):
            os.environ.pop(k, None)
        self.engine = _engine()
        self.rt = RealtimeEngine(self.engine)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def _persist(self, source="jupiter_organic", detail="top organic 5m", mint="MintA",
                 decision="REJECT", phase="graduated_or_external", priced=True):
        return self.rt._persist_candidate(
            CandidateEvent(mint=mint, source=source, detail=detail),
            "1000" if priced else None, "900" if priced else None,
            -100.0 if priced else None, 0.0 if priced else None,
            decision, "test", market_phase=phase if priced else "",
        )

    def _row(self, cid):
        with self.engine.begin() as cx:
            return cx.execute(text("SELECT * FROM realtime_candidate WHERE id=:id"),
                              {"id": cid}).mappings().first()

    def test_repolls_share_one_episode_and_one_primary(self):
        a = self._persist()
        b = self._persist()
        self.assertEqual(self._row(a)["episode_key"], self._row(b)["episode_key"])
        self.assertEqual(self._row(a)["episode_primary"], 1)
        self.assertEqual(self._row(b)["episode_primary"], 0)

    def test_other_source_or_wallet_is_a_separate_signal(self):
        a = self._persist()
        b = self._persist(source="wallet_buy", detail="wallet AAAAAA… bought")
        c = self._persist(source="wallet_buy", detail="wallet BBBBBB… bought")
        self.assertEqual({self._row(x)["episode_primary"] for x in (a, b, c)}, {1})

    def test_gap_or_migration_starts_new_episode(self):
        a = self._persist(phase="bonding_curve")
        b = self._persist(phase="graduated_or_external")  # migrated
        self.assertNotEqual(self._row(a)["episode_key"], self._row(b)["episode_key"])
        self.assertEqual(self._row(b)["episode_primary"], 1)
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        with self.engine.begin() as cx:
            cx.execute(text("UPDATE realtime_candidate SET created_at_utc=:t"), {"t": old})
        c = self._persist(phase="graduated_or_external")
        self.assertNotEqual(self._row(b)["episode_key"], self._row(c)["episode_key"])
        self.assertEqual(self._row(c)["episode_primary"], 1)

    def test_unpriced_row_never_takes_primary(self):
        a = self._persist(priced=False, decision="REJECT")
        b = self._persist()
        self.assertEqual(self._row(a)["episode_primary"], 0)
        self.assertEqual(self._row(b)["episode_primary"], 1)

    def test_later_acceptance_takes_over_primary_and_clears_old_markouts(self):
        a = self._persist(decision="REJECT")
        with self.engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO candidate_markout (candidate_id, horizon_seconds, checked_at_utc,
                    value_lamports, pnl_bps, sellable) VALUES (:id, 30, 'x', 1, 1.0, 1)
            """), {"id": a})
        b = self._persist(decision="ACTIONABLE_PAPER")
        c = self._persist(decision="ACTIONABLE_PAPER")
        self.assertEqual(self._row(a)["episode_primary"], 0)
        self.assertEqual(self._row(b)["episode_primary"], 1)
        self.assertEqual(self._row(c)["episode_primary"], 0)
        with self.engine.begin() as cx:
            n = cx.execute(text("SELECT COUNT(*) FROM candidate_markout WHERE candidate_id=:id"),
                           {"id": a}).scalar_one()
        self.assertEqual(n, 0)

    # (5) idle reasons
    def test_idle_and_degraded_reasons(self):
        reasons = self.rt.idle_reasons()
        self.assertTrue(any("REALTIME_ENABLED" in r for r in reasons))
        self.assertTrue(any("JUPITER_API_KEY" in r for r in reasons))
        degraded = " ".join(self.rt.degraded_reasons())
        self.assertIn("HELIUS", degraded)
        self.assertIn("sidecar", degraded)
        self.assertFalse(self.rt.running)

        os.environ.update({"REALTIME_ENABLED": "true", "JUPITER_API_KEY": "k", "HELIUS_API_KEY": "h"})
        rt = RealtimeEngine(self.engine)
        self.assertEqual(rt.idle_reasons(), [])
        self.assertFalse(any("HELIUS" in r for r in rt.degraded_reasons()))


    # Postgres-safe boolean writes (paper_entered is BOOLEAN on Postgres).
    def test_paper_enter_sets_boolean_flag(self):
        cid = self._persist(decision="ACTIONABLE_PAPER")

        async def buy_quote(mint, amount):
            return {"outAmount": "123456"}

        self.rt._market_buy_quote = buy_quote
        pid = asyncio.run(self.rt.paper_enter(cid))
        self.assertIsNotNone(pid)
        self.assertTrue(bool(self._row(cid)["paper_entered"]))
        with self.engine.begin() as cx:
            n = cx.execute(text("SELECT COUNT(*) FROM paper_position WHERE status='OPEN'")).scalar_one()
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
