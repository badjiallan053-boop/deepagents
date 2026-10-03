# Survival Alpha — Agentic Trading Desk

## Mission

Measure whether memecoin signals contain **executable** forward alpha after:
latency, fees, sellability, manipulation, market phase, and source quality.

The desk is paper-only. No agent can authorize a live transaction.

## Team

### 1. TELEGRAM_SCOUT
Two interchangeable ingestion modes:

- Bot API: for chats/channels where the bot is explicitly present and the chat ID
  is listed in `TG_BOT_SIGNAL_CHAT_IDS`.
- MTProto / Telethon: for channels the research account has joined. Requires a
  pre-authenticated `TG_SESSION_STRING`; the cloud service never asks for OTP.

Both modes use the same parser and forward-tape path. The first actionable
BUY/MENTION per channel/mint is measured; follow-up HOLD/SELL posts do not become
new entries.

### 2. WALLET_SCOUT
Helius `transactionSubscribe` observes the selected wallet set in real time.
Historical wallet PnL is not accepted as alpha. Every observed buy must survive
our own quote-drift and sellability checks.

### 3. PUMP_SCOUT
PumpPortal supplies creation/migration discovery. High-volume paid account/token
trade streams remain optional.

### 4. ORGANIC_SCOUT
Jupiter's recent organic-activity universe nominates candidates independently of
Telegram and wallet reputation.

### 5. NARRATIVE_SCOUT
ChatGPT Work / social adapters inspect X, Reddit, Telegram chatter and narratives.
This agent is deliberately off the sub-second hot path.

### 6. MICROSTRUCTURE_AGENT
For each candidate, Helius measures:
- recent buy/sell count
- unique buyers/sellers
- buy/sell balance
- same-slot buy concentration
- top-buyer concentration
- fee intensity
- mint/freeze authority
- top-account concentration

### 7. EXECUTION_QUALITY_AGENT
The actual market phase determines the quote engine:
- Pump bonding curve -> local quote-only Pump SDK sidecar
- graduated/routable -> Jupiter Swap V2 order

It measures:
- hypothetical entry
- immediate sell-back
- round-trip cost
- 500 ms quote decay
- market phase and graduation state

### 8. RISK_GOVERNOR
Hard vetoes execute before any strategy vote can matter. Examples:
- mint/freeze authority still enabled
- severe same-slot/buyer concentration
- insufficient buyer diversity
- unacceptable sellability
- unacceptable 500 ms adverse drift

### 9. STRATEGY_TOURNAMENT
Independent hypotheses compete on the same forward tape:

- TRENCHER_ORGANIC
- INDEPENDENT_WALLET_CONSENSUS
- POST_MIGRATION_SURVIVOR
- ORGANIC_MIND_SHARE
- TELEGRAM_CHANNEL_EDGE

No aggregate LLM confidence score can override the risk governor.

### 10. PAPER_EXECUTOR
Only `ACTIONABLE_PAPER` candidates receive a paper entry from the executable
quote. Position marks are executable sell quotes, not candle closes.

### 11. COUNTERFACTUAL_AGENT
Every accepted and rejected candidate is marked at the same research horizon.
This prevents the desk from learning only from trades it chose to take.

### 12. CHANNEL_FORENSICS
Every Telegram channel gets its own scorecard from OUR delayed fills:
- n
- mean / median return
- profit factor
- positive rate
- large-loss rate
- 95% bootstrap lower bound for mean return

A channel is not promoted from reputation, subscriber count, screenshots, or
claimed win rate.

### 13. META_ALLOCATOR
Default promotion gate:
- at least 20 forward samples
- profit factor > 1.30
- positive bootstrap 95% lower bound

Until then, status is COLLECT. Failing mature sources become REJECT_OR_REWORK.

### 14. WORK_SUPERVISOR
ChatGPT Work is the desk's slow-thinking supervisor:
- inspect strategy/channel scorecards
- search X/Reddit for narrative explanations
- inspect GitHub/logs when a subsystem degrades
- propose parameter/code changes
- compare pre-bonding vs post-migration regimes
- kill strategies whose forward separation disappears

Work does NOT sign or submit trades and should not own a private key.

## Telegram signal security

For MTProto monitoring, use a dedicated research Telegram account where possible.
Create the session locally and place the resulting string directly into the
deployment provider's secret field. Do not paste the session string, API hash,
bot token, or OTP into chat.

Bot mode is safer and should be preferred whenever the target channel/group can
add the bot.

## Evidence hierarchy

1. Forward executable outcomes
2. Counterfactual accepted-vs-rejected separation
3. Channel/strategy bootstrap confidence
4. Historical replay
5. Reported trader/channel PnL
6. Social screenshots

Lower items can nominate hypotheses but never override higher evidence.

## GitHub patterns used

The implementation is independent code, but the architecture deliberately
borrows tested patterns from public projects:

- Hummingbot Condor: multi-agent isolation, deterministic routines, auditability,
  Telegram control surface.
- solana-signal-trader: per-channel parsing, hard-gate-first design, replay-gated
  self-tuning, rollback mindset, channel-specific configuration.
- signal-backtest-harness: first-call-per-mint measurement, latency-honest fills,
  dead-token denominator, profit-factor/confidence gating.
- solana-narrative-scanner: social adapters, fingerprinting, promoter/source
  tracking, queue-oriented signal processing.

No AGPL source code from solana-signal-trader is vendored into this repository.

## Current operating state

- LIVE EXECUTION: unavailable
- WALLET KEY: absent
- PAPER AUTO-ENTRY: available
- TELEGRAM BOT INGESTION: available when configured
- TELEGRAM MTProto INGESTION: available when configured
- PUMP BONDING-CURVE QUOTING: available
- JUPITER POST-MIGRATION QUOTING: available
- HELIUS WALLET STREAM: available
- STRATEGY TOURNAMENT: available
- COUNTERFACTUAL EVALUATION: available

## Key endpoints

- `GET /team/manifest`
- `GET /team/channel-scorecards`
- `GET /team/strategy-scorecards`
- `GET /team/diagnostics`
- `GET /realtime/status`
- `GET /realtime/candidates`
- `GET /realtime/positions`
- `GET /realtime/evaluation`
- `GET /realtime/strategy-evaluation`
- `POST /realtime/watch-wallet`

## Promotion to a future Stage 1

A live signer is a separate future component. Do not add it to this process.
A Stage-1 experiment should only be considered after the forward tape shows
repeatable separation and the measured execution model remains close to actual
quotes. The first Stage-1 bankroll remains isolated and tiny.


### 15. PORTFOLIO_MANAGER
Runs a second, simulated fund book. Research candidates are never given capital
merely because they passed today's gate. A currently passing strategy must first
have been PROMOTED from prior forward samples. Telegram channels must earn the
same promotion independently.

### 16. FIRM_RISK
Portfolio-level veto that sits above the allocator. It enforces daily loss,
gross exposure, single-position, source/channel concentration, open-position and
duplicate-mint limits. It cannot generate a trade.

### 17. MARKOUT_AGENT
Marks every candidate at fixed 30s / 2m / 5m / 15m executable exit horizons.
This reveals whether an edge is only theoretical at fast horizons or persists
long enough for our infrastructure to capture.

## Book structure

```
SCOUTS -> RISK/STRATEGY -> RESEARCH BOOK -> FORWARD EVIDENCE
                                      |
                                      v
                              PROMOTION GATE
                                      |
                                      v
                              CAPITAL ALLOCATOR
                                      |
                                      v
                                FIRM RISK
                                      |
                                      v
                           SIMULATED FUND BOOK
```

The research book and firm book must never be conflated. The research book asks
"does information exist?" The firm book asks "would we allocate scarce capital
to this already-proven edge under portfolio constraints?"
