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

