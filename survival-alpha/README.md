# Survival Alpha — Paper Lab

See `AGENT_TEAM.md` for the complete agentic-desk architecture.

This service is intentionally **paper-only**. It contains no wallet library, no private-key configuration, no transaction builder, and no execution endpoint.

## Endpoints

- `GET /health`
- `POST /paper/quote-drift`
- `GET /paper/quote-drift/summary`
- `POST /paper/backfill`
- `POST /paper/social/ingest`
- `GET /paper/social/signal/{mint}`
- `GET /paper/social/recent`
- `GET /paper/export/quote-drift.csv`

POST/export endpoints require `X-Paper-Token`.

## Required deployment secrets

- `JUPITER_API_KEY`
- `HELIUS_API_KEY`
- `PAPER_ADMIN_TOKEN`
- `DATABASE_URL` (optional; SQLite is the local fallback)

Set secrets only in the deployment provider. Never commit or paste them into chat.

## Gate before any Stage 1

Keep live trading absent until there are hundreds of forward observations, latency-adjusted profit factor exceeds 1.3, drawdown is inside the explicit cap, and observed slippage remains close to the paper model. Then test a separate ~$5 Stage 1 before the $50 wallet is ever enabled.


## Social layer

X and Reddit are candidate-generation and manipulation-detection inputs only.
They can never authorize execution.

Raw social post text is not persisted. The service stores provenance and a
normalized content fingerprint, then measures:

- unique-author velocity
- X/Reddit cross-source diversity
- duplicate/copied-promotion ratio
- new-account concentration
- engagement
- contract-address presence
- mention acceleration

A social candidate can only return `SAMPLE_QUOTES_ONLY`, which means the
next step is empirical Jupiter quote-drift measurement. See
`SOCIAL_SIGNAL_SPEC.md`.


## Realtime action engine

The service now runs an always-on event engine when `REALTIME_ENABLED=true`.

Sources:
- Telegram signal channels via Bot API or optional Telethon MTProto
- Helius Developer `transactionSubscribe` for watched-wallet buys
- PumpPortal creation/migration streams
- Jupiter `/tokens/v2/toporganicscore/5m`
- slower X/Reddit narrative context through the social/Work layer

Hot path:
1. candidate event arrives;
2. market phase is detected;
3. Pump bonding-curve quote or Jupiter graduated-market quote;
4. immediate hypothetical sell-back;
5. 500ms re-quote while Helius microstructure is collected;
6. risk governor vetoes unsafe candidates;
7. independent strategy agents vote;
8. passing candidates become `ACTIONABLE_PAPER`;
9. paper executor + Telegram operator controls handle the forward experiment.

No live transaction endpoint exists.

### Team endpoints

- `GET /team/manifest`
- `GET /team/channel-scorecards`
- `GET /team/strategy-scorecards`
- `GET /team/diagnostics`

### Realtime endpoints

- `GET /realtime/status`
- `GET /realtime/candidates`
- `GET /realtime/positions`
- `GET /realtime/evaluation`
- `POST /realtime/watch-wallet`
- `POST /realtime/paper-enter/{candidate_id}`
- `POST /realtime/paper-exit/{position_id}`

### Optional realtime secrets

- `PUMPPORTAL_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TG_BOT_SIGNAL_CHAT_IDS` — signal chats where the bot is present
- `TG_API_ID`, `TG_API_HASH`, `TG_SESSION_STRING` — optional Telethon mode
- `TG_SIGNAL_CHANNELS` — comma-separated MTProto signal sources
- `WATCH_WALLETS` — comma-separated; wallets can also be hot-added via API

Prefer bot mode where possible. For MTProto mode, create the session locally and
store it only in the deployment provider's secret store; a dedicated research
Telegram account is safer than a primary personal account.

### Research controls

- `PAPER_NOTIONAL_LAMPORTS=40000000`
- `MAX_ROUNDTRIP_COST_BPS=800`
- `MAX_ADVERSE_500_BPS=500`
- `JUPITER_ORGANIC_MIN=50`
- `MAX_OPEN_PAPER_POSITIONS=20`
- `PAPER_MAX_HOLD_SECS=300`
- `AUTO_PAPER=true`

These defaults are experiment thresholds, not claims of profitability. Change them only after forward results support doing so.

### Deployment

Use an always-on service in Render's Singapore region. The Blueprint uses
`0.5c-512mb`; the free plan is intentionally not used because sleeping a realtime
WebSocket process destroys the experiment.


Every candidate with an executable entry quote is marked again at the same
5-minute horizon, including candidates that were rejected. `/realtime/evaluation`
compares accepted versus rejected outcomes so the filter must prove that it
improves the base rate rather than merely generating attractive alerts.


## Strategy tournament

Every candidate is now scored by independent hypotheses rather than one opaque
model:

- `TRENCHER_ORGANIC`: mint/freeze authority off, no same-slot/buyer concentration,
  buyer diversity, two-sided flow, executable quote.
- `INDEPENDENT_WALLET_CONSENSUS`: at least two independently watched wallets plus
  sellability/latency gates.
- `POST_MIGRATION_SURVIVOR`: migration signal + organic activity + buyer diversity
  + executable quote.
- `ORGANIC_MIND_SHARE`: high Jupiter organic score confirmed by another source,
  while bundle and execution gates remain healthy.
- `TELEGRAM_CHANNEL_EDGE`: a Telegram source is allowed to become a strategy
  only after >=20 of our own forward samples, profit factor >1.3, and a positive
  95% bootstrap lower bound.

The thresholds are hypotheses. They are not assumed to be profitable.

`GET /realtime/strategy-evaluation` compares each strategy's 5-minute forward
outcomes when it passed versus when it failed. A strategy earns promotion only
from forward evidence.

Each candidate also stores a Helius microstructure snapshot containing recent
buy/sell counts, unique buyers/sellers, same-slot buy concentration, top-buyer
concentration, fee intensity, mint/freeze authority state, and top-account
concentration, alongside the actual Jupiter round-trip and 500ms quote drift.


## CI battle test

The branch CI compiles every Python agent, runs deterministic unit tests for the
Telegram parser, channel-evidence gate and strategy tournament, syntax-checks the
Pump quote sidecar, and fails if a Python private-key/send path or a Pump SDK
transaction-builder primitive is introduced.


## Simulated firm book

The project now keeps two separate books:

1. **Research book** — fixed-notional forward measurement. It exists to answer
   whether a signal/strategy contains information. It keeps counterfactuals and
   does not allocate capital based on confidence.
2. **Firm book** — capital-allocation simulation. It can open only when a
   currently-passing strategy has already earned promotion from prior forward
   outcomes. Telegram sources must independently earn channel promotion too.

The firm book has an independent veto-only risk governor:

- daily realized-loss kill switch
- maximum open positions
- maximum gross exposure
- maximum position size
- maximum source/channel concentration
- no duplicate open mint

Multi-horizon markouts are collected at 30s, 2m, 5m and 15m by default. This
lets the desk discover where each signal source actually has edge rather than
hard-coding a five-minute exit.

### Firm endpoints

- `GET /firm/status`
- `GET /firm/positions`
- `GET /firm/markouts`
- `GET /team/horizon-scorecards`

### Persistence

The Render Blueprint now provisions a Singapore Postgres database and injects
its private connection string into `DATABASE_URL`. The forward tape therefore
survives service redeploys; SQLite is only a local-development fallback.

### Capital promotion defaults

- minimum 30 prior forward samples
- profit factor > 1.30
- positive 95% bootstrap lower bound
- 2.5% simulated NAV base allocation
- 10% hard single-position ceiling
- 50% gross-exposure ceiling
- 25% per-source/channel ceiling
- 5% daily-loss kill switch

These are conservative experimental defaults, not optimal parameters and not
claims of expected returns.
