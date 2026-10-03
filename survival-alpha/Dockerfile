FROM python:3.12-slim
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt package.json ./
RUN pip install --no-cache-dir -r requirements.txt \
    && npm install --omit=dev

COPY app.py realtime_engine.py social_signal.py elite_signals.py strategy_tournament.py telegram_parser.py telegram_signal_agent.py channel_evaluator.py agent_team.py pump_quote_service.mjs ./

ENV PYTHONUNBUFFERED=1
ENV PUMP_QUOTER_PORT=10001

CMD ["sh", "-c", "node pump_quote_service.mjs & uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
