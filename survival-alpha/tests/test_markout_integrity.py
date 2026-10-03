import asyncio
import os
import unittest
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import create_engine, text

from firm_book import (
    CONFIG_ERROR, MARK_FAILED, MISSED, NO_ROUTE, SOLD, TRANSIENT, UNSELLABLE,
    FirmPortfolioBook, QuoteUnavailable, classify_quote_exception,
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


NO_ROUTE_BODY = '{"error": "No routes found"}'


def _http_error(code: int, body: str = "") -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "https://api.jup.ag/swap/v2/order")
    return httpx.HTTPStatusError(
        "x", request=req, response=httpx.Response(code, request=req, text=body)
    )


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


class _MarkoutBase(unittest.TestCase):
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
        # Fee-free so the bps arithmetic below stays readable; fees have
        # their own tests (test_network_fees_*).
        self.book.network_fee_lamports_per_tx = 0

    def tearDown(self):
        self.engine.dispose()

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


class MarkoutIntegrityTests(_MarkoutBase):
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
        quotes = ScriptedQuotes(_http_error(400, NO_ROUTE_BODY))
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
        quotes = ScriptedQuotes(_http_error(404, NO_ROUTE_BODY), 20_000_000)
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
        for code in (429, 500, 502, 503, 408):
            self.assertEqual(classify_quote_exception(_http_error(code)), TRANSIENT, code)
        for code in (400, 404, 422):
            self.assertEqual(classify_quote_exception(_http_error(code, NO_ROUTE_BODY)), NO_ROUTE, code)
        # A 4xx without an explicit no-route body (bad params, schema change)
        # and 401/403 are our own problem, never evidence of a rug.
        for code in (400, 401, 403, 404, 422):
            self.assertEqual(classify_quote_exception(
                _http_error(code, '{"error": "dexes and excludeDexes are mutually exclusive"}')
            ), CONFIG_ERROR, code)
        self.assertEqual(classify_quote_exception(QuoteUnavailable("sidecar down")), TRANSIENT)
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

    def test_later_acceptance_keeps_rejection_and_its_markouts(self):
        # Regression (red-team B1-1): a later acceptance used to delete the
        # earlier REJECT primary's markouts (future-conditioned rejected set).
        a = self._persist(decision="REJECT")
        with self.engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO candidate_markout (candidate_id, horizon_seconds, checked_at_utc,
                    value_lamports, pnl_bps, sellable, status) VALUES (:id, 30, 'x', 1, 1.0, 1, 'SOLD')
            """), {"id": a})
        b = self._persist(decision="ACTIONABLE_PAPER")
        c = self._persist(decision="ACTIONABLE_PAPER")
        d = self._persist(decision="REJECT")
        ra, rb, rc, rd = (self._row(x) for x in (a, b, c, d))
        # The rejection keeps its decision-time primary status and markouts.
        self.assertEqual(ra["episode_primary"], 1)
        self.assertEqual(ra["decision"], "REJECT")
        self.assertIsNotNone(ra["accepted_later_at_utc"])  # audit-only annotation
        with self.engine.begin() as cx:
            n = cx.execute(text("SELECT COUNT(*) FROM candidate_markout WHERE candidate_id=:id"),
                           {"id": a}).scalar_one()
        self.assertEqual(n, 1)
        # The acceptance is its own episode, measured from its own decision.
        self.assertEqual(rb["episode_primary"], 1)
        self.assertEqual(rb["episode_key"], ra["episode_key"] + "#accept")
        # Re-polls after that are deduped into the accept episode.
        self.assertEqual(rc["episode_key"], rb["episode_key"])
        self.assertEqual(rc["episode_primary"], 0)
        self.assertEqual(rd["episode_primary"], 0)
        # Firm level: one token move = one firm sample, fixed at first sight.
        self.assertEqual(ra["firm_primary"], 1)
        self.assertEqual(rb["firm_primary"], 0)

    def test_cross_source_duplicates_are_one_firm_sample(self):
        # Red-team N1-2: same mint seen by three sources is three per-source
        # signals but ONE firm-level sample.
        a = self._persist()
        b = self._persist(source="wallet_buy", detail="wallet AAAAAA… bought")
        c = self._persist(source="telegram", detail="@chan", decision="ACTIONABLE_PAPER")
        rows = [self._row(x) for x in (a, b, c)]
        self.assertEqual({r["episode_primary"] for r in rows}, {1})
        self.assertEqual(len({r["firm_episode_key"] for r in rows}), 1)
        self.assertEqual([r["firm_primary"] for r in rows], [1, 0, 0])
        other = self._row(self._persist(mint="MintZ"))
        self.assertEqual(other["firm_primary"], 1)
        from agent_team import AgentTeam
        with self.engine.begin() as cx:
            cx.execute(text("UPDATE realtime_candidate SET outcome_5m_bps=100, strategy_votes_json=:v"),
                       {"v": '[{"name": "S", "passed": true}]'})
        cards = AgentTeam(self.engine).strategy_scorecards()
        self.assertEqual(cards["S"]["passed"]["n"], 2)  # MintA once + MintZ

    def test_channel_cards_do_not_double_count_late_acceptance(self):
        # Red-team R2-2: reject-then-accept is two primaries but one channel call.
        from agent_team import AgentTeam
        from capital_allocator import FirmCapitalAllocator
        a = self._persist(source="telegram", detail="@chan", decision="REJECT")
        b = self._persist(source="telegram", detail="@chan", decision="ACTIONABLE_PAPER")
        self.assertEqual({self._row(a)["episode_primary"], self._row(b)["episode_primary"]}, {1})
        with self.engine.begin() as cx:
            cx.execute(text("UPDATE realtime_candidate SET outcome_5m_bps=100"))
        self.assertEqual(AgentTeam(self.engine).channel_scorecards()["@chan"]["n"], 1)
        self.assertEqual(FirmCapitalAllocator(self.engine)._telegram_channel_card("@chan")["n"], 1)
        self.assertEqual(self.rt._telegram_channel_prior("@chan")["n"], 1)

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


class MarkoutCostAndVenueTests(_MarkoutBase):
    """Network fees, venue-confirmed no-route, lateness symmetry, entry anchor."""

    def test_network_fees_default_is_conservative_and_configurable(self):
        os.environ.pop("MARKOUT_NETWORK_FEE_LAMPORTS_PER_TX", None)
        self.assertEqual(FirmPortfolioBook(self.engine).network_fee_lamports_per_tx, 505_000)
        os.environ["MARKOUT_NETWORK_FEE_LAMPORTS_PER_TX"] = "10000"
        try:
            self.assertEqual(FirmPortfolioBook(self.engine).network_fee_lamports_per_tx, 10_000)
        finally:
            os.environ.pop("MARKOUT_NETWORK_FEE_LAMPORTS_PER_TX", None)

    def test_network_fees_reduce_sold_markout(self):
        self.book.network_fee_lamports_per_tx = 505_000
        cid = self._candidate()
        self._mark(ScriptedQuotes(44_000_000), 31)
        m = self._markouts(cid)[30]
        self.assertAlmostEqual(m["gross_pnl_bps"], 1000.0)
        self.assertEqual(m["network_fee_lamports"], 1_010_000)  # buy + sell tx
        self.assertAlmostEqual(m["pnl_bps"], 1000.0 - 252.5)

    def test_network_fees_on_unsellable_charge_buy_tx_only(self):
        self.book.network_fee_lamports_per_tx = 505_000
        cid = self._candidate()
        quotes = ScriptedQuotes(_http_error(400, NO_ROUTE_BODY))
        for t in range(30, 100, 3):
            self._mark(quotes, t)
        m = self._markouts(cid)[30]
        self.assertEqual(m["status"], UNSELLABLE)
        self.assertEqual(m["network_fee_lamports"], 505_000)
        self.assertAlmostEqual(m["pnl_bps"], -10_000.0 - 126.25)

    def test_malformed_request_400_is_never_minus_100(self):
        cid = self._candidate()
        quotes = ScriptedQuotes(_http_error(400, '{"error": "Invalid amount"}'))
        for t in range(300, 420, 3):
            self._mark(quotes, t)
        self.assertNotIn(300, self._markouts(cid))
        self.assertEqual(self._attempt(cid, 300)["status"], MARK_FAILED)
        self.assertIsNotNone(self.book.last_config_error)

    def test_unconfirmed_venue_no_route_is_never_minus_100(self):
        cid = self._candidate()
        quotes = ScriptedQuotes(QuoteUnavailable("sidecar HTTP 500; Jupiter fallback no route"))
        for t in range(300, 420, 3):
            self._mark(quotes, t)
        self.assertNotIn(300, self._markouts(cid))
        self.assertEqual(self._attempt(cid, 300)["status"], MARK_FAILED)

    def test_recovered_no_route_judged_late_like_a_rug(self):
        # Red-team B1-2 probe: 404 at 30-32 s then sold at 44 s used to be
        # excluded as late while a persistent 404 was included.
        cid = self._candidate()
        quotes = ScriptedQuotes(_http_error(404, NO_ROUTE_BODY), _http_error(404, NO_ROUTE_BODY), 40_000_000)
        for t in (30, 32, 44):
            self._mark(quotes, t)
        m = self._markouts(cid)[30]
        self.assertEqual(m["status"], SOLD)
        self.assertEqual(m["late"], 0)
        self.assertAlmostEqual(m["first_attempt_age_seconds"], 30.0)
        self.assertAlmostEqual(m["observed_age_seconds"], 44.0)

    def test_markout_loop_passes_entry_phase_to_quoter(self):
        cid = self._candidate()
        with self.engine.begin() as cx:
            cx.execute(text("UPDATE realtime_candidate SET market_phase='graduated_or_external' WHERE id=:id"),
                       {"id": cid})
        seen = []

        async def quoter(mint, amount, entry_phase=None):
            seen.append(entry_phase)
            raise _http_error(400, NO_ROUTE_BODY)
        for t in range(30, 100, 3):
            self._mark(quoter, t)
        self.assertEqual(set(seen), {"graduated_or_external"})
        self.assertEqual(self._markouts(cid)[30]["status"], UNSELLABLE)

    def test_assumptions_are_labeled(self):
        self.book.network_fee_lamports_per_tx = 505_000
        a = self.book.assumptions(40_000_000)
        self.assertIn("ASSUMPTION", a["label"])
        self.assertEqual(a["network_fee_lamports_per_tx"], 505_000)
        self.assertAlmostEqual(a["roundtrip_network_fee_bps_at_notional"], 252.5)

    def test_markout_clock_starts_at_entry_quote(self):
        cid = self._candidate()
        with self.engine.begin() as cx:
            cx.execute(text("UPDATE realtime_candidate SET entry_quote_at_utc=:t WHERE id=:id"),
                       {"t": (T0 + timedelta(seconds=10)).isoformat(), "id": cid})
        quotes = ScriptedQuotes(44_000_000)
        self._mark(quotes, 31)  # only 21 s after entry: not due yet
        self.assertEqual(self._markouts(cid), {})
        self._mark(quotes, 41)
        self.assertAlmostEqual(self._markouts(cid)[30]["observed_age_seconds"], 31.0)

    def test_horizon_scorecards_report_exclusions(self):
        from agent_team import AgentTeam
        ok = self._candidate()
        bad = self._candidate(mint="MintB")
        with self.engine.begin() as cx:
            cx.execute(text("UPDATE realtime_candidate SET firm_primary=1"))
        self._mark(ScriptedQuotes(44_000_000, httpx.ReadTimeout("t")), 31)
        for t in range(33, 100, 3):
            self._mark(ScriptedQuotes(httpx.ReadTimeout("t")), t)
        card = AgentTeam(self.engine).horizon_scorecards()["30"]
        self.assertEqual(card["n_excluded_by_reason"].get("MARK_FAILED"), 1)
        self.assertAlmostEqual(card["exclusion_rate"], 0.5)
        self.assertFalse(card["data_quality_ok"])
        self.assertEqual(card["rejected"]["status"], "DATA_QUALITY")
        self.assertTrue(ok and bad)


class SellVenueTests(unittest.TestCase):
    """X1: a sidecar failure + Jupiter no-route must not become a fake rug."""

    def setUp(self):
        self._env = dict(os.environ)
        self.engine = _engine()
        self.rt = RealtimeEngine(self.engine)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        self.engine.dispose()

    def _client(self, sidecar):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "127.0.0.1":
                return sidecar(request)
            return httpx.Response(400, json={"error": "No routes found"})
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    def _sell(self, sidecar):
        async def run():
            self.rt._http = self._client(sidecar)
            try:
                return await self.rt._market_sell_quote("MintA", 1000)
            finally:
                await self.rt._http.aclose()
        return asyncio.run(run())

    def test_sidecar_500_then_jupiter_no_route_is_transient(self):
        with self.assertRaises(QuoteUnavailable) as ctx:
            self._sell(lambda r: httpx.Response(500, json={"error": "rpc down"}))
        self.assertEqual(classify_quote_exception(ctx.exception), TRANSIENT)

    def test_sidecar_down_then_jupiter_no_route_is_transient(self):
        def down(r):
            raise httpx.ConnectError("refused")
        with self.assertRaises(QuoteUnavailable):
            self._sell(down)

    def test_confirmed_graduated_jupiter_no_route_is_no_route(self):
        with self.assertRaises(httpx.HTTPStatusError) as ctx:
            self._sell(lambda r: httpx.Response(200, json={"phase": "graduated", "graduated": True}))
        self.assertEqual(classify_quote_exception(ctx.exception), NO_ROUTE)

    def test_jupiter_entry_exits_on_jupiter_even_without_sidecar(self):
        # Red-team R2-1: no sidecar must not hide a real rug of a Jupiter-entered token.
        calls = []

        def down(r):
            calls.append(r.url.path)
            raise httpx.ConnectError("refused")

        async def run():
            self.rt._http = self._client(down)
            try:
                return await self.rt._market_sell_quote("MintA", 1000, entry_phase="graduated_or_external")
            finally:
                await self.rt._http.aclose()
        with self.assertRaises(httpx.HTTPStatusError) as ctx:
            asyncio.run(run())
        self.assertEqual(classify_quote_exception(ctx.exception), NO_ROUTE)
        self.assertEqual(calls, [])  # sidecar not consulted: same venue as the entry

    def test_bonding_entry_with_sidecar_down_stays_transient(self):
        async def run():
            def down(r):
                raise httpx.ConnectError("refused")
            self.rt._http = self._client(down)
            try:
                return await self.rt._market_sell_quote("MintA", 1000, entry_phase="bonding_curve")
            finally:
                await self.rt._http.aclose()
        with self.assertRaises(QuoteUnavailable):
            asyncio.run(run())

    def test_bonding_curve_quote_from_sidecar(self):
        q = self._sell(lambda r: httpx.Response(
            200, json={"phase": "bonding_curve", "solOutLamports": "123", "sellImpactBps": 5}))
        self.assertEqual(q["outAmount"], "123")


class EntryAfterDecisionTests(unittest.TestCase):
    """Red-team/Solana B2: the paper entry is the first quote AFTER the decision."""

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
        self.engine.dispose()

    def test_entry_is_post_decision_quote_with_latency(self):
        buys = iter([1_000_000, 1_010_000, 970_000])  # q0, q500, post-decision entry
        calls = []

        async def buy(mint, amount):
            calls.append(datetime.now(timezone.utc))
            return {"outAmount": str(next(buys)), "phase": "graduated_or_external",
                    "_market": "jupiter"}

        async def sell(mint, amount):
            return {"outAmount": "39000000"}

        self.rt._market_buy_quote = buy
        self.rt._market_sell_quote = sell
        cid = asyncio.run(self.rt.evaluate(CandidateEvent(mint="MintE", source="jupiter_organic")))
        with self.engine.begin() as cx:
            row = cx.execute(text("SELECT * FROM realtime_candidate WHERE id=:id"),
                             {"id": cid}).mappings().first()
        self.assertEqual(len(calls), 3)
        self.assertEqual(row["buy_out_amount"], "970000")
        self.assertEqual(row["pre_decision_buy_out_amount"], "1000000")
        self.assertAlmostEqual(row["drift_500_bps"], 100.0)
        decided = datetime.fromisoformat(row["decision_at_utc"])
        entry = datetime.fromisoformat(row["entry_quote_at_utc"])
        self.assertLessEqual(decided, calls[2])
        self.assertLessEqual(calls[2], entry)
        self.assertGreaterEqual(row["entry_latency_ms"], 0.0)

    def test_no_post_decision_quote_means_unmeasured(self):
        buys = iter([1_000_000, 1_000_000, 0])

        async def buy(mint, amount):
            return {"outAmount": str(next(buys)), "phase": "graduated_or_external"}

        async def sell(mint, amount):
            return {"outAmount": "39000000"}

        self.rt._market_buy_quote = buy
        self.rt._market_sell_quote = sell
        cid = asyncio.run(self.rt.evaluate(CandidateEvent(mint="MintF", source="jupiter_organic")))
        with self.engine.begin() as cx:
            row = cx.execute(text("SELECT * FROM realtime_candidate WHERE id=:id"),
                             {"id": cid}).mappings().first()
        self.assertIsNone(row["buy_out_amount"])
        self.assertEqual(row["episode_primary"], 0)
        self.assertIn("no executable entry quote after decision", row["reason"])


if __name__ == "__main__":
    unittest.main()
