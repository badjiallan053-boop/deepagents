from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy import text


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_firm_tables(engine) -> None:
    sqlite = str(engine.url).startswith("sqlite")
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if sqlite else "BIGSERIAL PRIMARY KEY"
    with engine.begin() as cx:
        cx.execute(text(f"""
        CREATE TABLE IF NOT EXISTS firm_portfolio_position (
            id {pk},
            candidate_id BIGINT NOT NULL,
            opened_at_utc TEXT NOT NULL,
            closed_at_utc TEXT,
            mint TEXT NOT NULL,
            source TEXT NOT NULL,
            source_detail TEXT,
            allocated_lamports BIGINT NOT NULL,
            token_amount TEXT NOT NULL,
            strategy_names_json TEXT NOT NULL,
            market_phase TEXT,
            latest_value_lamports BIGINT,
            latest_pnl_lamports BIGINT,
            latest_pnl_bps DOUBLE PRECISION,
            realized_value_lamports BIGINT,
            realized_pnl_lamports BIGINT,
            realized_pnl_bps DOUBLE PRECISION,
            status TEXT NOT NULL
        )
        """))
        cx.execute(text(f"""
        CREATE TABLE IF NOT EXISTS candidate_markout (
            id {pk},
            candidate_id BIGINT NOT NULL,
            horizon_seconds INTEGER NOT NULL,
            checked_at_utc TEXT NOT NULL,
            value_lamports BIGINT NOT NULL,
            pnl_bps DOUBLE PRECISION NOT NULL,
            sellable INTEGER NOT NULL,
            UNIQUE(candidate_id, horizon_seconds)
        )
        """))


class FirmPortfolioBook:
    """
    Simulated capital book, separate from the research paper book.

    Research book: fixed notional, every eligible hypothesis.
    Firm book: only promoted strategies/sources, explicit risk budgets.
    """

    def __init__(self, engine):
        self.engine = engine
        ensure_firm_tables(engine)
        self.hold_seconds = int(os.getenv("FIRM_HOLD_SECONDS", "300") or 300)
        self.markout_horizons = tuple(
            sorted({
                int(x.strip())
                for x in os.getenv("MARKOUT_HORIZONS_SECONDS", "30,120,300,900").split(",")
                if x.strip()
            })
        )

    async def open_position(
        self,
        *,
        candidate_id: int,
        allocated_lamports: int,
        strategy_names: list[str],
        quote_buy: Callable[[str, int], Awaitable[dict[str, Any]]],
    ) -> Optional[int]:
        with self.engine.begin() as cx:
            c = cx.execute(text("""
                SELECT id, mint, source, source_detail, market_phase
                FROM realtime_candidate
                WHERE id=:id
            """), {"id": candidate_id}).mappings().first()
            existing = int(cx.execute(text("""
                SELECT COUNT(*) FROM firm_portfolio_position
                WHERE candidate_id=:id
            """), {"id": candidate_id}).scalar_one())

        if not c or existing:
            return None

        q = await quote_buy(str(c["mint"]), int(allocated_lamports))
        tokens = int(q.get("outAmount") or 0)
        if tokens <= 0:
            return None

        row = {
            "candidate_id": int(candidate_id),
            "opened_at_utc": utc_now(),
            "mint": str(c["mint"]),
            "source": str(c["source"]),
            "source_detail": c["source_detail"],
            "allocated_lamports": int(allocated_lamports),
            "token_amount": str(tokens),
            "strategy_names_json": json.dumps(strategy_names, separators=(",", ":")),
            "market_phase": q.get("phase") or c["market_phase"],
            "status": "OPEN",
        }

        with self.engine.begin() as cx:
            result = cx.execute(text("""
                INSERT INTO firm_portfolio_position (
                    candidate_id, opened_at_utc, mint, source, source_detail,
                    allocated_lamports, token_amount, strategy_names_json,
                    market_phase, status
                ) VALUES (
                    :candidate_id, :opened_at_utc, :mint, :source, :source_detail,
                    :allocated_lamports, :token_amount, :strategy_names_json,
                    :market_phase, :status
                )
            """), row)
            pid = getattr(result, "lastrowid", None)
            if not pid:
                pid = cx.execute(text("""
                    SELECT id FROM firm_portfolio_position
                    WHERE candidate_id=:candidate_id
                    ORDER BY id DESC LIMIT 1
                """), {"candidate_id": candidate_id}).scalar_one()
        return int(pid)

    async def mark_open(
        self,
        quote_sell: Callable[[str, int], Awaitable[dict[str, Any]]],
    ) -> None:
        with self.engine.begin() as cx:
            rows = cx.execute(text("""
                SELECT * FROM firm_portfolio_position
                WHERE status='OPEN'
                ORDER BY id
            """)).mappings().all()

        now = datetime.now(timezone.utc)
        for pos in rows:
            try:
                q = await quote_sell(str(pos["mint"]), int(pos["token_amount"]))
                value = int(q.get("outAmount") or 0)
                cost = int(pos["allocated_lamports"])
                pnl = value - cost
                pnl_bps = (pnl / cost) * 10_000 if cost > 0 else -10_000.0

                opened = datetime.fromisoformat(
                    str(pos["opened_at_utc"]).replace("Z", "+00:00")
                )
                if opened.tzinfo is None:
                    opened = opened.replace(tzinfo=timezone.utc)
                age = (now - opened).total_seconds()

                with self.engine.begin() as cx:
                    cx.execute(text("""
                        UPDATE firm_portfolio_position
                        SET latest_value_lamports=:v,
                            latest_pnl_lamports=:p,
                            latest_pnl_bps=:b
                        WHERE id=:id
                    """), {"v": value, "p": pnl, "b": pnl_bps, "id": pos["id"]})

                if age >= self.hold_seconds:
                    with self.engine.begin() as cx:
                        cx.execute(text("""
                            UPDATE firm_portfolio_position
                            SET closed_at_utc=:closed,
                                realized_value_lamports=:v,
                                realized_pnl_lamports=:p,
                                realized_pnl_bps=:b,
                                status='CLOSED'
                            WHERE id=:id
                        """), {
                            "closed": utc_now(),
                            "v": value,
                            "p": pnl,
                            "b": pnl_bps,
                            "id": pos["id"],
                        })
            except Exception:
                # Mark failures should not mutate the position into a false exit.
                continue

    async def mark_candidate_horizons(
        self,
        quote_sell: Callable[[str, int], Awaitable[dict[str, Any]]],
    ) -> None:
        """
        Multi-horizon markouts for every candidate that had an executable entry.
        This is independent of whether the strategy passed.
        """
        with self.engine.begin() as cx:
            rows = cx.execute(text("""
                SELECT id, created_at_utc, mint, notional_lamports, buy_out_amount
                FROM realtime_candidate
                WHERE buy_out_amount IS NOT NULL
                ORDER BY id DESC
                LIMIT 2000
            """)).mappings().all()
            existing = {
                (int(r["candidate_id"]), int(r["horizon_seconds"]))
                for r in cx.execute(text("""
                    SELECT candidate_id, horizon_seconds
                    FROM candidate_markout
                """)).mappings().all()
            }

        now = datetime.now(timezone.utc)
        for row in rows:
            created = datetime.fromisoformat(
                str(row["created_at_utc"]).replace("Z", "+00:00")
            )
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age = (now - created).total_seconds()

            due = [
                h for h in self.markout_horizons
                if age >= h and (int(row["id"]), h) not in existing
            ]
            if not due:
                continue

            try:
                q = await quote_sell(str(row["mint"]), int(row["buy_out_amount"]))
                value = int(q.get("outAmount") or 0)
                cost = int(row["notional_lamports"])
                pnl_bps = ((value / cost) - 1.0) * 10_000 if value > 0 and cost > 0 else -10_000.0
                sellable = 1 if value > 0 else 0
            except Exception:
                value = 0
                pnl_bps = -10_000.0
                sellable = 0

            with self.engine.begin() as cx:
                for horizon in due:
                    try:
                        cx.execute(text("""
                            INSERT INTO candidate_markout (
                                candidate_id, horizon_seconds, checked_at_utc,
                                value_lamports, pnl_bps, sellable
                            ) VALUES (
                                :candidate_id, :horizon_seconds, :checked_at_utc,
                                :value_lamports, :pnl_bps, :sellable
                            )
                        """), {
                            "candidate_id": int(row["id"]),
                            "horizon_seconds": int(horizon),
                            "checked_at_utc": utc_now(),
                            "value_lamports": int(value),
                            "pnl_bps": float(pnl_bps),
                            "sellable": int(sellable),
                        })
                    except Exception:
                        pass

    def summary(self) -> dict[str, Any]:
        with self.engine.begin() as cx:
            rows = cx.execute(text("""
                SELECT status, COUNT(*) AS n,
                       COALESCE(SUM(allocated_lamports),0) AS allocated,
                       COALESCE(SUM(CASE WHEN status='CLOSED' THEN realized_pnl_lamports ELSE 0 END),0) AS pnl
                FROM firm_portfolio_position
                GROUP BY status
            """)).mappings().all()
        return {
            str(r["status"]): {
                "n": int(r["n"]),
                "allocated_lamports": int(r["allocated"] or 0),
                "realized_pnl_lamports": int(r["pnl"] or 0),
            }
            for r in rows
        }
