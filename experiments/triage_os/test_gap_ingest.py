import os, sqlite3, tempfile, datetime as dt, json
from unittest import mock
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

def _atom_page(entries):
    parts = []
    for title, pub, link in entries:
        parts.append(
            f"<entry><title>{title}</title><published>{pub}</published>"
            f'<category term="Appointment of Administrators"/>'
            f"<id>{link}</id></entry>"
        )
    return "<?xml version='1.0'?><feed>" + "".join(parts) + "</feed>"

def test_uk_gazette_paginates_and_cache_busts():
    today = g.now().date()
    d0 = today.isoformat() + "T12:00:00Z"
    d1 = (today - dt.timedelta(days=1)).isoformat() + "T12:00:00Z"
    old = (today - dt.timedelta(days=10)).isoformat() + "T12:00:00Z"
    pages = {
        1: _atom_page([(f"FIRM{i} LTD", d0, f"https://example/u{i}") for i in range(100)]),
        2: _atom_page([(f"NEXT{i} PLC", d1, f"https://example/n{i}") for i in range(50)]
                      + [("STALE LTD", old, "https://example/stale")]),
    }
    seen = []

    def fake_get(url):
        seen.append(url)
        assert "Cache-Control" in g.UA and g.UA["Cache-Control"] == "no-cache"
        assert "_=" in url and "results-page=" in url
        page = int(url.split("results-page=")[1].split("&")[0])
        return pages[page], 0.01, 200

    with mock.patch.object(g, "get", side_effect=fake_get), mock.patch.object(g.time, "sleep"):
        rows, secs, raw = g.uk_gazette(days=2, page_size=100, max_pages=5)
    assert raw == 151
    assert len(rows) == 150  # 100+50; STALE LTD dropped by cutoff
    assert all(r["entity"] != "STALE LTD" for r in rows)
    assert any("results-page=1" in u for u in seen) and any("results-page=2" in u for u in seen)
    assert all("_=" in u for u in seen)

def test_uk_gazette_raises_on_waf():
    with mock.patch.object(g, "get", return_value=("<html>challenge.js awswaf</html>", 0.01, 202)):
        try:
            g.uk_gazette(days=2, max_pages=1)
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "WAF" in str(e)

def test_fr_bodacc_paginates_past_100():
    today = g.now().date().isoformat()
    total = 250

    def make_rec(i, person="pm"):
        return {
            "listepersonnes": json.dumps({"personne": {"typePersonne": person, "nom": f"Co{i}"}}),
            "jugement": json.dumps({"nature": "ouverture de liquidation judiciaire"}),
            "commercant": f"SOCIETE {i} SAS",
            "dateparution": today,
            "tribunal": "Paris",
            "url_complete": f"https://bodacc.example/{i}",
        }

    def fake_get(url):
        assert "offset=" in url and "limit=100" in url
        assert "dateparution>=" in urllib_unquote(url) or "dateparution%3E%3D" in url or "dateparution" in url
        qs = dict(x.split("=", 1) for x in url.split("?", 1)[1].split("&"))
        offset = int(qs["offset"]); limit = int(qs["limit"])
        assert limit == 100
        batch = [make_rec(offset + i) for i in range(min(limit, max(0, total - offset)))]
        # inject one natural person on first page; must be dropped
        if offset == 0 and batch:
            batch[0] = make_rec(0, person="pp"); batch[0]["commercant"] = "Jean Dupont"
        return json.dumps({"total_count": total, "results": batch}), 0.01, 200

    def urllib_unquote(u):
        import urllib.parse
        return urllib.parse.unquote(u)

    with mock.patch.object(g, "get", side_effect=fake_get), mock.patch.object(g.time, "sleep"):
        rows, secs, raw_or_total = g.fr_bodacc(days=2, page_size=100, max_pages=10)
    assert raw_or_total == total
    assert len(rows) == total - 1  # one pp dropped
    assert all(r["entity"] != "Jean Dupont" for r in rows)
    assert all(r["src"] == "fr_bodacc" for r in rows)

if __name__ == "__main__":
    test_cli_dedupe_and_window()
    test_uk_gazette_paginates_and_cache_busts()
    test_uk_gazette_raises_on_waf()
    test_fr_bodacc_paginates_past_100()
    print("ok")
