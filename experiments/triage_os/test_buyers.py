import csv, os, tempfile, unittest
import buyers

class T(unittest.TestCase):
    def test_build(self):
        out = os.path.join(tempfile.mkdtemp(), "b.csv"); rows = buyers.build(None, out)
        self.assertGreaterEqual(len(rows), 140)
        self.assertEqual(len({r["firm"] for r in rows}), len(rows))
        self.assertTrue(all(r["type"] in buyers.TYPES and r["evidence_url"].startswith("https://") for r in rows))
        self.assertEqual([r["rank"] for r in rows], list(range(1, len(rows)+1)))
        self.assertEqual(len(list(csv.DictReader(open(out)))), len(rows))
if __name__ == "__main__": unittest.main()
