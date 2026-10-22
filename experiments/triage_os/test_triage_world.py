import json, os, unittest
D = "/workspace/triage_os_data"
class TestTriageWorld(unittest.TestCase):
    def setUp(self): self.J = json.load(open(f"{D}/world.json"))
    def test_25_verified_non_us(self):
        S = self.J["situations"]; self.assertEqual(len(S), 25)
        self.assertTrue(all(s["status"].startswith("VERIFIED") and s["chokepoint"] and "US" != s["country"] for s in S))
    def test_buyers_backers(self):
        self.assertEqual(len(self.J["buyers"]), 30); self.assertEqual(sum(b["status"].startswith("VERIFIED") for b in self.J["backers"]), 15)
    def test_drafts_not_send(self):
        t = open(f"{D}/world/email_drafts_DO_NOT_SEND.txt").read(); blocks = t.split("\n\n\nDO NOT SEND")
        self.assertEqual(t.count("DO NOT SEND - DRAFT"), 8); self.assertTrue(t.startswith("DO NOT SEND - DRAFT"))
    def test_pdf(self):
        self.assertTrue(os.path.exists(os.path.join(os.path.dirname(__file__), "research/TRIAGE_World.pdf")))
if __name__ == "__main__": unittest.main()
