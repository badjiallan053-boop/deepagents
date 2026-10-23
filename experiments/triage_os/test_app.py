import importlib, os, sqlite3, sys, tempfile, unittest, json
class T(unittest.TestCase):
    def setUp(self):
        self.db = tempfile.mktemp(); c = sqlite3.connect(self.db)
        c.execute("create table cap_structures_top15(situation,issuer,tranche,amount_usd_m,coupon,maturity,lien,guarantors,covenants,agent_trustee,holder,mark,as_of,source_url,status)")
        c.execute("insert into cap_structures_top15 values('Hughes','Hughes Satellite Systems Corp','Senior Secured Notes',750,'5.25%','2026-08-01','1st lien','','','','','','2026-03-31','https://sec','VERIFIED')")
        c.execute("create table verification(claim_id,artifact,claim,status,primary_url,checked,method,fix)"); c.execute("insert into verification values('M1','m','Hughes filed 2 Aug 2026','VERIFIED','u','2026-10-22','m','')")
        c.execute("create table claims_calendar(case_name,court,agent,event,date,time_tz,state,source_url,status)"); c.execute("insert into claims_calendar values('Hughes Satellite Systems 26-90739','SDTX','Epiq','Hearing','2026-12-01','','scheduled','u','VERIFIED')")
        c.commit(); os.environ["TRIAGE_DB"] = self.db; os.environ["TRIAGE_HITLOG"] = tempfile.mktemp()
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app")); import server; self.s = importlib.reload(server)
    def test_graph(self):
        g = self.s.graph("Hughes Satellite Systems Corp"); kinds = {n["kind"] for n in g["nodes"]}
        self.assertIn("tranche", kinds); self.assertIn("gap", kinds); self.assertTrue(all(e["s"] and e["t"] for e in g["edges"]))
    def test_situations_timeline(self):
        h = [s for s in self.s.situations() if s["key"] == "hughes"][0]
        self.assertEqual([e["date"] for e in h["timeline"]], ["2026-08-02", "2026-12-01"]); self.assertEqual(h["facts"][0]["status"], "VERIFIED")
    def test_readonly(self):
        with self.assertRaises(sqlite3.OperationalError):
            sqlite3.connect(f"file:{self.db}?mode=ro", uri=True).execute("insert into verification values(1,2,3,4,5,6,7,8)")
    def test_hitlog_empty(self): self.assertEqual(self.s.hitlog()["count"], 0)
if __name__ == "__main__": unittest.main()
