from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import text

from channel_evaluator import evaluate_outcomes


@dataclass(frozen=True)
class AgentRole:
    name: str
    responsibility: str
    hot_path: bool
    can_authorize_live_trade: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


TEAM: tuple[AgentRole, ...] = (
    AgentRole("TELEGRAM_SCOUT", "Ingest configured Telegram calls and extract valid Solana mints.", True),
    AgentRole("WALLET_SCOUT", "Watch selected wallet buys through Helius transactionSubscribe.", True),
    AgentRole("PUMP_SCOUT", "Discover creations/migrations from PumpPortal.", True),
    AgentRole("ORGANIC_SCOUT", "Discover rising organic Solana activity from Jupiter.", False),
    AgentRole("NARRATIVE_SCOUT", "Bring slower X/Reddit narrative context from Work/social adapters.", False),
    AgentRole("MICROSTRUCTURE_AGENT", "Measure early two-sided flow, concentration, authorities and fee intensity.", True),
    AgentRole("EXECUTION_QUALITY_AGENT", "Measure buy, sell-back, 500ms decay and market phase.", True),
    AgentRole("RISK_GOVERNOR", "Hard-veto authority, concentration, sellability and latency failures.", True),
    AgentRole("STRATEGY_TOURNAMENT", "Run independent strategy hypotheses on the same candidate.", True),
    AgentRole("PAPER_EXECUTOR", "Create and mark forward paper positions only.", True),
    AgentRole("COUNTERFACTUAL_AGENT", "Mark rejected and accepted candidates at identical horizons.", False),
    AgentRole("CHANNEL_FORENSICS", "Score each Telegram source using only prior forward outcomes.", False),
    AgentRole("META_ALLOCATOR", "Promote/collect/rework channels and strategies from evidence.", False),
    AgentRole("PORTFOLIO_MANAGER", "Allocate only promoted strategy/source combinations into the simulated fund book.", False),
    AgentRole("FIRM_RISK", "Veto portfolio allocations on loss, exposure, duplication and concentration limits.", True),
    AgentRole("MARKOUT_AGENT", "Measure every candidate at multiple fixed horizons for horizon-specific edge.", False),
    AgentRole("WORK_SUPERVISOR", "Research narratives, inspect failures, propose code/config changes.", False),
)


class AgentTeam:
    def __init__(self, engine):
        self.engine = engine

    def manifest(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in TEAM]

    def channel_scorecards(
        self,
        *,
        min_samples: int = 20,
        min_profit_factor: float = 1.30,
    ) -> dict[str, Any]:
        """
        Telegram channel quality is measured from executable forward outcomes only.
        First-call de-duplication happens before candidates enter the book.
        """
        with self.engine.begin() as cx:
            rows = cx.execute(text("""
                SELECT source_detail, outcome_5m_bps
                FROM realtime_candidate
                WHERE source='telegram'
                  AND outcome_5m_bps IS NOT NULL
                  AND source_detail IS NOT NULL
            """)).mappings().all()

        grouped: dict[str, list[float]] = {}
        for row in rows:
            channel = str(row["source_detail"])
            grouped.setdefault(channel, []).append(float(row["outcome_5m_bps"]))

        return {
            channel: evaluate_outcomes(
                outcomes,
                min_samples=min_samples,
                min_profit_factor=min_profit_factor,
            ).to_dict()
            for channel, outcomes in sorted(grouped.items())
        }

    def strategy_scorecards(
        self,
        *,
        min_samples: int = 20,
        min_profit_factor: float = 1.30,
    ) -> dict[str, Any]:
        with self.engine.begin() as cx:
            rows = cx.execute(text("""
                SELECT strategy_votes_json, outcome_5m_bps
                FROM realtime_candidate
                WHERE outcome_5m_bps IS NOT NULL
                  AND strategy_votes_json IS NOT NULL
            """)).mappings().all()

        passed: dict[str, list[float]] = {}
        failed: dict[str, list[float]] = {}
        for row in rows:
            try:
                votes = json.loads(row["strategy_votes_json"] or "[]")
            except Exception:
                continue
            outcome = float(row["outcome_5m_bps"])
            for vote in votes:
                name = str(vote.get("name") or "UNKNOWN")
                target = passed if bool(vote.get("passed")) else failed
                target.setdefault(name, []).append(outcome)

        names = sorted(set(passed) | set(failed))
        out: dict[str, Any] = {}
        for name in names:
            p = evaluate_outcomes(
                passed.get(name, []),
                min_samples=min_samples,
                min_profit_factor=min_profit_factor,
            ).to_dict()
            f = evaluate_outcomes(
                failed.get(name, []),
                min_samples=min_samples,
                min_profit_factor=min_profit_factor,
                require_positive_ci=False,
            ).to_dict()
            edge = None
            if p.get("mean_bps") is not None and f.get("mean_bps") is not None:
                edge = p["mean_bps"] - f["mean_bps"]
            out[name] = {
                "passed": p,
                "failed": f,
                "pass_minus_fail_mean_bps": edge,
            }
        return out

    def horizon_scorecards(
        self,
        *,
        min_samples: int = 20,
        min_profit_factor: float = 1.30,
    ) -> dict[str, Any]:
        """
        Evaluate accepted vs rejected and strategy pass/fail at each fixed markout
        horizon. This tells the desk whether an information edge is fast-decaying
        or survives long enough to be executable.
        """
        with self.engine.begin() as cx:
            rows = cx.execute(text("""
                SELECT m.horizon_seconds, m.pnl_bps,
                       c.decision, c.strategy_votes_json
                FROM candidate_markout m
                JOIN realtime_candidate c ON c.id=m.candidate_id
            """)).mappings().all()

        by_horizon: dict[int, dict[str, Any]] = {}
        for row in rows:
            h = int(row["horizon_seconds"])
            rec = by_horizon.setdefault(
                h,
                {"accepted": [], "rejected": [], "strategy_pass": {}, "strategy_fail": {}},
            )
            outcome = float(row["pnl_bps"])
            if str(row["decision"]) == "ACTIONABLE_PAPER":
                rec["accepted"].append(outcome)
            elif str(row["decision"]) == "REJECT":
                rec["rejected"].append(outcome)

            try:
                votes = json.loads(row["strategy_votes_json"] or "[]")
            except Exception:
                votes = []
            for vote in votes:
                name = str(vote.get("name") or "UNKNOWN")
                target = rec["strategy_pass"] if bool(vote.get("passed")) else rec["strategy_fail"]
                target.setdefault(name, []).append(outcome)

        out: dict[str, Any] = {}
        for horizon, rec in sorted(by_horizon.items()):
            accepted = evaluate_outcomes(
                rec["accepted"],
                min_samples=min_samples,
                min_profit_factor=min_profit_factor,
            ).to_dict()
            rejected = evaluate_outcomes(
                rec["rejected"],
                min_samples=min_samples,
                min_profit_factor=min_profit_factor,
                require_positive_ci=False,
            ).to_dict()
            strategy_cards = {}
            names = sorted(set(rec["strategy_pass"]) | set(rec["strategy_fail"]))
            for name in names:
                p = evaluate_outcomes(
                    rec["strategy_pass"].get(name, []),
                    min_samples=min_samples,
                    min_profit_factor=min_profit_factor,
                ).to_dict()
                f = evaluate_outcomes(
                    rec["strategy_fail"].get(name, []),
                    min_samples=min_samples,
                    min_profit_factor=min_profit_factor,
                    require_positive_ci=False,
                ).to_dict()
                strategy_cards[name] = {"passed": p, "failed": f}

            out[str(horizon)] = {
                "accepted": accepted,
                "rejected": rejected,
                "strategies": strategy_cards,
            }
        return out


    def diagnostics(self) -> dict[str, Any]:
        with self.engine.begin() as cx:
            decisions = cx.execute(text("""
                SELECT decision, COUNT(*) AS n
                FROM realtime_candidate
                GROUP BY decision
            """)).mappings().all()
            sources = cx.execute(text("""
                SELECT source, COUNT(*) AS n
                FROM realtime_candidate
                GROUP BY source
            """)).mappings().all()
            errors = cx.execute(text("""
                SELECT source, reason, COUNT(*) AS n
                FROM realtime_candidate
                WHERE decision='ERROR'
                GROUP BY source, reason
                ORDER BY n DESC
                LIMIT 20
            """)).mappings().all()

        return {
            "decisions": {str(r["decision"]): int(r["n"]) for r in decisions},
            "sources": {str(r["source"]): int(r["n"]) for r in sources},
            "top_errors": [dict(r) for r in errors],
        }
