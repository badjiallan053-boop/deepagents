import json, os, unittest
D = "/workspace/triage_os_data"
class TestTriageWorldV2(unittest.TestCase):
    def setUp(self): self.J = json.load(open(f"{D}/world.json"))
    def test_25_live_all_sourced(self):
        S = self.J["situations"]; self.assertEqual(len(S), 25)
        for s in S:
            self.assertTrue(s["chokepoint"] and s["checks"])
            self.assertIn(s["status"], ("VERIFIED-PRIMARY", "SECONDARY-LABELLED"))
            for c in s["checks"]: self.assertTrue(c["found"] and c["quote"] and c["fetched"].startswith("2026-10-23") or c["key"] == "bodacc")
    def test_kills_applied(self):
        names = " ".join(s["entity"] for s in self.J["situations"])
        for k in ("LVGEM", "China SCE", "Toys"): self.assertNotIn(k, names)
        self.assertIn("Booster", names)  # debate kill rejected on primary evidence
    def test_gap_only_with_current_price_and_recovery(self):
        for s in self.J["situations"]:
            if s["gap"] is not None: self.assertTrue(s["price"] and s["recovery"] and "STALE" not in s["price"]["kind"])
    def test_debtwire_and_scenarios(self):
        self.assertEqual(round(self.J["debtwire"]["total"] / 3), 39606)
        self.assertEqual([x["arr"] for x in self.J["scenarios"]], [146, 294, 920])
    def test_drafts(self):
        t = open(f"{D}/world/email_drafts_DO_NOT_SEND.txt").read()
        self.assertEqual(t.count("DO NOT SEND - DRAFT"), 8); self.assertTrue(t.startswith("DO NOT SEND - DRAFT"))
        for p in ("Highland", "Augmentum", "ION Group", "Antler", "Redalpine"): self.assertNotIn(f"To: [{p}", t)
if __name__ == "__main__": unittest.main()
