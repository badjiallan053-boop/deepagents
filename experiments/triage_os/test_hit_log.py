import json, os, sqlite3, tempfile, unittest, hit_log as h
class T(unittest.TestCase):
    def test_chain_and_tamper(self):
        p = tempfile.mktemp(); h.append(p, {"kind": "a", "entity": "X"}); h.append(p, {"kind": "b", "entity": "Y"})
        self.assertEqual(h.verify_chain(p), (True, None))
        L = open(p).read().splitlines(); e = json.loads(L[0]); e["entity"] = "Z"; L[0] = json.dumps(e)
        open(p, "w").write("\n".join(L) + "\n"); self.assertEqual(h.verify_chain(p)[0], False)
    def test_precision(self):
        db = tempfile.mktemp(); c = sqlite3.connect(db)
        c.execute("create table bdc_marks(bdc,borrower,borrower_key,identifier,period,par,cost,fv,mark,source_url,status)")
        for i, q1, q2 in [("a", 70, 50), ("b", 75, 74), ("c", 95, 95), ("d", 99, 80)]:
            c.execute("insert into bdc_marks values('X','','',?, '2026-03-31',1,1,1,?,'','')", (i, q1)); c.execute("insert into bdc_marks values('X','','',?, '2026-06-30',1,1,1,?,'','')", (i, q2))
        c.commit(); r = h.precision_at_trade(db)
        self.assertEqual((r["signals"], r["hits"], r["precision"], r["base_rate"]), (2, 1, 0.5, 0.5))
if __name__ == "__main__": unittest.main()
