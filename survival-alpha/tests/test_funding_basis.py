import asyncio
import gzip
import json
import os
import sys
import tempfile
import unittest

import httpx
from sqlalchemy import create_engine, text

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import funding_basis as fb  # noqa: E402

FIX = os.path.join(HERE, "fixtures", "funding", "recording_20261003.json.gz")


def load_fixture():
    with gzip.open(FIX, "rt") as f:
        return json.load(f)


def replay_transport(fx, extra=None):
    """Serve recorded real responses. Key: HL by type(+coin); others by URL."""
    table = {}
    for r in fx["responses"]:
        if r["body"]:
            b = json.loads(r["body"])
            key = ("HL", b["type"], b.get("coin"))
        else:
            key = ("GET", r["url"])
        if r["status"] == 200 or key not in table:
            table[key] = r

    def handler(req: httpx.Request):
        if req.content:
            b = json.loads(req.content)
            key = ("HL", b["type"], b.get("coin"))
        else:
            key = ("GET", str(req.url))
        if extra:
            res = extra(req, key)
            if res is not None:
                return res
        r = table.get(key)
        if r is None:
            if "binance" in str(req.url):
                return httpx.Response(451, json={"code": 0, "msg": "restricted"})
            return httpx.Response(404, json={"error": "not recorded"})
        return httpx.Response(r["status"], content=r["text"].encode(), headers={"content-type": "application/json"})
    return httpx.MockTransport(handler)


class EnvMixin:
    def setUp(self):
        self._env = dict(os.environ)
        for k in list(os.environ):
            if k.startswith("FUNDING_"):
                os.environ.pop(k)
        fb.PublicClient.MIN_INTERVAL = {k: 0.0 for k in fb.PublicClient.MIN_INTERVAL}

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.fx = load_fixture()
        self.by = {}
        for r in self.fx["responses"]:
            key = json.loads(r["body"])["type"] if r["body"] else r["url"].split("/api/v5/")[-1] if "okx" in r["url"] else r["url"]
            if r["status"] == 200:
                self.by.setdefault(key, json.loads(r["text"]))

    def test_hyperliquid_parse(self):
        rows = fb.parse_hyperliquid(self.by["metaAndAssetCtxs"], self.by["spotMetaAndAssetCtxs"],
                                    self.by["predictedFundings"], now_ms=self.fx["now_ms"])
        btc = next(r for r in rows if r["venue"] == "hyperliquid" and r["kind"] == "perp" and r["symbol"] == "BTC")
        self.assertEqual(btc["funding_interval_h"], 1.0)
        self.assertEqual(btc["funding_rate_hourly"], btc["funding_rate"])
        self.assertGreater(btc["mark"], 0)
        self.assertGreater(btc["open_interest_usd"], 1e8)
        self.assertIsNotNone(btc["spread_bps"])
        self.assertAlmostEqual(btc["mmr"], 0.5 / btc["max_leverage"])
        ubtc = next(r for r in rows if r["kind"] == "spot" and r["symbol"] == "UBTC")
        self.assertLess(abs(ubtc["mark"] / btc["mark"] - 1), 0.03)
        pred = [r for r in rows if r["kind"] == "predicted"]
        self.assertTrue(any(r["venue"] == "binance" for r in pred))
        self.assertTrue(all(r.get("mark") is None for r in pred))

    def test_hl_k_prefix(self):
        self.assertEqual(fb._hl_base("kPEPE"), ("PEPE", 1000.0))
        self.assertEqual(fb._hl_base("BTC"), ("BTC", 1.0))
        self.assertEqual(fb._hl_base("k"), ("k", 1.0))

    def test_okx_parse(self):
        b = self.by
        rows = fb.parse_okx(b["public/funding-rate?instId=ANY"], b["public/mark-price?instType=SWAP"],
                            b["market/tickers?instType=SWAP"], b["public/open-interest?instType=SWAP"],
                            b["market/index-tickers?quoteCcy=USDT"], b["public/instruments?instType=SWAP"],
                            b["market/tickers?instType=SPOT"])
        btc = next(r for r in rows if r["kind"] == "perp" and r["symbol"] == "BTC")
        self.assertEqual(btc["funding_interval_h"], 8.0)
        self.assertAlmostEqual(btc["funding_rate_hourly"], btc["funding_rate"] / 8.0)
        self.assertGreater(btc["open_interest_usd"], 1e6)
        self.assertIsNotNone(btc["index_px"])
        self.assertTrue(any(r["kind"] == "spot" and r["symbol"] == "BTC" for r in rows))
        self.assertFalse(any(r["venue_symbol"].endswith("-USD-SWAP") for r in rows))

    def test_binance_parse_format(self):
        # Box is geo-blocked from fapi.binance.com (HTTP 451). This sample is
        # hand-constructed in the documented response format, NOT market data.
        prem = [{"symbol": "XYZUSDT", "markPrice": "10.0", "indexPrice": "9.99", "lastFundingRate": "0.0004",
                 "nextFundingTime": 1791072000000, "interestRate": "0.0001", "time": 1791059000000}]
        rows = fb.parse_binance(prem, [{"symbol": "XYZUSDT", "fundingIntervalHours": 4}],
                                [{"symbol": "XYZUSDT", "bidPrice": "9.99", "askPrice": "10.01"}],
                                [{"symbol": "XYZUSDT", "quoteVolume": "5000000"}],
                                [{"symbol": "XYZUSDT", "bidPrice": "9.98", "askPrice": "10.0"}])
        perp = rows[0]
        self.assertEqual(perp["funding_interval_h"], 4)
        self.assertAlmostEqual(perp["funding_rate_hourly"], 0.0001)
        self.assertAlmostEqual(perp["spread_bps"], 20.0, places=3)
        self.assertEqual(rows[1]["kind"], "spot")

    def test_history_normalization(self):
        hl = fb.history_hourly("hyperliquid", [{"time": 1, "fundingRate": "0.0001"}])
        self.assertEqual(hl, [(1.0, 0.0001)])
        okx = fb.history_hourly("okx", {"data": [
            {"fundingTime": str(8 * 3_600_000), "realizedRate": "0.0008", "fundingRate": "0.0009"},
            {"fundingTime": str(16 * 3_600_000), "realizedRate": "0.0016", "fundingRate": ""}]})
        self.assertAlmostEqual(okx[1][1], 0.0002)
        self.assertEqual(fb.settlements("okx", {"data": [{"fundingTime": "5", "realizedRate": "0.001"}]}), [(5.0, 0.001)])
        self.assertEqual(fb.step_series([(0, 1.0), (2 * 3_600_000, 2.0)], 0, 3 * 3_600_000), [1.0, 1.0, 2.0, 2.0])


def leg(venue, kind, sym="XYZ", mark=100.0, bid=99.99, ask=100.01, f=None, oi=1e8, vol=1e9, mmr=None, maxlev=20):
    return {"venue": venue, "kind": kind, "symbol": sym, "venue_symbol": sym, "mark": mark, "bid": bid, "ask": ask,
            "spread_bps": fb._spread_bps(bid, ask), "funding_rate_hourly": f, "open_interest_usd": oi if kind == "perp" else None,
            "volume_24h_usd": vol, "mmr": mmr, "max_leverage": maxlev}


class EvaluateTests(EnvMixin, unittest.TestCase):
    def test_cash_carry_math_and_conservative_rate(self):
        cfg = fb.config()
        now = 100 * 3_600_000
        hist = [(now - h * 3_600_000, 0.0002) for h in range(25, 0, -1)]
        e = fb.evaluate_candidate("CASH_CARRY", leg("okx", "spot"), leg("okx", "perp", f=0.0003), cfg,
                                  hist_short=hist, now_ms=now)
        self.assertAlmostEqual(e["carry_hourly_expected"], 0.0002)  # min(current, trailing)
        self.assertAlmostEqual(e["gross_bps"], 0.0002 * 72 * 1e4)
        self.assertAlmostEqual(e["fees_bps"], 2 * (10.0 + 5.0))  # okx spot taker + swap taker, entry+exit
        self.assertEqual(e["flip_rate_24h"], 0.0)
        self.assertTrue(e["checks"]["history_available"])
        self.assertLessEqual(e["basis_adj_bps"], 0.0)
        self.assertAlmostEqual(e["net_bps"], e["gross_bps"] - e["fees_bps"] - e["slippage_bps"] + e["basis_adj_bps"])
        self.assertTrue(e["eligible"])

    def test_no_history_is_not_eligible(self):
        e = fb.evaluate_candidate("CASH_CARRY", leg("okx", "spot"), leg("okx", "perp", f=0.001), fb.config())
        self.assertFalse(e["checks"]["history_available"])
        self.assertFalse(e["eligible"])

    def test_flip_rate_and_liq_and_price_mismatch(self):
        cfg = fb.config()
        now = 100 * 3_600_000
        hist = [(now - h * 3_600_000, (0.0002 if h % 2 else -0.0002)) for h in range(25, 0, -1)]
        e = fb.evaluate_candidate("PERP_PERP", leg("hyperliquid", "perp", f=0.0, mmr=0.25, maxlev=2),
                                  leg("okx", "perp", f=0.0005, mark=110.0, bid=109.9, ask=110.1), cfg,
                                  hist_long=[(now - 30 * 3_600_000, 0.0)], hist_short=hist, now_ms=now)
        self.assertAlmostEqual(e["flip_rate_24h"], 0.5, delta=0.05)
        self.assertFalse(e["checks"]["flip_rate_ok"])
        self.assertFalse(e["checks"]["price_match"])  # 10% apart -> different instrument risk
        self.assertFalse(e["checks"]["leverage_allowed"])  # 3x > max 2x
        self.assertAlmostEqual(fb.liq_distance_pct(3, 0.01, 0.01), (1 / 3 - 0.01) * 100)

    def test_fee_override(self):
        os.environ["FUNDING_FEES_JSON"] = json.dumps({"okx": {"perp_taker": 1.0}})
        self.assertEqual(fb.config()["fees_bps"]["okx"]["perp_taker"], 1.0)
        self.assertEqual(fb.config()["fees_bps"]["okx"]["spot_taker"], 10.0)

    def test_scorecard_stats(self):
        s = fb.scorecard_stats([10.0, -5.0, 20.0, 0.0])
        self.assertEqual(s["count"], 4)
        self.assertAlmostEqual(s["mean_bps"], 6.25)
        self.assertAlmostEqual(s["median_bps"], 5.0)
        self.assertAlmostEqual(s["profit_factor"], 6.0)
        self.assertFalse(s["profit_factor_capped"])
        self.assertAlmostEqual(s["hit_rate"], 0.5)
        self.assertLessEqual(s["bootstrap_mean_lower95_bps"], s["mean_bps"])
        self.assertEqual(s, fb.scorecard_stats([10.0, -5.0, 20.0, 0.0]))  # deterministic
        allwin = fb.scorecard_stats([1.0, 2.0])
        self.assertEqual(allwin["profit_factor"], fb.PF_CAP)
        self.assertTrue(allwin["profit_factor_capped"])
        self.assertEqual(fb.scorecard_stats([])["count"], 0)


class ReplayTests(EnvMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.fx = load_fixture()
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{self.tmp.name}/f.db")

    def tearDown(self):
        self.engine.dispose()
        self.tmp.cleanup()
        super().tearDown()

    def test_replay_real_recording_default_thresholds(self):
        t = fb.FundingBasisTracker(self.engine, transport=replay_transport(self.fx))
        s = asyncio.run(t.scan_once(now_ms=self.fx["now_ms"]))
        self.assertTrue(s["venues"]["hyperliquid"]["ok"])
        self.assertTrue(s["venues"]["okx"]["ok"])
        self.assertTrue(s["venues"]["binance"]["blocked"])
        self.assertTrue(any("binance" in r for r in t.idle_reasons()))
        opps = t.opportunities(limit=50)
        self.assertGreater(len(opps), 3)
        top = opps[0]
        self.assertEqual((top["strategy"], top["symbol"]), ("PERP_PERP", "SAND"))
        self.assertFalse(top["eligible"])  # 24h flip rate too high in the real data
        self.assertEqual(t.positions(), [])  # nothing clears the default threshold
        st = t.status()
        self.assertFalse(st["live_execution_available"])
        self.assertGreater(st["latest_snapshots"].get("hyperliquid:perp", 0), 0)

    def test_entry_mtm_and_exit(self):
        os.environ["FUNDING_ENTRY_MIN_NET_BPS"] = "-1000"
        os.environ["FUNDING_MAX_FLIP_RATE"] = "1.0"
        os.environ["FUNDING_MAX_OPEN_PER_STRATEGY"] = "1"
        t = fb.FundingBasisTracker(self.engine, transport=replay_transport(self.fx))
        s = asyncio.run(t.scan_once(now_ms=self.fx["now_ms"]))
        self.assertGreaterEqual(s["entered"], 1)
        pos = t.positions(status="OPEN")
        pp = next(p for p in pos if p["strategy"] == "PERP_PERP")
        self.assertEqual(pp["symbol"], "SAND")
        self.assertEqual((pp["venue_long"], pp["venue_short"]), ("hyperliquid", "okx"))
        self.assertGreater(pp["fees_usd"], 0)
        now = self.fx["now_ms"]

        def extra(req, key):
            # synthetic settlements AFTER entry (unit-test inputs, not market data)
            if key[0] == "HL" and key[1] == "fundingHistory":
                return httpx.Response(200, json=[{"coin": key[2], "fundingRate": "0.0001", "premium": "0",
                                                  "time": now + 3_600_000}])
            if key[0] == "GET" and "funding-rate-history" in key[1]:
                return httpx.Response(200, json={"code": "0", "data": [
                    {"instId": "X", "fundingTime": str(now + 8 * 3_600_000), "realizedRate": "0.0005",
                     "fundingRate": "0.0005"}]})
            return None

        t.transport = replay_transport(self.fx, extra)
        later = now + 9 * 3_600_000
        client = fb.PublicClient(t.transport)
        snaps = asyncio.run(self._snaps(t, client))
        m, c = asyncio.run(t._mark_positions(client, snaps, fb.config(), later))
        asyncio.run(client.close())
        self.assertGreaterEqual(m, 1)
        p2 = next(p for p in t.positions() if p["id"] == pp["id"])
        N = p2["notional_usd"]
        # long HL pays 0.0001*N, short OKX receives 0.0005*N
        self.assertAlmostEqual(p2["funding_pnl_usd"], (-0.0001 + 0.0005) * N, places=6)
        with self.engine.begin() as cx:
            row = cx.execute(text("SELECT * FROM funding_mtm WHERE position_id=:i"), {"i": pp["id"]}).mappings().first()
        self.assertEqual(row["settlements"], 2)
        # horizon exit
        client = fb.PublicClient(t.transport)
        m, c = asyncio.run(t._mark_positions(client, snaps, fb.config(), now + 73 * 3_600_000))
        asyncio.run(client.close())
        self.assertGreaterEqual(c, 1)
        closed = [p for p in t.positions(status="CLOSED")]
        self.assertTrue(any(p["exit_reason"].startswith(("HORIZON", "STOP_LOSS", "FUNDING_FLIP")) for p in closed))
        sc = t.scorecard()
        self.assertGreaterEqual(sc["all"]["count"], 1)
        self.assertIn("PERP_PERP", sc["strategies"])

    async def _snaps(self, t, client):
        out = []
        for v in ("hyperliquid", "okx"):
            out.extend(await t.fetch_venue(client, v))
        return out

    def test_opportunity_rows_share_an_episode_across_scans(self):
        t = fb.FundingBasisTracker(self.engine, transport=replay_transport(self.fx))
        now = self.fx["now_ms"]
        asyncio.run(t.scan_once(now_ms=now))
        asyncio.run(t.scan_once(now_ms=now + 300_000))
        with self.engine.begin() as cx:
            rows = cx.execute(text("SELECT COUNT(*) FROM funding_opportunity")).scalar_one()
            eps = cx.execute(text("SELECT COUNT(DISTINCT opportunity_episode_id) FROM funding_opportunity")).scalar_one()
            nulls = cx.execute(text("SELECT COUNT(*) FROM funding_opportunity WHERE opportunity_episode_id IS NULL")
                               ).scalar_one()
        self.assertEqual(nulls, 0)
        self.assertGreater(rows, eps)  # repeated scans of the same pair are one episode
        st = t.status()["opportunities"]
        self.assertEqual((st["rows"], st["episodes"]), (rows, eps))

    def test_migrations_idempotent(self):
        fb.ensure_funding_tables(self.engine)
        fb.ensure_funding_tables(self.engine)


class ExitSpreadTests(EnvMixin, unittest.TestCase):
    """Risk red-team B4-2: no mid exits on legs without a book."""

    def test_book_used_when_present(self):
        cfg = fb.config()
        self.assertEqual(fb.exit_price({"bid": 99.0, "ask": 101.0, "mark": 100.0}, "long", {}, cfg), 99.0)
        self.assertEqual(fb.exit_price({"bid": 99.0, "ask": 101.0, "mark": 100.0}, "short", {}, cfg), 101.0)

    def test_hl_spot_without_book_pays_half_entry_spread(self):
        cfg = fb.config()
        pos = {"entry_detail_json": json.dumps({"entry_spread_bps_long": 10.0})}
        px = fb.exit_price({"bid": None, "ask": None, "mark": 100.0}, "long", pos, cfg)
        self.assertAlmostEqual(px, 100.0 * (1 - 5.0 / 1e4))

    def test_unknown_entry_spread_falls_back_to_cap(self):
        cfg = fb.config()
        px = fb.exit_price({"bid": None, "mark": 100.0}, "long", {"entry_detail_json": "{}"}, cfg)
        self.assertAlmostEqual(px, 100.0 * (1 - cfg["max_spread_bps"] / 2 / 1e4))
        self.assertLess(px, 100.0)


class SafetyAndApiTests(EnvMixin, unittest.TestCase):
    def test_no_keys_or_order_paths(self):
        src = open(os.path.join(os.path.dirname(HERE), "funding_basis.py")).read()
        for bad in ("X-MBX-APIKEY", "OK-ACCESS-KEY", "OK-ACCESS-SIGN", "/api/v5/trade", "/fapi/v1/order",
                    "\"type\": \"order\"", "sign_l1_action", "eth_account", "private_key"):
            self.assertNotIn(bad, src)

    def test_disabled_by_default(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            eng = create_engine(f"sqlite:///{tmp.name}/d.db")
            t = fb.FundingBasisTracker(eng)
            asyncio.run(t.start())
            self.assertIsNone(t._task)
            self.assertIn("FUNDING_BASIS_ENABLED", " ".join(t.idle_reasons()))
            eng.dispose()
        finally:
            tmp.cleanup()

    def test_endpoints_auth(self):
        from fastapi.testclient import TestClient
        tmp = tempfile.mkdtemp()
        os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/app.db"
        os.environ["PAPER_ADMIN_TOKEN"] = "admin-secret"
        os.environ["PAPER_READ_TOKEN"] = "read-secret"
        sys.modules.pop("app", None)
        import app as app_mod
        c = TestClient(app_mod.app)
        for path in ("/funding/status", "/funding/opportunities", "/funding/positions", "/funding/scorecard"):
            self.assertEqual(c.get(path).status_code, 401, path)
            self.assertEqual(c.get(path, headers={"X-Paper-Token": "nope"}).status_code, 401, path)
            self.assertEqual(c.get(path, headers={"X-Paper-Token": "read-secret"}).status_code, 200, path)
            self.assertEqual(c.get(path, headers={"X-Paper-Token": "admin-secret"}).status_code, 200, path)
        body = c.get("/funding/status", headers={"X-Paper-Token": "read-secret"}).json()
        self.assertFalse(body["enabled"])
        self.assertFalse(body["live_execution_available"])
        app_mod.engine.dispose()


@unittest.skipUnless(os.getenv("SA_TEST_DATABASE_URL"), "SA_TEST_DATABASE_URL not set")
class PostgresFundingTests(EnvMixin, unittest.TestCase):
    def test_pg_replay(self):
        engine = create_engine(os.environ["SA_TEST_DATABASE_URL"])
        with engine.begin() as cx:
            for tname in ("funding_snapshot", "funding_opportunity", "funding_position", "funding_mtm"):
                cx.execute(text(f"DROP TABLE IF EXISTS {tname}"))
        fb.ensure_funding_tables(engine)
        fb.ensure_funding_tables(engine)
        os.environ["FUNDING_ENTRY_MIN_NET_BPS"] = "-1000"
        os.environ["FUNDING_MAX_FLIP_RATE"] = "1.0"
        fx = load_fixture()
        t = fb.FundingBasisTracker(engine, transport=replay_transport(fx))
        s = asyncio.run(t.scan_once(now_ms=fx["now_ms"]))
        self.assertGreaterEqual(s["entered"], 1)
        self.assertIsInstance(t.scorecard()["all"], dict)
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
