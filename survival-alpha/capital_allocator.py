from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Optional

from sqlalchemy import text

from channel_evaluator import evaluate_outcomes


@dataclass(frozen=True)
class AllocationDecision:
    eligible: bool
    requested_lamports: int
    promoted_strategies: list[str]
    channel_status: Optional[str]
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FirmCapitalAllocator:
    """
    Evidence-gated allocator for the simulated fund book.

    The research book measures everything at a fixed notional. This allocator is
    a *second* book: it only allocates to signals backed by strategies/sources
    that have earned promotion from prior forward outcomes.
    """

    def __init__(self, engine):
        self.engine = engine
        self.nav_lamports = int(os.getenv("FIRM_PAPER_NAV_LAMPORTS", "400000000") or 400_000_000)
        self.base_risk_bps = int(os.getenv("FIRM_BASE_POSITION_BPS", "250") or 250)
        self.max_position_bps = int(os.getenv("FIRM_MAX_SINGLE_POSITION_BPS", "1000") or 1000)
        self.min_samples = int(os.getenv("FIRM_MIN_PROMOTION_SAMPLES", "30") or 30)
        self.min_profit_factor = float(os.getenv("FIRM_MIN_PROFIT_FACTOR", "1.30") or 1.30)

    def _strategy_cards(self) -> dict[str, dict[str, Any]]:
        with self.engine.begin() as cx:
            rows = cx.execute(text("""
                SELECT strategy_votes_json, outcome_5m_bps
                FROM realtime_candidate
                WHERE outcome_5m_bps IS NOT NULL
                  AND strategy_votes_json IS NOT NULL
            """)).mappings().all()

        passed: dict[str, list[float]] = {}
        for row in rows:
            try:
                votes = json.loads(row["strategy_votes_json"] or "[]")
            except Exception:
                continue
            outcome = float(row["outcome_5m_bps"])
            for vote in votes:
                if not bool(vote.get("passed")):
                    continue
                name = str(vote.get("name") or "")
                if name:
                    passed.setdefault(name, []).append(outcome)

        return {
            name: evaluate_outcomes(
                vals,
                min_samples=self.min_samples,
                min_profit_factor=self.min_profit_factor,
            ).to_dict()
            for name, vals in passed.items()
        }

    def _telegram_channel_card(self, channel: str) -> Optional[dict[str, Any]]:
        if not channel:
            return None
        with self.engine.begin() as cx:
            vals = cx.execute(text("""
                SELECT outcome_5m_bps
                FROM realtime_candidate
                WHERE source='telegram'
                  AND source_detail=:channel
                  AND outcome_5m_bps IS NOT NULL
                ORDER BY id
            """), {"channel": channel}).scalars().all()
        return evaluate_outcomes(
            vals,
            min_samples=self.min_samples,
            min_profit_factor=self.min_profit_factor,
        ).to_dict()

    def decide(
        self,
        *,
        source: str,
        source_detail: str,
        strategy_votes: list[dict[str, Any]],
    ) -> AllocationDecision:
        cards = self._strategy_cards()
        passing_now = {
            str(v.get("name"))
            for v in strategy_votes
            if bool(v.get("passed")) and v.get("name")
        }
        promoted = sorted(
            name for name in passing_now
            if cards.get(name, {}).get("status") == "PROMOTE"
        )

        reasons: list[str] = []
        channel_status = None
        if source == "telegram":
            card = self._telegram_channel_card(source_detail)
            channel_status = (card or {}).get("status")
            if channel_status != "PROMOTE":
                reasons.append("telegram channel has not earned promotion")

        if not promoted:
            reasons.append("no currently-passing strategy has earned promotion")

        if reasons:
            return AllocationDecision(
                eligible=False,
                requested_lamports=0,
                promoted_strategies=promoted,
                channel_status=channel_status,
                reasons=reasons,
            )

        # Start small. Independent promoted confirmations can increase the paper
        # allocation, but no model can exceed the explicit portfolio cap.
        multiplier = min(3.0, 1.0 + 0.5 * max(0, len(promoted) - 1))
        requested_bps = min(
            self.max_position_bps,
            int(round(self.base_risk_bps * multiplier)),
        )
        requested = self.nav_lamports * requested_bps // 10_000

        return AllocationDecision(
            eligible=True,
            requested_lamports=max(1, requested),
            promoted_strategies=promoted,
            channel_status=channel_status,
            reasons=[
                f"{len(promoted)} promoted strategy confirmations",
                f"allocation={requested_bps}bps of simulated NAV",
            ],
        )
