import importlib.util
import io
import json
import unittest.mock
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

def sec_fetch(overrides=None):
    """Offline SEC: full-text fixture + submissions items fixture (optionally overridden)."""
    items = load("sec_submissions_items.json")
    for cik, acc_items in (overrides or {}).items():
        for acc, it in acc_items.items():
            i = items[cik]["accessionNumber"].index(acc)
            items[cik]["items"][i] = it
    def fetch(url, headers):
        if "efts.sec.gov" in url:
            return load("sec_fulltext.json")
        cik = url.rsplit("CIK", 1)[1].split(".")[0]
        return {"filings": {"recent": items[cik]}}
    return fetch

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
                                         fetch=sec_fetch())
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
                                     fetch=sec_fetch())
            out = Path(d) / "o.csv"
            self.assertEqual(desk.export_csv(con, out, 3), 3)
            self.assertIn("signal_type", out.read_text().splitlines()[0])

class DedupeAndHuntTests(unittest.TestCase):
    def test_text_only_mention_dropped(self):
        # metadata says the Petros filing has no item 1.03 -> text-only mention, dropped
        fetch = sec_fetch({"0001815903": {"0001104659-26-112399": "5.02,9.01"}})
        with tempfile.TemporaryDirectory() as d, desk.connect(Path(d) / "t.db") as con:
            n = desk.ingest_sec_fulltext(con, "q", "T t@example.com", "a", "b", ["1.03"], fetch=fetch)
            self.assertEqual(n, 4)
            self.assertEqual(con.execute("select count(*) from signals where title like '%Petros%'").fetchone()[0], 0)

    def test_metadata_items_override_search_items(self):
        fetch = sec_fetch({"0001743745": {"0001493152-26-047256": "1.03,2.04"}})
        with tempfile.TemporaryDirectory() as d, desk.connect(Path(d) / "t.db") as con:
            desk.ingest_sec_fulltext(con, "q", "T t@example.com", "a", "b", ["1.03"], fetch=fetch)
            raw = json.loads(con.execute("select raw_json from signals where external_id='0001493152-26-047256'").fetchone()[0])
            self.assertEqual(raw["items"], ["1.03", "2.04"])

    def test_entity_dedupe_across_forms_and_sources(self):
        with tempfile.TemporaryDirectory() as d, desk.connect(Path(d) / "t.db") as con:
            desk.ingest_sec_fulltext(con, "q", "T t@example.com", "a", "b", ["1.03"], fetch=sec_fetch())
            desk.store(con, "courtlistener", "999", "Leslie's Inc.", "https://www.courtlistener.com/docket/999/x/",
                       "2026-10-01", {"caseName": "Leslie's Inc.", "chapter": 11})
            rows = desk.rank(con, 50, dedupe=True)
            self.assertEqual(len(rows), 3)  # Petros, Greenlane, Leslie's
            les = [r for r in rows if r["entity_key"] == "cik:1821806"][0]
            self.assertEqual(les["signal_count"], 3)
            self.assertEqual(set(les["sources"].split(",")), {"sec", "courtlistener"})
            self.assertEqual(les["all_urls"].count("https://"), 3)

    def test_name_only_entity_absorbed_by_later_cik(self):
        with tempfile.TemporaryDirectory() as d, desk.connect(Path(d) / "t.db") as con:
            desk.store(con, "courtlistener", "1", "Acme Holdings LLC", "https://www.courtlistener.com/docket/1/",
                       "2026-10-01", {"caseName": "Acme Holdings LLC"})
            desk.store(con, "sec", "a-1", "Acme Inc — 8-K", "https://www.sec.gov/x", "2026-10-02",
                       {"entity": "ACME INC  (ACM)  (CIK 0000000042)", "cik": "42", "items": ["1.03"]})
            self.assertEqual(len(desk.rank(con, 10, dedupe=True)), 1)

    def test_court_partial_results_on_throttle(self):
        page = load("courtlistener_v4.json")
        page["next"] = "https://www.courtlistener.com/next"
        calls = []
        def fetch(url, headers):
            calls.append(url)
            if len(calls) > 1:
                raise urllib.error.URLError("timed out")
            return page
        with tempfile.TemporaryDirectory() as d, desk.connect(Path(d) / "t.db") as con:
            self.assertEqual(desk.ingest_court(con, "x", fetch=fetch), 3)
            self.assertEqual(con.execute("select count(*) from signals").fetchone()[0], 3)

    def test_court_token_from_env(self):
        seen = {}
        def fetch(url, headers):
            seen.update(headers); return {"results": [], "next": None}
        with tempfile.TemporaryDirectory() as d, desk.connect(Path(d) / "t.db") as con:
            with unittest.mock.patch.dict("os.environ", {"COURTLISTENER_TOKEN": "abc"}):
                desk.ingest_court(con, "x", fetch=fetch)
        self.assertEqual(seen["Authorization"], "Token abc")

    def test_daily_hunt_new_entities_only(self):
        court = load("courtlistener_v4.json"); court["next"] = None
        def court_fetch(url, headers):
            return court
        def broken_sec(url, headers):
            raise urllib.error.URLError("down")
        with tempfile.TemporaryDirectory() as d:
            r1 = desk.daily_hunt(d, 2, "T t@example.com", sec_fetch=sec_fetch(), court_fetch=court_fetch)
            self.assertGreater(r1["new_entities"], 0)
            self.assertTrue((Path(d) / "signals_new.csv").exists())
            r2 = desk.daily_hunt(d, 2, "T t@example.com", sec_fetch=broken_sec, court_fetch=court_fetch)
            self.assertEqual(r2["new_entities"], 0)          # nothing unseen
            self.assertEqual(len(r2["errors"]), 4)           # SEC failures isolated
            lines = (Path(d) / "signals_new.csv").read_text().splitlines()
            self.assertEqual(len(lines), 1)                  # header only

if __name__ == "__main__":
    unittest.main()
