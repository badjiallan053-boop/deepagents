from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reasons: list[str]
    open_positions: int
    gross_open_lamports: int
    daily_realized_pnl_lamports: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FirmRiskGovernor:
    """
    Portfolio-level veto layer for the simulated fund book.

    It never creates a trade. It can only say no.

    The research tape remains unconstrained so rejected/accepted signals stay
    measurable. These limits apply only to the portfolio book that simulates
    how a real firm would allocate validated strategies.
    """

    def __init__(self, engine):
        self.engine = engine
        self.nav_lamports = int(os.getenv("FIRM_PAPER_NAV_LAMPORTS", "400000000") or 400_000_000)
        self.max_open_positions = int(os.getenv("FIRM_MAX_OPEN_POSITIONS", "5") or 5)
        self.max_gross_exposure_bps = int(os.getenv("FIRM_MAX_GROSS_EXPOSURE_BPS", "5000") or 5000)
        self.max_single_position_bps = int(os.getenv("FIRM_MAX_SINGLE_POSITION_BPS", "1000") or 1000)
        self.max_source_exposure_bps = int(os.getenv("FIRM_MAX_SOURCE_EXPOSURE_BPS", "2500") or 2500)
        self.daily_loss_limit_bps = int(os.getenv("FIRM_DAILY_LOSS_LIMIT_BPS", "500") or 500)

    @staticmethod
    def _today_utc() -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def snapshot(self) -> dict[str, int]:
        with self.engine.begin() as cx:
            open_rows = cx.execute(text("""
                SELECT allocated_lamports, source
                FROM firm_portfolio_position
                WHERE status='OPEN'
            """)).mappings().all()
            daily = cx.execute(text("""
                SELECT COALESCE(SUM(realized_pnl_lamports), 0)
                FROM firm_portfolio_position
                WHERE status='CLOSED'
                  AND substr(closed_at_utc, 1, 10)=:day
            """), {"day": self._today_utc()}).scalar_one()

        return {
            "open_positions": len(open_rows),
            "gross_open_lamports": sum(int(r["allocated_lamports"]) for r in open_rows),
            "daily_realized_pnl_lamports": int(daily or 0),
        }

    def check(
        self,
        *,
        mint: str,
        source: str,
        requested_lamports: int,
    ) -> RiskDecision:
        snap = self.snapshot()
        reasons: list[str] = []

        if requested_lamports <= 0:
            reasons.append("non-positive allocation")

        max_single = self.nav_lamports * self.max_single_position_bps // 10_000
        if requested_lamports > max_single:
            reasons.append("single-position risk cap")

        max_gross = self.nav_lamports * self.max_gross_exposure_bps // 10_000
        if snap["gross_open_lamports"] + requested_lamports > max_gross:
            reasons.append("gross exposure cap")

        if snap["open_positions"] >= self.max_open_positions:
            reasons.append("max open positions")

        daily_floor = -(self.nav_lamports * self.daily_loss_limit_bps // 10_000)
        if snap["daily_realized_pnl_lamports"] <= daily_floor:
            reasons.append("daily loss kill switch")

        with self.engine.begin() as cx:
            same_mint = int(cx.execute(text("""
                SELECT COUNT(*) FROM firm_portfolio_position
                WHERE status='OPEN' AND mint=:mint
            """), {"mint": mint}).scalar_one())
            source_open = int(cx.execute(text("""
                SELECT COALESCE(SUM(allocated_lamports), 0)
                FROM firm_portfolio_position
                WHERE status='OPEN' AND source=:source
            """), {"source": source}).scalar_one() or 0)

        if same_mint:
            reasons.append("duplicate mint exposure")

        source_cap = self.nav_lamports * self.max_source_exposure_bps // 10_000
        if source_open + requested_lamports > source_cap:
            reasons.append("source concentration cap")

        return RiskDecision(
            allowed=not reasons,
            reasons=reasons,
            open_positions=snap["open_positions"],
            gross_open_lamports=snap["gross_open_lamports"],
            daily_realized_pnl_lamports=snap["daily_realized_pnl_lamports"],
        )
