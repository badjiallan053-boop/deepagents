import os, sys, unittest, sqlite3, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "research"))
import hughes_note as hn

class TestDesign(unittest.TestCase):
    def test_badge_and_charts(self):
        self.assertIn("b-VERIFIED", design.badge("VERIFIED; x"))
        svg = design.grouped_bars(["a"], [("s", "#000", [50])], ref_lines=[(85.6, "FV", "#f00")])
        self.assertTrue(svg.startswith("<svg") and "FV" in svg)
        self.assertIn("<svg", design.timeline_svg([("2026-08-02", "Petition", False), ("2026-12-01", "Hearing", True)], "2026-07-01", "2026-12-31"))
        self.assertIn("50.0%", design.stacked([("a", 1, "#000"), ("b", 1, "#111")]))

class TestHughesModel(unittest.TestCase):
    def test_capital_bridge(self):
        self.assertAlmostEqual(hn.SEC_3P + hn.SEC_ECHO, hn.SEC_TOTAL, places=1)   # 627.3 + 122.7 = 750 (10-Q bridge)
        self.assertAlmostEqual(hn.SEC_TOTAL + hn.J3_ADV, 800.0)                   # Dkt 320 'approximately $800 million'
    def test_subordination_helps_third_party_secured(self):
        for c in hn.EV:
            self.assertGreaterEqual(hn.recover(c, True)["sec"], hn.recover(c, False)["sec"])
        self.assertEqual(hn.recover("High", False)["sec"], 100.0)
        self.assertEqual(hn.recover("Low", False)["uns"], 0.0)
    def test_every_fact_has_url_and_token(self):
        for fid, claim, doc, tok, kind in hn.FACTS:
            self.assertTrue(hn.U[doc].startswith("https://")); self.assertTrue(len(tok) > 8); self.assertIn(kind, ("fact", "allegation", "proposal"))
    def test_verify_flags_missing_cache(self):
        old = hn.CACHE; hn.CACHE = tempfile.mkdtemp()
        try: self.assertTrue(all(r["status"] == "UNVERIFIABLE" for r in hn.verify().values()))
        finally: hn.CACHE = old

class TestServerEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = tempfile.mkdtemp(); cls.db = os.path.join(d, "t.db"); c = sqlite3.connect(cls.db)
        c.execute("create table bdc_marks(bdc,borrower,borrower_key,identifier,period,par,fv,mark,source_url)")
        c.execute("create table bdc_marks_hist(bdc,borrower,borrower_key,identifier,period,par,fv,mark,source_url)")
        c.execute("insert into bdc_marks values('ARCC','Acme Software Inc','acme software','TL','2026-06-30',100e6,40e6,40,'https://sec.gov/x')")
        c.execute("insert into bdc_marks_hist values('ARCC','Acme Software Inc','acme software','TL','2026-03-31',100e6,80e6,80,'https://sec.gov/y')")
        c.execute("create table cap_structures_top15(situation,issuer,tranche,amount_usd_m,coupon,maturity,lien,guarantors,covenants,agent_trustee,holder,mark,as_of,source_url,status)")
        c.execute("insert into cap_structures_top15 values('Hughes 26-90739','HSSC','Senior Secured Notes',750,'5.25%','2026-08-01','1st lien','','','','','','2026-03-31','https://sec.gov/z','VERIFIED')")
        c.commit()
        os.environ["TRIAGE_DB"] = cls.db
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))
        import importlib, server; cls.s = importlib.reload(server); cls.s._DIST = None
    def test_distressed_hist_and_change(self):
        r = self.s.distressed()[0]
        self.assertEqual(r["mark"], 40.0); self.assertEqual(r["chg_q"], -40.0); self.assertEqual(len(r["hist"]), 2); self.assertEqual(r["qa"], "ok")
    def test_marks_and_cap(self):
        self.assertIn("ARCC", self.s.marks_history("acme"))
        self.assertEqual(self.s.cap("Hughes")[0]["amount_usd_m"], 750)

if __name__ == "__main__": unittest.main()
