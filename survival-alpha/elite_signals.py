from __future__ import annotations

import asyncio
import base64
import json
import math
import struct
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Optional

import httpx


@dataclass
class MicrostructureSnapshot:
    tx_count: int = 0
    buy_count: int = 0
    sell_count: int = 0
    unique_buyers: int = 0
    unique_sellers: int = 0
    buy_sell_ratio: float = 0.0
    flow_imbalance: float = 0.0
    same_slot_buy_share: float = 0.0
    top_buyer_amount_share: float = 0.0
    total_fee_lamports: int = 0
    median_fee_lamports: float = 0.0
    mint_authority_enabled: Optional[bool] = None
    freeze_authority_enabled: Optional[bool] = None
    top10_account_concentration: Optional[float] = None
    sample_age_seconds: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StrategyVerdict:
    score: float
    decision: str
    reasons: list[str]
    components: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _keys_and_signers(tx: dict) -> tuple[list[str], set[str]]:
    message = ((tx.get("transaction") or {}).get("message") or {})
    raw = message.get("accountKeys") or message.get("staticAccountKeys") or []
    keys: list[str] = []
    signers: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            keys.append(item)
        elif isinstance(item, dict):
            pubkey = item.get("pubkey")
            if pubkey:
                keys.append(pubkey)
                if item.get("signer"):
                    signers.add(pubkey)
    loaded = ((tx.get("meta") or {}).get("loadedAddresses") or {})
    keys.extend(loaded.get("writable") or [])
    keys.extend(loaded.get("readonly") or [])
    # Raw/non-jsonParsed fall back to the first key as fee payer signer.
    if not signers and keys:
        signers.add(keys[0])
    return keys, signers


def _token_by_owner(tx: dict, side: str, mint: str) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    balances = ((tx.get("meta") or {}).get(side) or [])
    for b in balances:
        if b.get("mint") != mint:
            continue
        owner = b.get("owner")
        if not owner:
            continue
        amount = ((b.get("uiTokenAmount") or {}).get("amount") or "0")
        try:
            out[owner] += int(amount)
        except (TypeError, ValueError):
            continue
    return dict(out)


def _median(xs: list[int]) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    n = len(ys)
    if n % 2:
        return float(ys[n // 2])
    return (ys[n // 2 - 1] + ys[n // 2]) / 2.0


async def _rpc(http: httpx.AsyncClient, url: str, method: str, params: list[Any]) -> Any:
    r = await http.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
    )
    r.raise_for_status()
    body = r.json()
    if body.get("error"):
        raise RuntimeError(f"{method}: {body['error']}")
    return body.get("result")


def _decode_mint_authorities(account_result: Any) -> tuple[Optional[bool], Optional[bool]]:
    try:
        value = (account_result or {}).get("value") or {}
        data = value.get("data")
        if isinstance(data, list):
            raw = base64.b64decode(data[0])
        elif isinstance(data, str):
            raw = base64.b64decode(data)
        else:
            return None, None
        if len(raw) < 82:
            return None, None
        mint_opt = struct.unpack_from("<I", raw, 0)[0]
        freeze_opt = struct.unpack_from("<I", raw, 46)[0]
        return bool(mint_opt), bool(freeze_opt)
    except Exception:
        return None, None


def _largest_concentration(largest: Any, supply: Any) -> Optional[float]:
    try:
        total = int((((supply or {}).get("value") or {}).get("amount")) or 0)
        if total <= 0:
            return None
        values = (largest or {}).get("value") or []
        top = sum(int(v.get("amount") or 0) for v in values[:10])
        return top / total
    except Exception:
        return None


async def microstructure_snapshot(
    http: httpx.AsyncClient,
    helius_rpc_url: str,
    mint: str,
    lookback_seconds: int = 300,
    limit: int = 100,
) -> MicrostructureSnapshot:
    """
    Candidate-local snapshot from Helius. This intentionally uses only information
    observable at decision time. It is not a historical hindsight label.
    """
    now = int(time.time())
    gtfa_params = [
        mint,
        {
            "transactionDetails": "full",
            "sortOrder": "desc",
            "limit": min(max(limit, 10), 100),
            "filters": {
                "blockTime": {"gte": now - max(30, lookback_seconds)},
                "status": "succeeded",
            },
        },
    ]

    try:
        gtfa, mint_info, largest, supply = await asyncio.gather(
            _rpc(http, helius_rpc_url, "getTransactionsForAddress", gtfa_params),
            _rpc(http, helius_rpc_url, "getAccountInfo", [mint, {"encoding": "base64"}]),
            _rpc(http, helius_rpc_url, "getTokenLargestAccounts", [mint, {"commitment": "confirmed"}]),
            _rpc(http, helius_rpc_url, "getTokenSupply", [mint, {"commitment": "confirmed"}]),
        )
    except Exception as exc:
        return MicrostructureSnapshot(error=f"{type(exc).__name__}: {exc}")

    txs = (gtfa or {}).get("data") or []
    buy_wallets: set[str] = set()
    sell_wallets: set[str] = set()
    buy_slots: list[int] = []
    buy_amounts: dict[str, int] = defaultdict(int)
    fees: list[int] = []
    times: list[int] = []

    buy_count = 0
    sell_count = 0

    for tx in txs:
        if not isinstance(tx, dict):
            continue
        meta = tx.get("meta") or {}
        if meta.get("err") is not None:
            continue

        _, signers = _keys_and_signers(tx)
        pre = _token_by_owner(tx, "preTokenBalances", mint)
        post = _token_by_owner(tx, "postTokenBalances", mint)

        owner_deltas = {
            owner: post.get(owner, 0) - pre.get(owner, 0)
            for owner in set(pre) | set(post)
        }
        trader_deltas = {o: d for o, d in owner_deltas.items() if o in signers and d != 0}
        # Fallback: use non-zero owners if parsed signer flags were unavailable.
        if not trader_deltas:
            trader_deltas = {o: d for o, d in owner_deltas.items() if d != 0}

        positives = [(o, d) for o, d in trader_deltas.items() if d > 0]
        negatives = [(o, d) for o, d in trader_deltas.items() if d < 0]

        slot = int(tx.get("slot") or 0)
        if positives and not negatives:
            buy_count += 1
            buy_slots.append(slot)
            for owner, amount in positives:
                buy_wallets.add(owner)
                buy_amounts[owner] += amount
        elif negatives and not positives:
            sell_count += 1
            for owner, _ in negatives:
                sell_wallets.add(owner)

        fee = meta.get("fee")
        if fee is not None:
            try:
                fees.append(int(fee))
            except (TypeError, ValueError):
                pass
        bt = tx.get("blockTime")
        if bt:
            times.append(int(bt))

    total_directional = buy_count + sell_count
    buy_sell_ratio = buy_count / total_directional if total_directional else 0.0
    flow_imbalance = (
        (buy_count - sell_count) / total_directional if total_directional else 0.0
    )

    slot_counts = Counter(buy_slots)
    same_slot_share = (
        max(slot_counts.values()) / buy_count if buy_count and slot_counts else 0.0
    )

    total_bought = sum(buy_amounts.values())
    top_buyer_share = (
        max(buy_amounts.values()) / total_bought if total_bought and buy_amounts else 0.0
    )

    mint_auth, freeze_auth = _decode_mint_authorities(mint_info)
    concentration = _largest_concentration(largest, supply)
    sample_age = float(now - min(times)) if times else None

    return MicrostructureSnapshot(
        tx_count=len(txs),
        buy_count=buy_count,
        sell_count=sell_count,
        unique_buyers=len(buy_wallets),
        unique_sellers=len(sell_wallets),
        buy_sell_ratio=buy_sell_ratio,
        flow_imbalance=flow_imbalance,
        same_slot_buy_share=same_slot_share,
        top_buyer_amount_share=top_buyer_share,
        total_fee_lamports=sum(fees),
        median_fee_lamports=_median(fees),
        mint_authority_enabled=mint_auth,
        freeze_authority_enabled=freeze_auth,
        top10_account_concentration=concentration,
        sample_age_seconds=sample_age,
    )


def elite_verdict(
    *,
    micro: MicrostructureSnapshot,
    roundtrip_bps: float,
    drift_500_bps: float,
    organic_score: Optional[float],
    source_count: int,
    independent_wallet_count: int,
) -> StrategyVerdict:
    """
    Deterministic research score distilled from public trader heuristics and
    large-sample on-chain evidence. It is intentionally conservative and must
    be calibrated on forward outcomes before any live use.
    """
    reasons: list[str] = []

    # Hard risk vetoes.
    if micro.error:
        reasons.append("microstructure unavailable")
    if micro.mint_authority_enabled is True:
        reasons.append("mint authority enabled")
    if micro.freeze_authority_enabled is True:
        reasons.append("freeze authority enabled")
    if micro.buy_count >= 4 and micro.same_slot_buy_share >= 0.60:
        reasons.append("same-slot buy concentration")
    if micro.buy_count >= 4 and micro.top_buyer_amount_share >= 0.55:
        reasons.append("single-buyer concentration")
    if micro.tx_count >= 10 and micro.unique_buyers < 3:
        reasons.append("too few unique buyers")
    if roundtrip_bps <= -800:
        reasons.append("poor sellability")
    if drift_500_bps <= -500:
        reasons.append("adverse 500ms quote decay")

    # Component scores: 0-100 total.
    sellability = max(0.0, min(25.0, 25.0 * (1.0 + roundtrip_bps / 800.0)))
    latency = max(0.0, min(20.0, 20.0 * (1.0 + drift_500_bps / 500.0)))

    organic = 0.0
    if organic_score is not None:
        organic = max(0.0, min(20.0, (organic_score - 30.0) / 70.0 * 20.0))

    flow = 0.0
    if micro.buy_count + micro.sell_count:
        diversity = min(1.0, micro.unique_buyers / 8.0)
        # Prefer genuine buy pressure but not one-way/no-exit flow.
        balance = max(0.0, 1.0 - abs(micro.buy_sell_ratio - 0.68) / 0.68)
        flow = 20.0 * (0.60 * diversity + 0.40 * balance)

    confirmation = min(15.0, 5.0 * source_count + 3.0 * independent_wallet_count)

    components = {
        "sellability": round(sellability, 4),
        "latency": round(latency, 4),
        "organic": round(organic, 4),
        "flow": round(flow, 4),
        "independent_confirmation": round(confirmation, 4),
    }
    score = sum(components.values())

    # Low sample count is a reason to observe, not an automatic rug label.
    if micro.buy_count < 5 or micro.sell_count < 2:
        reasons.append("insufficient two-sided flow sample")

    hard_reject = any(
        r in reasons
        for r in {
            "mint authority enabled",
            "freeze authority enabled",
            "same-slot buy concentration",
            "single-buyer concentration",
            "too few unique buyers",
            "poor sellability",
            "adverse 500ms quote decay",
        }
    )

    if hard_reject:
        decision = "REJECT"
    elif score >= 65.0 and "insufficient two-sided flow sample" not in reasons:
        decision = "ACTIONABLE_PAPER"
    else:
        decision = "OBSERVE"

    return StrategyVerdict(
        score=round(score, 4),
        decision=decision,
        reasons=reasons or ["all current gates passed"],
        components=components,
    )
