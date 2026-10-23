import os, sqlite3, tempfile, datetime as dt
import gap_ingest as g

def test_cli_dedupe_and_window():
    today = g.now().date()
    rows = [{"src": "uk_gazette", "entity": "ACME LTD", "event": "x", "published": today.isoformat(), "url": "u1"},
            {"src": "uk_gazette", "entity": "OLD LTD", "event": "x", "published": (today - dt.timedelta(days=30)).isoformat(), "url": "u2"},
            {"src": "jp_tdb_flash", "entity": "株式会社A", "url": "u3"}]
    f = {"uk_gazette": lambda: rows[:2], "jp_tdb": lambda: rows[2:]}
    db = os.path.join(tempfile.mkdtemp(), "t.db")
    r1 = g.cli(["--days", "3", "--db", db, "--sources", "uk_gazette,jp_tdb"], fetchers=f)
    assert r1 == {"uk_gazette": 1, "jp_tdb": 1}
    r2 = g.cli(["--days", "3", "--db", db, "--sources", "uk_gazette,jp_tdb"], fetchers=f)
    assert r2 == {"uk_gazette": 0, "jp_tdb": 0}
    assert sqlite3.connect(db).execute("select count(*) from gap_entities").fetchone()[0] == 2

if __name__ == "__main__":
    test_cli_dedupe_and_window(); print("ok")
