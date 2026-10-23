import datetime as dt, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import lse_ingest as L


def fake(calls):
    def op(method, path, params, body):
        calls.append((method, path))
        if path == "/catalog":
            return [{"symbol": "GBP_CORP_BBB", "name": "GBP BBB", "dataset": "credit_indices", "frequency": "daily"},
                    {"symbol": "GBP_CORP_AAA", "name": "GBP AAA", "dataset": "credit_indices", "frequency": "daily"}]
        if path == "/series":
            base = 100 if params["symbol"].endswith("AAA") else 200
            d0 = dt.date(2025, 9, 1)
            return [{"date": (d0 + dt.timedelta(days=i)).isoformat(), "value": base + i * 0.01} for i in range(400)]
        if path == "/export":
            return {"job_id": f"j{len(calls)}"}
        if path.startswith("/export/"):
            return {"status": "running"}
        return {}
    return op


def test_series_cache_pit_and_backdrop():
    with tempfile.TemporaryDirectory() as t:
        calls = []
        c = L.Client(out=t, opener=fake(calls))
        L.PANELS["T"] = {"credit": ["GBP_CORP_BBB", "GBP_CORP_AAA"], "curve": [], "funding": [], "stress": []}
        bd = L.backdrop("T", c, today=dt.date(2026, 10, 23))
        bd2 = L.backdrop("T", c, today=dt.date(2026, 10, 23))
        assert sum(1 for m, p in calls if p == "/series") == 2  # second run served from cache
        s = bd["groups"]["credit"][0]
        assert s["last_date"] == "2026-10-05" and calls and s["flag"] == "STALE" and s["stale_days"] == 18
        assert os.listdir(os.path.join(t, "pit"))
        h = L.backdrop_html(bd)
        assert "London Strategic Edge" in h and "STALE" in h and "not option-adjusted spreads" in h


def test_export_queue_respects_cap():
    with tempfile.TemporaryDirectory() as t:
        calls = []
        c = L.Client(out=t, opener=fake(calls))
        for i in range(7):
            c.queue_export("bond_yields", start=f"20{10+i}-01-01")
        c.queue_export("bond_yields", start="2010-01-01")  # duplicate ignored
        q = c.run_exports()
        assert len(q["jobs"]) == 7
        assert sum(j["status"] == "running" for j in q["jobs"]) == 5
        assert sum(1 for m, p in calls if p == "/export") == 5
        q = c.run_exports()  # resume: still capped within the hour
        assert sum(1 for m, p in calls if p == "/export") == 5


def test_key_never_written():
    with tempfile.TemporaryDirectory() as t:
        os.environ["LSE_API_KEY_TEST_SENTINEL"] = "x"
        c = L.Client(out=t, opener=fake([]))
        L.backdrop("T", c) if "T" in L.PANELS else None
        for root, _, fs in os.walk(t):
            for f in fs:
                assert os.environ.get("LSE_API_KEY", "@@none@@") not in open(os.path.join(root, f)).read()


if __name__ == "__main__":
    L.PANELS["T"] = {"credit": ["GBP_CORP_BBB", "GBP_CORP_AAA"], "curve": [], "funding": [], "stress": []}
    test_series_cache_pit_and_backdrop(); test_export_queue_respects_cap(); test_key_never_written()
    print("ok")
