from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text

from grok_team import GrokTeam


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


STAGES = [
    "DESK_REVIEW",
    "DATA_AUDIT",
    "QUANT_RD",
    "EXECUTION_TEST",
    "RED_TEAM",
    "RISK",
    "PORTFOLIO",
    "IC",
    "SHADOW_READY",
]

STAGE_ROLE = {
    "DATA_AUDIT": "DATA_PROVENANCE",
    "QUANT_RD": "QUANT_RD",
    "EXECUTION_TEST": "EXECUTION_ROUTER",
    "RED_TEAM": "RED_TEAM",
    "RISK": "RISK_OFFICER",
    "PORTFOLIO": "PORTFOLIO_CONSTRUCTION",
    "IC": "INVESTMENT_COMMITTEE",
}

DESK_ROLE = {
    "GLOBAL_MACRO": "GLOBAL_MACRO",
    "EQUITY_EVENT": "EQUITY_EVENT",
    "OPTIONS_VOL": "OPTIONS_VOL",
    "STAT_ARB": "STAT_ARB",
    "CRYPTO_RELATIVE_VALUE": "CRYPTO_RELATIVE_VALUE",
    "SOLANA_ONCHAIN": "WALLET_INTELLIGENCE",
    "SPECIAL_SITUATIONS": "SPECIAL_SITUATIONS",
    "INDEX_AUCTION": "INDEX_AUCTION",
    "EARNINGS_INTELLIGENCE": "EARNINGS_INTELLIGENCE",
    "YOUTUBE_ATTENTION": "YOUTUBE_ATTENTION",
    "BORROW_INTELLIGENCE": "BORROW_INTELLIGENCE",
    "TREASURY_FINANCING": "TREASURY_FINANCING",
    "CROSS_VENUE_ARBITRAGE": "CROSS_VENUE_ARBITRAGE",
    "MARKET_MAKING": "MARKET_MAKING_RESEARCH",
    "NEWS_EVENT": "NEWS_EVENT",
    "ALT_DATA": "ALT_DATA",
}


def ensure_profit_tables(engine) -> None:
    sqlite = str(engine.url).startswith("sqlite")
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if sqlite else "BIGSERIAL PRIMARY KEY"
    with engine.begin() as cx:
        cx.execute(text(f"""
        CREATE TABLE IF NOT EXISTS profit_hypothesis (
            id {pk},
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            title TEXT NOT NULL,
            desk TEXT NOT NULL,
            asset_class TEXT NOT NULL,
            instruments_json TEXT NOT NULL,
            mechanism TEXT NOT NULL,
            horizon TEXT NOT NULL,
            source_refs_json TEXT NOT NULL,
            falsification_test TEXT NOT NULL,
            data_needed TEXT,
            execution_constraints TEXT,
            correlation_cluster TEXT,
            expected_edge_bps DOUBLE PRECISION,
            expected_cost_bps DOUBLE PRECISION,
            capacity_usd DOUBLE PRECISION,
            confidence DOUBLE PRECISION,
            current_stage TEXT NOT NULL,
            status TEXT NOT NULL,
            owner_role TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            notes TEXT
        )
        """))
        cx.execute(text(f"""
        CREATE TABLE IF NOT EXISTS profit_gate_review (
            id {pk},
            hypothesis_id BIGINT NOT NULL,
            created_at_utc TEXT NOT NULL,
            stage TEXT NOT NULL,
            role TEXT NOT NULL,
            verdict TEXT NOT NULL,
            grok_run_id BIGINT,
            response_text TEXT,
            cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0
        )
        """))


@dataclass(frozen=True)
class HypothesisInput:
    title: str
    desk: str
    asset_class: str
    instruments: list[str]
    mechanism: str
    horizon: str
    source_refs: list[str]
    falsification_test: str
    data_needed: str = ""
    execution_constraints: str = ""
    correlation_cluster: str = ""
    expected_edge_bps: Optional[float] = None
    expected_cost_bps: Optional[float] = None
    capacity_usd: Optional[float] = None
    confidence: Optional[float] = None
    notes: str = ""


class ProfitTeam:
    """
    Profit-first research operating system.

    Objective:
      maximize long-run executable net P&L after costs, financing, slippage,
      infrastructure spend and tail losses, subject to hard risk/survival gates.

    Grok can research and recommend. It cannot promote a hypothesis directly
    into live capital; the pipeline ends at SHADOW_READY.
    """

    def __init__(self, engine, grok: GrokTeam):
        self.engine = engine
        self.grok = grok
        ensure_profit_tables(engine)

    def manifest(self) -> dict[str, Any]:
        return {
            "objective": (
                "maximize long-run executable net P&L after all costs subject "
                "to firm survival and independent risk veto"
            ),
            "stages": STAGES,
            "desk_roles": DESK_ROLE,
            "stage_roles": STAGE_ROLE,
            "terminal_states": ["SHADOW_READY", "KILLED", "REWORK", "COLLECT"],
            "live_trade_authority": False,
            "promotion_to_live_capital": False,
        }

    def create(self, h: HypothesisInput) -> int:
        desk = h.desk.strip().upper()
        if desk not in DESK_ROLE:
            raise ValueError(f"Unknown desk: {desk}. Choose one of {sorted(DESK_ROLE)}")
        if not h.instruments:
            raise ValueError("At least one instrument is required")
        now = utc_now()
        row = {
            "created": now,
            "updated": now,
            "title": h.title.strip(),
            "desk": desk,
            "asset_class": h.asset_class.strip().upper(),
            "instruments_json": json.dumps(h.instruments, separators=(",", ":")),
            "mechanism": h.mechanism.strip(),
            "horizon": h.horizon.strip(),
            "source_refs_json": json.dumps(h.source_refs, separators=(",", ":")),
            "falsification_test": h.falsification_test.strip(),
            "data_needed": h.data_needed.strip(),
            "execution_constraints": h.execution_constraints.strip(),
            "correlation_cluster": h.correlation_cluster.strip(),
            "expected_edge_bps": h.expected_edge_bps,
            "expected_cost_bps": h.expected_cost_bps,
            "capacity_usd": h.capacity_usd,
            "confidence": h.confidence,
            "owner_role": DESK_ROLE[desk],
            "notes": h.notes.strip(),
        }
        with self.engine.begin() as cx:
            r = cx.execute(text("""
                INSERT INTO profit_hypothesis (
                    created_at_utc, updated_at_utc, title, desk, asset_class,
                    instruments_json, mechanism, horizon, source_refs_json,
                    falsification_test, data_needed, execution_constraints,
                    correlation_cluster, expected_edge_bps, expected_cost_bps,
                    capacity_usd, confidence, current_stage, status, owner_role,
                    version, notes
                ) VALUES (
                    :created, :updated, :title, :desk, :asset_class,
                    :instruments_json, :mechanism, :horizon, :source_refs_json,
                    :falsification_test, :data_needed, :execution_constraints,
                    :correlation_cluster, :expected_edge_bps, :expected_cost_bps,
                    :capacity_usd, :confidence, 'DESK_REVIEW', 'ACTIVE', :owner_role,
                    1, :notes
                )
            """), row)
            hid = getattr(r, "lastrowid", None)
            if not hid:
                hid = cx.execute(text(
                    "SELECT id FROM profit_hypothesis ORDER BY id DESC LIMIT 1"
                )).scalar_one()
        return int(hid)

    def get(self, hypothesis_id: int) -> Optional[dict[str, Any]]:
        with self.engine.begin() as cx:
            row = cx.execute(text("""
                SELECT * FROM profit_hypothesis WHERE id=:id
            """), {"id": int(hypothesis_id)}).mappings().first()
        return dict(row) if row else None

    def list(self, limit: int = 200, status: Optional[str] = None) -> list[dict[str, Any]]:
        limit = min(max(int(limit), 1), 2000)
        q = "SELECT * FROM profit_hypothesis"
        params: dict[str, Any] = {"limit": limit}
        if status:
            q += " WHERE status=:status"
            params["status"] = status
        q += " ORDER BY id DESC LIMIT :limit"
        with self.engine.begin() as cx:
            rows = cx.execute(text(q), params).mappings().all()
        return [dict(r) for r in rows]

    def reviews(self, hypothesis_id: int) -> list[dict[str, Any]]:
        with self.engine.begin() as cx:
            rows = cx.execute(text("""
                SELECT * FROM profit_gate_review
                WHERE hypothesis_id=:id ORDER BY id
            """), {"id": int(hypothesis_id)}).mappings().all()
        return [dict(r) for r in rows]

    @staticmethod
    def _parse_verdict(text_value: str) -> str:
        m = re.search(
            r"(?:GATE_VERDICT|VERDICT)\s*[:=\-]\s*(PASS|REWORK|KILL|COLLECT)",
            text_value or "",
            flags=re.I,
        )
        return m.group(1).upper() if m else "COLLECT"

    @staticmethod
    def _next_stage(stage: str) -> str:
        idx = STAGES.index(stage)
        return STAGES[min(idx + 1, len(STAGES) - 1)]

    def _role_for(self, h: dict[str, Any]) -> str:
        stage = str(h["current_stage"])
        if stage == "DESK_REVIEW":
            return DESK_ROLE[str(h["desk"])]
        return STAGE_ROLE.get(stage, "CIO")

    def _gate_objective(self, h: dict[str, Any], stage: str) -> str:
        packet = {
            "id": h["id"],
            "title": h["title"],
            "desk": h["desk"],
            "asset_class": h["asset_class"],
            "instruments": json.loads(h["instruments_json"] or "[]"),
            "mechanism": h["mechanism"],
            "horizon": h["horizon"],
            "source_refs": json.loads(h["source_refs_json"] or "[]"),
            "falsification_test": h["falsification_test"],
            "data_needed": h["data_needed"],
            "execution_constraints": h["execution_constraints"],
            "correlation_cluster": h["correlation_cluster"],
            "expected_edge_bps": h["expected_edge_bps"],
            "expected_cost_bps": h["expected_cost_bps"],
            "capacity_usd": h["capacity_usd"],
            "confidence": h["confidence"],
            "version": h["version"],
            "notes": h["notes"],
        }
        stage_mandates = {
            "DESK_REVIEW": "Is the economic mechanism coherent, differentiated, and worth testing?",
            "DATA_AUDIT": "Are sources point-in-time, reproducible, legally usable, correctly timestamped, and free of leakage?",
            "QUANT_RD": "Design or critique the minimum reproducible experiment, baseline, walk-forward test, ablations and promotion thresholds.",
            "EXECUTION_TEST": "Can the apparent edge survive spreads, fees, impact, borrow/funding, latency, fill probability, settlement and capacity?",
            "RED_TEAM": "Try to falsify the edge. Search aggressively for hidden common causes, p-hacking, outliers, impossible fills and regime luck.",
            "RISK": "Would this hypothesis create unacceptable tail, liquidity, concentration, gap, leverage, counterparty or operational risk?",
            "PORTFOLIO": "Does this add independent expected net value after correlation and capacity, or merely duplicate existing exposures?",
            "IC": "Synthesize the prior gate logic and decide whether this deserves SHADOW capital only. No live-capital authorization.",
        }
        return (
            f"PROFIT GATE: {stage}\n"
            f"{stage_mandates.get(stage, '')}\n\n"
            "HYPOTHESIS PACKET:\n"
            + json.dumps(packet, indent=2, default=str)
            + "\n\nREQUIRED: evaluate the economic mechanism, evidence quality, expected net value, capacity, robustness and cheapest falsification test. "
              "End with exactly one line: GATE_VERDICT: PASS, REWORK, KILL, or COLLECT."
        )

    async def review_next(self, hypothesis_id: int) -> dict[str, Any]:
        h = self.get(hypothesis_id)
        if not h:
            raise ValueError("Hypothesis not found")
        if h["status"] != "ACTIVE":
            raise RuntimeError(f"Hypothesis is not active: {h['status']}")
        stage = str(h["current_stage"])
        if stage == "SHADOW_READY":
            raise RuntimeError("Hypothesis already reached SHADOW_READY")
        role = self._role_for(h)
        use_web = stage in {"DESK_REVIEW", "DATA_AUDIT"}
        use_x = role in {"X_NARRATIVE_SCOUT", "YOUTUBE_ATTENTION", "OPPORTUNITY_SCOUT"}
        result = await self.grok.run(
            role_name=role,
            objective=self._gate_objective(h, stage),
            deep=(stage == "IC"),
            use_web=use_web,
            use_x=use_x,
        )
        verdict = self._parse_verdict(result.get("response") or "")
        new_stage = stage
        new_status = "ACTIVE"
        if verdict == "PASS":
            new_stage = self._next_stage(stage)
            if new_stage == "SHADOW_READY":
                new_status = "SHADOW_READY"
        elif verdict == "KILL":
            new_status = "KILLED"
        elif verdict == "REWORK":
            new_status = "REWORK"
        else:
            new_status = "COLLECT"

        now = utc_now()
        with self.engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO profit_gate_review (
                    hypothesis_id, created_at_utc, stage, role, verdict,
                    grok_run_id, response_text, cost_usd
                ) VALUES (
                    :hid, :created, :stage, :role, :verdict,
                    :run_id, :response, :cost
                )
            """), {
                "hid": int(hypothesis_id),
                "created": now,
                "stage": stage,
                "role": role,
                "verdict": verdict,
                "run_id": result.get("id"),
                "response": (result.get("response") or "")[:100_000],
                "cost": float(result.get("cost_usd") or 0.0),
            })
            cx.execute(text("""
                UPDATE profit_hypothesis
                SET updated_at_utc=:updated,
                    current_stage=:stage,
                    status=:status
                WHERE id=:id
            """), {
                "updated": now,
                "stage": new_stage,
                "status": new_status,
                "id": int(hypothesis_id),
            })

        return {
            "hypothesis_id": int(hypothesis_id),
            "reviewed_stage": stage,
            "role": role,
            "verdict": verdict,
            "new_stage": new_stage,
            "new_status": new_status,
            "grok_run_id": result.get("id"),
            "cost_usd": result.get("cost_usd"),
            "live_trade_authorized": False,
        }

    def dashboard(self) -> dict[str, Any]:
        with self.engine.begin() as cx:
            statuses = cx.execute(text("""
                SELECT status, COUNT(*) AS n
                FROM profit_hypothesis GROUP BY status
            """)).mappings().all()
            stages = cx.execute(text("""
                SELECT current_stage, COUNT(*) AS n
                FROM profit_hypothesis GROUP BY current_stage
            """)).mappings().all()
            spend = cx.execute(text("""
                SELECT COALESCE(SUM(cost_usd),0)
                FROM profit_gate_review
            """)).scalar_one()
        return {
            "hypotheses_by_status": {str(r["status"]): int(r["n"]) for r in statuses},
            "hypotheses_by_stage": {str(r["current_stage"]): int(r["n"]) for r in stages},
            "grok_gate_spend_usd": float(spend or 0.0),
            "north_star": "long-run executable net PnL after all costs and tail losses",
            "live_execution": False,
        }
