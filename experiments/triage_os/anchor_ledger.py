"""Daily public anchor of the PAPER-ONLY committee ledger with OpenTimestamps (reference client,
github.com/opentimestamps/opentimestamps-client). Headless and idempotent — safe to run from cron/routine:
  * verifies the hash chain first (exit 2 if broken — never anchors a broken ledger);
  * copies the ledger to ledger_proofs/track_record.jsonl;
  * if today's (SGT) anchor already exists with the same last_hash → no new stamp (exit 0, 'unchanged');
    if the ledger grew since → rewrites today's anchor and re-stamps;
  * runs `ots upgrade` on older pending proofs (adds Bitcoin attestations once confirmed);
  * only a SHA-256 digest is sent to the public calendars. Exit 0 ok/unchanged, 1 stamp failed, 2 chain broken.
Optional: --commit  → git add ledger_proofs && git commit (push is left to the caller/routine)."""
import os, json, shutil, subprocess, datetime, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__)); P = f"{HERE}/ledger_proofs"; os.makedirs(P, exist_ok=True)
SRC = os.environ.get("TRIAGE_LEDGER", "/workspace/triage_os_data/committee/track_record.jsonl")
def ots_bin():
    for c in [os.environ.get("OTS"), shutil.which("ots"), os.path.expanduser("~/.local/bin/ots"), "/home/box/.local/bin/ots"]:
        if c and os.path.exists(c): return c
    return None
def main():
    sys.path.insert(0, HERE); import committee as C
    C.LEDGER = SRC
    ok, n = C.verify()
    if not ok: print(f"ABORT: ledger chain broken at record {n+1}"); return 2
    shutil.copy(SRC, f"{P}/track_record.jsonl")
    last = json.loads([l for l in open(SRC) if l.strip()][-1])["hash"]
    d = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
    f = f"{P}/{d}.anchor.txt"; body = f"TRIAGE Alpha Committee paper ledger\nrecords={n}\nlast_hash={last}\nanchored_sgt={d}\n"
    ots = ots_bin()
    if not ots: print("ERROR: ots client not found (pip install opentimestamps-client)"); return 1
    for old in sorted(glob.glob(f"{P}/*.anchor.txt.ots")):
        if not old.startswith(f): subprocess.run([ots, "upgrade", old], capture_output=True, text=True, timeout=120)
    if os.path.exists(f) and open(f).read() == body and os.path.exists(f + ".ots"):
        print(f"unchanged: {d} already anchored (records={n})"); rc = 0
    else:
        open(f, "w").write(body)
        if os.path.exists(f + ".ots"): os.remove(f + ".ots")
        rc = 1
        for attempt in range(3):
            r = subprocess.run([ots, "stamp", f], capture_output=True, text=True, timeout=180)
            if os.path.exists(f + ".ots"): rc = 0; break
        print(f"stamped {os.path.basename(f)} records={n} last_hash={last[:16]}…" if rc == 0 else f"STAMP FAILED: {r.stderr[-300:]}")
    if rc == 0 and "--commit" in sys.argv:
        subprocess.run(["git", "-C", HERE, "add", "ledger_proofs"], check=False)
        r = subprocess.run(["git", "-C", HERE, "diff", "--cached", "--quiet"])
        if r.returncode: subprocess.run(["git", "-C", HERE, "-c", "user.name=badjiallan053-boop", "-c", "user.email=badjiallan053@gmail.com", "commit", "-qm", f"ledger anchor {d}"], check=False)
    return rc
if __name__ == "__main__": sys.exit(main())
