import importlib
import os
import tempfile
import unittest

app_module = None
_tmp = None
_saved_env = {}
_KEYS = ("DATABASE_URL", "PAPER_ADMIN_TOKEN", "PAPER_READ_TOKEN", "REALTIME_ENABLED", "JUPITER_API_KEY")


def setUpModule():
    global app_module, _tmp
    _saved_env.update({k: os.environ.get(k) for k in _KEYS})
    _tmp = tempfile.TemporaryDirectory()
    os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}/test.db"
    os.environ["PAPER_ADMIN_TOKEN"] = "admin-secret"
    os.environ["PAPER_READ_TOKEN"] = "read-secret"
    os.environ.pop("REALTIME_ENABLED", None)
    os.environ.pop("JUPITER_API_KEY", None)
    app_module = importlib.import_module("app")


def tearDownModule():
    for k, v in _saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    app_module.engine.dispose()
    _tmp.cleanup()


class AppAuthTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        self.client = TestClient(app_module.app)

    def test_read_token_works_on_get(self):
        r = self.client.get("/realtime/status", headers={"X-Paper-Token": "read-secret"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["engine_running"])
        self.assertTrue(any("REALTIME_ENABLED" in x for x in body["idle_reasons"]))
        self.assertTrue(any("JUPITER_API_KEY" in x for x in body["idle_reasons"]))
        self.assertIn("degraded_reasons", body)
        self.assertIn("episode_primary", body["counts"])

    def test_admin_token_still_works_everywhere(self):
        h = {"X-Paper-Token": "admin-secret"}
        self.assertEqual(self.client.get("/team/horizon-scorecards", headers=h).status_code, 200)
        r = self.client.post("/realtime/watch-wallet", headers=h,
                             json={"wallet": "W" * 40, "label": "t"})
        self.assertEqual(r.status_code, 200)

    def test_read_token_rejected_on_post(self):
        r = self.client.post("/realtime/watch-wallet", headers={"X-Paper-Token": "read-secret"},
                             json={"wallet": "R" * 40})
        self.assertEqual(r.status_code, 401)
        r = self.client.post("/realtime/paper-exit/1", headers={"X-Paper-Token": "read-secret"})
        self.assertEqual(r.status_code, 401)

    def test_missing_or_wrong_token(self):
        self.assertEqual(self.client.get("/realtime/status").status_code, 401)
        self.assertEqual(
            self.client.get("/realtime/status", headers={"X-Paper-Token": "nope"}).status_code, 401
        )

    def test_get_routes_all_use_reader_and_posts_use_admin(self):
        import inspect
        for route in app_module.app.routes:
            methods = getattr(route, "methods", set()) or set()
            src = inspect.getsource(route.endpoint) if hasattr(route, "endpoint") else ""
            if "POST" in methods:
                self.assertNotIn("require_reader", src, route.path)
            if "GET" in methods and "require_admin(" in src:
                self.fail(f"GET {route.path} should use require_reader")

    def test_quote_drift_summary_requires_token(self):
        self.assertEqual(self.client.get("/paper/quote-drift/summary").status_code, 401)
        r = self.client.get("/paper/quote-drift/summary", headers={"X-Paper-Token": "read-secret"})
        self.assertEqual(r.status_code, 200)

    def test_scorecards_survive_all_winning_buckets(self):
        from sqlalchemy import text
        votes = '[{"name":"TRENCHER_ORGANIC","passed":true}]'
        with app_module.engine.begin() as cx:
            for i in range(3):
                cx.execute(text("""
                    INSERT INTO realtime_candidate (created_at_utc, updated_at_utc, mint, source,
                        notional_lamports, buy_out_amount, decision, strategy_votes_json,
                        outcome_5m_bps, episode_primary, firm_primary)
                    VALUES ('2026-10-03T00:00:00+00:00', 'x', :m, 'jupiter_organic', 40000000,
                        '1', 'ACTIONABLE_PAPER', :v, 500.0, 1, 1)
                """), {"m": f"WinMint{i}", "v": votes})
                cid = cx.execute(text("SELECT MAX(id) FROM realtime_candidate")).scalar_one()
                cx.execute(text("""
                    INSERT INTO candidate_markout (candidate_id, horizon_seconds, checked_at_utc,
                        value_lamports, pnl_bps, sellable, late, status)
                    VALUES (:id, 300, 'x', 42000000, 500.0, 1, 0, 'SOLD')
                """), {"id": cid})
        h = {"X-Paper-Token": "read-secret"}
        r = self.client.get("/team/strategy-scorecards", headers=h)
        self.assertEqual(r.status_code, 200)
        card = r.json()["strategies"]["TRENCHER_ORGANIC"]["passed"]
        self.assertTrue(card["profit_factor_capped"])
        r = self.client.get("/team/horizon-scorecards", headers=h)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["horizons"]["300"]["accepted"]["profit_factor_capped"])

    def test_profit_team_reads_allow_read_token_but_writes_need_admin(self):
        h = {"X-Paper-Token": "read-secret"}
        self.assertEqual(self.client.get("/profit-team/dashboard", headers=h).status_code, 200)
        self.assertEqual(self.client.get("/profit-team/manifest", headers=h).status_code, 200)
        body = {
            "title": "test hypothesis", "desk": "SOLANA_ONCHAIN", "asset_class": "crypto",
            "instruments": ["SOL"], "mechanism": "mechanism text here",
            "horizon": "5m", "falsification_test": "falsify it",
        }
        self.assertEqual(self.client.post("/profit-team/hypotheses", headers=h, json=body).status_code, 401)


if __name__ == "__main__":
    unittest.main()
