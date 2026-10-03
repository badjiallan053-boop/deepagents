"""
Crypto funding / basis tracker (PAPER ONLY).

Snapshots public perpetual-futures market data (no API keys) and evaluates
delta-neutral carry candidates, opens PAPER positions when the net expected
carry over a horizon clears a threshold, marks them to market at every funding
settlement with realized funding + basis P&L, and closes them on rule-based
exits. There is no order placement, no signing, no account access, and no
broker/exchange integration of any kind.

Venues / sources (all free, public, keyless)
--------------------------------------------
* Hyperliquid info API  POST https://api.hyperliquid.xyz/info
    metaAndAssetCtxs (hourly funding, mark, oracle, OI, impact prices),
    spotMetaAndAssetCtxs, l2Book (spot best bid/ask for candidates),
    fundingHistory (realized hourly funding), predictedFundings (also reports
    Binance/Bybit predicted funding; stored as context only).
* OKX public REST v5  funding-rate?instId=ANY, mark-price, market/tickers
    (SWAP + SPOT bid/ask), open-interest, index-tickers, instruments,
    funding-rate-history.
* Binance USD-M public REST  premiumIndex, fundingInfo, ticker/bookTicker,
    ticker/24hr, fundingRate; spot book via data-api.binance.vision.
  Binance (and Bybit) return HTTP 451/403 from some regions (e.g. US); this is
  detected and reported in /funding/status rather than retried aggressively.

Strategies
----------
CASH_CARRY  short perp + long spot on the same venue (only positive funding:
            reverse carry would need a spot borrow, which is not modeled).
PERP_PERP   long perp on the lower-funding venue, short perp on the higher one.

Expected carry (conservative): the hourly carry rate used is the MIN of the
current rate and the trailing 24h mean (realized history); entries require
history. Net = carry * horizon - round-trip fees (both legs, entry + exit) -
round-trip spread/slippage + min(0, entry basis). Basis convergence is only
ever counted against us, never as a gain.

Attribution: the cross-venue design (per-venue funding intervals normalized to
a common time unit, fee-adjusted entry threshold on the funding-rate
difference, exit when the difference reverses beyond a stop or when a profit
target is hit) follows the ideas in Hummingbot's scripts/v2_funding_rate_arb.py
(Apache-2.0, https://github.com/hummingbot/hummingbot). No Hummingbot code is
copied; this is an independent implementation.

Default fees (bps of notional, public base tiers, verify against your tier):
  hyperliquid perp taker 4.5 / maker 1.5, spot taker 7.0 / maker 4.0
      (hyperliquid.gitbook.io/hyperliquid-docs/trading/fees, base rate)
  okx swap taker 5.0 / maker 2.0, spot taker 10.0 / maker 8.0 (Regular user)
  binance usdm taker 5.0 / maker 2.0, spot taker 10.0 / maker 10.0 (regular)
Override with FUNDING_FEES_JSON='{"okx":{"perp_taker":4.0,...}}'.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import math
import os
import random
import statistics
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import text

log = logging.getLogger("funding_basis")

HL_INFO = "https://api.hyperliquid.xyz/info"
OKX = "https://www.okx.com/api/v5"
BINANCE_FAPI = "https://fapi.binance.com/fapi/v1"
BINANCE_SPOT = "https://data-api.binance.vision/api/v3"

DEFAULT_FEES_BPS = {
    "hyperliquid": {"perp_taker": 4.5, "perp_maker": 1.5, "spot_taker": 7.0, "spot_maker": 4.0},
    "okx": {"perp_taker": 5.0, "perp_maker": 2.0, "spot_taker": 10.0, "spot_maker": 8.0},
    "binance": {"perp_taker": 5.0, "perp_maker": 2.0, "spot_taker": 10.0, "spot_maker": 10.0},
}
# Hyperliquid spot tokens that wrap a perp's underlying under another name.
HL_SPOT_ALIASES = {"BTC": "UBTC", "ETH": "UETH", "SOL": "USOL", "FARTCOIN": "UFART", "PUMP": "UPUMP"}
PF_CAP = 999.0


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ms_to_iso(ms: Optional[float]) -> Optional[str]:
    if not ms:
        return None
    return datetime.fromtimestamp(float(ms) / 1000.0, timezone.utc).isoformat()


def fnum(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except ValueError:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None or not v.strip():
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def config() -> dict[str, Any]:
    fees = json.loads(json.dumps(DEFAULT_FEES_BPS))
    try:
        override = json.loads(os.getenv("FUNDING_FEES_JSON", "") or "{}")
        for venue, vals in override.items():
            fees.setdefault(venue, {}).update({k: float(v) for k, v in vals.items()})
    except (ValueError, AttributeError, TypeError):
        pass
    return {
        "venues": [v.strip().lower() for v in (os.getenv("FUNDING_VENUES", "hyperliquid,okx,binance")).split(",") if v.strip()],
        "poll_seconds": max(60.0, env_float("FUNDING_POLL_SECONDS", 300)),
        "notional_usd": env_float("FUNDING_NOTIONAL_USD", 10_000),
        "horizon_hours": env_float("FUNDING_HORIZON_HOURS", 72),
        "entry_min_net_bps": env_float("FUNDING_ENTRY_MIN_NET_BPS", 10),
        "leverage": env_float("FUNDING_LEVERAGE", 3),
        "default_mmr": env_float("FUNDING_DEFAULT_MMR", 0.01),
        "min_liq_distance_pct": env_float("FUNDING_MIN_LIQ_DISTANCE_PCT", 20),
        "min_oi_usd": env_float("FUNDING_MIN_OI_USD", 5_000_000),
        "min_volume_usd": env_float("FUNDING_MIN_VOLUME_USD", 10_000_000),
        "max_spread_bps": env_float("FUNDING_MAX_SPREAD_BPS", 15),
        "slippage_extra_bps": env_float("FUNDING_SLIPPAGE_EXTRA_BPS", 2),
        "max_flip_rate": env_float("FUNDING_MAX_FLIP_RATE", 0.25),
        "max_price_mismatch_pct": env_float("FUNDING_MAX_PRICE_MISMATCH_PCT", 3),
        "fee_mode": (os.getenv("FUNDING_FEE_MODE", "taker") or "taker").lower(),
        "fees_bps": fees,
        "max_open_per_strategy": int(env_float("FUNDING_MAX_OPEN_PER_STRATEGY", 10)),
        "history_candidates": int(env_float("FUNDING_HISTORY_CANDIDATES", 12)),
        "stop_loss_bps": env_float("FUNDING_STOP_LOSS_BPS", 75),
        "exit_flip_obs": int(env_float("FUNDING_EXIT_FLIP_OBS", 2)),
        "liq_guard_fraction": env_float("FUNDING_LIQ_GUARD_FRACTION", 0.5),
        "note": "fees are public base-tier defaults; probabilities are not used; all P&L is paper",
    }


def check_read_or_admin(token: Optional[str]) -> tuple[int, str]:
    """(status, detail); 200 = authorized. PAPER_READ_TOKEN or PAPER_ADMIN_TOKEN."""
    admin = os.getenv("PAPER_ADMIN_TOKEN", "")
    reader = os.getenv("PAPER_READ_TOKEN", "")
    if not admin and not reader:
        return 503, "PAPER_ADMIN_TOKEN is not configured"
    if token:
        for expected in (admin, reader):
            if expected and hmac.compare_digest(token.encode(), expected.encode()):
                return 200, "ok"
    return 401, "unauthorized"


# ---------------------------------------------------------------------------
# normalization of raw venue payloads (pure functions, fixture-tested)
# ---------------------------------------------------------------------------

def _hl_base(name: str) -> tuple[str, float]:
    """Hyperliquid 'kPEPE' quotes 1000 PEPE; return (base, units_per_quote)."""
    if len(name) > 1 and name[0] == "k" and name[1:].isupper():
        return name[1:], 1000.0
    return name, 1.0


def _spread_bps(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
    if not bid or not ask or bid <= 0 or ask < bid:
        return None
    mid = (bid + ask) / 2
    return (ask - bid) / mid * 1e4


def parse_hyperliquid(meta_ctx: Any, spot_ctx: Any = None, predicted: Any = None,
                      now_ms: Optional[float] = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    now_ms = now_ms or time.time() * 1000
    next_hour = (int(now_ms // 3_600_000) + 1) * 3_600_000
    meta, ctxs = meta_ctx
    for u, c in zip(meta.get("universe", []), ctxs):
        if u.get("isDelisted"):
            continue
        base, mult = _hl_base(u["name"])
        mark = fnum(c.get("markPx"))
        oracle = fnum(c.get("oraclePx"))
        if not mark:
            continue
        imp = c.get("impactPxs") or [None, None]
        bid, ask = fnum(imp[0]), fnum(imp[1]) if len(imp) > 1 else None
        rate = fnum(c.get("funding"))
        max_lev = fnum(u.get("maxLeverage"))
        out.append({
            "venue": "hyperliquid", "kind": "perp", "symbol": base, "venue_symbol": u["name"],
            "price_mult": mult,
            "funding_rate": rate, "funding_interval_h": 1.0,
            "funding_rate_hourly": rate,
            "next_funding_ms": next_hour,
            "mark": mark / mult, "index_px": (oracle / mult) if oracle else None,
            "bid": (bid / mult) if bid else None, "ask": (ask / mult) if ask else None,
            "spread_bps": _spread_bps(bid, ask), "spread_source": "impactPxs",
            "open_interest_usd": (fnum(c.get("openInterest")) or 0) * mark,
            "volume_24h_usd": fnum(c.get("dayNtlVlm")),
            "max_leverage": max_lev,
            "mmr": (0.5 / max_lev) if max_lev else None,  # HL maintenance = half of initial margin at max leverage
            "basis_bps": ((mark - oracle) / oracle * 1e4) if oracle else None,
            "source": "hyperliquid metaAndAssetCtxs",
        })
    if spot_ctx:
        smeta, sctxs = spot_ctx
        toks = {t["index"]: t["name"] for t in smeta.get("tokens", [])}
        by_coin = {c.get("coin"): c for c in sctxs}
        for u in smeta.get("universe", []):
            ti = u.get("tokens") or []
            if len(ti) != 2 or toks.get(ti[1]) != "USDC":
                continue
            c = by_coin.get(u["name"]) or {}
            mid = fnum(c.get("midPx")) or fnum(c.get("markPx"))
            if not mid:
                continue
            out.append({
                "venue": "hyperliquid", "kind": "spot", "symbol": toks.get(ti[0]), "venue_symbol": u["name"],
                "price_mult": 1.0, "mark": mid, "bid": None, "ask": None, "spread_bps": None,
                "spread_source": None, "volume_24h_usd": fnum(c.get("dayNtlVlm")),
                "source": "hyperliquid spotMetaAndAssetCtxs",
            })
    for row in predicted or []:
        try:
            coin, venues = row
        except (TypeError, ValueError):
            continue
        base, _mult = _hl_base(coin)
        for vname, v in venues or []:
            if not v or vname == "HlPerp":
                continue
            rate = fnum(v.get("fundingRate"))
            ih = fnum(v.get("fundingIntervalHours")) or 8.0
            out.append({
                "venue": {"BinPerp": "binance", "BybitPerp": "bybit"}.get(vname, vname.lower()),
                "kind": "predicted", "symbol": base, "venue_symbol": coin, "price_mult": 1.0,
                "funding_rate": rate, "funding_interval_h": ih,
                "funding_rate_hourly": (rate / ih) if rate is not None else None,
                "next_funding_ms": fnum(v.get("nextFundingTime")),
                "source": "hyperliquid predictedFundings (context only; no prices)",
            })
    return out


def parse_okx(funding: dict, marks: dict, swap_tickers: dict, oi: dict, index: dict,
              instruments: Optional[dict] = None, spot_tickers: Optional[dict] = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    mk = {d["instId"]: fnum(d.get("markPx")) for d in marks.get("data", [])}
    tk = {d["instId"]: d for d in swap_tickers.get("data", [])}
    oim = {d["instId"]: fnum(d.get("oiUsd")) for d in oi.get("data", [])}
    idx = {d["instId"]: fnum(d.get("idxPx")) for d in index.get("data", [])}
    lev = {d["instId"]: fnum(d.get("lever")) for d in (instruments or {}).get("data", [])}
    for f in funding.get("data", []):
        inst = f.get("instId", "")
        if not inst.endswith("-USDT-SWAP"):
            continue  # linear USDT-margined only
        base = inst[: -len("-USDT-SWAP")]
        mark = mk.get(inst)
        if not mark:
            continue
        rate = fnum(f.get("fundingRate"))
        ft, pft = fnum(f.get("fundingTime")), fnum(f.get("prevFundingTime"))
        ih = ((ft - pft) / 3_600_000.0) if ft and pft and ft > pft else 8.0
        t = tk.get(inst) or {}
        bid, ask, last = fnum(t.get("bidPx")), fnum(t.get("askPx")), fnum(t.get("last"))
        ix = idx.get(f"{base}-USDT")
        vol_base = fnum(t.get("volCcy24h"))
        hi, lo, op = fnum(t.get("high24h")), fnum(t.get("low24h")), fnum(t.get("open24h"))
        out.append({
            "venue": "okx", "kind": "perp", "symbol": base, "venue_symbol": inst, "price_mult": 1.0,
            "funding_rate": rate, "funding_interval_h": ih,
            "funding_rate_hourly": (rate / ih) if rate is not None else None,
            "next_funding_ms": ft, "mark": mark, "index_px": ix, "bid": bid, "ask": ask,
            "spread_bps": _spread_bps(bid, ask), "spread_source": "top of book",
            "open_interest_usd": oim.get(inst),
            "volume_24h_usd": (vol_base * last) if vol_base and last else None,
            "range_24h_pct": ((hi - lo) / op * 100) if hi and lo and op else None,
            "max_leverage": lev.get(inst), "mmr": None,
            "basis_bps": ((mark - ix) / ix * 1e4) if ix else None,
            "source": "okx public v5",
        })
    for t in (spot_tickers or {}).get("data", []):
        inst = t.get("instId", "")
        if not inst.endswith("-USDT"):
            continue
        bid, ask, last = fnum(t.get("bidPx")), fnum(t.get("askPx")), fnum(t.get("last"))
        if not last:
            continue
        vol_quote = fnum(t.get("volCcy24h"))
        out.append({
            "venue": "okx", "kind": "spot", "symbol": inst[:-5], "venue_symbol": inst, "price_mult": 1.0,
            "mark": ((bid + ask) / 2) if bid and ask else last, "bid": bid, "ask": ask,
            "spread_bps": _spread_bps(bid, ask), "spread_source": "top of book",
            "volume_24h_usd": vol_quote, "source": "okx public v5",
        })
    return out


def parse_binance(premium: list, funding_info: Optional[list] = None, book: Optional[list] = None,
                  t24: Optional[list] = None, spot_book: Optional[list] = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    interval = {d["symbol"]: fnum(d.get("fundingIntervalHours")) for d in (funding_info or [])}
    bk = {d["symbol"]: d for d in (book or [])}
    vol = {d["symbol"]: fnum(d.get("quoteVolume")) for d in (t24 or [])}
    for p in premium or []:
        sym = p.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        mark, ix = fnum(p.get("markPrice")), fnum(p.get("indexPrice"))
        if not mark:
            continue
        rate = fnum(p.get("lastFundingRate"))
        ih = interval.get(sym) or 8.0
        b = bk.get(sym) or {}
        bid, ask = fnum(b.get("bidPrice")), fnum(b.get("askPrice"))
        out.append({
            "venue": "binance", "kind": "perp", "symbol": sym[:-4], "venue_symbol": sym, "price_mult": 1.0,
            "funding_rate": rate, "funding_interval_h": ih,
            "funding_rate_hourly": (rate / ih) if rate is not None else None,
            "next_funding_ms": fnum(p.get("nextFundingTime")), "mark": mark, "index_px": ix,
            "bid": bid, "ask": ask, "spread_bps": _spread_bps(bid, ask), "spread_source": "top of book",
            "open_interest_usd": None, "volume_24h_usd": vol.get(sym), "max_leverage": None, "mmr": None,
            "basis_bps": ((mark - ix) / ix * 1e4) if ix else None, "source": "binance usdm public",
        })
    for b in spot_book or []:
        sym = b.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        bid, ask = fnum(b.get("bidPrice")), fnum(b.get("askPrice"))
        if not bid or not ask:
            continue
        out.append({
            "venue": "binance", "kind": "spot", "symbol": sym[:-4], "venue_symbol": sym, "price_mult": 1.0,
            "mark": (bid + ask) / 2, "bid": bid, "ask": ask, "spread_bps": _spread_bps(bid, ask),
            "spread_source": "top of book", "volume_24h_usd": None, "source": "binance spot (data-api.binance.vision)",
        })
    return out


def parse_hl_l2(book: Any) -> tuple[Optional[float], Optional[float]]:
    try:
        bids, asks = book["levels"]
        return fnum(bids[0]["px"]), fnum(asks[0]["px"])
    except (TypeError, KeyError, IndexError, ValueError):
        return None, None


def history_hourly(venue: str, payload: Any) -> list[tuple[float, float]]:
    """Return [(time_ms, hourly_rate)] realized funding history."""
    rows: list[tuple[float, float]] = []
    if venue == "hyperliquid":
        for r in payload or []:
            t, f = fnum(r.get("time")), fnum(r.get("fundingRate"))
            if t is not None and f is not None:
                rows.append((t, f))
        return sorted(rows)
    if venue == "okx":
        data = sorted((payload or {}).get("data", []), key=lambda r: float(r.get("fundingTime", 0)))
        for i, r in enumerate(data):
            t = fnum(r.get("fundingTime"))
            f = fnum(r.get("realizedRate")) if r.get("realizedRate") not in (None, "") else fnum(r.get("fundingRate"))
            if t is None or f is None:
                continue
            ih = ((t - fnum(data[i - 1]["fundingTime"])) / 3_600_000.0) if i > 0 else 8.0
            rows.append((t, f / (ih if ih and ih > 0 else 8.0)))
        return rows
    if venue == "binance":
        data = sorted(payload or [], key=lambda r: float(r.get("fundingTime", 0)))
        for i, r in enumerate(data):
            t, f = fnum(r.get("fundingTime")), fnum(r.get("fundingRate"))
            if t is None or f is None:
                continue
            ih = ((t - fnum(data[i - 1]["fundingTime"])) / 3_600_000.0) if i > 0 else 8.0
            rows.append((t, f / (ih if ih and ih > 0 else 8.0)))
        return rows
    return rows


def settlements(venue: str, payload: Any) -> list[tuple[float, float]]:
    """Realized funding settlements [(time_ms, rate_per_interval)]."""
    if venue == "hyperliquid":
        return sorted((fnum(r["time"]), fnum(r["fundingRate"])) for r in payload or []
                      if fnum(r.get("time")) is not None and fnum(r.get("fundingRate")) is not None)
    if venue == "okx":
        out = []
        for r in (payload or {}).get("data", []):
            t = fnum(r.get("fundingTime"))
            f = fnum(r.get("realizedRate")) if r.get("realizedRate") not in (None, "") else fnum(r.get("fundingRate"))
            if t is not None and f is not None:
                out.append((t, f))
        return sorted(out)
    if venue == "binance":
        return sorted((fnum(r["fundingTime"]), fnum(r["fundingRate"])) for r in payload or []
                      if fnum(r.get("fundingTime")) is not None and fnum(r.get("fundingRate")) is not None)
    return []


def step_series(hist: list[tuple[float, float]], start_ms: float, end_ms: float) -> list[float]:
    """Hourly samples of a step function (rate in effect = latest settlement <= t)."""
    if not hist:
        return []
    out = []
    t = start_ms
    i = 0
    cur = None
    while t <= end_ms:
        while i < len(hist) and hist[i][0] <= t:
            cur = hist[i][1]
            i += 1
        if cur is not None:
            out.append(cur)
        t += 3_600_000
    return out


# ---------------------------------------------------------------------------
# opportunity evaluation (pure)
# ---------------------------------------------------------------------------

def liq_distance_pct(leverage: float, mmr: Optional[float], default_mmr: float) -> float:
    m = mmr if mmr is not None else default_mmr
    return max(0.0, (1.0 / max(leverage, 1e-9) - m) * 100.0)


def _fee(cfg: dict, venue: str, kind: str) -> float:
    f = cfg["fees_bps"].get(venue, {})
    mode = "maker" if cfg["fee_mode"] == "maker" else "taker"
    return float(f.get(f"{'perp' if kind == 'perp' else 'spot'}_{mode}", 10.0))


def _leg_spread(leg: dict, cfg: dict) -> Optional[float]:
    return leg.get("spread_bps")


def evaluate_candidate(strategy: str, long_leg: dict, short_leg: dict, cfg: dict,
                       hist_long: Optional[list[tuple[float, float]]] = None,
                       hist_short: Optional[list[tuple[float, float]]] = None,
                       now_ms: Optional[float] = None) -> dict[str, Any]:
    """Evaluate a delta-neutral carry pair. long_leg/short_leg are snapshot dicts.
    Carry is received by the short perp when its funding is positive and by the
    long perp when its funding is negative."""
    now_ms = now_ms or time.time() * 1000
    H = cfg["horizon_hours"]
    checks: dict[str, Any] = {}
    f_short = short_leg.get("funding_rate_hourly") or 0.0
    f_long = long_leg.get("funding_rate_hourly") if long_leg.get("kind") == "perp" else 0.0
    f_long = f_long or 0.0
    current = f_short - f_long  # hourly carry rate (fraction of notional)
    trailing = None
    flip_rate = None
    start = now_ms - 24 * 3_600_000
    if hist_short is not None and (long_leg.get("kind") != "perp" or hist_long is not None):
        s_short = step_series(hist_short, start, now_ms)
        s_long = step_series(hist_long, start, now_ms) if long_leg.get("kind") == "perp" else [0.0] * len(s_short)
        n = min(len(s_short), len(s_long))
        if n >= 6:
            diffs = [s_short[-n:][i] - s_long[-n:][i] for i in range(n)]
            trailing = sum(diffs) / n
            flip_rate = sum(1 for d in diffs if d <= 0) / n
    expected = min(current, trailing) if trailing is not None else current
    checks["history_available"] = trailing is not None
    gross_bps = expected * H * 1e4
    fees_bps = 2 * (_fee(cfg, long_leg["venue"], long_leg["kind"]) + _fee(cfg, short_leg["venue"], short_leg["kind"]))
    sp_l, sp_s = _leg_spread(long_leg, cfg), _leg_spread(short_leg, cfg)
    checks["spreads_known"] = sp_l is not None and sp_s is not None
    slip_bps = (sp_l or 0.0) + (sp_s or 0.0) + 4 * cfg["slippage_extra_bps"]
    # basis between the two legs, measured at execution side (short sells bid, long buys ask)
    sell_px = short_leg.get("bid") or short_leg.get("mark")
    buy_px = long_leg.get("ask") or long_leg.get("mark")
    basis_bps = ((sell_px - buy_px) / buy_px * 1e4) if sell_px and buy_px else None
    basis_adj = min(0.0, basis_bps) if basis_bps is not None else 0.0
    mism = abs((short_leg["mark"] - long_leg["mark"]) / long_leg["mark"] * 100) if long_leg.get("mark") else 999
    checks["price_match"] = mism <= cfg["max_price_mismatch_pct"]
    net_bps = gross_bps - fees_bps - slip_bps + basis_adj
    lev = cfg["leverage"]
    perp_legs = [lg for lg in (long_leg, short_leg) if lg.get("kind") == "perp"]
    liq = min(liq_distance_pct(lev, lg.get("mmr"), cfg["default_mmr"]) for lg in perp_legs)
    checks["liq_distance_ok"] = liq >= cfg["min_liq_distance_pct"]
    checks["leverage_allowed"] = all((lg.get("max_leverage") or lev) >= lev for lg in perp_legs)
    rng = max([lg.get("range_24h_pct") or 0.0 for lg in perp_legs] or [0.0])
    checks["oi_ok"] = all((lg.get("open_interest_usd") or 0) >= cfg["min_oi_usd"] for lg in perp_legs
                          if lg.get("open_interest_usd") is not None) and any(
        lg.get("open_interest_usd") is not None for lg in perp_legs)
    checks["volume_ok"] = all((lg.get("volume_24h_usd") or 0) >= cfg["min_volume_usd"] for lg in (long_leg, short_leg))
    checks["spread_ok"] = checks["spreads_known"] and max(sp_l or 0, sp_s or 0) <= cfg["max_spread_bps"]
    checks["positive_current_carry"] = current > 0
    checks["flip_rate_ok"] = flip_rate is not None and flip_rate <= cfg["max_flip_rate"]
    eligible = all(bool(v) for v in checks.values())
    return {
        "strategy": strategy, "symbol": short_leg["symbol"],
        "venue_long": long_leg["venue"], "kind_long": long_leg["kind"],
        "venue_short": short_leg["venue"], "kind_short": short_leg["kind"],
        "carry_hourly_current": current, "carry_hourly_trailing_24h": trailing,
        "carry_hourly_expected": expected, "carry_apr_pct_expected": expected * 24 * 365 * 100,
        "horizon_h": H, "gross_bps": gross_bps, "fees_bps": fees_bps, "slippage_bps": slip_bps,
        "basis_bps": basis_bps, "basis_adj_bps": basis_adj, "net_bps": net_bps,
        "net_usd": net_bps / 1e4 * cfg["notional_usd"], "flip_rate_24h": flip_rate,
        "liq_distance_pct": liq, "range_24h_pct": rng or None,
        "price_mismatch_pct": mism, "checks": checks, "eligible": eligible,
        "next_funding_short": ms_to_iso(short_leg.get("next_funding_ms")),
        "long_px": buy_px, "short_px": sell_px,
    }


def build_candidates(snaps: list[dict], cfg: dict) -> list[tuple[str, dict, dict]]:
    perps: dict[str, dict[str, dict]] = {}
    spots: dict[str, dict[str, dict]] = {}
    for s in snaps:
        if s["kind"] == "perp" and s.get("funding_rate_hourly") is not None:
            perps.setdefault(s["symbol"], {})[s["venue"]] = s
        elif s["kind"] == "spot":
            spots.setdefault(s["venue"], {})[s["symbol"]] = s
    out = []
    for sym, by_venue in perps.items():
        for venue, p in by_venue.items():
            if (p["funding_rate_hourly"] or 0) > 0:
                sp_name = sym
                vs = spots.get(venue, {})
                spot = vs.get(sym)
                if spot is None and venue == "hyperliquid":
                    spot = vs.get(HL_SPOT_ALIASES.get(sym, "U" + sym))
                if spot is not None:
                    spot = dict(spot, symbol=sym, spot_token=spot.get("symbol") or sp_name)
                    out.append(("CASH_CARRY", spot, p))
        venues = sorted(by_venue)
        for i in range(len(venues)):
            for j in range(i + 1, len(venues)):
                a, b = by_venue[venues[i]], by_venue[venues[j]]
                if a["funding_rate_hourly"] == b["funding_rate_hourly"]:
                    continue
                long_leg, short_leg = (a, b) if a["funding_rate_hourly"] < b["funding_rate_hourly"] else (b, a)
                out.append(("PERP_PERP", long_leg, short_leg))
    return out


def scorecard_stats(pnls_bps: list[float], seed: int = 7, resamples: int = 2000) -> dict[str, Any]:
    n = len(pnls_bps)
    if n == 0:
        return {"count": 0, "mean_bps": None, "median_bps": None, "profit_factor": None,
                "profit_factor_capped": False, "hit_rate": None, "bootstrap_mean_lower95_bps": None}
    wins = sum(p for p in pnls_bps if p > 0)
    losses = -sum(p for p in pnls_bps if p < 0)
    if losses > 0:
        pf = wins / losses
        capped = pf > PF_CAP
        pf = min(pf, PF_CAP)
    else:
        pf, capped = (PF_CAP, True) if wins > 0 else (None, False)
    lb = None
    if n >= 2:
        rng = random.Random(seed)
        means = sorted(sum(rng.choice(pnls_bps) for _ in range(n)) / n for _ in range(resamples))
        lb = means[int(0.025 * resamples)]
    return {
        "count": n, "mean_bps": sum(pnls_bps) / n, "median_bps": statistics.median(pnls_bps),
        "profit_factor": pf, "profit_factor_capped": capped,
        "hit_rate": sum(1 for p in pnls_bps if p > 0) / n,
        "bootstrap_mean_lower95_bps": lb, "bootstrap_resamples": resamples if n >= 2 else 0,
    }


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------

def ensure_funding_tables(engine) -> None:
    sqlite = str(engine.url).startswith("sqlite")
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if sqlite else "BIGSERIAL PRIMARY KEY"
    stmts = [
        f"""CREATE TABLE IF NOT EXISTS funding_snapshot (
            id {pk},
            ts_utc TEXT NOT NULL,
            venue TEXT NOT NULL,
            kind TEXT NOT NULL,
            symbol TEXT NOT NULL,
            venue_symbol TEXT,
            funding_rate DOUBLE PRECISION,
            funding_interval_h DOUBLE PRECISION,
            funding_rate_hourly DOUBLE PRECISION,
            next_funding_utc TEXT,
            mark DOUBLE PRECISION,
            index_px DOUBLE PRECISION,
            basis_bps DOUBLE PRECISION,
            open_interest_usd DOUBLE PRECISION,
            volume_24h_usd DOUBLE PRECISION,
            bid DOUBLE PRECISION,
            ask DOUBLE PRECISION,
            spread_bps DOUBLE PRECISION,
            spread_source TEXT,
            max_leverage DOUBLE PRECISION,
            source TEXT,
            is_latest INTEGER NOT NULL DEFAULT 1
        )""",
        f"""CREATE TABLE IF NOT EXISTS funding_opportunity (
            id {pk},
            ts_utc TEXT NOT NULL,
            strategy TEXT NOT NULL,
            symbol TEXT NOT NULL,
            venue_long TEXT NOT NULL,
            kind_long TEXT NOT NULL,
            venue_short TEXT NOT NULL,
            kind_short TEXT NOT NULL,
            net_bps DOUBLE PRECISION,
            gross_bps DOUBLE PRECISION,
            fees_bps DOUBLE PRECISION,
            slippage_bps DOUBLE PRECISION,
            basis_bps DOUBLE PRECISION,
            carry_apr_pct DOUBLE PRECISION,
            flip_rate_24h DOUBLE PRECISION,
            liq_distance_pct DOUBLE PRECISION,
            eligible INTEGER NOT NULL DEFAULT 0,
            entered INTEGER NOT NULL DEFAULT 0,
            detail_json TEXT
        )""",
        f"""CREATE TABLE IF NOT EXISTS funding_position (
            id {pk},
            opened_at_utc TEXT NOT NULL,
            strategy TEXT NOT NULL,
            symbol TEXT NOT NULL,
            venue_long TEXT NOT NULL,
            kind_long TEXT NOT NULL,
            venue_symbol_long TEXT,
            venue_short TEXT NOT NULL,
            kind_short TEXT NOT NULL,
            venue_symbol_short TEXT,
            notional_usd DOUBLE PRECISION NOT NULL,
            leverage DOUBLE PRECISION NOT NULL,
            entry_long_px DOUBLE PRECISION NOT NULL,
            entry_short_px DOUBLE PRECISION NOT NULL,
            entry_net_bps_expected DOUBLE PRECISION,
            entry_detail_json TEXT,
            status TEXT NOT NULL,
            funding_pnl_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
            basis_pnl_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
            fees_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
            last_funding_ms_long DOUBLE PRECISION,
            last_funding_ms_short DOUBLE PRECISION,
            flip_obs INTEGER NOT NULL DEFAULT 0,
            stale_obs INTEGER NOT NULL DEFAULT 0,
            last_mtm_at_utc TEXT,
            closed_at_utc TEXT,
            exit_reason TEXT,
            exit_long_px DOUBLE PRECISION,
            exit_short_px DOUBLE PRECISION,
            pnl_usd DOUBLE PRECISION,
            pnl_bps DOUBLE PRECISION
        )""",
        f"""CREATE TABLE IF NOT EXISTS funding_mtm (
            id {pk},
            position_id BIGINT NOT NULL,
            ts_utc TEXT NOT NULL,
            settlements INTEGER NOT NULL DEFAULT 0,
            funding_accrued_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
            funding_pnl_usd DOUBLE PRECISION,
            basis_pnl_usd DOUBLE PRECISION,
            total_pnl_usd DOUBLE PRECISION,
            detail_json TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS ix_funding_snapshot_latest ON funding_snapshot (is_latest, venue, kind, symbol)",
        "CREATE INDEX IF NOT EXISTS ix_funding_opp_ts ON funding_opportunity (ts_utc)",
        "CREATE INDEX IF NOT EXISTS ix_funding_pos_status ON funding_position (status, strategy)",
    ]
    for s in stmts:  # one transaction per statement (Postgres aborts the whole tx on any error)
        with engine.begin() as cx:
            cx.execute(text(s))


# ---------------------------------------------------------------------------
# HTTP client with per-host throttle and backoff
# ---------------------------------------------------------------------------

class PublicClient:
    # Hyperliquid: 1200 weight/min per IP; info calls weigh 2-20+ -> stay well under.
    MIN_INTERVAL = {"api.hyperliquid.xyz": 1.0, "www.okx.com": 0.25, "fapi.binance.com": 0.25,
                    "data-api.binance.vision": 0.25}

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None):
        self._c = httpx.AsyncClient(timeout=20.0, transport=transport,
                                    headers={"User-Agent": "survival-alpha-paper-funding/1.0"})
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self.requests = 0
        self.errors: dict[str, str] = {}

    async def close(self) -> None:
        await self._c.aclose()

    async def _wait(self, host: str) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            gap = self._last.get(host, 0) + self.MIN_INTERVAL.get(host, 0.5) - time.monotonic()
            if gap > 0:
                await asyncio.sleep(gap)
            self._last[host] = time.monotonic()

    async def request(self, method: str, url: str, **kw) -> Any:
        host = httpx.URL(url).host
        delay = 3.0
        attempts = 4
        for attempt in range(attempts):
            await self._wait(host)
            self.requests += 1
            try:
                r = await self._c.request(method, url, **kw)
            except httpx.TransportError:
                if attempt == attempts - 1:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
                continue
            if r.status_code in (451, 403):
                raise VenueBlocked(f"{host}: HTTP {r.status_code} (restricted location / access denied)")
            if r.status_code == 429 or r.status_code >= 500:
                self.errors[host] = f"HTTP {r.status_code}"
                if attempt == attempts - 1:
                    r.raise_for_status()
                ra = r.headers.get("Retry-After")
                await asyncio.sleep(min(30.0, float(ra)) if ra and ra.replace(".", "").isdigit() else delay)
                delay *= 2
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"request failed: {url}")

    async def hl(self, body: dict) -> Any:
        return await self.request("POST", HL_INFO, json=body)

    async def get(self, url: str) -> Any:
        return await self.request("GET", url)


class VenueBlocked(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# tracker
# ---------------------------------------------------------------------------

class FundingBasisTracker:
    def __init__(self, engine, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.engine = engine
        self.transport = transport
        ensure_funding_tables(engine)
        self._task: Optional[asyncio.Task] = None
        self.last_scan: dict[str, Any] = {}
        self.last_error: Optional[str] = None
        self.venue_status: dict[str, dict[str, Any]] = {}
        self.scans = 0

    @staticmethod
    def enabled() -> bool:
        return env_bool("FUNDING_BASIS_ENABLED", False)

    def idle_reasons(self) -> list[str]:
        r = []
        if not self.enabled():
            r.append("FUNDING_BASIS_ENABLED is not true (feature flag off)")
        for v, st in self.venue_status.items():
            if st.get("blocked"):
                r.append(f"{v}: {st.get('error')}")
        return r

    async def start(self) -> None:
        if not self.enabled() or self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await self.scan_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"[:500]
                log.exception("funding scan failed")
            await asyncio.sleep(config()["poll_seconds"])

    # -- fetching ------------------------------------------------------------------
    async def fetch_venue(self, client: PublicClient, venue: str) -> list[dict[str, Any]]:
        if venue == "hyperliquid":
            meta = await client.hl({"type": "metaAndAssetCtxs"})
            spot = await client.hl({"type": "spotMetaAndAssetCtxs"})
            pred = None
            try:
                pred = await client.hl({"type": "predictedFundings"})
            except Exception as e:  # context only
                log.info("predictedFundings unavailable: %s", e)
            return parse_hyperliquid(meta, spot, pred)
        if venue == "okx":
            fund = await client.get(f"{OKX}/public/funding-rate?instId=ANY")
            marks = await client.get(f"{OKX}/public/mark-price?instType=SWAP")
            tick = await client.get(f"{OKX}/market/tickers?instType=SWAP")
            oi = await client.get(f"{OKX}/public/open-interest?instType=SWAP")
            idx = await client.get(f"{OKX}/market/index-tickers?quoteCcy=USDT")
            inst = await client.get(f"{OKX}/public/instruments?instType=SWAP")
            spot = await client.get(f"{OKX}/market/tickers?instType=SPOT")
            return parse_okx(fund, marks, tick, oi, idx, inst, spot)
        if venue == "binance":
            prem = await client.get(f"{BINANCE_FAPI}/premiumIndex")
            finfo = await client.get(f"{BINANCE_FAPI}/fundingInfo")
            book = await client.get(f"{BINANCE_FAPI}/ticker/bookTicker")
            t24 = await client.get(f"{BINANCE_FAPI}/ticker/24hr")
            spot = None
            try:
                spot = await client.get(f"{BINANCE_SPOT}/ticker/bookTicker")
            except Exception as e:
                log.info("binance spot book unavailable: %s", e)
            return parse_binance(prem, finfo, book, t24, spot)
        raise ValueError(f"unknown venue {venue}")

    async def fetch_history(self, client: PublicClient, venue: str, venue_symbol: str,
                            start_ms: float) -> Any:
        if venue == "hyperliquid":
            return await client.hl({"type": "fundingHistory", "coin": venue_symbol, "startTime": int(start_ms)})
        if venue == "okx":
            return await client.get(f"{OKX}/public/funding-rate-history?instId={venue_symbol}&limit=100")
        if venue == "binance":
            return await client.get(f"{BINANCE_FAPI}/fundingRate?symbol={venue_symbol}&startTime={int(start_ms)}&limit=1000")
        return None

    # -- storage helpers -------------------------------------------------------------
    def _store_snapshots(self, snaps: list[dict], ts: str) -> None:
        cols = ["venue", "kind", "symbol", "venue_symbol", "funding_rate", "funding_interval_h",
                "funding_rate_hourly", "mark", "index_px", "basis_bps", "open_interest_usd", "volume_24h_usd",
                "bid", "ask", "spread_bps", "spread_source", "max_leverage", "source"]
        rows = []
        for s in snaps:
            r = {c: s.get(c) for c in cols}
            r["ts_utc"] = ts
            r["next_funding_utc"] = ms_to_iso(s.get("next_funding_ms"))
            r["is_latest"] = 1
            rows.append(r)
        with self.engine.begin() as cx:
            # keep history only for symbols that matter (candidates / open positions); others are latest-only
            cx.execute(text("UPDATE funding_snapshot SET is_latest=0 WHERE is_latest=1"))
            cx.execute(text("DELETE FROM funding_snapshot WHERE is_latest=0 AND symbol NOT IN "
                            "(SELECT DISTINCT symbol FROM funding_position) AND symbol NOT IN "
                            "(SELECT DISTINCT symbol FROM funding_opportunity WHERE eligible=1)"))
            if rows:
                cx.execute(text(f"""INSERT INTO funding_snapshot (ts_utc, next_funding_utc, is_latest, {', '.join(cols)})
                                    VALUES (:ts_utc, :next_funding_utc, :is_latest, {', '.join(':' + c for c in cols)})"""),
                           rows)

    # -- main scan ---------------------------------------------------------------------
    async def scan_once(self, now_ms: Optional[float] = None) -> dict[str, Any]:
        cfg = config()
        now_ms = now_ms or time.time() * 1000
        ts = ms_to_iso(now_ms)
        client = PublicClient(self.transport)
        summary: dict[str, Any] = {"started_at_utc": ts, "venues": {}, "snapshots": 0, "candidates": 0,
                                   "eligible": 0, "entered": 0, "closed": 0, "mtm_rows": 0}
        try:
            snaps: list[dict] = []
            for v in cfg["venues"]:
                try:
                    vs = await self.fetch_venue(client, v)
                    snaps.extend(vs)
                    self.venue_status[v] = {"ok": True, "rows": len(vs), "at": ts, "blocked": False}
                except VenueBlocked as e:
                    self.venue_status[v] = {"ok": False, "blocked": True, "error": str(e), "at": ts}
                except Exception as e:
                    self.venue_status[v] = {"ok": False, "blocked": False, "error": f"{type(e).__name__}: {e}"[:300], "at": ts}
            summary["venues"] = {k: {kk: vv for kk, vv in s.items() if kk != "at"} for k, s in self.venue_status.items()}
            summary["snapshots"] = len(snaps)
            # HL spot books for cash-carry candidates (impact/top-of-book needed for spread)
            cands = build_candidates(snaps, cfg)
            summary["candidates"] = len(cands)
            prelim = [evaluate_candidate(s, lg, sg, cfg, now_ms=now_ms) for s, lg, sg in cands]
            order = sorted(range(len(cands)), key=lambda i: prelim[i]["gross_bps"] - prelim[i]["fees_bps"], reverse=True)
            top = [i for i in order if prelim[i]["checks"]["price_match"] and prelim[i]["checks"]["volume_ok"]
                   and prelim[i]["checks"]["positive_current_carry"]][: cfg["history_candidates"]]
            hist_cache: dict[tuple[str, str], Optional[list]] = {}
            evaluated = []
            for i in top:
                strat, lg, sg = cands[i]
                if lg["venue"] == "hyperliquid" and lg["kind"] == "spot" and lg.get("bid") is None:
                    try:
                        b, a = parse_hl_l2(await client.hl({"type": "l2Book", "coin": lg["venue_symbol"]}))
                        lg = dict(lg, bid=b, ask=a, spread_bps=_spread_bps(b, a), spread_source="l2Book")
                    except Exception as e:
                        log.info("l2Book failed %s: %s", lg["venue_symbol"], e)
                hl_, hs_ = None, None
                for leg in (lg, sg):
                    if leg["kind"] != "perp":
                        continue
                    key = (leg["venue"], leg["venue_symbol"])
                    if key not in hist_cache:
                        try:
                            raw = await self.fetch_history(client, leg["venue"], leg["venue_symbol"], now_ms - 26 * 3_600_000)
                            hist_cache[key] = history_hourly(leg["venue"], raw)
                        except Exception as e:
                            log.info("history failed %s: %s", key, e)
                            hist_cache[key] = None
                hs_ = hist_cache.get((sg["venue"], sg["venue_symbol"]))
                hl_ = hist_cache.get((lg["venue"], lg["venue_symbol"])) if lg["kind"] == "perp" else None
                ev = evaluate_candidate(strat, lg, sg, cfg, hist_long=hl_, hist_short=hs_, now_ms=now_ms)
                ev["_legs"] = (lg, sg)
                evaluated.append(ev)
            evaluated.sort(key=lambda e: e["net_bps"], reverse=True)
            summary["eligible"] = sum(1 for e in evaluated if e["eligible"])
            entered = self._enter_positions(evaluated, cfg, ts, now_ms)
            summary["entered"] = entered
            self._store_opportunities(evaluated, ts)
            self._store_snapshots(snaps, ts)
            m, c = await self._mark_positions(client, snaps, cfg, now_ms)
            summary["mtm_rows"], summary["closed"] = m, c
            summary["top"] = [{k: e[k] for k in ("strategy", "symbol", "venue_long", "kind_long", "venue_short",
                                                 "kind_short", "net_bps", "carry_apr_pct_expected", "eligible")}
                              for e in evaluated[:10]]
        finally:
            summary["requests"] = client.requests
            await client.close()
        summary["finished_at_utc"] = utc_now_iso()
        self.last_scan = summary
        self.last_error = None
        self.scans += 1
        return summary

    def _store_opportunities(self, evaluated: list[dict], ts: str) -> None:
        rows = []
        for e in evaluated:
            d = {k: v for k, v in e.items() if k != "_legs"}
            rows.append({
                "ts": ts, "strategy": e["strategy"], "symbol": e["symbol"], "vl": e["venue_long"],
                "kl": e["kind_long"], "vs": e["venue_short"], "ks": e["kind_short"], "net": e["net_bps"],
                "gross": e["gross_bps"], "fees": e["fees_bps"], "slip": e["slippage_bps"], "basis": e["basis_bps"],
                "apr": e["carry_apr_pct_expected"], "flip": e["flip_rate_24h"], "liq": e["liq_distance_pct"],
                "elig": 1 if e["eligible"] else 0, "ent": 1 if e.get("_entered") else 0,
                "detail": json.dumps(d, default=str),
            })
        if rows:
            with self.engine.begin() as cx:
                cx.execute(text("""INSERT INTO funding_opportunity (ts_utc, strategy, symbol, venue_long, kind_long,
                    venue_short, kind_short, net_bps, gross_bps, fees_bps, slippage_bps, basis_bps, carry_apr_pct,
                    flip_rate_24h, liq_distance_pct, eligible, entered, detail_json)
                    VALUES (:ts, :strategy, :symbol, :vl, :kl, :vs, :ks, :net, :gross, :fees, :slip, :basis, :apr,
                    :flip, :liq, :elig, :ent, :detail)"""), rows)

    def _enter_positions(self, evaluated: list[dict], cfg: dict, ts: str, now_ms: float) -> int:
        n = 0
        with self.engine.begin() as cx:
            for e in evaluated:
                if not e["eligible"] or e["net_bps"] < cfg["entry_min_net_bps"]:
                    continue
                open_n = cx.execute(text("SELECT COUNT(*) FROM funding_position WHERE status='OPEN' AND strategy=:s"),
                                    {"s": e["strategy"]}).scalar_one()
                if open_n >= cfg["max_open_per_strategy"]:
                    continue
                dup = cx.execute(text("""SELECT COUNT(*) FROM funding_position WHERE status='OPEN' AND strategy=:s
                                         AND symbol=:sym AND venue_long=:vl AND venue_short=:vs"""),
                                 {"s": e["strategy"], "sym": e["symbol"], "vl": e["venue_long"],
                                  "vs": e["venue_short"]}).scalar_one()
                if dup:
                    continue
                lg, sg = e["_legs"]
                x = cfg["slippage_extra_bps"] / 1e4
                long_px = (lg.get("ask") or lg["mark"]) * (1 + x)
                short_px = (sg.get("bid") or sg["mark"]) * (1 - x)
                N = cfg["notional_usd"]
                fees = N * (_fee(cfg, lg["venue"], lg["kind"]) + _fee(cfg, sg["venue"], sg["kind"])) / 1e4
                detail = {k: v for k, v in e.items() if k != "_legs"}
                cx.execute(text("""INSERT INTO funding_position (opened_at_utc, strategy, symbol, venue_long, kind_long,
                    venue_symbol_long, venue_short, kind_short, venue_symbol_short, notional_usd, leverage,
                    entry_long_px, entry_short_px, entry_net_bps_expected, entry_detail_json, status, fees_usd,
                    last_funding_ms_long, last_funding_ms_short)
                    VALUES (:ts, :s, :sym, :vl, :kl, :vsl, :vs, :ks, :vss, :n, :lev, :lp, :sp, :net, :d, 'OPEN',
                    :fees, :now, :now)"""),
                           {"ts": ts, "s": e["strategy"], "sym": e["symbol"], "vl": lg["venue"], "kl": lg["kind"],
                            "vsl": lg.get("venue_symbol"), "vs": sg["venue"], "ks": sg["kind"],
                            "vss": sg.get("venue_symbol"), "n": N, "lev": cfg["leverage"], "lp": long_px,
                            "sp": short_px, "net": e["net_bps"], "d": json.dumps(detail, default=str),
                            "fees": fees, "now": now_ms})
                e["_entered"] = True
                n += 1
        return n

    async def _mark_positions(self, client: PublicClient, snaps: list[dict], cfg: dict,
                              now_ms: float) -> tuple[int, int]:
        idx = {(s["venue"], s["kind"], s["symbol"]): s for s in snaps if s["kind"] in ("perp", "spot")}
        for s in snaps:
            if s["kind"] == "spot" and s["venue"] == "hyperliquid":
                idx.setdefault(("hyperliquid", "spot_vs", s.get("venue_symbol")), s)
        with self.engine.begin() as cx:
            positions = [dict(r) for r in cx.execute(text("SELECT * FROM funding_position WHERE status='OPEN'")).mappings()]
        mtm_rows = closed = 0
        x = cfg["slippage_extra_bps"] / 1e4
        for p in positions:
            N = p["notional_usd"]
            new_funding = 0.0
            n_settle = 0
            last_long, last_short = p["last_funding_ms_long"], p["last_funding_ms_short"]
            detail: dict[str, Any] = {"settlements": []}
            for side, venue, kind, vsym, last in (("long", p["venue_long"], p["kind_long"], p["venue_symbol_long"], last_long),
                                                  ("short", p["venue_short"], p["kind_short"], p["venue_symbol_short"], last_short)):
                if kind != "perp":
                    continue
                try:
                    raw = await self.fetch_history(client, venue, vsym, (last or now_ms) + 1)
                    st = [(t, r) for t, r in settlements(venue, raw) if t > (last or 0) and t <= now_ms]
                except Exception as e:
                    detail[f"{side}_history_error"] = str(e)[:200]
                    st = []
                for t, r in st:
                    pay = (-r if side == "long" else r) * N  # positive funding: longs pay shorts
                    new_funding += pay
                    n_settle += 1
                    detail["settlements"].append({"leg": side, "venue": venue, "time": ms_to_iso(t), "rate": r,
                                                  "pnl_usd": pay})
                    if side == "long":
                        last_long = max(last_long or 0, t)
                    else:
                        last_short = max(last_short or 0, t)
            def leg_snap(venue, kind, sym, vsym):
                s = idx.get((venue, kind, p["symbol"]))
                if s is None and venue == "hyperliquid" and kind == "spot":
                    s = idx.get(("hyperliquid", "spot_vs", vsym))
                return s
            ls = leg_snap(p["venue_long"], p["kind_long"], p["symbol"], p["venue_symbol_long"])
            ss = leg_snap(p["venue_short"], p["kind_short"], p["symbol"], p["venue_symbol_short"])
            funding_total = (p["funding_pnl_usd"] or 0) + new_funding
            if ls is None or ss is None:
                with self.engine.begin() as cx:
                    cx.execute(text("""UPDATE funding_position SET funding_pnl_usd=:f, last_funding_ms_long=:ll,
                        last_funding_ms_short=:ls, stale_obs=stale_obs+1 WHERE id=:id"""),
                               {"f": funding_total, "ll": last_long, "ls": last_short, "id": p["id"]})
                continue
            exit_long = (ls.get("bid") or ls["mark"]) * (1 - x)
            exit_short = (ss.get("ask") or ss["mark"]) * (1 + x)
            basis_pnl = N * (exit_long / p["entry_long_px"] - 1) + N * (1 - exit_short / p["entry_short_px"])
            exit_fees = N * (_fee(cfg, p["venue_long"], p["kind_long"]) + _fee(cfg, p["venue_short"], p["kind_short"])) / 1e4
            total_if_closed = funding_total + basis_pnl - p["fees_usd"] - exit_fees
            # carry sign now
            f_s = ss.get("funding_rate_hourly") or 0.0
            f_l = (ls.get("funding_rate_hourly") or 0.0) if p["kind_long"] == "perp" else 0.0
            flip_obs = (p["flip_obs"] + 1) if (f_s - f_l) <= 0 else 0
            # liquidation guard on the perp legs (adverse move vs entry)
            liq = liq_distance_pct(p["leverage"], None, cfg["default_mmr"])
            adverse = []
            if p["kind_short"] == "perp":
                adverse.append((ss["mark"] / p["entry_short_px"] - 1) * 100)
            if p["kind_long"] == "perp":
                adverse.append((1 - ls["mark"] / p["entry_long_px"]) * 100)
            worst = max(adverse) if adverse else 0.0
            age_h = (now_ms - datetime.fromisoformat(p["opened_at_utc"]).timestamp() * 1000) / 3_600_000
            reason = None
            if worst >= cfg["liq_guard_fraction"] * liq:
                reason = f"LIQ_GUARD adverse {worst:.1f}% >= {cfg['liq_guard_fraction']:.0%} of {liq:.1f}% distance"
            elif total_if_closed <= -cfg["stop_loss_bps"] / 1e4 * N:
                reason = f"STOP_LOSS {total_if_closed / N * 1e4:.1f} bps"
            elif flip_obs >= cfg["exit_flip_obs"]:
                reason = f"FUNDING_FLIP carry <= 0 for {flip_obs} consecutive scans"
            elif age_h >= cfg["horizon_hours"]:
                reason = f"HORIZON {age_h:.1f}h >= {cfg['horizon_hours']}h"
            now_iso = ms_to_iso(now_ms)
            with self.engine.begin() as cx:
                if n_settle:
                    cx.execute(text("""INSERT INTO funding_mtm (position_id, ts_utc, settlements, funding_accrued_usd,
                        funding_pnl_usd, basis_pnl_usd, total_pnl_usd, detail_json)
                        VALUES (:pid, :ts, :n, :acc, :f, :b, :t, :d)"""),
                               {"pid": p["id"], "ts": now_iso, "n": n_settle, "acc": new_funding, "f": funding_total,
                                "b": basis_pnl, "t": total_if_closed, "d": json.dumps(detail, default=str)})
                    mtm_rows += 1
                if reason:
                    cx.execute(text("""UPDATE funding_position SET status='CLOSED', closed_at_utc=:ts, exit_reason=:r,
                        exit_long_px=:el, exit_short_px=:es, funding_pnl_usd=:f, basis_pnl_usd=:b,
                        fees_usd=fees_usd+:xf, pnl_usd=:pnl, pnl_bps=:bps, last_funding_ms_long=:ll,
                        last_funding_ms_short=:lsh, flip_obs=:fo, last_mtm_at_utc=:ts, stale_obs=0 WHERE id=:id"""),
                               {"ts": now_iso, "r": reason, "el": exit_long, "es": exit_short, "f": funding_total,
                                "b": basis_pnl, "xf": exit_fees, "pnl": total_if_closed,
                                "bps": total_if_closed / N * 1e4, "ll": last_long, "lsh": last_short, "fo": flip_obs,
                                "id": p["id"]})
                    closed += 1
                else:
                    cx.execute(text("""UPDATE funding_position SET funding_pnl_usd=:f, basis_pnl_usd=:b,
                        last_funding_ms_long=:ll, last_funding_ms_short=:lsh, flip_obs=:fo, last_mtm_at_utc=:ts,
                        stale_obs=0 WHERE id=:id"""),
                               {"f": funding_total, "b": basis_pnl, "ll": last_long, "lsh": last_short, "fo": flip_obs,
                                "ts": now_iso, "id": p["id"]})
        return mtm_rows, closed

    # -- read API ------------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        with self.engine.begin() as cx:
            pos = {f"{r['strategy']}:{r['status']}": int(r["n"]) for r in cx.execute(text(
                "SELECT strategy, status, COUNT(*) AS n FROM funding_position GROUP BY strategy, status")).mappings()}
            latest = {f"{r['venue']}:{r['kind']}": int(r["n"]) for r in cx.execute(text(
                "SELECT venue, kind, COUNT(*) AS n FROM funding_snapshot WHERE is_latest=1 GROUP BY venue, kind")).mappings()}
        cfg = config()
        return {
            "mode": "paper-only", "live_execution_available": False, "order_code": False,
            "enabled": self.enabled(), "running": bool(self._task and not self._task.done()),
            "idle_reasons": self.idle_reasons(), "venue_status": self.venue_status,
            "latest_snapshots": latest, "positions": pos, "config": cfg,
            "scans": self.scans, "last_scan": self.last_scan, "last_error": self.last_error,
        }

    def opportunities(self, limit: int = 50, strategy: Optional[str] = None,
                      eligible_only: bool = False) -> list[dict[str, Any]]:
        limit = min(max(int(limit), 1), 500)
        with self.engine.begin() as cx:
            ts = cx.execute(text("SELECT MAX(ts_utc) FROM funding_opportunity")).scalar()
            if not ts:
                return []
            q = "SELECT * FROM funding_opportunity WHERE ts_utc=:ts"
            p: dict[str, Any] = {"ts": ts, "limit": limit}
            if strategy:
                q += " AND strategy=:s"
                p["s"] = strategy.upper()
            if eligible_only:
                q += " AND eligible=1"
            q += " ORDER BY net_bps DESC LIMIT :limit"
            rows = cx.execute(text(q), p).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["detail"] = json.loads(d.pop("detail_json") or "{}")
            d["eligible"] = bool(d["eligible"])
            d["entered"] = bool(d["entered"])
            out.append(d)
        return out

    def positions(self, status: Optional[str] = None, limit: int = 200) -> list[dict[str, Any]]:
        limit = min(max(int(limit), 1), 1000)
        q = "SELECT * FROM funding_position"
        p: dict[str, Any] = {"limit": limit}
        if status:
            q += " WHERE status=:st"
            p["st"] = status.upper()
        q += " ORDER BY id DESC LIMIT :limit"
        with self.engine.begin() as cx:
            rows = cx.execute(text(q), p).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["entry_detail"] = json.loads(d.pop("entry_detail_json") or "{}")
            d["paper_only"] = True
            out.append(d)
        return out

    def scorecard(self) -> dict[str, Any]:
        with self.engine.begin() as cx:
            rows = cx.execute(text("""SELECT strategy, pnl_bps FROM funding_position
                                      WHERE status='CLOSED' AND pnl_bps IS NOT NULL ORDER BY id""")).mappings().all()
            open_n = cx.execute(text("SELECT COUNT(*) FROM funding_position WHERE status='OPEN'")).scalar_one()
        by: dict[str, list[float]] = {}
        for r in rows:
            by.setdefault(str(r["strategy"]), []).append(float(r["pnl_bps"]))
        return {
            "mode": "paper-only", "open_positions": int(open_n),
            "strategies": {k: scorecard_stats(v) for k, v in sorted(by.items())},
            "all": scorecard_stats([p for v in by.values() for p in v]),
            "notes": "closed paper positions only; pnl in bps of notional after modeled fees/slippage; "
                     f"profit factor capped at {PF_CAP:g} (profit_factor_capped flag); bootstrap: 2000 resamples, seed 7",
        }
