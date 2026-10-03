# Survival Alpha — Paper Lab

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
- Helius Developer `transactionSubscribe` for watched-wallet buys
- PumpPortal migration stream (and optionally new-token stream)
- Jupiter `/tokens/v2/toporganicscore/5m`

Hot path:
1. candidate event arrives;
2. Jupiter WSOL->token executable quote;
3. immediate token->WSOL sell-back quote;
4. 500ms WSOL->token re-quote;
5. deterministic sellability + latency gate;
6. passing candidates become `ACTIONABLE_PAPER`;
7. Telegram sends `PAPER ENTER / REJECT / OPEN JUPITER`.

No live transaction endpoint exists.

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
- `WATCH_WALLETS` (comma-separated; wallets can also be hot-added via API)

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
