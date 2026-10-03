# Survival Alpha: promotion blockers

GitHub issues are disabled on this repository, so this file is the tracked
list of promotion blockers from the Risk re-review (`pr-redteam-002`).

**Rule: no desk, scorecard, report or Grok summary may claim
RESEARCH_CANDIDATE, GATE4_ELIGIBLE, "PROMOTE", Gate 4, or any allocator
promotion until every box below is checked.** These block promotion claims,
not merging. Flags stay off and nothing is deployed until a separate Risk
sign-off.

Background and wiring plan: `/workspace/fixwork/stats-issue.md` (local working
note, "wire the shared `gate_stats` helper into every Survival Alpha
scorecard"); Risk review: `/workspace/desks/risk/pr-redteam-002.md`.

Close an item only with a commit/PR link and the test that proves it.

## Checklist

- [ ] **gate_stats everywhere.** Wire `gate_stats` into all realtime channel
  cards, the allocator and the special-situations scorecard (new
  `/special/scorecard`), with exclusions passed in (UNRESOLVED, MARK_FAILED,
  MISSED, LATE, no-entry-quote) and a minimum of **30 clusters**. Rename
  `PROMOTE`, which `channel_evaluator` still emits at n>=20 (iid rows).
  (stats-issue items 1-2; B1-2, X4, R2-9)
- [ ] **B4-1 funding position rules.** One open position per symbol (across
  strategies), plus a cool-down after exit.
- [ ] **Multiple testing.** Holm correction across buckets, or one
  pre-registered primary strategy (and horizon) written down before data is
  read.
- [ ] **Regime tags** on samples (X3).
- [ ] **Sensitivity runs** reported next to the base case:
  - notional / fee at 0.04 / 0.25 / 1 SOL, and network fee base-only vs
    505,000 lamports per tx (R2-5);
  - tender fee (special situations; commission currently defaults to 0);
  - special-situations placeholder loss at 15 / 30 / 50% (R2-7), plus a cap on
    the placeholder share of losses;
  - MARK_FAILED booked as -100%, and late rows included.
- [ ] **The 300 gate counts resolved.** Firm-level and desk 300 counts use
  deduplicated, resolved, non-excluded samples only (firm-primary clusters
  with an outcome at the primary horizon), not episode counts such as
  `counts.firm_primary`. (X5, R2-4)
- [ ] **PR #2 (special situations).** Fix event-loop blocking: run
  `extract_terms` off the loop (`asyncio.to_thread`) (X2); use the New York
  trading date instead of `utc_now().date()` (N2-4,
  `special_situations.py` ~707, 1287, 1343, 1389, 1454).

## Also open from the re-review (lower severity)

- [ ] R2-3: report a `no_entry_quote` count and rate as an exclusion reason.
- [ ] R2-6: "purchased without proration and with priority" is a negation
  false negative; add the fixture and scope negation to the priority phrase.
- [ ] R2-8: funding scorecard passes no `exclusions=`; rename the legacy iid
  `strategies`/`all` stats to `legacy_iid` (or drop them); consider ISO week
  alone as the cluster for the pooled `all` card; optional cluster-equal-weight
  mean.

## Already addressed (on the PR branches, pending merge)

- R2-1: Jupiter-entered tokens are exit-quoted on Jupiter, so a real rug is
  booked even when the pump sidecar is down (PR #1).
- R2-2: channel cards / allocator / realtime prior exclude `#accept`
  late-acceptance episodes (PR #1).
- R2-5: fee assumptions are labeled in `/realtime/status` and the scorecards
  (PR #1).
- R2-8 / item 9: a capped profit factor or zero losses yields status REVIEW,
  never a pass, in `gate_stats` (PR #5) and `channel_evaluator` (PR #1).
