from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import text


XAI_RESPONSES_URL = "https://api.x.ai/v1/responses"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def ensure_grok_tables(engine) -> None:
    sqlite = str(engine.url).startswith("sqlite")
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if sqlite else "BIGSERIAL PRIMARY KEY"
    with engine.begin() as cx:
        cx.execute(text(f"""
        CREATE TABLE IF NOT EXISTS grok_run (
            id {pk},
            created_at_utc TEXT NOT NULL,
            role TEXT NOT NULL,
            model TEXT NOT NULL,
            objective TEXT,
            tools_json TEXT,
            context_hash TEXT,
            response_text TEXT,
            citations_json TEXT,
            cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            error TEXT
        )
        """))


@dataclass(frozen=True)
class GrokRole:
    name: str
    mandate: str
    default_web: bool = False
    default_x: bool = False
    deep_by_default: bool = False


ROLES: dict[str, GrokRole] = {
    "CIO": GrokRole(
        "CIO",
        "Review forward evidence, risk, strategy promotion/demotion, and research priorities. Never override risk.",
    ),
    "EXECUTION_ANALYST": GrokRole(
        "EXECUTION_ANALYST",
        "Analyze quote decay, round-trip friction, sellability, market phase, and where latency/cost destroys alpha.",
    ),
    "STRATEGY_FORENSICS": GrokRole(
        "STRATEGY_FORENSICS",
        "Compare strategy pass/fail outcomes, markout horizons, outlier concentration, and regime dependence.",
    ),
    "TELEGRAM_FORENSICS": GrokRole(
        "TELEGRAM_FORENSICS",
        "Evaluate Telegram channels only from our delayed executable outcomes; detect copied calls and toxic flow.",
    ),
    "WALLET_INTELLIGENCE": GrokRole(
        "WALLET_INTELLIGENCE",
        "Evaluate wallet-copy hypotheses, cluster dependence, post-observation alpha decay, and evidence gaps.",
    ),
    "X_NARRATIVE_SCOUT": GrokRole(
        "X_NARRATIVE_SCOUT",
        "Search X only for narrowly scoped, current narrative or promoter hypotheses that can be tested against our tape.",
        default_x=True,
    ),
    "WEB_INFRA_SCOUT": GrokRole(
        "WEB_INFRA_SCOUT",
        "Research current Solana execution/data infrastructure, official docs, releases, and cost/latency opportunities.",
        default_web=True,
    ),
    "RED_TEAM": GrokRole(
        "RED_TEAM",
        "Try to falsify the desk thesis: leakage, survivorship bias, correlated signals, bad execution assumptions, manipulation, and security.",
    ),
    "INVESTMENT_COMMITTEE": GrokRole(
        "INVESTMENT_COMMITTEE",
        "Act as an independent investment committee. Synthesize evidence across desks and issue research promotion/demotion recommendations only.",
        deep_by_default=True,
    ),
    "CODE_REVIEW": GrokRole(
        "CODE_REVIEW",
        "Review architecture and reliability from supplied context. Propose code changes; never request secrets.",
    ),
    "GLOBAL_MACRO": GrokRole(
        "GLOBAL_MACRO",
        "Track rates, FX, commodities, index futures, central banks, macro releases, positioning, and cross-asset regime shifts. Convert surprises into testable hypotheses, not trade commands.",
        default_web=True,
    ),
    "EQUITY_EVENT": GrokRole(
        "EQUITY_EVENT",
        "Analyze earnings, guidance, SEC filings, buybacks, M&A, insider activity, capital allocation, and company-specific catalysts. Separate primary-source facts from narrative.",
        default_web=True,
    ),
    "OPTIONS_VOL": GrokRole(
        "OPTIONS_VOL",
        "Study implied-volatility surfaces, skew, term structure, event vol, realized-vs-implied spreads, gamma/vanna exposure, and liquidity. Produce volatility hypotheses and hedging implications.",
    ),
    "STAT_ARB": GrokRole(
        "STAT_ARB",
        "Search for cross-sectional, pairs, lead-lag, mean-reversion, momentum, and relative-value signals. Require out-of-sample stability, turnover costs, capacity, and regime tests.",
    ),
    "CRYPTO_RELATIVE_VALUE": GrokRole(
        "CRYPTO_RELATIVE_VALUE",
        "Analyze cross-exchange basis, funding, open interest, liquidations, spot-perp dislocations, stablecoin flows, ETF/flow linkages, and market microstructure across crypto venues.",
        default_web=True,
    ),
    "NEWS_EVENT": GrokRole(
        "NEWS_EVENT",
        "Prioritize primary-source events and timestamped news. Measure novelty, source reliability, publication-to-observation latency, affected instruments, and post-event markouts.",
        default_web=True,
    ),
    "ALT_DATA": GrokRole(
        "ALT_DATA",
        "Evaluate alternative datasets such as app rankings, web traffic, GitHub activity, job postings, product pricing, shipping, supply-chain, and on-chain activity strictly by incremental forward value.",
        default_web=True,
    ),
    "DATA_PROVENANCE": GrokRole(
        "DATA_PROVENANCE",
        "Audit timestamps, revisions, source provenance, survivorship, point-in-time correctness, symbol mapping, corporate actions, and leakage. Reject datasets that cannot be reproduced.",
    ),
    "PORTFOLIO_CONSTRUCTION": GrokRole(
        "PORTFOLIO_CONSTRUCTION",
        "Combine promoted strategy sleeves under exposure, correlation, drawdown, liquidity, capacity, and tail-risk constraints. Prefer diversification of independent alpha rather than many correlated bets.",
    ),
    "RISK_OFFICER": GrokRole(
        "RISK_OFFICER",
        "Independently challenge portfolio exposures, leverage, liquidity, concentration, gap risk, correlation spikes, model drift, and operational risk. Risk may veto but never originate trades.",
    ),
    "EXECUTION_ROUTER": GrokRole(
        "EXECUTION_ROUTER",
        "Analyze venue selection, spread, market impact, fill probability, order type, routing, fees, rebates, adverse selection, and latency. Recommend execution experiments, not discretionary trades.",
    ),
    "MARKET_MAKING_RESEARCH": GrokRole(
        "MARKET_MAKING_RESEARCH",
        "Research spread capture, inventory skew, toxic-flow detection, quote placement, cross-venue hedging, and capacity for liquid markets. Demand realistic queue and fill models.",
    ),
}


class GrokTeam:
    """Slow-thinking research team above the deterministic engine."""

    def __init__(self, engine):
        self.engine = engine
        ensure_grok_tables(engine)
        self.enabled = env_bool("GROK_ENABLED", False)
        self.api_key = os.getenv("XAI_API_KEY", "").strip()
        self.routine_model = os.getenv("GROK_ROUTINE_MODEL", "grok-4.3").strip()
        self.deep_model = os.getenv("GROK_DEEP_MODEL", "grok-4.20-multi-agent-0309").strip()
        self.code_model = os.getenv("GROK_CODE_MODEL", "grok-build-0.1").strip()
        self.daily_budget_usd = float(os.getenv("GROK_DAILY_BUDGET_USD", "2.00") or 2.0)
        self.max_recent_candidates = int(os.getenv("GROK_MAX_RECENT_CANDIDATES", "120") or 120)
        self.max_markouts = int(os.getenv("GROK_MAX_MARKOUTS", "300") or 300)
        self.allow_web = env_bool("GROK_ALLOW_WEB_SEARCH", False)
        self.allow_x = env_bool("GROK_ALLOW_X_SEARCH", False)

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "api_key_present": bool(self.api_key),
            "routine_model": self.routine_model,
            "deep_model": self.deep_model,
            "code_model": self.code_model,
            "daily_budget_usd": self.daily_budget_usd,
            "spent_today_usd": round(self.spent_today_usd(), 6),
            "allow_web_search": self.allow_web,
            "allow_x_search": self.allow_x,
            "roles": sorted(ROLES),
            "can_authorize_trade": False,
            "can_access_private_keys": False,
        }

    def spent_today_usd(self) -> float:
        day = datetime.now(timezone.utc).date().isoformat()
        with self.engine.begin() as cx:
            value = cx.execute(text("""
                SELECT COALESCE(SUM(cost_usd), 0)
                FROM grok_run
                WHERE substr(created_at_utc, 1, 10)=:day
                  AND status='SUCCESS'
            """), {"day": day}).scalar_one()
        return float(value or 0.0)

    @staticmethod
    def _stats(values: list[float]) -> dict[str, Any]:
        if not values:
            return {"n": 0}
        xs = sorted(values)
        n = len(xs)
        median = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
        gains = sum(x for x in xs if x > 0)
        losses = -sum(x for x in xs if x < 0)
        return {
            "n": n,
            "mean_bps": sum(xs) / n,
            "median_bps": median,
            "positive_rate": sum(1 for x in xs if x > 0) / n,
            "large_loss_rate": sum(1 for x in xs if x <= -2000) / n,
            "profit_factor": (gains / losses) if losses > 0 else (999.0 if gains > 0 else 0.0),
        }

    def local_context(self, role: str) -> dict[str, Any]:
        role = role.upper()
        if role not in ROLES:
            raise ValueError(f"Unknown Grok role: {role}")

        with self.engine.begin() as cx:
            candidates = [
                dict(r) for r in cx.execute(text("""
                    SELECT id, created_at_utc, mint, source, source_detail,
                           roundtrip_bps, drift_500_bps, organic_score,
                           strategy_score, strategy_votes_json, signal_age_ms,
                           market_phase, decision, reason, outcome_5m_bps
                    FROM realtime_candidate
                    ORDER BY id DESC
                    LIMIT :limit
                """), {"limit": self.max_recent_candidates}).mappings().all()
            ]
            markouts = [
                dict(r) for r in cx.execute(text("""
                    SELECT m.candidate_id, m.horizon_seconds, m.pnl_bps, m.sellable,
                           c.source, c.source_detail, c.market_phase, c.decision,
                           c.strategy_votes_json
                    FROM candidate_markout m
                    JOIN realtime_candidate c ON c.id=m.candidate_id
                    ORDER BY m.id DESC
                    LIMIT :limit
                """), {"limit": self.max_markouts}).mappings().all()
            ]
            firm_positions = [
                dict(r) for r in cx.execute(text("""
                    SELECT id, opened_at_utc, closed_at_utc, mint, source,
                           source_detail, allocated_lamports, latest_pnl_bps,
                           realized_pnl_bps, status, strategy_names_json
                    FROM firm_portfolio_position
                    ORDER BY id DESC
                    LIMIT 100
                """)).mappings().all()
            ]

        by_source: dict[str, list[float]] = {}
        by_decision: dict[str, list[float]] = {}
        by_phase: dict[str, list[float]] = {}
        by_horizon: dict[str, list[float]] = {}
        strategy_pass: dict[str, list[float]] = {}
        strategy_fail: dict[str, list[float]] = {}

        for c in candidates:
            outcome = c.get("outcome_5m_bps")
            if outcome is None:
                continue
            x = float(outcome)
            by_source.setdefault(str(c.get("source") or "unknown"), []).append(x)
            by_decision.setdefault(str(c.get("decision") or "unknown"), []).append(x)
            by_phase.setdefault(str(c.get("market_phase") or "unknown"), []).append(x)
            try:
                votes = json.loads(c.get("strategy_votes_json") or "[]")
            except Exception:
                votes = []
            for vote in votes:
                name = str(vote.get("name") or "UNKNOWN")
                (strategy_pass if vote.get("passed") else strategy_fail).setdefault(name, []).append(x)

        for m in markouts:
            by_horizon.setdefault(str(m.get("horizon_seconds")), []).append(float(m.get("pnl_bps") or 0.0))

        compact_candidates = []
        for c in candidates[:60]:
            compact_candidates.append({
                "id": c.get("id"),
                "ts": c.get("created_at_utc"),
                "source": c.get("source"),
                "source_detail": c.get("source_detail"),
                "roundtrip_bps": c.get("roundtrip_bps"),
                "drift_500_bps": c.get("drift_500_bps"),
                "organic_score": c.get("organic_score"),
                "signal_age_ms": c.get("signal_age_ms"),
                "market_phase": c.get("market_phase"),
                "decision": c.get("decision"),
                "reason": c.get("reason"),
                "outcome_5m_bps": c.get("outcome_5m_bps"),
            })

        return {
            "generated_at_utc": utc_now(),
            "role": role,
            "principles": {
                "research_only": True,
                "live_signing_present": False,
                "grok_trade_authority": False,
                "promotion_is_evidence_gated": True,
                "risk_is_veto_only": True,
            },
            "scorecards": {
                "by_source": {k: self._stats(v) for k, v in by_source.items()},
                "by_decision": {k: self._stats(v) for k, v in by_decision.items()},
                "by_market_phase": {k: self._stats(v) for k, v in by_phase.items()},
                "by_horizon": {k: self._stats(v) for k, v in by_horizon.items()},
                "strategy_pass": {k: self._stats(v) for k, v in strategy_pass.items()},
                "strategy_fail": {k: self._stats(v) for k, v in strategy_fail.items()},
            },
            "firm_positions": firm_positions,
            "recent_candidates": compact_candidates,
        }

    def _system_prompt(self, role: GrokRole) -> str:
        return f"""
You are {role.name}, one desk in Survival Alpha, a systematic Solana memecoin research firm.

MANDATE:
{role.mandate}

NON-NEGOTIABLE GOVERNANCE:
- You are a research/supervisory agent, not an execution agent.
- You cannot authorize, sign, submit, or bypass controls for live trades.
- Never ask for private keys, seed phrases, API secrets, deployment tokens, or Telegram session secrets.
- Treat social-media claims as hypotheses until our own forward executable tape supports them.
- Distinguish facts in evidence from hypotheses and recommendations.
- Always state sample size when discussing performance.
- Prefer executable markouts, sellability, latency decay, and accepted-vs-rejected separation over win rate.
- Explicitly flag survivorship bias, look-ahead, correlated wallets, copied Telegram calls, and outlier dependence.
- If evidence is insufficient, say COLLECT rather than inventing conviction.
- Risk has veto authority. You do not.
- Output concise, testable research actions.

REQUIRED OUTPUT:
1. STATE
2. FAILURES
3. ACTIONS (maximum five)
4. PROMOTION: PROMOTE / COLLECT / REWORK / KILL, with evidence
5. BUDGET: whether extra data/tool/infrastructure spend is justified
""".strip()

    @staticmethod
    def _extract_text(body: dict[str, Any]) -> str:
        if isinstance(body.get("output_text"), str):
            return body["output_text"]
        chunks: list[str] = []
        for item in body.get("output") or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message":
                for part in item.get("content") or []:
                    if isinstance(part, dict):
                        txt = part.get("text") or part.get("output_text")
                        if txt:
                            chunks.append(str(txt))
            elif item.get("type") == "output_text" and item.get("text"):
                chunks.append(str(item["text"]))
        return "\n".join(chunks).strip()

    async def run(
        self,
        *,
        role_name: str,
        objective: str = "",
        deep: Optional[bool] = None,
        use_web: Optional[bool] = None,
        use_x: Optional[bool] = None,
    ) -> dict[str, Any]:
        role_name = role_name.upper()
        role = ROLES.get(role_name)
        if role is None:
            raise ValueError(f"Unknown Grok role: {role_name}")
        if not self.enabled:
            raise RuntimeError("GROK_ENABLED=false")
        if not self.api_key:
            raise RuntimeError("XAI_API_KEY is not configured")

        spent = self.spent_today_usd()
        if spent >= self.daily_budget_usd:
            raise RuntimeError(
                f"Grok daily budget exhausted: USD {spent:.4f} / USD {self.daily_budget_usd:.4f}"
            )

        deep = role.deep_by_default if deep is None else bool(deep)
        if role_name == "CODE_REVIEW":
            model = self.code_model
        else:
            model = self.deep_model if deep else self.routine_model

        web = role.default_web if use_web is None else bool(use_web)
        xsearch = role.default_x if use_x is None else bool(use_x)
        web = web and self.allow_web
        xsearch = xsearch and self.allow_x

        context = self.local_context(role_name)
        context_json = json.dumps(context, separators=(",", ":"), default=str)
        context_hash = hashlib.sha256(context_json.encode()).hexdigest()

        tools: list[dict[str, Any]] = []
        if web:
            tools.append({"type": "web_search"})
        if xsearch:
            tools.append({"type": "x_search"})

        prompt = (
            self._system_prompt(role)
            + "\n\nOBJECTIVE:\n"
            + (objective.strip() or "Review the supplied evidence under your mandate.")
            + "\n\nLOCAL FORWARD EVIDENCE (read-only):\n"
            + context_json
        )

        payload: dict[str, Any] = {"model": model, "input": prompt}
        if tools:
            payload["tools"] = tools

        created = utc_now()
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    XAI_RESPONSES_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                body = resp.json()

            output = self._extract_text(body)
            usage = body.get("usage") or {}
            ticks = usage.get("cost_in_usd_ticks") or 0
            cost = float(ticks) / 10_000_000_000.0
            citations = body.get("citations") or []

            with self.engine.begin() as cx:
                result = cx.execute(text("""
                    INSERT INTO grok_run (
                        created_at_utc, role, model, objective, tools_json,
                        context_hash, response_text, citations_json,
                        cost_usd, status, error
                    ) VALUES (
                        :created, :role, :model, :objective, :tools,
                        :context_hash, :response, :citations,
                        :cost, 'SUCCESS', NULL
                    )
                """), {
                    "created": created,
                    "role": role_name,
                    "model": model,
                    "objective": objective,
                    "tools": json.dumps(tools, separators=(",", ":")),
                    "context_hash": context_hash,
                    "response": output[:100_000],
                    "citations": json.dumps(citations, separators=(",", ":"), default=str)[:50_000],
                    "cost": cost,
                })
                run_id = getattr(result, "lastrowid", None)
                if not run_id:
                    run_id = cx.execute(text("SELECT id FROM grok_run ORDER BY id DESC LIMIT 1")).scalar_one()

            return {
                "id": int(run_id),
                "role": role_name,
                "model": model,
                "tools": tools,
                "response": output,
                "citations": citations,
                "cost_usd": cost,
                "spent_today_usd": self.spent_today_usd(),
                "can_authorize_trade": False,
            }
        except Exception as exc:
            with self.engine.begin() as cx:
                cx.execute(text("""
                    INSERT INTO grok_run (
                        created_at_utc, role, model, objective, tools_json,
                        context_hash, response_text, citations_json,
                        cost_usd, status, error
                    ) VALUES (
                        :created, :role, :model, :objective, :tools,
                        :context_hash, NULL, '[]', 0, 'ERROR', :error
                    )
                """), {
                    "created": created,
                    "role": role_name,
                    "model": model,
                    "objective": objective,
                    "tools": json.dumps(tools, separators=(",", ":")),
                    "context_hash": context_hash,
                    "error": f"{type(exc).__name__}: {exc}"[:4000],
                })
            raise

    def recent_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = min(max(int(limit), 1), 500)
        with self.engine.begin() as cx:
            rows = cx.execute(text("""
                SELECT id, created_at_utc, role, model, objective, tools_json,
                       response_text, citations_json, cost_usd, status, error
                FROM grok_run
                ORDER BY id DESC
                LIMIT :limit
            """), {"limit": limit}).mappings().all()
        return [dict(r) for r in rows]
