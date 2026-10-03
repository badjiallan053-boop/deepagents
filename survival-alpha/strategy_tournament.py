from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from elite_signals import MicrostructureSnapshot


@dataclass
class StrategyVote:
    name: str
    passed: bool
    score: float
    reason: str

    def to_dict(self):
        return asdict(self)


def evaluate_tournament(
    *,
    source: str,
    micro: MicrostructureSnapshot,
    roundtrip_bps: float,
    drift_500_bps: float,
    organic_score: Optional[float],
    source_count: int,
    independent_wallet_count: int,
) -> list[StrategyVote]:
    """
    Four deliberately different hypotheses. They are evaluated independently,
    forward, on the same candidates. No strategy is allowed to learn from its
    own future outcome.
    """
    votes: list[StrategyVote] = []

    authorities_safe = (
        micro.mint_authority_enabled is not True
        and micro.freeze_authority_enabled is not True
    )
    bundle_safe = (
        micro.same_slot_buy_share < 0.60
        and micro.top_buyer_amount_share < 0.55
    )
    executable = roundtrip_bps > -800 and drift_500_bps > -500
    flow_sample = micro.buy_count >= 5 and micro.sell_count >= 2
    balanced_pressure = 0.55 <= micro.buy_sell_ratio <= 0.88
    diverse = micro.unique_buyers >= 4

    # 1) Reverse-engineered "human trencher" style:
    # organic-looking 1-second flow, authorities off, both-sided market.
    s = 0.0
    s += 25 if authorities_safe else 0
    s += 20 if bundle_safe else 0
    s += 20 if flow_sample else 0
    s += 15 if diverse else 0
    s += 10 if balanced_pressure else 0
    s += 10 if executable else 0
    passed = all([authorities_safe, bundle_safe, flow_sample, diverse, executable])
    votes.append(StrategyVote(
        "TRENCHER_ORGANIC",
        passed,
        s,
        "authority + bundle + two-sided-flow + buyer-diversity + executable-price",
    ))

    # 2) Less-obvious-wallet consensus rather than copying a famous wallet.
    s = 0.0
    s += min(40.0, independent_wallet_count * 20.0)
    s += min(20.0, source_count * 7.0)
    s += 20 if executable else 0
    s += 10 if bundle_safe else 0
    s += 10 if diverse else 0
    passed = independent_wallet_count >= 2 and executable and bundle_safe
    votes.append(StrategyVote(
        "INDEPENDENT_WALLET_CONSENSUS",
        passed,
        s,
        "requires >=2 independent watched wallets plus executable quote",
    ))

    # 3) Post-migration survivor. Intentionally avoids creation-slot sniper race.
    score_org = max(0.0, min(30.0, ((organic_score or 0) - 30.0) / 70.0 * 30.0))
    s = score_org
    s += 25 if source == "pumpportal" else 0
    s += 20 if executable else 0
    s += 15 if diverse else 0
    s += 10 if balanced_pressure else 0
    passed = (
        source == "pumpportal"
        and (organic_score or 0) >= 45
        and executable
        and diverse
    )
    votes.append(StrategyVote(
        "POST_MIGRATION_SURVIVOR",
        passed,
        s,
        "migration + organic activity + buyer diversity + sellability",
    ))

    # 4) Organic/narrative acceleration. Uses Jupiter's wallet classification
    # as a proxy for real participation; social/narrative data can later add
    # a second independent source, but cannot pass this alone without execution.
    s = max(0.0, min(50.0, ((organic_score or 0) - 30.0) / 70.0 * 50.0))
    s += 20 if source_count >= 2 else 0
    s += 15 if executable else 0
    s += 15 if bundle_safe else 0
    passed = (
        (organic_score or 0) >= 60
        and source_count >= 2
        and executable
        and bundle_safe
    )
    votes.append(StrategyVote(
        "ORGANIC_MIND_SHARE",
        passed,
        s,
        "high organic score confirmed by another independent source",
    ))

    return votes
