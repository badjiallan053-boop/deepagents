# Verifying the TRIAGE Alpha Committee paper ledger

PAPER-ONLY calls. No trades are placed, and the ledger is not investment advice.

Files
- `track_record.jsonl`: one JSON record per call. Each record holds `prev_hash` and `hash`, where `hash` = SHA-256 of the record (sorted keys, UTF-8) without the `hash` field.
- `<date>.anchor.txt`: contains the ledger's `last_hash` on that day (SGT).
- `<date>.anchor.txt.ots`: an OpenTimestamps proof of that file. Only its SHA-256 digest was sent to the public calendars (a/b.pool.opentimestamps.org, eternitywall, catallaxy).

Check it yourself
1. `pip install opentimestamps-client` (reference client: github.com/opentimestamps/opentimestamps-client)
2. `python3 verify_ledger.py`. This recomputes every hash and the chain, checks that each anchor's last_hash is in the ledger, and runs `ots verify`.
3. Until the calendars commit to Bitcoin (usually a few hours), `ots verify` reports "Pending confirmation". Run `ots upgrade ledger_proofs/<date>.anchor.txt.ots` later, then verify again. The proof then shows the Bitcoin block whose time bounds when the ledger existed.
4. Tampering: any edit to an earlier record changes its hash, which breaks every later `prev_hash` and the anchored `last_hash`.

Daily routine (operator): `python3 anchor_ledger.py && git add ledger_proofs && git commit -m "ledger anchor <date>"`, then push.
