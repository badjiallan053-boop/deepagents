# Node 20 pinned from the official image (Debian's apt nodejs is Node 18 on
# bookworm and drifts with the base image); the Python base stays as before.
FROM node:20.19.2-bookworm-slim AS nodebin
FROM python:3.12-slim
WORKDIR /app

# The official node binary links libstdc++/libgcc_s; make sure they exist.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=nodebin /usr/local/bin/node /usr/local/bin/node
COPY --from=nodebin /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version | grep -q '^v20\.'

COPY requirements.txt package.json package-lock.json ./
RUN pip install --no-cache-dir -r requirements.txt \
    && npm ci --omit=dev --ignore-scripts --no-audit --no-fund

COPY app.py realtime_engine.py social_signal.py elite_signals.py strategy_tournament.py telegram_parser.py telegram_signal_agent.py channel_evaluator.py agent_team.py grok_team.py grok_profit_team.py funding_basis.py capital_allocator.py firm_risk.py firm_book.py pump_quote_service.mjs ./

ENV PYTHONUNBUFFERED=1
ENV PUMP_QUOTER_PORT=10001
# Separate line so PRs editing the module COPY list above do not conflict.
COPY pump_quote_math.mjs ./

CMD ["sh", "-c", "if [ -n \"$SOLANA_RPC_URL\" ] || [ -n \"$HELIUS_API_KEY\" ]; then node pump_quote_service.mjs & fi; exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
