import os, re, unittest, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "research"))
import control_bottleneck as cb, cmbs_control

class VotingMath(unittest.TestCase):
    def test_thresholds(self):
        self.assertAlmostEqual(cb.block_threshold(750), 250.0)
        self.assertTrue(cb.can_carry(500, 750)); self.assertFalse(cb.can_carry(499.9, 750))
    def test_hughes_classes(self):
        c = {x["cls"][:22]: x for x in cb.hughes_classes()}
        full = c["Secured Notes, all hol"]; ex = c["Secured Notes, EchoSta"]; uns = c["6.625% Senior Notes (u"]
        self.assertTrue(full["group_blocks"]); self.assertFalse(full["group_carries"]); self.assertFalse(full["insider_blocks"])
        self.assertTrue(ex["group_carries"]); self.assertFalse(ex["outside_can_block"])
        self.assertAlmostEqual(ex["block"], 209.1, places=1)
        self.assertFalse(uns["outside_can_block"]); self.assertAlmostEqual(uns["cost"], 145.0, places=1)
        # EchoStar + outside float can block the full class if not designated
        self.assertGreater(full["insider"] + full["outside"], full["block"])

class CmbsParse(unittest.TestCase):
    def test_parse_directing_holder(self):
        r = cmbs_control.parse("Historical Bond Detail 24 Directing Certificateholder Cytium Investment Management Interest Shortfall Detail")
        self.assertIn("Cytium Investment Management", str(r))

if __name__ == "__main__": unittest.main()
