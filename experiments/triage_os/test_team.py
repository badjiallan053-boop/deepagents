import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("team", Path(__file__).with_name("team.py"))
team = importlib.util.module_from_spec(spec)
spec.loader.exec_module(team)

SIGNAL = {"title": "Acme Corp — 8-K (items 1.03)", "entity": "Acme Corp",
          "url": "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/a.htm",
          "event_date": "2026-10-01", "signal_type": "8-K items 1.03", "source": "sec"}

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bus = team.bus_connect(Path(self.tmp.name) / "bus.db")
        self.store = team.CaseStore(Path(self.tmp.name) / "cases")
    def tearDown(self):
        self.bus.close(); self.tmp.cleanup()

class BusTests(Base):
    def post(self, **kw):
        args = dict(unknowns=[], skipped=[], risks=[]); args.update(kw)
        return team.post(self.bus, "c1", "credit_analyst", ["valuation"], "HANDOFF", "ANALYZE", "s", **args)

    def test_append_only(self):
        self.post()
        with self.assertRaises(sqlite3.DatabaseError):
            self.bus.execute("UPDATE bus SET summary='x'")
        with self.assertRaises(sqlite3.DatabaseError):
            self.bus.execute("DELETE FROM bus")

    def test_unsourced_claim_downgraded(self):
        m = self.post(claims=[{"text": "LTV 80%", "confidence": "verified"},
                              {"text": "x", "confidence": "verified", "source_url": "https://a", "as_of": "2026-10-01"}])
        self.assertEqual(m["claims"][0]["confidence"], "unknown")
        self.assertTrue(m["claims"][0]["downgraded"])
        self.assertEqual(m["claims"][1]["confidence"], "verified")

    def test_mandatory_footer_and_limits(self):
        with self.assertRaises(ValueError):
            team.post(self.bus, "c1", "a", ["b"], "HANDOFF", "p", "s", unknowns=[], skipped=[], risks=None)
        with self.assertRaises(ValueError):
            self.post(summary="w " * 201) if False else team.post(self.bus, "c1", "a", ["b"], "HANDOFF", "p", "w " * 201, unknowns=[], skipped=[], risks=[])
        with self.assertRaises(ValueError):
            team.post(self.bus, "c1", "a", ["b"], "GOSSIP", "p", "s", unknowns=[], skipped=[], risks=[])

    def test_only_human_posts_decision(self):
        with self.assertRaises(team.GateError):
            team.post(self.bus, "c1", "desk_lead", ["x"], "DECISION", "p", "s", unknowns=[], skipped=[], risks=[])

    def test_inbox_routing(self):
        self.post()
        self.assertEqual(len(team.messages(self.bus, "c1", to_role="valuation")), 1)
        self.assertEqual(len(team.messages(self.bus, "c1", to_role="buyer_matcher")), 0)

class CheckpointTests(Base):
    def test_only_desk_lead_mutates_and_lock(self):
        case = team.new_case(SIGNAL)
        (self.store.root / case["case_id"]).mkdir(parents=True)
        self.store.write(case["case_id"], team.DESK_LEAD, case)
        with self.assertRaises(team.GateError):
            self.store.write(case["case_id"], "credit_analyst", case)
        with self.store.lock(case["case_id"], team.DESK_LEAD):
            with self.assertRaises(team.GateError):
                self.store.write(case["case_id"], team.DESK_LEAD, case)

    def test_pipeline_checkpoints(self):
        case = team.DeskLead(self.bus, self.store).run(SIGNAL, {"bid_deadline": "2026-11-15"})
        self.assertEqual(case["status"], "AWAITING_HUMAN")
        self.assertEqual(case["gates"]["G1"], "advance")
        self.assertEqual(case["gates"]["G3"], "advance")
        self.assertEqual(case["gates"]["G5"], "escalate")
        self.assertEqual(case["revise_loops"], team.MAX_REVISE_LOOPS)
        self.assertEqual(case["deadlines"]["bid_deadline"], "2026-11-15")
        self.assertEqual(self.store.read(case["case_id"])["status"], "AWAITING_HUMAN")
        phases = [m["phase"] for m in team.messages(self.bus, case["case_id"])]
        self.assertEqual(phases[0], "DISCOVER"); self.assertEqual(phases[-1], "IC_PACK")

    def test_kill_needs_standard_reason(self):
        lead = team.DeskLead(self.bus, self.store)
        bad = dict(SIGNAL, url="http://insecure")
        case = lead.run(bad)
        self.assertEqual(case["status"], "KILLED")
        self.assertIn(case["rejection_reason"], team.REJECTION_REASONS)
        with self.assertRaises(ValueError):
            lead.kill(case, "BECAUSE", "x")

    def test_verifier_veto(self):
        out = team.verifier({}, [{"claims": [{"text": "x", "confidence": "verified"}], "unknowns": [], "risks": []}])
        self.assertFalse(out["payload"]["pass"])

class AbstentionTests(Base):
    def test_valuation_abstains_on_unknown(self):
        case = team.DeskLead(self.bus, self.store).run(SIGNAL)
        self.assertEqual(case["gates"]["G4"], "abstain")
        ab = [m for m in team.messages(self.bus, case["case_id"], mtype="ABSTAIN") if m["from"] == "valuation"]
        self.assertEqual(len(ab), 1)

    def test_valuation_runs_with_cited_inputs(self):
        def llm(role, case, inbox):
            if role in ("credit_analyst", "property_analyst"):
                return {"critical_inputs": {k: "verified" for k in team.CRITICAL_INPUTS}}
            if role == "contrarian":
                return {"veto": False}
            return {}
        case = team.DeskLead(self.bus, self.store, llm=llm).run(SIGNAL)
        self.assertEqual(case["gates"]["G4"], "advance")
        self.assertEqual(case["gates"]["G5"], "advance")
        self.assertEqual(case["revise_loops"], 0)

class FullReadTests(Base):
    def test_ic_pack_and_verifier_see_whole_case(self):
        case = team.DeskLead(self.bus, self.store).run(SIGNAL)
        msgs = team.messages(self.bus, case["case_id"])
        ver = [m for m in msgs if m["from"] == "verifier"][0]
        self.assertGreaterEqual(ver["payload"]["checked"], 2)   # scout + entity claims
        ic = [m for m in msgs if m["from"] == "ic_secretary"][0]
        self.assertIn("signal_scout", {c["from_role"] for c in ic["claims"]})
        for u in ("capital stack", "title", "sponsor/owner", "seller constraint"):
            self.assertIn(u, ic["unknowns"])

    def test_verifier_flags_non_https_source(self):
        inbox = [{"claims": [{"text": "x", "confidence": "verified", "source_url": "http://a", "as_of": "d"}]}]
        self.assertFalse(team.verifier({}, inbox)["payload"]["pass"])

class HumanGateTests(Base):
    def test_external_action_blocked_until_decision(self):
        case = team.DeskLead(self.bus, self.store).run(SIGNAL)
        with self.assertRaises(team.HumanGateRequired):
            team.external_action(self.bus, case["case_id"], "contact_seller")
        team.record_decision(self.bus, self.store, case["case_id"], "arslane", "APPROVE", ["request_documents"])
        with self.assertRaises(team.HumanGateRequired):
            team.external_action(self.bus, case["case_id"], "contact_seller")
        self.assertTrue(team.external_action(self.bus, case["case_id"], "request_documents")["permitted"])

    def test_human_reject_kills(self):
        case = team.DeskLead(self.bus, self.store).run(SIGNAL)
        c = team.record_decision(self.bus, self.store, case["case_id"], "arslane", "REJECT", note="no asset")
        self.assertEqual(c["rejection_reason"], "HUMAN_REJECTED")

class SpecialistTests(Base):
    def test_specialists_post_and_gate(self):
        ev = [{"signal": "bdc_asset_coverage", "entity": "X", "value": 145, "detail": "BELOW 170%", "source_url": "https://data.sec.gov/x", "as_of": "2026-06-30"},
              {"signal": "trade_claims_top20", "entity": "X", "value": 1, "detail": "free", "source_url": "https://www.courtlistener.com/d", "as_of": "2026-07-01"},
              {"signal": "exposure_10k_mention", "entity": "Y Corp", "value": 1, "detail": "10%", "source_url": "https://www.sec.gov/y", "as_of": "2026-02-01"}]
        lead = team.DeskLead(self.bus, self.store)
        case = team.new_case(dict(SIGNAL, evidence=ev))
        self.store.root.joinpath(case["case_id"]).mkdir(parents=True, exist_ok=True)
        case = lead._set(case)
        out = lead.specialist_pass(case)
        self.assertEqual([m["from"] for m in out], list(team.SPECIALISTS))
        self.assertEqual(out[0]["type"], "HANDOFF"); self.assertEqual(out[0]["payload"]["forced_seller_count"], 1)
        self.assertEqual(out[2]["payload"]["exposed"], ["Y Corp"])
        ir = out[3]
        self.assertTrue(ir["requires_human"]); self.assertTrue(ir["payload"]["draft"].startswith("DO NOT SEND - DRAFT"))
        with self.assertRaises(team.GateError):
            team.external_action(self.bus, case["case_id"], "send_investor_update")
    def test_abstain_without_evidence(self):
        case = team.new_case(SIGNAL)
        self.assertEqual(team.forced_seller_monitor(case, [])["type"], "ABSTAIN")
        self.assertEqual(team.trade_claims_desk(case, [])["type"], "ABSTAIN")
    def test_evidence_from_db(self):
        con = sqlite3.connect(":memory:")
        con.execute("create table signals2 (signal, entity, key, value, detail, source_url, as_of, status)")
        con.execute("insert into signals2 values ('cross_markdown','Pluralsight','pluralsight',19,'d','https://x','2026-06-30','U')")
        self.assertEqual(team.evidence_from_db(con, "%pluralsight%")[0]["signal"], "cross_markdown")

if __name__ == "__main__":
    unittest.main()
