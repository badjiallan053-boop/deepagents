import json, os, sqlite3, tempfile, unittest
from pathlib import Path
import world, desk

FX = Path(__file__).parent / "fixtures" / "world"
def fx(name): return (FX / name).read_text(encoding="utf-8")

class TestWorld(unittest.TestCase):
    def test_bodacc_companies_only(self):
        res = json.loads(fx("bodacc.json"))["results"]
        sigs = [s for s in map(world.parse_bodacc, res) if s]
        self.assertEqual(len(sigs), 1)  # 3 natural persons dropped
        self.assertNotIn("REDACTED", json.dumps(sigs))
        self.assertEqual(sigs[0]["country"], "FR")
        self.assertTrue(sigs[0]["url"].startswith("https://"))

    def test_fr_taxonomy(self):
        self.assertEqual(world.fr_procedure("Jugement arrêtant le plan de cession"), "asset_sale")
        self.assertEqual(world.fr_procedure("Jugement d'ouverture d'une procédure de redressement judiciaire"), "administration_reorg")
        self.assertEqual(world.fr_procedure("Clôture pour insuffisance d'actif de la liquidation"), "closure")

    def test_gazette_drops_personal(self):
        sigs = [s for s in map(world.parse_gazette, json.loads(fx("gazette.json"))["entry"]) if s]
        self.assertEqual(len(sigs), 3)
        self.assertTrue(all(s["notice_code"].startswith("24") for s in sigs))
        self.assertEqual(world.uk_procedure("Appointment of Administrators", "2410"), "administration_reorg")
        self.assertEqual(world.uk_procedure("Petitions to Wind Up (Companies)", "2450"), "winding_up_petition")

    def test_asx_filter(self):
        items = json.loads(fx("asx.json"))["data"]["items"]
        sigs = [s for s in map(world.parse_asx, items) if s]
        va = [s for s in sigs if s["symbol"] == "XYZ"][0]
        self.assertEqual(va["procedure"], "administration_reorg")
        self.assertEqual(va["score"], 35 + 25 + 10)

    def test_hkex(self):
        rows = json.loads(json.loads(fx("hkex.json"))["result"])
        sigs = [world.parse_hkex(r, "WINDING UP") for r in rows]
        self.assertTrue(sigs and all(s["listed"] and s["url"].startswith("https://www1.hkexnews.hk") for s in sigs))
        self.assertRegex(sigs[0]["event_date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_hkex_privatisation_scheme_dropped(self):
        self.assertIsNone(world.parse_hkex({"NEWS_ID": "2", "TITLE": "PROPOSED PRIVATISATION BY WAY OF SCHEME", "DATE_TIME": "20/10/2026 10:00", "FILE_LINK": "/b.pdf"}, "RESTRUCTURING"))
        row = {"NEWS_ID": "1", "TITLE": "DELAY IN DESPATCH OF THE SCHEME DOCUMENT", "DATE_TIME": "20/10/2026 10:00",
               "STOCK_NAME": "X", "STOCK_CODE": "1", "FILE_LINK": "/a.pdf", "LONG_TEXT": "Privatisation"}
        self.assertIsNone(world.parse_hkex(row, "SCHEME OF ARRANGEMENT"))
        row["TITLE"], row["LONG_TEXT"] = "SCHEME OF ARRANGEMENT OF OFFSHORE DEBT", ""
        self.assertEqual(world.parse_hkex(row, "SCHEME OF ARRANGEMENT")["procedure"], "scheme_ccaa")

    def test_tdb_debt_and_procedure(self):
        sigs = world.parse_tdb(fx("tdb.html"))
        self.assertTrue(sigs)
        self.assertEqual(world.jp_debt_oku("負債132億円"), 132)
        self.assertAlmostEqual(world.jp_debt_oku("負債60億4535万円"), 60.4535)
        self.assertEqual(world.jp_procedure("民事再生法の適用を申請"), "administration_reorg")
        self.assertEqual(world.jp_procedure("破産手続き開始決定受ける"), "liquidation")

    def test_companies_house_needs_key(self):
        os.environ.pop("CH_API_KEY", None)
        self.assertIsNone(world.companies_house_profile("01234567"))
        p = world.companies_house_profile("01234567", key="k",
              fetch=lambda u: json.dumps({"company_status": "administration", "sic_codes": ["68209"]}))
        self.assertEqual(p["company_status"], "administration")

    def test_store_and_rank(self):
        with tempfile.TemporaryDirectory() as d:
            con = desk.connect(Path(d) / "t.db")
            a = world.make("FR", "fr_bodacc", "1", "Acme SAS", "Acme: cession", "https://x/1", "2026-10-20", "asset_sale")
            b = world.make("FR", "fr_bodacc", "2", "Acme SAS", "Acme: LJ", "https://x/2", "2026-10-20", "liquidation")
            bad = world.make("FR", "fr_bodacc", "3", "Bad", "no url", "http://x", "2026-10-20", "liquidation")
            self.assertEqual(world.store_all(con, [a, b, bad]), 2)
            world.store_all(con, [a])  # idempotent
            rows = world.rank_world(con)
            self.assertEqual(len(rows), 1)  # deduped by entity
            self.assertEqual(rows[0]["procedure"], "asset_sale")
            for i in range(5):
                world.store_all(con, [world.make("UK", "uk_gazette", str(i), f"Co{i} Ltd", "t", "https://g/" + str(i), "2026-10-20", "administration_reorg")])
            capped = world.rank_world(con, per_country=2)
            self.assertEqual(sum(r["country"] == "UK" for r in capped), 2)

if __name__ == "__main__":
    unittest.main()
