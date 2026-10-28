import sqlite3
import unittest
import bigfund as b


class T(unittest.TestCase):
    def test_people(self):
        rec = {"n": "X Co", "hc": 100, "hcg": {"six_months": -20.0, "yoy": -5},
               "cx": [["A", "Interim Chief Financial Officer", "2026-03-01"], ["B", "CFO", "2023-01-01"],
                      ["C", "VP Sales", "2026-05-01"], ["D", "Chief Executive Officer", "2026-09-01"],
                      ["E", "Chief Revenue Officer (CRO)", "2026-06-01"], ["F", "Chief of Staff to CEO", "2026-04-01"],
                      ["G", "Interim CMO", "2026-04-01"]]}
        r = b.people_from_crust(rec, "2026-10-22", "u", "t")
        types = sorted(x["signal_type"] for x in r)
        self.assertEqual(types, ["cro_or_interim", "headcount_drop_six_months", "key_exec_new"])

    def test_digital(self):
        self.assertEqual(len(b.digital_from_crust({"n": "X", "jg": {"yoy": -0.9}}, "d", "u", "t")), 1)
        self.assertEqual(b.digital_from_crust({"n": "X", "jg": {"yoy": -0.2}}, "d", "u", "t"), [])
        self.assertEqual(b.digital_from_crust({"n": "X"}, "d", "u", "t"), [])

    def test_holders(self):
        h = [{"fund": "Oaktree", "form": "SCHEDULE 13G/A", "date": "2026-08-10",
              "names": ["SharonAI Holdings Inc.  (SHAZ)  (CIK 0002068385)", "Oaktree"], "url": "u"}]
        r = b.holder_rows(h, "t", watch=["sharonai"])
        self.assertEqual(r[0]["signal_type"], "amend_13G")
        self.assertIn("WATCHLIST", r[0]["detail"])

    def test_litigation(self):
        self.assertEqual(b.classify_litigation("T.E.C. Engineering, Inc. v. Peraton, Inc.", "190 Contract: Other", "Peraton"), "supplier_or_landlord_suit")
        self.assertEqual(b.classify_litigation("Saks Global Holdings LLC", "", "Saks Global"), "own_bankruptcy_or_petition")
        self.assertEqual(b.classify_litigation("Kaseya US LLC v. Project Orca", "830 Patent", "Kaseya"), "plaintiff_or_unrelated")

    def test_advisors_and_multi(self):
        self.assertEqual(b.advisor_mentions("Hertz taps PJT Partners; lenders hire Gibson Dunn"), ["PJT", "Gibson Dunn"])
        db = sqlite3.connect(":memory:")
        b.init(db)
        b.insert(db, "people_signals", [dict(entity="A", signal_type="x", detail="d", source_url="1")])
        b.insert(db, "litigation_signals", [dict(entity="a", signal_type="y", detail="d", source_url="2")])
        b.insert(db, "digital_signals", [dict(entity="B", signal_type="y", detail="d", source_url="3")])
        m = b.multi_source(db)
        self.assertEqual(len(m), 1)
        self.assertEqual(m[0][1], 2)


if __name__ == "__main__":
    unittest.main()
