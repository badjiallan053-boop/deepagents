"""Outsider verification of the TRIAGE paper ledger. Needs only Python 3 and (for step 3) the OpenTimestamps
client: pip install opentimestamps-client.
1) recompute every record's SHA-256 and the prev_hash chain; 2) check each anchor file's last_hash appears in
the ledger; 3) run `ots verify` / `ots info` on each .ots proof (Bitcoin attestation appears after ~1-6 h; a
pending proof shows calendar attestations only — run `ots upgrade` later)."""
import json, hashlib, glob, os, subprocess, sys
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledger_proofs")
def chain(path):
    prev = "0" * 64; hashes = []
    for i, l in enumerate(open(path)):
        r = json.loads(l); h = r.pop("hash")
        if r["prev_hash"] != prev: return False, f"record {i+1}: prev_hash mismatch", hashes
        if hashlib.sha256(json.dumps(r, sort_keys=True, ensure_ascii=False).encode()).hexdigest() != h: return False, f"record {i+1}: content altered", hashes
        prev = h; hashes.append(h)
    return True, f"{len(hashes)} records, chain intact", hashes
if __name__ == "__main__":
    ok, msg, hs = chain(f"{P}/track_record.jsonl"); print("chain:", ok, msg)
    for a in sorted(glob.glob(f"{P}/*.anchor.txt")):
        last = [l.split("=", 1)[1].strip() for l in open(a) if l.startswith("last_hash=")][0]
        print(os.path.basename(a), "last_hash in ledger:", last in hs)
        if os.path.exists(a + ".ots"):
            ots = os.environ.get("OTS", "ots")
            r = subprocess.run([ots, "verify", a + ".ots"], capture_output=True, text=True); out = (r.stdout + r.stderr).strip()
            print("  ots verify:", out.splitlines()[-1] if out else r.returncode)
    sys.exit(0 if ok else 1)
