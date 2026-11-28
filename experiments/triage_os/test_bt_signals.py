import json, os, tempfile, unittest
import bt_signals as b

class T(unittest.TestCase):
    def test_prefiling(self):
        p = os.path.join(tempfile.mkdtemp(), "i.jsonl")
        rows = [("1", "2.04", "2020-01-10"), ("1", "1.03", "2020-06-01"), ("2", "2.04", "2021-01-01"),
                ("3", "3.01", "2020-02-01"), ("3", "1.03", "2023-01-01"), ("4", "1.03", "2022-01-01"), ("4", "2.04", "2022-03-01")]
        open(p, "w").write("\n".join(json.dumps({"cik": c, "name": c, "date": d, "items": [i]}) for c, i, d in rows))
        ev, _ = b.load_8k(p); r = b.prefiling(ev)
        a = r["2.04 acceleration"]
        self.assertEqual((a["flagged_issuers"], a["filed_ch11_within_540d"]), (2, 1))  # cik 4 flag is post-petition, dropped
        self.assertEqual(a["median_lead_days"], 143)
        self.assertEqual(r["3.01 delisting"]["filed_ch11_within_540d"], 0)  # outside horizon
        self.assertEqual(r["recall"]["ch11_8k_filers"], 3); self.assertEqual(r["recall"]["flagged_before"], 1)
    def test_cliff(self):
        m = {("A", "x"): {"q1": 95, "q2": 75, "q3": 50}, ("A", "y"): {"q1": 95, "q2": 94, "q3": 93},
             ("A", "z"): {"q1": 90, "q2": 40, "q3": 40}}
        r = b.mark_cliff(m)
        self.assertEqual((r["cliff_events"], r["fell_below_60_within_4q"], r["precision"]), (1, 1, 1.0))
        self.assertEqual(r["positions_that_broke_below_60"], 2); self.assertEqual(r["preceded_by_cliff"], 1)
if __name__ == "__main__": unittest.main()
