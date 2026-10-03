from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
import websockets
from sqlalchemy import text

from elite_signals import elite_verdict, microstructure_snapshot
from strategy_tournament import evaluate_tournament
from channel_evaluator import evaluate_outcomes
from telegram_parser import TelegramCall, parse_telegram_message
from telegram_signal_agent import TelegramSignalAgent

log = logging.getLogger("survival-alpha.realtime")

WSOL_MINT = "So11111111111111111111111111111111111111112"
JUPITER_ORDER_URL = "https://api.jup.ag/swap/v2/order"
JUPITER_ORGANIC_URL = "https://api.jup.ag/tokens/v2/toporganicscore/5m"
PUMPPORTAL_WS_BASE = "wss://pumpportal.fun/api/data"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _now_utc() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def ensure_realtime_tables(engine) -> None:
    sqlite = str(engine.url).startswith("sqlite")
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if sqlite else "BIGSERIAL PRIMARY KEY"
    bool_type = "INTEGER" if sqlite else "BOOLEAN"
    with engine.begin() as cx:
        cx.execute(text(f"""
        CREATE TABLE IF NOT EXISTS realtime_candidate (
            id {pk},
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            mint TEXT NOT NULL,
            source TEXT NOT NULL,
            source_detail TEXT,
            source_signature TEXT,
            source_wallet TEXT,
            source_slot BIGINT,
            notional_lamports BIGINT NOT NULL,
            buy_out_amount TEXT,
            sellback_out_lamports TEXT,
            roundtrip_bps DOUBLE PRECISION,
            drift_500_bps DOUBLE PRECISION,
            price_impact DOUBLE PRECISION,
            organic_score DOUBLE PRECISION,
            strategy_score DOUBLE PRECISION,
            microstructure_json TEXT,
            strategy_votes_json TEXT,
            signal_published_at_utc TEXT,
            signal_age_ms DOUBLE PRECISION,
            market_phase TEXT,
            market_data_json TEXT,
            decision TEXT NOT NULL,
            reason TEXT,
            paper_entered {bool_type} NOT NULL DEFAULT 0,
            outcome_5m_bps DOUBLE PRECISION,
            outcome_checked_at_utc TEXT,
            UNIQUE(source, source_signature, mint)
        )
        """))
        cx.execute(text(f"""
        CREATE TABLE IF NOT EXISTS paper_position (
            id {pk},
            candidate_id BIGINT NOT NULL,
            opened_at_utc TEXT NOT NULL,
            closed_at_utc TEXT,
            mint TEXT NOT NULL,
            cost_lamports BIGINT NOT NULL,
            token_amount TEXT NOT NULL,
            latest_value_lamports TEXT,
            latest_pnl_bps DOUBLE PRECISION,
            realized_value_lamports TEXT,
            realized_pnl_bps DOUBLE PRECISION,
            status TEXT NOT NULL,
            telegram_message_id BIGINT
        )
        """))
        cx.execute(text(f"""
        CREATE TABLE IF NOT EXISTS watch_wallet (
            wallet TEXT PRIMARY KEY,
            enabled {bool_type} NOT NULL DEFAULT 1,
            label TEXT,
            created_at_utc TEXT NOT NULL
        )
        """))
        # Lightweight forward-compatible migrations for already-created paper DBs.
        for ddl in (
            "ALTER TABLE realtime_candidate ADD COLUMN outcome_5m_bps DOUBLE PRECISION",
            "ALTER TABLE realtime_candidate ADD COLUMN outcome_checked_at_utc TEXT",
            "ALTER TABLE realtime_candidate ADD COLUMN strategy_score DOUBLE PRECISION",
            "ALTER TABLE realtime_candidate ADD COLUMN microstructure_json TEXT",
            "ALTER TABLE realtime_candidate ADD COLUMN strategy_votes_json TEXT",
            "ALTER TABLE realtime_candidate ADD COLUMN signal_published_at_utc TEXT",
            "ALTER TABLE realtime_candidate ADD COLUMN signal_age_ms DOUBLE PRECISION",
            "ALTER TABLE realtime_candidate ADD COLUMN market_phase TEXT",
            "ALTER TABLE realtime_candidate ADD COLUMN market_data_json TEXT",
        ):
            try:
                cx.execute(text(ddl))
            except Exception:
                pass


@dataclass
class CandidateEvent:
    mint: str
    source: str
    detail: str = ""
    signature: str = ""
    wallet: str = ""
    slot: int = 0
    organic_score: Optional[float] = None
    published_at_utc: str = ""


class RealtimeEngine:
    """
    Real-time candidate engine.

    Hot path:
      source event -> Jupiter buy quote -> immediate sell-back quote ->
      500ms re-quote -> deterministic gate -> action queue / Telegram.

    It has no wallet key and no transaction-submit method.
    """

    def __init__(self, engine):
        self.engine = engine
        ensure_realtime_tables(engine)
        self.enabled = _env_bool("REALTIME_ENABLED", False)
        self.notional = _env_int("PAPER_NOTIONAL_LAMPORTS", 40_000_000)
        self.max_roundtrip_cost_bps = _env_float("MAX_ROUNDTRIP_COST_BPS", 800.0)
        self.max_adverse_500_bps = _env_float("MAX_ADVERSE_500_BPS", 500.0)
        self.organic_min = _env_float("JUPITER_ORGANIC_MIN", 50.0)
        self.organic_poll_secs = _env_float("JUPITER_ORGANIC_POLL_SECS", 20.0)
        self.candidate_cooldown_secs = _env_float("CANDIDATE_COOLDOWN_SECS", 60.0)
        self.position_poll_secs = _env_float("PAPER_POSITION_POLL_SECS", 5.0)
        self.paper_max_hold_secs = _env_float("PAPER_MAX_HOLD_SECS", 300.0)
        self.auto_paper = _env_bool("AUTO_PAPER", False)
        self.max_open_paper = _env_int("MAX_OPEN_PAPER_POSITIONS", 20)

        self.jupiter_key = os.getenv("JUPITER_API_KEY", "").strip()
        self.helius_key = os.getenv("HELIUS_API_KEY", "").strip()
        self.helius_rpc_url = (
            os.getenv("HELIUS_RPC_URL", "").strip()
            or (f"https://mainnet.helius-rpc.com/?api-key={self.helius_key}" if self.helius_key else "")
        )
        self.pumpportal_key = os.getenv("PUMPPORTAL_API_KEY", "").strip()
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self.bot_signal_chat_ids = {
            x.strip() for x in os.getenv("TG_BOT_SIGNAL_CHAT_IDS", "").split(",") if x.strip()
        }
        self.pump_quoter_url = os.getenv(
            "PUMP_QUOTER_URL", "http://127.0.0.1:10001"
        ).rstrip("/")

        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._seen: dict[str, float] = {}
        self._http: Optional[httpx.AsyncClient] = None
        self._watchlist_version = 0
        self._telegram_offset = 0
        self._tg_signal_agent = TelegramSignalAgent(self._handle_telegram_call)

    async def start(self) -> None:
        if not self.enabled:
            log.warning("REALTIME_ENABLED=false; realtime engine is idle")
            return
        if not self.jupiter_key:
            log.error("JUPITER_API_KEY missing; realtime engine cannot score candidates")
            return

        self._http = httpx.AsyncClient(timeout=12.0)
        self._tasks = [
            asyncio.create_task(self._organic_loop(), name="jupiter-organic"),
            asyncio.create_task(self._position_loop(), name="paper-positions"),
            asyncio.create_task(self._counterfactual_loop(), name="counterfactuals"),
        ]
        if self.helius_key:
            self._tasks.append(asyncio.create_task(self._helius_loop(), name="helius-wallets"))
        if self.pumpportal_key:
            self._tasks.append(asyncio.create_task(self._pumpportal_loop(), name="pumpportal"))
        if self.telegram_token and (self.telegram_chat_id or self.bot_signal_chat_ids):
            self._tasks.append(asyncio.create_task(self._telegram_callback_loop(), name="telegram-callbacks"))
        if self._tg_signal_agent.enabled:
            self._tasks.append(asyncio.create_task(self._tg_signal_agent.run(), name="telegram-mtproto"))

        await self._telegram_send(
            "🟢 Survival Alpha realtime engine online\n"
            f"Notional: {self.notional/1e9:.4f} SOL (paper)\n"
            "Execution: DISABLED — no wallet key loaded."
        )

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._http:
            await self._http.aclose()

    def request_watchlist_reload(self) -> None:
        self._watchlist_version += 1

    def watch_wallets(self) -> list[str]:
        env_wallets = [
            x.strip() for x in os.getenv("WATCH_WALLETS", "").split(",") if x.strip()
        ]
        with self.engine.begin() as cx:
            db = cx.execute(text(
                "SELECT wallet FROM watch_wallet WHERE enabled = 1 ORDER BY created_at_utc"
            )).scalars().all()
        # stable de-dupe
        return list(dict.fromkeys(env_wallets + list(db)))

    async def _handle_telegram_call(self, call: TelegramCall) -> None:
        # Measure the first actionable call per channel/mint. Follow-ups are useful
        # context but must not be double-counted as independent entries.
        if call.call_type not in {"BUY", "MENTION"}:
            return
        with self.engine.begin() as cx:
            seen = int(cx.execute(text("""
                SELECT COUNT(*) FROM realtime_candidate
                WHERE source='telegram' AND source_detail=:channel AND mint=:mint
            """), {"channel": call.channel, "mint": call.mint}).scalar_one())
        if seen:
            return

        await self.evaluate(CandidateEvent(
            mint=call.mint,
            source="telegram",
            detail=call.channel,
            signature=f"tg:{call.channel}:{call.message_id}",
            published_at_utc=call.published_at_utc,
        ))

    def _telegram_channel_prior(self, channel: str) -> dict[str, Any]:
        if not channel:
            return {"n": 0, "profit_factor": None, "bootstrap_mean_lower_95_bps": None, "status": "NO_DATA"}
        with self.engine.begin() as cx:
            rows = cx.execute(text("""
                SELECT outcome_5m_bps FROM realtime_candidate
                WHERE source='telegram'
                  AND source_detail=:channel
                  AND outcome_5m_bps IS NOT NULL
                ORDER BY id
            """), {"channel": channel}).scalars().all()
        return evaluate_outcomes(rows, min_samples=20, min_profit_factor=1.30).to_dict()

    @staticmethod
    def _signal_age_ms(published_at_utc: str) -> Optional[float]:
        if not published_at_utc:
            return None
        try:
            from datetime import datetime, timezone
            s = published_at_utc.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() * 1000.0)
        except Exception:
            return None

    def _recent_confirmations(
        self, mint: str, current: CandidateEvent, horizon_seconds: int = 120
    ) -> tuple[int, int, Optional[float]]:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        sources = {current.source}
        wallets = {current.wallet} if current.wallet else set()
        organic_values = [current.organic_score] if current.organic_score is not None else []

        with self.engine.begin() as cx:
            rows = cx.execute(text("""
                SELECT created_at_utc, source, source_wallet, organic_score
                FROM realtime_candidate
                WHERE mint=:mint
                ORDER BY id DESC
                LIMIT 50
            """), {"mint": mint}).mappings().all()

        for row in rows:
            try:
                ts = str(row["created_at_utc"])
                if ts.endswith("Z"):
                    ts = ts[:-1] + "+00:00"
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if (now - dt).total_seconds() > horizon_seconds:
                    continue
            except Exception:
                continue
            if row["source"]:
                sources.add(str(row["source"]))
            if row["source_wallet"]:
                wallets.add(str(row["source_wallet"]))
            if row["organic_score"] is not None:
                organic_values.append(float(row["organic_score"]))

        return len(sources), len(wallets), (max(organic_values) if organic_values else None)


    async def _jupiter_quote(self, input_mint: str, output_mint: str, amount: int) -> dict[str, Any]:
        assert self._http is not None
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(int(amount)),
            "swapMode": "ExactIn",
        }
        started = time.perf_counter()
        r = await self._http.get(
            JUPITER_ORDER_URL,
            params=params,
            headers={"x-api-key": self.jupiter_key},
        )
        rtt_ms = (time.perf_counter() - started) * 1000.0
        r.raise_for_status()
        data = r.json()
        data["_clientRttMs"] = rtt_ms
        return data

    async def _market_buy_quote(self, mint: str, amount: int) -> dict[str, Any]:
        """
        Quote the actual market phase. Bonding-curve tokens are priced from live
        Pump reserves through the local quote-only SDK sidecar; graduated/routable
        tokens fall back to Jupiter.
        """
        assert self._http is not None
        try:
            r = await self._http.get(
                f"{self.pump_quoter_url}/buy-quote",
                params={"mint": mint, "lamports": str(int(amount))},
                timeout=4.0,
            )
            if r.status_code == 200:
                p = r.json()
                if p.get("phase") == "bonding_curve":
                    return {
                        "_market": "pump_bonding_curve",
                        "phase": "bonding_curve",
                        "outAmount": p.get("tokensOut"),
                        "sellbackLamports": p.get("sellbackLamports"),
                        "roundtripBps": p.get("roundtripBps"),
                        "priceImpact": (
                            float(p.get("buyImpactBps") or 0) / 10_000.0
                        ),
                        "graduationProgressBps": p.get("graduationProgressBps"),
                        "marketCapLamports": p.get("marketCapLamports"),
                        "solNeededToGraduate": p.get("solNeededToGraduate"),
                    }
        except Exception:
            log.debug("Pump sidecar buy quote unavailable for %s", mint, exc_info=True)

        q = await self._jupiter_quote(WSOL_MINT, mint, amount)
        q["_market"] = "jupiter"
        q["phase"] = "graduated_or_external"
        return q

    async def _market_sell_quote(self, mint: str, token_amount: int) -> dict[str, Any]:
        assert self._http is not None
        try:
            r = await self._http.get(
                f"{self.pump_quoter_url}/sell-quote",
                params={"mint": mint, "tokens": str(int(token_amount))},
                timeout=4.0,
            )
            if r.status_code == 200:
                p = r.json()
                if p.get("phase") == "bonding_curve":
                    return {
                        "_market": "pump_bonding_curve",
                        "phase": "bonding_curve",
                        "outAmount": p.get("solOutLamports"),
                        "priceImpact": (
                            float(p.get("sellImpactBps") or 0) / 10_000.0
                        ),
                    }
        except Exception:
            log.debug("Pump sidecar sell quote unavailable for %s", mint, exc_info=True)

        q = await self._jupiter_quote(mint, WSOL_MINT, token_amount)
        q["_market"] = "jupiter"
        q["phase"] = "graduated_or_external"
        return q


    async def evaluate(self, event: CandidateEvent) -> Optional[int]:
        if not event.mint or event.mint == WSOL_MINT:
            return None

        now = time.time()
        seen_key = f"{event.source}:{event.mint}"
        if now - self._seen.get(seen_key, 0) < self.candidate_cooldown_secs:
            return None
        self._seen[seen_key] = now

        try:
            q0 = await self._market_buy_quote(event.mint, self.notional)
            out0 = int(q0.get("outAmount") or 0)
            if out0 <= 0:
                return self._persist_candidate(event, None, None, None, None, "REJECT", "no executable buy quote")

            if q0.get("_market") == "pump_bonding_curve" and q0.get("sellbackLamports"):
                sell_lamports = int(q0.get("sellbackLamports") or 0)
                roundtrip_bps = float(
                    q0.get("roundtripBps")
                    if q0.get("roundtripBps") is not None
                    else ((sell_lamports / self.notional) - 1.0) * 10_000.0
                )
            else:
                sell0 = await self._market_sell_quote(event.mint, out0)
                sell_lamports = int(sell0.get("outAmount") or 0)
                roundtrip_bps = ((sell_lamports / self.notional) - 1.0) * 10_000.0

            # Use the 500ms window productively: while quote decay accrues,
            # collect candidate-local on-chain microstructure from Helius.
            micro_task = None
            if self.helius_rpc_url:
                micro_task = asyncio.create_task(
                    microstructure_snapshot(self._http, self.helius_rpc_url, event.mint)
                )

            await asyncio.sleep(0.5)
            q500 = await self._market_buy_quote(event.mint, self.notional)
            out500 = int(q500.get("outAmount") or 0)
            drift500 = ((out500 / out0) - 1.0) * 10_000.0 if out500 > 0 else -10_000.0

            if micro_task:
                micro = await micro_task
            else:
                from elite_signals import MicrostructureSnapshot
                micro = MicrostructureSnapshot(error="HELIUS_API_KEY missing")

            source_count, independent_wallet_count, recent_organic = self._recent_confirmations(
                event.mint, event
            )
            effective_organic = (
                event.organic_score if event.organic_score is not None else recent_organic
            )

            verdict = elite_verdict(
                micro=micro,
                roundtrip_bps=roundtrip_bps,
                drift_500_bps=drift500,
                organic_score=effective_organic,
                source_count=source_count,
                independent_wallet_count=independent_wallet_count,
            )
            channel_prior = (
                self._telegram_channel_prior(event.detail)
                if event.source == "telegram"
                else {"n": 0, "profit_factor": None, "bootstrap_mean_lower_95_bps": None}
            )
            votes = evaluate_tournament(
                source=event.source,
                micro=micro,
                roundtrip_bps=roundtrip_bps,
                drift_500_bps=drift500,
                organic_score=effective_organic,
                source_count=source_count,
                independent_wallet_count=independent_wallet_count,
                telegram_channel_samples=int(channel_prior.get("n") or 0),
                telegram_channel_profit_factor=channel_prior.get("profit_factor"),
                telegram_channel_ci_lower_bps=channel_prior.get("bootstrap_mean_lower_95_bps"),
            )

            # A strategy must pass independently; the aggregate score is diagnostic,
            # not a permission slip.
            passing = [v for v in votes if v.passed]
            decision = "ACTIONABLE_PAPER" if passing and verdict.decision != "REJECT" else verdict.decision
            reason = (
                "passed: " + ",".join(v.name for v in passing)
                if passing else "; ".join(verdict.reasons)
            )

            cid = self._persist_candidate(
                event,
                str(out0),
                str(sell_lamports),
                roundtrip_bps,
                drift500,
                decision,
                reason,
                price_impact=q0.get("priceImpact"),
                strategy_score=verdict.score,
                microstructure=micro.to_dict(),
                strategy_votes=[v.to_dict() for v in votes],
                organic_score=effective_organic,
                market_phase=str(q0.get("phase") or q0.get("_market") or ""),
                market_data={
                    "market": q0.get("_market"),
                    "graduationProgressBps": q0.get("graduationProgressBps"),
                    "marketCapLamports": q0.get("marketCapLamports"),
                    "solNeededToGraduate": q0.get("solNeededToGraduate"),
                    "channelPrior": channel_prior if event.source == "telegram" else None,
                },
            )

            if decision == "ACTIONABLE_PAPER":
                await self._notify_candidate(cid, event, roundtrip_bps, drift500, q0)
                if self.auto_paper and self._open_position_count() < self.max_open_paper:
                    await self.paper_enter(cid)
            return cid
        except Exception as exc:
            log.exception("candidate evaluation failed for %s", event.mint)
            return self._persist_candidate(
                event, None, None, None, None, "ERROR", f"{type(exc).__name__}: {exc}"
            )

    def _persist_candidate(
        self,
        event: CandidateEvent,
        buy_out: Optional[str],
        sellback_out: Optional[str],
        roundtrip_bps: Optional[float],
        drift500: Optional[float],
        decision: str,
        reason: str,
        price_impact: Optional[float] = None,
        strategy_score: Optional[float] = None,
        microstructure: Optional[dict] = None,
        strategy_votes: Optional[list[dict]] = None,
        organic_score: Optional[float] = None,
        market_phase: str = "",
        market_data: Optional[dict] = None,
    ) -> int:
        row = {
            "created_at_utc": _now_utc(),
            "updated_at_utc": _now_utc(),
            "mint": event.mint,
            "source": event.source,
            "source_detail": event.detail,
            "source_signature": event.signature or None,
            "source_wallet": event.wallet or None,
            "source_slot": event.slot or None,
            "notional_lamports": self.notional,
            "buy_out_amount": buy_out,
            "sellback_out_lamports": sellback_out,
            "roundtrip_bps": roundtrip_bps,
            "drift_500_bps": drift500,
            "price_impact": price_impact,
            "organic_score": organic_score if organic_score is not None else event.organic_score,
            "strategy_score": strategy_score,
            "microstructure_json": json.dumps(microstructure or {}, separators=(",", ":")),
            "strategy_votes_json": json.dumps(strategy_votes or [], separators=(",", ":")),
            "signal_published_at_utc": event.published_at_utc or None,
            "signal_age_ms": self._signal_age_ms(event.published_at_utc),
            "market_phase": market_phase or None,
            "market_data_json": json.dumps(market_data or {}, separators=(",", ":")),
            "decision": decision,
            "reason": reason,
        }
        with self.engine.begin() as cx:
            result = cx.execute(text("""
                INSERT INTO realtime_candidate (
                    created_at_utc, updated_at_utc, mint, source, source_detail,
                    source_signature, source_wallet, source_slot, notional_lamports,
                    buy_out_amount, sellback_out_lamports, roundtrip_bps,
                    drift_500_bps, price_impact, organic_score, strategy_score,
                    microstructure_json, strategy_votes_json, signal_published_at_utc,
                    signal_age_ms, market_phase, market_data_json, decision, reason
                ) VALUES (
                    :created_at_utc, :updated_at_utc, :mint, :source, :source_detail,
                    :source_signature, :source_wallet, :source_slot, :notional_lamports,
                    :buy_out_amount, :sellback_out_lamports, :roundtrip_bps,
                    :drift_500_bps, :price_impact, :organic_score, :strategy_score,
                    :microstructure_json, :strategy_votes_json, :signal_published_at_utc,
                    :signal_age_ms, :market_phase, :market_data_json, :decision, :reason
                )
            """), row)
            cid = getattr(result, "lastrowid", None)
            if not cid:
                cid = cx.execute(text(
                    "SELECT id FROM realtime_candidate WHERE mint=:mint ORDER BY id DESC LIMIT 1"
                ), {"mint": event.mint}).scalar_one()
        return int(cid)

    async def _notify_candidate(
        self, cid: int, event: CandidateEvent, rt_bps: float, drift_bps: float, quote: dict
    ) -> None:
        impact = quote.get("priceImpact")
        organic = f"{event.organic_score:.1f}" if event.organic_score is not None else "n/a"
        msg = (
            "⚡ ACTIONABLE PAPER CANDIDATE\n"
            f"#{cid}  {event.mint}\n"
            f"source: {event.source} {event.detail}\n"
            f"organic: {organic}\n"
            f"round-trip: {rt_bps:.0f} bps\n"
            f"500ms drift: {drift_bps:.0f} bps\n"
            f"price impact: {impact}\n"
            f"notional: {self.notional/1e9:.4f} SOL\n"
            "No live transaction has been sent."
        )
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🧪 PAPER ENTER", "callback_data": f"paper:{cid}"},
                    {"text": "❌ REJECT", "callback_data": f"reject:{cid}"},
                ],
                [
                    {"text": "↗ Open Jupiter", "url": f"https://jup.ag/swap/SOL-{event.mint}"},
                    {"text": "↗ Pump.fun", "url": f"https://pump.fun/coin/{event.mint}"},
                ],
            ]
        }
        await self._telegram_send(msg, keyboard)

    async def paper_enter(self, candidate_id: int) -> Optional[int]:
        with self.engine.begin() as cx:
            row = cx.execute(text(
                "SELECT * FROM realtime_candidate WHERE id=:id"
            ), {"id": candidate_id}).mappings().first()
        if not row or row["decision"] != "ACTIONABLE_PAPER":
            return None
        if self._open_position_count() >= self.max_open_paper:
            await self._telegram_send("Paper entry skipped: max open paper positions reached.")
            return None
        with self.engine.begin() as cx:
            already_open = int(cx.execute(text(
                "SELECT COUNT(*) FROM paper_position WHERE status='OPEN' AND mint=:mint"
            ), {"mint": row["mint"]}).scalar_one())
        if already_open:
            return None

        q = await self._market_buy_quote(row["mint"], int(row["notional_lamports"]))
        tokens = str(q.get("outAmount") or "0")
        if tokens == "0":
            return None

        data = {
            "candidate_id": candidate_id,
            "opened_at_utc": _now_utc(),
            "mint": row["mint"],
            "cost_lamports": int(row["notional_lamports"]),
            "token_amount": tokens,
            "latest_value_lamports": None,
            "latest_pnl_bps": None,
            "status": "OPEN",
        }
        with self.engine.begin() as cx:
            result = cx.execute(text("""
                INSERT INTO paper_position (
                    candidate_id, opened_at_utc, mint, cost_lamports, token_amount,
                    latest_value_lamports, latest_pnl_bps, status
                ) VALUES (
                    :candidate_id, :opened_at_utc, :mint, :cost_lamports, :token_amount,
                    :latest_value_lamports, :latest_pnl_bps, :status
                )
            """), data)
            pid = getattr(result, "lastrowid", None)
            if not pid:
                pid = cx.execute(text(
                    "SELECT id FROM paper_position WHERE candidate_id=:cid ORDER BY id DESC LIMIT 1"
                ), {"cid": candidate_id}).scalar_one()
            cx.execute(text(
                "UPDATE realtime_candidate SET paper_entered=1, updated_at_utc=:u WHERE id=:id"
            ), {"u": _now_utc(), "id": candidate_id})

        await self._telegram_send(
            f"🧪 PAPER ENTERED #{pid}\n{row['mint']}\n"
            f"cost: {int(row['notional_lamports'])/1e9:.4f} SOL",
            {"inline_keyboard": [[
                {"text": "🧪 PAPER EXIT NOW", "callback_data": f"paper_exit:{pid}"},
                {"text": "↗ Jupiter", "url": f"https://jup.ag/swap/{row['mint']}-SOL"},
            ]]}
        )
        return int(pid)

    async def paper_exit(self, position_id: int) -> None:
        with self.engine.begin() as cx:
            pos = cx.execute(text(
                "SELECT * FROM paper_position WHERE id=:id AND status='OPEN'"
            ), {"id": position_id}).mappings().first()
        if not pos:
            return
        q = await self._market_sell_quote(pos["mint"], int(pos["token_amount"]))
        value = int(q.get("outAmount") or 0)
        pnl_bps = ((value / int(pos["cost_lamports"])) - 1.0) * 10_000 if value else -10_000.0
        with self.engine.begin() as cx:
            cx.execute(text("""
                UPDATE paper_position
                SET closed_at_utc=:closed, realized_value_lamports=:v,
                    realized_pnl_bps=:p, latest_value_lamports=:v,
                    latest_pnl_bps=:p, status='CLOSED'
                WHERE id=:id
            """), {"closed": _now_utc(), "v": str(value), "p": pnl_bps, "id": position_id})
        await self._telegram_send(
            f"🏁 PAPER CLOSED #{position_id}\n"
            f"value: {value/1e9:.5f} SOL\nPnL: {pnl_bps/100:.2f}%"
        )

    def _open_position_count(self) -> int:
        with self.engine.begin() as cx:
            return int(cx.execute(text(
                "SELECT COUNT(*) FROM paper_position WHERE status='OPEN'"
            )).scalar_one())

    async def _position_loop(self) -> None:
        while not self._stop.is_set():
            try:
                with self.engine.begin() as cx:
                    rows = cx.execute(text(
                        "SELECT * FROM paper_position WHERE status='OPEN' ORDER BY id"
                    )).mappings().all()
                for pos in rows:
                    try:
                        opened = str(pos["opened_at_utc"])
                        if opened.endswith("Z"):
                            opened = opened[:-1] + "+00:00"
                        from datetime import datetime, timezone
                        opened_dt = datetime.fromisoformat(opened)
                        if opened_dt.tzinfo is None:
                            opened_dt = opened_dt.replace(tzinfo=timezone.utc)
                        age_secs = (datetime.now(timezone.utc) - opened_dt).total_seconds()
                        if age_secs >= self.paper_max_hold_secs:
                            await self.paper_exit(int(pos["id"]))
                            continue

                        q = await self._market_sell_quote(
                            pos["mint"], int(pos["token_amount"])
                        )
                        value = int(q.get("outAmount") or 0)
                        pnl_bps = ((value / int(pos["cost_lamports"])) - 1.0) * 10_000 if value else -10_000.0
                        with self.engine.begin() as cx:
                            cx.execute(text("""
                                UPDATE paper_position
                                SET latest_value_lamports=:v, latest_pnl_bps=:p
                                WHERE id=:id
                            """), {"v": str(value), "p": pnl_bps, "id": pos["id"]})
                    except Exception:
                        log.exception("paper position mark failed id=%s", pos["id"])
            except Exception:
                log.exception("paper position loop error")
            await asyncio.sleep(self.position_poll_secs)

    async def _counterfactual_loop(self) -> None:
        """
        Mark every candidate, accepted or rejected, at the same 5-minute horizon.
        This is the anti-self-deception loop: filters are judged against what they rejected.
        """
        from datetime import datetime, timezone
        while not self._stop.is_set():
            try:
                with self.engine.begin() as cx:
                    rows = cx.execute(text("""
                        SELECT id, created_at_utc, mint, notional_lamports, buy_out_amount
                        FROM realtime_candidate
                        WHERE buy_out_amount IS NOT NULL
                          AND outcome_checked_at_utc IS NULL
                        ORDER BY id
                        LIMIT 200
                    """)).mappings().all()

                for row in rows:
                    created = str(row["created_at_utc"])
                    if created.endswith("Z"):
                        created = created[:-1] + "+00:00"
                    dt = datetime.fromisoformat(created)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    age = (datetime.now(timezone.utc) - dt).total_seconds()
                    if age < 300:
                        continue
                    try:
                        q = await self._market_sell_quote(
                            row["mint"], int(row["buy_out_amount"])
                        )
                        value = int(q.get("outAmount") or 0)
                        cost = int(row["notional_lamports"])
                        outcome_bps = ((value / cost) - 1.0) * 10_000 if value else -10_000.0
                        with self.engine.begin() as cx:
                            cx.execute(text("""
                                UPDATE realtime_candidate
                                SET outcome_5m_bps=:o, outcome_checked_at_utc=:u,
                                    updated_at_utc=:u
                                WHERE id=:id
                            """), {"o": outcome_bps, "u": _now_utc(), "id": row["id"]})
                    except Exception:
                        log.exception("counterfactual mark failed candidate=%s", row["id"])
            except Exception:
                log.exception("counterfactual loop error")
            await asyncio.sleep(10)

    async def _organic_loop(self) -> None:
        while not self._stop.is_set():
            try:
                assert self._http is not None
                r = await self._http.get(
                    JUPITER_ORGANIC_URL,
                    headers={"x-api-key": self.jupiter_key},
                )
                r.raise_for_status()
                body = r.json()
                rows = body if isinstance(body, list) else body.get("data", [])
                for item in rows[:50]:
                    mint = item.get("id") or item.get("address") or item.get("mint")
                    score = item.get("organicScore")
                    try:
                        score_f = float(score)
                    except (TypeError, ValueError):
                        score_f = None
                    if not mint:
                        continue
                    # evaluate() has a per-source/mint cooldown, so rising scores
                    # can be reconsidered without hammering Jupiter every poll.
                    if score_f is not None and score_f >= self.organic_min:
                        asyncio.create_task(self.evaluate(CandidateEvent(
                            mint=mint,
                            source="jupiter_organic",
                            detail="top organic 5m",
                            organic_score=score_f,
                        )))
            except Exception:
                log.exception("Jupiter organic polling failed")
            await asyncio.sleep(self.organic_poll_secs)

    async def _pumpportal_loop(self) -> None:
        uri = f"{PUMPPORTAL_WS_BASE}?api-key={self.pumpportal_key}"
        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
                    backoff = 1.0
                    await ws.send(json.dumps({"method": "subscribeMigration"}))
                    if _env_bool("PUMPPORTAL_NEW_TOKENS", False):
                        await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    async for raw in ws:
                        data = json.loads(raw)
                        mint = (
                            data.get("mint") or data.get("address") or data.get("token")
                            or (data.get("data") or {}).get("mint")
                        )
                        if not mint:
                            continue
                        event_type = str(data.get("txType") or data.get("type") or "pumpportal")
                        asyncio.create_task(self.evaluate(CandidateEvent(
                            mint=mint,
                            source="pumpportal",
                            detail=event_type,
                            signature=str(data.get("signature") or ""),
                        )))
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("PumpPortal websocket disconnected")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _helius_loop(self) -> None:
        backoff = 1.0
        observed_version = -1
        while not self._stop.is_set():
            wallets = self.watch_wallets()
            observed_version = self._watchlist_version
            if not wallets:
                await asyncio.sleep(5)
                continue
            uri = f"wss://mainnet.helius-rpc.com/?api-key={self.helius_key}"
            try:
                async with websockets.connect(uri, ping_interval=30, ping_timeout=20) as ws:
                    backoff = 1.0
                    sub = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "transactionSubscribe",
                        "params": [
                            {"accountInclude": wallets, "vote": False, "failed": False},
                            {
                                "commitment": "processed",
                                "encoding": "jsonParsed",
                                "transactionDetails": "full",
                                "maxSupportedTransactionVersion": 0,
                            },
                        ],
                    }
                    await ws.send(json.dumps(sub))
                    while not self._stop.is_set():
                        if observed_version != self._watchlist_version:
                            break
                        raw = await asyncio.wait_for(ws.recv(), timeout=35)
                        msg = json.loads(raw)
                        if msg.get("method") != "transactionNotification":
                            continue
                        result = ((msg.get("params") or {}).get("result") or {})
                        await self._handle_helius_tx(result, wallets)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Helius websocket disconnected")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    @staticmethod
    def _account_keys(tx: dict) -> list[str]:
        inner = tx.get("transaction") or {}
        message = inner.get("message") or {}
        raw = message.get("accountKeys") or message.get("staticAccountKeys") or []
        keys = []
        for item in raw:
            if isinstance(item, str):
                keys.append(item)
            elif isinstance(item, dict) and item.get("pubkey"):
                keys.append(item["pubkey"])
        loaded = (tx.get("meta") or {}).get("loadedAddresses") or {}
        keys.extend(loaded.get("writable") or [])
        keys.extend(loaded.get("readonly") or [])
        return keys

    @staticmethod
    def _token_map(tx: dict, wallet: str, key: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for b in (tx.get("meta") or {}).get(key) or []:
            if b.get("owner") != wallet:
                continue
            mint = b.get("mint")
            if not mint or mint == WSOL_MINT:
                continue
            raw = int(((b.get("uiTokenAmount") or {}).get("amount") or "0"))
            out[mint] = out.get(mint, 0) + raw
        return out

    async def _handle_helius_tx(self, result: dict, wallets: list[str]) -> None:
        envelope = result.get("transaction") or {}
        inner = envelope.get("transaction")
        if isinstance(inner, dict):
            # Helius wraps parsed message/signatures and meta separately.
            tx = {"transaction": inner, "meta": envelope.get("meta") or {}}
        else:
            tx = envelope
        if not isinstance(tx, dict):
            return
        keys = self._account_keys(tx)
        meta = tx.get("meta") or {}
        pre_bal = meta.get("preBalances") or []
        post_bal = meta.get("postBalances") or []
        signature = result.get("signature") or ""
        slot = int(result.get("slot") or 0)

        for wallet in wallets:
            if wallet not in keys:
                continue
            try:
                idx = keys.index(wallet)
                sol_delta = int(post_bal[idx]) - int(pre_bal[idx])
            except (ValueError, IndexError):
                sol_delta = 0
            pre = self._token_map(tx, wallet, "preTokenBalances")
            post = self._token_map(tx, wallet, "postTokenBalances")
            for mint in set(pre) | set(post):
                token_delta = post.get(mint, 0) - pre.get(mint, 0)
                if token_delta > 0 and sol_delta < 0:
                    asyncio.create_task(self.evaluate(CandidateEvent(
                        mint=mint,
                        source="wallet_buy",
                        detail=f"wallet {wallet[:6]}… bought",
                        signature=signature,
                        wallet=wallet,
                        slot=slot,
                    )))

    async def _telegram_send(self, message: str, reply_markup: Optional[dict] = None) -> None:
        if not (self.telegram_token and self.telegram_chat_id and self._http):
            log.info("TELEGRAM: %s", message.replace("\n", " | "))
            return
        payload: dict[str, Any] = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            r = await self._http.post(
                f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                json=payload,
            )
            r.raise_for_status()
        except Exception:
            log.exception("Telegram send failed")

    async def _telegram_callback_loop(self) -> None:
        assert self._http is not None
        while not self._stop.is_set():
            try:
                r = await self._http.get(
                    f"https://api.telegram.org/bot{self.telegram_token}/getUpdates",
                    params={"timeout": 20, "offset": self._telegram_offset},
                    timeout=25.0,
                )
                r.raise_for_status()
                for update in r.json().get("result", []):
                    self._telegram_offset = max(self._telegram_offset, int(update["update_id"]) + 1)

                    # Bot-mode signal ingestion for channels/groups where the bot
                    # is actually present. Only explicitly whitelisted chat IDs count.
                    msg = update.get("channel_post") or update.get("message")
                    if msg:
                        chat = msg.get("chat") or {}
                        chat_id = str(chat.get("id") or "")
                        if chat_id in self.bot_signal_chat_ids:
                            username = chat.get("username")
                            channel = f"@{username}" if username else f"id_{chat_id}"
                            body = msg.get("text") or msg.get("caption") or ""
                            calls = parse_telegram_message(
                                channel=channel,
                                message_id=int(msg.get("message_id") or 0),
                                published_at=int(msg.get("date") or time.time()),
                                text=body,
                                source_url=(
                                    f"https://t.me/{username}/{msg.get('message_id')}"
                                    if username else ""
                                ),
                            )
                            for call in calls:
                                await self._handle_telegram_call(call)

                    cb = update.get("callback_query")
                    if not cb:
                        continue
                    data = str(cb.get("data") or "")
                    if data.startswith("paper:"):
                        await self.paper_enter(int(data.split(":", 1)[1]))
                    elif data.startswith("paper_exit:"):
                        await self.paper_exit(int(data.split(":", 1)[1]))
                    elif data.startswith("reject:"):
                        cid = int(data.split(":", 1)[1])
                        with self.engine.begin() as cx:
                            cx.execute(text(
                                "UPDATE realtime_candidate SET decision='USER_REJECT', updated_at_utc=:u WHERE id=:id"
                            ), {"u": _now_utc(), "id": cid})
                    await self._http.post(
                        f"https://api.telegram.org/bot{self.telegram_token}/answerCallbackQuery",
                        json={"callback_query_id": cb["id"]},
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Telegram callback loop failed")
                await asyncio.sleep(3)
