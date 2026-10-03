from __future__ import annotations

import csv
import hmac
import io
import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from social_signal import compute_features, content_fingerprint
from realtime_engine import RealtimeEngine
from agent_team import AgentTeam

JUPITER_ORDER_URL = "https://api.jup.ag/swap/v2/order"
WSOL_MINT = "So11111111111111111111111111111111111111112"
PUMP_FUN_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./arena.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
app = FastAPI(title="Survival Alpha Paper Lab", version="0.2.0")
realtime = RealtimeEngine(engine)
agent_team = AgentTeam(engine)


@app.on_event("startup")
async def _start_realtime():
    await realtime.start()


@app.on_event("shutdown")
async def _stop_realtime():
    await realtime.stop()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_admin(token: Optional[str]) -> None:
    expected = os.getenv("PAPER_ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(503, "PAPER_ADMIN_TOKEN is not configured")
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(401, "unauthorized")


def jupiter_key() -> str:
    key = os.getenv("JUPITER_API_KEY", "")
    if not key:
        raise HTTPException(503, "JUPITER_API_KEY is not configured")
    return key


def helius_url() -> str:
    override = os.getenv("HELIUS_RPC_URL", "").strip()
    if override:
        return override
    key = os.getenv("HELIUS_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "HELIUS_API_KEY is not configured")
    return f"https://mainnet.helius-rpc.com/?api-key={key}"


def init_db() -> None:
    if DATABASE_URL.startswith("sqlite"):
        quote_pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
        wallet_pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
    else:
        quote_pk = "BIGSERIAL PRIMARY KEY"
        wallet_pk = "BIGSERIAL PRIMARY KEY"

    with engine.begin() as cx:
        cx.execute(text(f"""
        CREATE TABLE IF NOT EXISTS quote_drift (
            id {quote_pk},
            observed_at_utc TEXT NOT NULL,
            signal_id TEXT NOT NULL,
            mint TEXT NOT NULL,
            input_mint TEXT NOT NULL,
            amount_lamports BIGINT NOT NULL,
            delay_label TEXT NOT NULL,
            scheduled_delay_ms INTEGER NOT NULL,
            actual_delay_ms DOUBLE PRECISION NOT NULL,
            http_rtt_ms DOUBLE PRECISION,
            jupiter_total_time_ms DOUBLE PRECISION,
            in_amount TEXT,
            out_amount TEXT,
            baseline_out_amount TEXT,
            drift_bps DOUBLE PRECISION,
            fee_bps DOUBLE PRECISION,
            price_impact DOUBLE PRECISION,
            router TEXT,
            request_id TEXT,
            raw_json TEXT NOT NULL
        )
        """))
        cx.execute(text(f"""
        CREATE TABLE IF NOT EXISTS wallet_replay (
            id {wallet_pk},
            captured_at_utc TEXT NOT NULL,
            wallet TEXT NOT NULL,
            signature TEXT,
            block_time BIGINT,
            mint TEXT NOT NULL,
            side TEXT NOT NULL,
            sol_delta DOUBLE PRECISION NOT NULL,
            token_delta_raw TEXT NOT NULL,
            is_pumpfun BOOLEAN NOT NULL
        )
        """))
        cx.execute(text(f"""
        CREATE TABLE IF NOT EXISTS social_event (
            id {wallet_pk},
            observed_at_utc TEXT NOT NULL,
            published_at_utc TEXT NOT NULL,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            author_id TEXT NOT NULL,
            mint TEXT NOT NULL,
            content_fingerprint TEXT NOT NULL,
            author_age_days DOUBLE PRECISION,
            follower_count BIGINT,
            engagement_count BIGINT NOT NULL,
            is_verified BOOLEAN NOT NULL,
            contract_present BOOLEAN NOT NULL,
            source_url TEXT,
            UNIQUE(source, external_id)
        )
        """))


init_db()


class QuoteSignal(BaseModel):
    signal_id: str = Field(min_length=1, max_length=100)
    mint: str = Field(min_length=30, max_length=60)
    amount_lamports: int = Field(gt=0)
    input_mint: str = WSOL_MINT
    singapore_delay_ms: Optional[int] = Field(default=None, ge=1, le=5000)


class BackfillRequest(BaseModel):
    wallets: list[str] = Field(min_length=1, max_length=20)
    days: int = Field(default=30, ge=1, le=180)
    max_pages: int = Field(default=20, ge=1, le=100)
    page_limit: int = Field(default=100, ge=1, le=1000)
    pump_only: bool = True


class WatchWalletRequest(BaseModel):
    wallet: str = Field(min_length=30, max_length=60)
    label: Optional[str] = Field(default=None, max_length=200)
    enabled: bool = True


class SocialEvent(BaseModel):
    source: str = Field(min_length=1, max_length=20)
    external_id: str = Field(min_length=1, max_length=200)
    published_at_utc: str = Field(min_length=10, max_length=64)
    author_id: str = Field(min_length=1, max_length=200)
    mint: str = Field(min_length=30, max_length=60)
    text: str = Field(min_length=1, max_length=10000)
    author_age_days: Optional[float] = Field(default=None, ge=0)
    follower_count: Optional[int] = Field(default=None, ge=0)
    engagement_count: int = Field(default=0, ge=0)
    is_verified: bool = False
    contract_present: bool = False
    source_url: Optional[str] = Field(default=None, max_length=2000)


def _quote(session: requests.Session, signal: QuoteSignal):
    params = {
        "inputMint": signal.input_mint,
        "outputMint": signal.mint,
        "amount": signal.amount_lamports,
        "swapMode": "ExactIn",
    }
    started = time.perf_counter()
    r = session.get(
        JUPITER_ORDER_URL,
        params=params,
        headers={"x-api-key": jupiter_key()},
        timeout=12,
    )
    rtt_ms = (time.perf_counter() - started) * 1000
    r.raise_for_status()
    return r.json(), rtt_ms


def _to_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


@app.get("/health")
def health():
    return {
        "ok": True,
        "mode": "paper-only",
        "trading_enabled": False,
        "wallet_key_loaded": False,
        "time_utc": utc_now(),
    }


@app.post("/paper/quote-drift")
def quote_drift(signal: QuoteSignal, x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)

    schedule = [(0, "decision")]
    if signal.singapore_delay_ms:
        schedule.append((signal.singapore_delay_ms, "singapore_measured"))
    schedule.extend([(500, "500ms"), (1000, "1000ms"), (2000, "2000ms")])

    seen = set()
    schedule = [(ms, label) for ms, label in sorted(schedule) if not (ms in seen or seen.add(ms))]

    session = requests.Session()
    baseline_done = None
    baseline_out = None
    output_rows = []

    for delay_ms, label in schedule:
        if baseline_done is not None:
            target = baseline_done + delay_ms / 1000.0
            sleep_for = target - time.perf_counter()
            if sleep_for > 0:
                time.sleep(sleep_for)

        request_started = time.perf_counter()
        q, rtt_ms = _quote(session, signal)

        if baseline_done is None:
            baseline_done = time.perf_counter()
            baseline_out = _to_int(q.get("outAmount")) or None
            actual_delay_ms = 0.0
        else:
            actual_delay_ms = (request_started - baseline_done) * 1000.0

        out_amt = _to_int(q.get("outAmount"))
        drift_bps = None
        if baseline_out and out_amt:
            drift_bps = ((out_amt / baseline_out) - 1.0) * 10000.0

        row = {
            "observed_at_utc": utc_now(),
            "signal_id": signal.signal_id,
            "mint": signal.mint,
            "input_mint": signal.input_mint,
            "amount_lamports": signal.amount_lamports,
            "delay_label": label,
            "scheduled_delay_ms": delay_ms,
            "actual_delay_ms": actual_delay_ms,
            "http_rtt_ms": rtt_ms,
            "jupiter_total_time_ms": q.get("totalTime"),
            "in_amount": q.get("inAmount"),
            "out_amount": q.get("outAmount"),
            "baseline_out_amount": str(baseline_out or ""),
            "drift_bps": drift_bps,
            "fee_bps": q.get("feeBps"),
            "price_impact": q.get("priceImpact"),
            "router": q.get("router"),
            "request_id": q.get("requestId"),
            "raw_json": json.dumps(q, separators=(",", ":")),
        }

        with engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO quote_drift (
                  observed_at_utc, signal_id, mint, input_mint, amount_lamports,
                  delay_label, scheduled_delay_ms, actual_delay_ms, http_rtt_ms,
                  jupiter_total_time_ms, in_amount, out_amount, baseline_out_amount,
                  drift_bps, fee_bps, price_impact, router, request_id, raw_json
                ) VALUES (
                  :observed_at_utc, :signal_id, :mint, :input_mint, :amount_lamports,
                  :delay_label, :scheduled_delay_ms, :actual_delay_ms, :http_rtt_ms,
                  :jupiter_total_time_ms, :in_amount, :out_amount, :baseline_out_amount,
                  :drift_bps, :fee_bps, :price_impact, :router, :request_id, :raw_json
                )
            """), row)
        output_rows.append({k: v for k, v in row.items() if k != "raw_json"})

    return {"mode": "paper-only", "rows": output_rows}


@app.get("/paper/quote-drift/summary")
def quote_summary(limit: int = 5000):
    limit = min(max(limit, 1), 20000)
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT scheduled_delay_ms, drift_bps, http_rtt_ms
            FROM quote_drift
            WHERE scheduled_delay_ms > 0 AND drift_bps IS NOT NULL
            ORDER BY id DESC LIMIT :limit
        """), {"limit": limit}).mappings().all()

    by_delay = {}
    for r in rows:
        d = int(r["scheduled_delay_ms"])
        by_delay.setdefault(d, {"drift": [], "rtt": []})
        by_delay[d]["drift"].append(float(r["drift_bps"]))
        if r["http_rtt_ms"] is not None:
            by_delay[d]["rtt"].append(float(r["http_rtt_ms"]))

    def percentile(xs, p):
        if not xs:
            return None
        xs = sorted(xs)
        k = (len(xs) - 1) * p
        lo = int(k)
        hi = min(lo + 1, len(xs) - 1)
        frac = k - lo
        return xs[lo] * (1 - frac) + xs[hi] * frac

    summary = {}
    for d, vals in sorted(by_delay.items()):
        summary[str(d)] = {
            "n": len(vals["drift"]),
            "median_drift_bps": percentile(vals["drift"], .5),
            "p25_drift_bps": percentile(vals["drift"], .25),
            "p10_drift_bps": percentile(vals["drift"], .10),
            "median_http_rtt_ms": percentile(vals["rtt"], .5),
        }
    return {"mode": "paper-only", "summary": summary}


def _account_keys(tx):
    msg = ((tx.get("transaction") or {}).get("message") or {})
    raw = msg.get("accountKeys") or msg.get("staticAccountKeys") or []
    out = []
    for k in raw:
        if isinstance(k, str):
            out.append(k)
        elif isinstance(k, dict) and k.get("pubkey"):
            out.append(k["pubkey"])
    loaded = ((tx.get("meta") or {}).get("loadedAddresses") or {})
    out.extend(loaded.get("writable") or [])
    out.extend(loaded.get("readonly") or [])
    return out


def _token_map(tx, wallet, key):
    out = {}
    for b in ((tx.get("meta") or {}).get(key) or []):
        if b.get("owner") != wallet:
            continue
        mint = b.get("mint")
        if not mint or mint == WSOL_MINT:
            continue
        amount = int(((b.get("uiTokenAmount") or {}).get("amount") or "0"))
        out[mint] = out.get(mint, 0) + amount
    return out


def _native_delta(tx, wallet):
    keys = _account_keys(tx)
    meta = tx.get("meta") or {}
    pre, post = meta.get("preBalances") or [], meta.get("postBalances") or []
    for i, k in enumerate(keys[:min(len(pre), len(post))]):
        if k == wallet:
            return int(post[i]) - int(pre[i])
    return 0


def _is_pump(tx):
    return PUMP_FUN_PROGRAM_ID in set(_account_keys(tx))


def _fetch_wallet(wallet, days, page_limit, max_pages):
    session = requests.Session()
    start_ts = int(time.time()) - days * 86400
    token = None
    all_txs = []
    for _ in range(max_pages):
        opts = {
            "transactionDetails": "full",
            "sortOrder": "asc",
            "limit": page_limit,
            "filters": {"tokenAccounts": "all", "status": "succeeded", "blockTime": {"gte": start_ts}},
        }
        if token:
            opts["paginationToken"] = token
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getTransactionsForAddress", "params": [wallet, opts]}
        r = session.post(helius_url(), json=payload, timeout=35)
        r.raise_for_status()
        body = r.json()
        if "error" in body:
            raise RuntimeError(body["error"])
        result = body["result"]
        batch = result.get("data") or []
        all_txs.extend(batch)
        token = result.get("paginationToken")
        if not token or not batch:
            break
    return all_txs





@app.get("/team/manifest")
def team_manifest(x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    return {
        "mode": "paper-only",
        "agents": agent_team.manifest(),
        "live_execution_available": False,
    }


@app.get("/team/channel-scorecards")
def team_channel_scorecards(x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    return {
        "mode": "paper-only",
        "channels": agent_team.channel_scorecards(),
        "promotion_rule": "n>=20, PF>1.3, positive 95% bootstrap lower bound",
    }


@app.get("/team/strategy-scorecards")
def team_strategy_scorecards(x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    return {
        "mode": "paper-only",
        "strategies": agent_team.strategy_scorecards(),
        "promotion_rule": "forward outcomes only",
    }


@app.get("/team/diagnostics")
def team_diagnostics(x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    return {
        "mode": "paper-only",
        "diagnostics": agent_team.diagnostics(),
    }


@app.get("/realtime/status")
def realtime_status(x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    with engine.begin() as cx:
        counts = {
            "candidates": int(cx.execute(text("SELECT COUNT(*) FROM realtime_candidate")).scalar_one()),
            "actionable": int(cx.execute(text(
                "SELECT COUNT(*) FROM realtime_candidate WHERE decision='ACTIONABLE_PAPER'"
            )).scalar_one()),
            "open_paper": int(cx.execute(text(
                "SELECT COUNT(*) FROM paper_position WHERE status='OPEN'"
            )).scalar_one()),
            "watch_wallets": int(cx.execute(text(
                "SELECT COUNT(*) FROM watch_wallet WHERE enabled=1"
            )).scalar_one()),
        }
    return {
        "mode": "paper-only",
        "realtime_enabled": realtime.enabled,
        "live_execution_available": False,
        "wallet_key_loaded": False,
        "sources": {
            "helius_wallets": bool(realtime.helius_key),
            "pumpportal": bool(realtime.pumpportal_key),
            "jupiter_organic": bool(realtime.jupiter_key),
            "telegram_actions": bool(realtime.telegram_token and realtime.telegram_chat_id),
        },
        "counts": counts,
    }


@app.get("/realtime/candidates")
def realtime_candidates(limit: int = 100, decision: Optional[str] = None,
                        x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    limit = min(max(limit, 1), 1000)
    query = """
        SELECT id, created_at_utc, updated_at_utc, mint, source, source_detail,
               source_signature, source_wallet, source_slot, notional_lamports,
               buy_out_amount, sellback_out_lamports, roundtrip_bps,
               drift_500_bps, price_impact, organic_score, strategy_score,
               microstructure_json, strategy_votes_json, decision, reason,
               paper_entered, outcome_5m_bps, outcome_checked_at_utc
        FROM realtime_candidate
    """
    params = {"limit": limit}
    if decision:
        query += " WHERE decision=:decision"
        params["decision"] = decision
    query += " ORDER BY id DESC LIMIT :limit"
    with engine.begin() as cx:
        rows = cx.execute(text(query), params).mappings().all()
    return {"mode": "paper-only", "candidates": [dict(r) for r in rows]}



@app.get("/realtime/evaluation")
def realtime_evaluation(x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT decision, outcome_5m_bps
            FROM realtime_candidate
            WHERE outcome_5m_bps IS NOT NULL
        """)).mappings().all()

    groups = {}
    for r in rows:
        key = str(r["decision"])
        groups.setdefault(key, []).append(float(r["outcome_5m_bps"]))

    def summarize(values):
        if not values:
            return {"n": 0}
        xs = sorted(values)
        n = len(xs)
        median = xs[n // 2] if n % 2 else (xs[n//2 - 1] + xs[n//2]) / 2
        return {
            "n": n,
            "mean_5m_bps": sum(xs) / n,
            "median_5m_bps": median,
            "positive_rate": sum(1 for x in xs if x > 0) / n,
            "large_loss_rate": sum(1 for x in xs if x <= -2000) / n,
        }

    summary = {k: summarize(v) for k, v in groups.items()}
    accepted = groups.get("ACTIONABLE_PAPER", [])
    rejected = groups.get("REJECT", [])
    edge_bps = None
    if accepted and rejected:
        edge_bps = (sum(accepted)/len(accepted)) - (sum(rejected)/len(rejected))

    return {
        "mode": "paper-only",
        "horizon": "5m",
        "summary": summary,
        "accepted_minus_rejected_mean_bps": edge_bps,
        "live_execution_available": False,
    }



@app.get("/realtime/strategy-evaluation")
def realtime_strategy_evaluation(x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT strategy_votes_json, outcome_5m_bps
            FROM realtime_candidate
            WHERE outcome_5m_bps IS NOT NULL
              AND strategy_votes_json IS NOT NULL
        """)).mappings().all()

    groups = {}
    for r in rows:
        try:
            votes = json.loads(r["strategy_votes_json"] or "[]")
        except Exception:
            continue
        outcome = float(r["outcome_5m_bps"])
        for vote in votes:
            name = str(vote.get("name") or "UNKNOWN")
            passed = bool(vote.get("passed"))
            bucket = groups.setdefault(name, {"pass": [], "fail": []})
            bucket["pass" if passed else "fail"].append(outcome)

    def stats(xs):
        if not xs:
            return {"n": 0}
        vals = sorted(xs)
        n = len(vals)
        med = vals[n//2] if n % 2 else (vals[n//2-1] + vals[n//2]) / 2
        return {
            "n": n,
            "mean_5m_bps": sum(vals)/n,
            "median_5m_bps": med,
            "positive_rate": sum(1 for x in vals if x > 0)/n,
            "large_loss_rate": sum(1 for x in vals if x <= -2000)/n,
        }

    out = {}
    for name, buckets in groups.items():
        passed = stats(buckets["pass"])
        failed = stats(buckets["fail"])
        edge = None
        if buckets["pass"] and buckets["fail"]:
            edge = (
                sum(buckets["pass"])/len(buckets["pass"])
                - sum(buckets["fail"])/len(buckets["fail"])
            )
        out[name] = {
            "passed": passed,
            "failed": failed,
            "pass_minus_fail_mean_bps": edge,
        }

    return {
        "mode": "paper-only",
        "horizon": "5m",
        "strategies": out,
        "live_execution_available": False,
    }


@app.get("/realtime/positions")
def realtime_positions(x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT * FROM paper_position ORDER BY id DESC LIMIT 200
        """)).mappings().all()
    return {"mode": "paper-only", "positions": [dict(r) for r in rows]}


@app.post("/realtime/watch-wallet")
def add_watch_wallet(req: WatchWalletRequest,
                     x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    with engine.begin() as cx:
        existing = cx.execute(text(
            "SELECT wallet FROM watch_wallet WHERE wallet=:wallet"
        ), {"wallet": req.wallet}).first()
        if existing:
            cx.execute(text("""
                UPDATE watch_wallet SET enabled=:enabled, label=:label
                WHERE wallet=:wallet
            """), {"enabled": req.enabled, "label": req.label, "wallet": req.wallet})
        else:
            cx.execute(text("""
                INSERT INTO watch_wallet (wallet, enabled, label, created_at_utc)
                VALUES (:wallet, :enabled, :label, :created)
            """), {
                "wallet": req.wallet, "enabled": req.enabled,
                "label": req.label, "created": utc_now(),
            })
    realtime.request_watchlist_reload()
    return {
        "mode": "paper-only",
        "wallet": req.wallet,
        "enabled": req.enabled,
        "watchlist_reloaded": True,
    }


@app.post("/realtime/paper-enter/{candidate_id}")
async def realtime_paper_enter(candidate_id: int,
                               x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    pid = await realtime.paper_enter(candidate_id)
    return {"mode": "paper-only", "position_id": pid, "live_trade_sent": False}


@app.post("/realtime/paper-exit/{position_id}")
async def realtime_paper_exit(position_id: int,
                              x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    await realtime.paper_exit(position_id)
    return {"mode": "paper-only", "position_id": position_id, "live_trade_sent": False}


@app.post("/paper/social/ingest")
def social_ingest(event: SocialEvent, x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    source = event.source.strip().lower()
    if source not in {"x", "reddit"}:
        raise HTTPException(400, "source must be x or reddit")

    # Raw post text is deliberately not persisted. We only store a normalized
    # fingerprint and structured provenance/features.
    row = {
        "observed_at_utc": utc_now(),
        "published_at_utc": event.published_at_utc,
        "source": source,
        "external_id": event.external_id,
        "author_id": event.author_id,
        "mint": event.mint,
        "content_fingerprint": content_fingerprint(event.text),
        "author_age_days": event.author_age_days,
        "follower_count": event.follower_count,
        "engagement_count": event.engagement_count,
        "is_verified": event.is_verified,
        "contract_present": event.contract_present,
        "source_url": event.source_url,
    }

    try:
        with engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO social_event (
                    observed_at_utc, published_at_utc, source, external_id, author_id,
                    mint, content_fingerprint, author_age_days, follower_count,
                    engagement_count, is_verified, contract_present, source_url
                ) VALUES (
                    :observed_at_utc, :published_at_utc, :source, :external_id, :author_id,
                    :mint, :content_fingerprint, :author_age_days, :follower_count,
                    :engagement_count, :is_verified, :contract_present, :source_url
                )
            """), row)
    except Exception as exc:
        # Duplicate source/external_id should not create multiple votes.
        if "unique" not in str(exc).lower() and "duplicate" not in str(exc).lower():
            raise
        return {"mode": "paper-only", "inserted": False, "duplicate": True}

    return {
        "mode": "paper-only",
        "inserted": True,
        "raw_text_stored": False,
        "next_action": "RECOMPUTE_SOCIAL_SIGNAL_ONLY",
    }


@app.get("/paper/social/signal/{mint}")
def social_signal(mint: str, x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT published_at_utc, source, author_id, content_fingerprint,
                   author_age_days, follower_count, engagement_count,
                   is_verified, contract_present
            FROM social_event
            WHERE mint = :mint
            ORDER BY id DESC
            LIMIT 1000
        """), {"mint": mint}).mappings().all()

    features = compute_features([dict(r) for r in rows], time.time())
    return {
        "mode": "paper-only",
        "mint": mint,
        "features": features,
        "next_action": "SAMPLE_QUOTES_ONLY" if features["social_candidate"] else "IGNORE",
        "can_authorize_trade": False,
    }


@app.get("/paper/social/recent")
def social_recent(limit: int = 100, x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    limit = min(max(limit, 1), 1000)
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT observed_at_utc, published_at_utc, source, external_id, author_id,
                   mint, author_age_days, follower_count, engagement_count,
                   is_verified, contract_present, source_url
            FROM social_event
            ORDER BY id DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
    return {"mode": "paper-only", "events": [dict(r) for r in rows]}


@app.post("/paper/backfill")
def backfill(req: BackfillRequest, x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    inserted = 0
    wallet_counts = {}

    for wallet in req.wallets:
        txs = _fetch_wallet(wallet, req.days, req.page_limit, req.max_pages)
        count = 0
        for tx in txs:
            meta = tx.get("meta") or {}
            if meta.get("err") is not None:
                continue
            pump = _is_pump(tx)
            if req.pump_only and not pump:
                continue
            sol_delta = _native_delta(tx, wallet)
            pre = _token_map(tx, wallet, "preTokenBalances")
            post = _token_map(tx, wallet, "postTokenBalances")
            sigs = ((tx.get("transaction") or {}).get("signatures") or [])
            sig = sigs[0] if sigs else ""
            bt = int(tx.get("blockTime") or 0)

            for mint in set(pre) | set(post):
                delta = post.get(mint, 0) - pre.get(mint, 0)
                side = None
                if delta > 0 and sol_delta < 0:
                    side = "BUY"
                elif delta < 0 and sol_delta > 0:
                    side = "SELL"
                if not side:
                    continue

                row = {
                    "captured_at_utc": utc_now(),
                    "wallet": wallet,
                    "signature": sig,
                    "block_time": bt,
                    "mint": mint,
                    "side": side,
                    "sol_delta": sol_delta / 1e9,
                    "token_delta_raw": str(delta),
                    "is_pumpfun": pump,
                }
                with engine.begin() as cx:
                    cx.execute(text("""
                        INSERT INTO wallet_replay
                        (captured_at_utc, wallet, signature, block_time, mint, side,
                         sol_delta, token_delta_raw, is_pumpfun)
                        VALUES
                        (:captured_at_utc, :wallet, :signature, :block_time, :mint, :side,
                         :sol_delta, :token_delta_raw, :is_pumpfun)
                    """), row)
                count += 1
                inserted += 1
        wallet_counts[wallet] = count

    return {"mode": "paper-only", "inserted_events": inserted, "wallet_counts": wallet_counts}


@app.get("/paper/export/quote-drift.csv")
def export_quote_csv(x_paper_token: Optional[str] = Header(default=None)):
    require_admin(x_paper_token)
    with engine.begin() as cx:
        rows = cx.execute(text("""
            SELECT observed_at_utc, signal_id, mint, input_mint, amount_lamports,
                   delay_label, scheduled_delay_ms, actual_delay_ms, http_rtt_ms,
                   jupiter_total_time_ms, in_amount, out_amount, baseline_out_amount,
                   drift_bps, fee_bps, price_impact, router, request_id
            FROM quote_drift ORDER BY id
        """)).mappings().all()
    if not rows:
        return {"csv": ""}
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return {"csv": buf.getvalue()}
