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
            decision TEXT NOT NULL,
            reason TEXT,
            paper_entered {bool_type} NOT NULL DEFAULT 0,
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


@dataclass
class CandidateEvent:
    mint: str
    source: str
    detail: str = ""
    signature: str = ""
    wallet: str = ""
    slot: int = 0
    organic_score: Optional[float] = None


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
        self.auto_paper = _env_bool("AUTO_PAPER", False)
        self.max_open_paper = _env_int("MAX_OPEN_PAPER_POSITIONS", 3)

        self.jupiter_key = os.getenv("JUPITER_API_KEY", "").strip()
        self.helius_key = os.getenv("HELIUS_API_KEY", "").strip()
        self.pumpportal_key = os.getenv("PUMPPORTAL_API_KEY", "").strip()
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._seen: dict[str, float] = {}
        self._http: Optional[httpx.AsyncClient] = None
        self._watchlist_version = 0
        self._telegram_offset = 0

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
        ]
        if self.helius_key:
            self._tasks.append(asyncio.create_task(self._helius_loop(), name="helius-wallets"))
        if self.pumpportal_key:
            self._tasks.append(asyncio.create_task(self._pumpportal_loop(), name="pumpportal"))
        if self.telegram_token and self.telegram_chat_id:
            self._tasks.append(asyncio.create_task(self._telegram_callback_loop(), name="telegram-callbacks"))

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

    async def evaluate(self, event: CandidateEvent) -> Optional[int]:
        if not event.mint or event.mint == WSOL_MINT:
            return None

        now = time.time()
        seen_key = f"{event.source}:{event.mint}"
        if now - self._seen.get(seen_key, 0) < self.candidate_cooldown_secs:
            return None
        self._seen[seen_key] = now

        try:
            q0 = await self._jupiter_quote(WSOL_MINT, event.mint, self.notional)
            out0 = int(q0.get("outAmount") or 0)
            if out0 <= 0:
                return self._persist_candidate(event, None, None, None, None, "REJECT", "no executable buy quote")

            sell0 = await self._jupiter_quote(event.mint, WSOL_MINT, out0)
            sell_lamports = int(sell0.get("outAmount") or 0)
            roundtrip_bps = ((sell_lamports / self.notional) - 1.0) * 10_000.0

            await asyncio.sleep(0.5)
            q500 = await self._jupiter_quote(WSOL_MINT, event.mint, self.notional)
            out500 = int(q500.get("outAmount") or 0)
            drift500 = ((out500 / out0) - 1.0) * 10_000.0 if out500 > 0 else -10_000.0

            reasons = []
            if roundtrip_bps < -abs(self.max_roundtrip_cost_bps):
                reasons.append(f"roundtrip {roundtrip_bps:.0f}bps")
            if drift500 < -abs(self.max_adverse_500_bps):
                reasons.append(f"500ms drift {drift500:.0f}bps")
            if event.source == "jupiter_organic" and (event.organic_score or 0) < self.organic_min:
                reasons.append("organic score below floor")

            decision = "REJECT" if reasons else "ACTIONABLE_PAPER"
            cid = self._persist_candidate(
                event,
                str(out0),
                str(sell_lamports),
                roundtrip_bps,
                drift500,
                decision,
                "; ".join(reasons) if reasons else "sellability + 500ms drift passed",
                price_impact=q0.get("priceImpact"),
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
            "organic_score": event.organic_score,
            "decision": decision,
            "reason": reason,
        }
        with self.engine.begin() as cx:
            result = cx.execute(text("""
                INSERT INTO realtime_candidate (
                    created_at_utc, updated_at_utc, mint, source, source_detail,
                    source_signature, source_wallet, source_slot, notional_lamports,
                    buy_out_amount, sellback_out_lamports, roundtrip_bps,
                    drift_500_bps, price_impact, organic_score, decision, reason
                ) VALUES (
                    :created_at_utc, :updated_at_utc, :mint, :source, :source_detail,
                    :source_signature, :source_wallet, :source_slot, :notional_lamports,
                    :buy_out_amount, :sellback_out_lamports, :roundtrip_bps,
                    :drift_500_bps, :price_impact, :organic_score, :decision, :reason
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

        q = await self._jupiter_quote(WSOL_MINT, row["mint"], int(row["notional_lamports"]))
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
        q = await self._jupiter_quote(pos["mint"], WSOL_MINT, int(pos["token_amount"]))
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
                        q = await self._jupiter_quote(
                            pos["mint"], WSOL_MINT, int(pos["token_amount"])
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

    async def _organic_loop(self) -> None:
        known: set[str] = set()
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
                    if not mint or mint in known:
                        continue
                    known.add(mint)
                    if len(known) > 5000:
                        known = set(list(known)[-2500:])
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
        tx = envelope.get("transaction") if isinstance(envelope.get("transaction"), dict) else envelope
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
