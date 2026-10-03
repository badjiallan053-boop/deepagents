FROM python:3.12-slim
WORKDIR /app
# Shared gate statistics (imported by funding_basis); own line to avoid merge conflicts.
COPY gate_stats.py ./

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt package.json ./
RUN pip install --no-cache-dir -r requirements.txt \
    && npm install --omit=dev

COPY app.py realtime_engine.py social_signal.py elite_signals.py strategy_tournament.py telegram_parser.py telegram_signal_agent.py channel_evaluator.py agent_team.py grok_team.py grok_profit_team.py funding_basis.py capital_allocator.py firm_risk.py firm_book.py pump_quote_service.mjs ./

ENV PYTHONUNBUFFERED=1
ENV PUMP_QUOTER_PORT=10001

CMD ["sh", "-c", "if [ -n \"$SOLANA_RPC_URL\" ] || [ -n \"$HELIUS_API_KEY\" ]; then node pump_quote_service.mjs & fi; exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
