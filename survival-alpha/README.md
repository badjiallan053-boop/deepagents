# Survival Alpha — Paper Lab

This service is intentionally **paper-only**. It contains no wallet library, no private-key configuration, no transaction builder, and no execution endpoint.

## Endpoints

- `GET /health`
- `POST /paper/quote-drift`
- `GET /paper/quote-drift/summary`
- `POST /paper/backfill`
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
