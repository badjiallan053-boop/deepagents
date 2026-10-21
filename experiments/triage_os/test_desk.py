import importlib.util
import io
import json
import urllib.error
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

FIX = Path(__file__).with_name("fixtures")

def load(name):
    return json.loads((FIX / name).read_text())

class ConnectorTests(unittest.TestCase):
    """Offline: connectors are fed recorded JSON fixtures, no network."""
    def db(self, d):
        return desk.connect(Path(d) / "t.db")

    def test_sec_submissions(self):
        calls = []
        def fetch(url, headers):
            calls.append(url)
            self.assertIn("@", headers["User-Agent"])
            return load("sec_submissions.json")
        with tempfile.TemporaryDirectory() as d, self.db(d) as con:
            n = desk.ingest_sec(con, "1815903", "Test test@example.com", fetch=fetch)
            self.assertGreater(n, 0)
            self.assertTrue(calls[0].endswith("CIK0001815903.json"))
            for (url,) in con.execute("select url from signals"):
                self.assertTrue(url.startswith("https://www.sec.gov/Archives/edgar/data/1815903/"))

    def test_sec_requires_contact(self):
        with tempfile.TemporaryDirectory() as d, self.db(d) as con:
            with self.assertRaises(ValueError):
                desk.ingest_sec(con, "1", "anon", fetch=lambda u, h: {})

    def test_sec_fulltext_items_and_scoring(self):
        with tempfile.TemporaryDirectory() as d, self.db(d) as con:
            n = desk.ingest_sec_fulltext(con, '"Item 1.03"', "T t@example.com", "2026-09-22",
                                         "2026-10-22", ["1.03"],
                                         fetch=lambda u, h: load("sec_fulltext.json"))
            self.assertEqual(n, 5)
            top = desk.rank(con)[0]
            self.assertGreaterEqual(top["priority"], 40)
            self.assertIn("1.03", top["signal_type"])
            self.assertEqual(top["status"], "unverified")
            self.assertTrue(top["url"].startswith("https://www.sec.gov/Archives/edgar/data/"))

    def test_sec_item_scoring(self):
        self.assertEqual(desk.score_sec_items(["1.03", "2.04"]), 70)
        self.assertEqual(desk.score_sec_items(["9.01"]), 0)

    def test_court_v4_pagination_and_fields(self):
        page1 = load("courtlistener_v4.json")
        page1["next"] = "https://www.courtlistener.com/api/rest/v4/search/?cursor=abc"
        page2 = {"results": [], "next": None}
        urls = []
        def fetch(url, headers):
            urls.append(url)
            self.assertNotIn("Authorization", headers)
            return page1 if len(urls) == 1 else page2
        with tempfile.TemporaryDirectory() as d, self.db(d) as con:
            n = desk.ingest_court(con, "363 sale", None, filed_after="2026-09-22", fetch=fetch)
            self.assertEqual(n, 3)
            self.assertEqual(len(urls), 2)
            self.assertIn("/api/rest/v4/search/", urls[0])
            self.assertIn("order_by=dateFiled+desc", urls[0])
            self.assertIn("filed_after=2026-09-22", urls[0])
            for (url,) in con.execute("select url from signals"):
                self.assertTrue(url.startswith("https://www.courtlistener.com/docket/"))

    def test_court_page_cap(self):
        page = load("courtlistener_v4.json")
        page["next"] = "https://www.courtlistener.com/next"
        calls = []
        def fetch(url, headers):
            calls.append(url)
            return page
        with tempfile.TemporaryDirectory() as d, self.db(d) as con:
            desk.ingest_court(con, "x", "tok", max_pages=2, fetch=fetch)
            self.assertEqual(len(calls), 2)

    def test_court_scoring_uses_chapter_and_docs(self):
        item = {"caseName": "Acme LLC", "chapter": 11,
                "recap_documents": [{"description": "Motion to approve 363 sale"}]}
        self.assertEqual(desk.score_court_item(item), 42)

    def test_retry_then_success(self):
        attempts = []
        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False
        def opener(req, timeout):
            attempts.append(1)
            if len(attempts) < 3:
                raise urllib.error.HTTPError(req.full_url, 503, "busy", {}, None)
            return Resp(b'{"ok": true}')
        self.assertEqual(desk.get_json("https://x", {}, backoff=0, opener=opener), {"ok": True})
        self.assertEqual(len(attempts), 3)

    def test_no_retry_on_404(self):
        attempts = []
        def opener(req, timeout):
            attempts.append(1)
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)
        with self.assertRaises(urllib.error.HTTPError):
            desk.get_json("https://x", {}, backoff=0, opener=opener)
        self.assertEqual(len(attempts), 1)

    def test_export_csv(self):
        with tempfile.TemporaryDirectory() as d, self.db(d) as con:
            desk.ingest_sec_fulltext(con, "q", "T t@example.com", "a", "b",
                                     fetch=lambda u, h: load("sec_fulltext.json"))
            out = Path(d) / "o.csv"
            self.assertEqual(desk.export_csv(con, out, 3), 3)
            self.assertIn("signal_type", out.read_text().splitlines()[0])

if __name__ == "__main__":
    unittest.main()
