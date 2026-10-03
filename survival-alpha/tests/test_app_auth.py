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


if __name__ == "__main__":
    unittest.main()
