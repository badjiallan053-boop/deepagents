import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("desk", Path(__file__).with_name("desk.py"))
desk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desk)

class DeskTests(unittest.TestCase):
    def test_scoring(self):
        self.assertGreater(desk.score("Chapter 11 bankruptcy 363 sale"), desk.score("ordinary quarterly update"))
        self.assertLessEqual(desk.score("bankruptcy chapter 11 363 sale default foreclosure"), 100)

    def test_provenance_and_deduplication(self):
        with tempfile.TemporaryDirectory() as d:
            with desk.connect(Path(d) / "test.db") as con:
                desk.store(con, "court", "123", "363 sale", "https://example.com/docket", "2026-10-20", {"x": 1})
                desk.store(con, "court", "123", "363 sale revised", "https://example.com/docket", "2026-10-20", {"x": 2})
                self.assertEqual(con.execute("select count(*) from signals").fetchone()[0], 1)
                self.assertEqual(desk.rank(con)[0]["status"], "unverified")

    def test_rejects_missing_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            with desk.connect(Path(d) / "test.db") as con:
                with self.assertRaises(ValueError):
                    desk.store(con, "court", "123", "title", "http://example.com", None, {})

if __name__ == "__main__":
    unittest.main()
