import os, tempfile, unittest
import world_situations as ws

class T(unittest.TestCase):
    def test_store_and_rank(self):
        d = tempfile.mkdtemp(); db = os.path.join(d, "t.db")
        self.assertEqual(ws.store(db), len(ws.SITUATIONS))
        self.assertEqual(ws.store(db), len(ws.SITUATIONS))  # idempotent
        rows = ws.top(db, 5)
        self.assertEqual(rows[0][0], "baywa_hybrid")
        self.assertTrue(all(r[6].startswith("https://") for r in rows))
    def test_unique_keys_and_sources(self):
        keys = [s[0] for s in ws.SITUATIONS]
        self.assertEqual(len(keys), len(set(keys)))
        for s in ws.SITUATIONS: self.assertTrue(s[7].startswith("https://") and s[8].startswith("2026"))
if __name__ == "__main__": unittest.main()
