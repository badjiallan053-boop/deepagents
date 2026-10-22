"""Daily public anchor of the PAPER-ONLY committee ledger with OpenTimestamps (reference client,
github.com/opentimestamps/opentimestamps-client). Only a SHA-256 digest of a small text file containing the
ledger's last hash is sent to the public OTS calendars — no ledger content leaves the box.
Outputs (committed): ledger_proofs/track_record.jsonl (copy of the ledger), ledger_proofs/<date>.anchor.txt,
ledger_proofs/<date>.anchor.txt.ots."""
import os, json, shutil, subprocess, datetime, sys
HERE = os.path.dirname(os.path.abspath(__file__)); P = f"{HERE}/ledger_proofs"; os.makedirs(P, exist_ok=True)
SRC = "/workspace/triage_os_data/committee/track_record.jsonl"
def main():
    sys.path.insert(0, HERE); import committee as C
    ok, n = C.verify(); assert ok, "ledger chain broken — refusing to anchor"
    shutil.copy(SRC, f"{P}/track_record.jsonl")
    last = json.loads(open(SRC).read().splitlines()[-1])["hash"]
    d = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
    f = f"{P}/{d}.anchor.txt"
    open(f, "w").write(f"TRIAGE Alpha Committee paper ledger\nrecords={n}\nlast_hash={last}\nanchored_sgt={d}\n")
    if os.path.exists(f + ".ots"): os.remove(f + ".ots")
    r = subprocess.run([os.path.expanduser("~/.local/bin/ots"), "stamp", f], capture_output=True, text=True)
    print(r.stdout, r.stderr); return f
if __name__ == "__main__": main()
