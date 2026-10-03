from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

import httpx
from sqlalchemy import text

# The 5-minute candidate outcome (realtime_candidate.outcome_5m_bps) is derived
# from this horizon's markout so there is exactly one source of truth.
OUTCOME_HORIZON_SECONDS = 300

# Markout classifications.
SOLD = "SOLD"                # executable sell quote with value > 0
UNSELLABLE = "UNSELLABLE"    # no route / zero value persisted past the retry window: -100%
NO_ROUTE = "NO_ROUTE"        # single-attempt observation, retried until the window closes
TRANSIENT = "TRANSIENT"      # 429 / 5xx / timeout / transport: never a loss by itself
MARK_FAILED = "MARK_FAILED"  # transient errors persisted past the window: excluded, not -100%
MISSED = "MISSED"            # horizon window passed before any attempt (e.g. downtime)
PENDING = "PENDING"
DONE = "DONE"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except ValueError:
        return default


def classify_quote_exception(exc: BaseException) -> str:
    """
    A sell quote that errors is NOT automatically a rug. Only an explicit
    "cannot route this sell" answer (400/404/422) counts towards UNSELLABLE.
    Rate limits, server errors, auth problems, timeouts and transport errors
    are infrastructure noise and are retried, never booked as -100%.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (400, 404, 422):
            return NO_ROUTE
        return TRANSIENT
    return TRANSIENT


async def classify_sell_quote(
    quote_sell: Callable[[str, int], Awaitable[dict[str, Any]]],
    mint: str,
    token_amount: int,
) -> tuple[str, int, str]:
    """Returns (SOLD | NO_ROUTE | TRANSIENT, value_lamports, error)."""
    try:
        q = await quote_sell(mint, int(token_amount))
    except Exception as exc:  # classified, never swallowed into a fake loss
        return classify_quote_exception(exc), 0, f"{type(exc).__name__}: {exc}"[:300]
    try:
        value = int(q.get("outAmount") or 0)
    except (TypeError, ValueError):
        value = 0
    if value > 0:
        return SOLD, value, ""
    err = str(q.get("error") or q.get("errorMessage") or q.get("errorCode") or "zero outAmount")
    return NO_ROUTE, 0, err[:300]


def _add_columns(engine, ddls) -> None:
    # One transaction per ALTER: on Postgres a failed ALTER (column exists)
    # aborts the whole transaction and would silently skip later migrations.
    for ddl in ddls:
        try:
            with engine.begin() as cx:
                cx.execute(text(ddl))
        except Exception:
            pass


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
            observed_age_seconds DOUBLE PRECISION,
            lateness_seconds DOUBLE PRECISION,
            late INTEGER NOT NULL DEFAULT 0,
            status TEXT,
            UNIQUE(candidate_id, horizon_seconds)
        )
        """))
        cx.execute(text(f"""
        CREATE TABLE IF NOT EXISTS markout_attempt (
            id {pk},
            candidate_id BIGINT NOT NULL,
            horizon_seconds INTEGER NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            first_attempt_age_seconds DOUBLE PRECISION,
            first_no_route_age_seconds DOUBLE PRECISION,
            last_kind TEXT,
            last_error TEXT,
            next_attempt_epoch DOUBLE PRECISION,
            updated_at_utc TEXT NOT NULL,
            UNIQUE(candidate_id, horizon_seconds)
        )
        """))
    _add_columns(engine, (
        "ALTER TABLE candidate_markout ADD COLUMN observed_age_seconds DOUBLE PRECISION",
        "ALTER TABLE candidate_markout ADD COLUMN lateness_seconds DOUBLE PRECISION",
        "ALTER TABLE candidate_markout ADD COLUMN late INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE candidate_markout ADD COLUMN status TEXT",
    ))


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
            } | {OUTCOME_HORIZON_SECONDS})
        )
        # A markout is "late" when observed more than max(min_secs, frac*h) after h.
        self.late_tolerance_frac = _env_float("MARKOUT_LATE_TOLERANCE_FRAC", 0.20)
        self.late_tolerance_min_secs = _env_float("MARKOUT_LATE_TOLERANCE_MIN_SECS", 5.0)
        # How long after h we keep retrying no-route / transient quote failures.
        self.retry_window_secs = _env_float("MARKOUT_RETRY_WINDOW_SECS", 60.0)
        self.retry_base_secs = _env_float("MARKOUT_RETRY_BASE_SECS", 2.0)
        self.retry_max_backoff_secs = _env_float("MARKOUT_RETRY_MAX_BACKOFF_SECS", 20.0)

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

    def late_tolerance(self, horizon: int) -> float:
        return max(self.late_tolerance_min_secs, self.late_tolerance_frac * horizon)

    def retry_window(self, horizon: int) -> float:
        return max(self.retry_window_secs, self.late_tolerance(horizon))

    async def mark_candidate_horizons(
        self,
        quote_sell: Callable[[str, int], Awaitable[dict[str, Any]]],
        now_epoch: Optional[float] = None,
    ) -> None:
        """
        Multi-horizon markouts for every episode-primary candidate that had an
        executable entry, independent of whether the strategy passed.

        Each horizon gets its own quote, taken when that horizon is due; the
        observed age is stored and late observations are flagged. Quote
        failures are classified: no-route that persists past the retry window
        is booked as UNSELLABLE (-100%); transient errors are retried with
        backoff and end as MARK_FAILED (excluded) rather than a fake loss.
        Every (candidate, horizon) reaches a terminal state, so failing rows
        can never block newer candidates.
        """
        clock = time.time if now_epoch is None else (lambda: float(now_epoch))
        horizons = self.markout_horizons
        with self.engine.begin() as cx:
            rows = cx.execute(text("""
                SELECT c.id, c.created_at_utc, c.mint, c.notional_lamports, c.buy_out_amount
                FROM realtime_candidate c
                WHERE c.buy_out_amount IS NOT NULL
                  AND c.episode_primary=1
                  AND (
                    SELECT COUNT(*) FROM markout_attempt a
                    WHERE a.candidate_id=c.id AND a.status<>'PENDING'
                  ) < :nh
                ORDER BY c.id
                LIMIT 500
            """), {"nh": len(horizons)}).mappings().all()
            if not rows:
                return
            attempts = {
                (int(r["candidate_id"]), int(r["horizon_seconds"])): dict(r)
                for r in cx.execute(text("""
                    SELECT * FROM markout_attempt WHERE candidate_id >= :min_id
                """), {"min_id": int(rows[0]["id"])}).mappings().all()
            }

        for row in rows:
            cid = int(row["id"])
            created = datetime.fromisoformat(
                str(row["created_at_utc"]).replace("Z", "+00:00")
            )
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            for h in horizons:
                st = attempts.get((cid, h))
                if st and st["status"] != PENDING:
                    continue
                now = clock()
                age = now - created.timestamp()
                if age < h:
                    continue
                deadline_age = h + self.retry_window(h)
                if st is None and age > deadline_age:
                    self._finish_attempt(cid, h, MISSED, st, age, "", "window passed before first attempt")
                    continue
                if st and st.get("next_attempt_epoch") and now < float(st["next_attempt_epoch"]):
                    continue

                kind, value, err = await classify_sell_quote(
                    quote_sell, str(row["mint"]), int(row["buy_out_amount"])
                )
                now = clock()
                age = now - created.timestamp()
                cost = int(row["notional_lamports"])
                first_no_route = st.get("first_no_route_age_seconds") if st else None
                if kind == NO_ROUTE and first_no_route is None:
                    first_no_route = age

                if kind == SOLD:
                    pnl_bps = ((value / cost) - 1.0) * 10_000 if cost > 0 else -10_000.0
                    self._record_markout(cid, h, SOLD, value, pnl_bps, 1, age)
                    self._finish_attempt(cid, h, DONE, st, age, kind, "", first_no_route)
                elif age >= deadline_age:
                    if first_no_route is not None:
                        # Seen unroutable and never sold inside the window: book
                        # -100% at the age it was first observed unsellable.
                        self._record_markout(cid, h, UNSELLABLE, 0, -10_000.0, 0, float(first_no_route))
                        self._finish_attempt(cid, h, DONE, st, age, NO_ROUTE, err, first_no_route)
                    else:
                        self._finish_attempt(cid, h, MARK_FAILED, st, age, kind, err, first_no_route)
                else:
                    n = int(st["attempts"]) + 1 if st else 1
                    delay = min(self.retry_max_backoff_secs, self.retry_base_secs * (2 ** (n - 1)))
                    next_epoch = min(now + delay, created.timestamp() + deadline_age)
                    self._schedule_retry(cid, h, st, age, kind, err, first_no_route, next_epoch)

    def _upsert_attempt(self, cx, cid: int, h: int, exists: bool, params: dict[str, Any]) -> None:
        params = {**params, "cid": cid, "h": h, "u": utc_now()}
        if exists:
            cx.execute(text("""
                UPDATE markout_attempt
                SET status=:status, attempts=attempts+:inc,
                    first_no_route_age_seconds=:fnr, last_kind=:kind,
                    last_error=:err, next_attempt_epoch=:next, updated_at_utc=:u
                WHERE candidate_id=:cid AND horizon_seconds=:h
            """), params)
        else:
            cx.execute(text("""
                INSERT INTO markout_attempt (
                    candidate_id, horizon_seconds, status, attempts,
                    first_attempt_age_seconds, first_no_route_age_seconds,
                    last_kind, last_error, next_attempt_epoch, updated_at_utc
                ) VALUES (
                    :cid, :h, :status, :inc, :age, :fnr, :kind, :err, :next, :u
                )
            """), params)

    def _schedule_retry(self, cid, h, st, age, kind, err, first_no_route, next_epoch) -> None:
        with self.engine.begin() as cx:
            self._upsert_attempt(cx, cid, h, st is not None, {
                "status": PENDING, "inc": 1, "age": age, "fnr": first_no_route,
                "kind": kind, "err": err, "next": next_epoch,
            })

    def _finish_attempt(self, cid, h, status, st, age, kind, err, first_no_route=None) -> None:
        with self.engine.begin() as cx:
            self._upsert_attempt(cx, cid, h, st is not None, {
                "status": status, "inc": 0 if status == MISSED else 1, "age": age,
                "fnr": first_no_route, "kind": kind or status, "err": err, "next": None,
            })
            if h == OUTCOME_HORIZON_SECONDS and status in (MARK_FAILED, MISSED):
                self._sync_outcome(cx, cid, None, status)

    def _record_markout(self, cid, h, status, value, pnl_bps, sellable, observed_age) -> None:
        lateness = float(observed_age) - h
        late = 1 if lateness > self.late_tolerance(h) else 0
        with self.engine.begin() as cx:
            exists = cx.execute(text("""
                SELECT COUNT(*) FROM candidate_markout
                WHERE candidate_id=:cid AND horizon_seconds=:h
            """), {"cid": int(cid), "h": int(h)}).scalar_one()
            if int(exists):
                return  # legacy row from the pre-classification marker; keep it
            cx.execute(text("""
                INSERT INTO candidate_markout (
                    candidate_id, horizon_seconds, checked_at_utc,
                    value_lamports, pnl_bps, sellable,
                    observed_age_seconds, lateness_seconds, late, status
                ) VALUES (
                    :candidate_id, :horizon_seconds, :checked_at_utc,
                    :value_lamports, :pnl_bps, :sellable,
                    :age, :lateness, :late, :status
                )
            """), {
                "candidate_id": int(cid),
                "horizon_seconds": int(h),
                "checked_at_utc": utc_now(),
                "value_lamports": int(value),
                "pnl_bps": float(pnl_bps),
                "sellable": int(sellable),
                "age": float(observed_age),
                "lateness": lateness,
                "late": late,
                "status": status,
            })
            if h == OUTCOME_HORIZON_SECONDS:
                if late:
                    self._sync_outcome(cx, cid, None, "LATE")
                else:
                    self._sync_outcome(cx, cid, float(pnl_bps), status)

    @staticmethod
    def _sync_outcome(cx, cid: int, outcome_bps: Optional[float], status: str) -> None:
        cx.execute(text("""
            UPDATE realtime_candidate
            SET outcome_5m_bps=:o, outcome_5m_status=:s,
                outcome_checked_at_utc=:u, updated_at_utc=:u
            WHERE id=:id
        """), {"o": outcome_bps, "s": status, "u": utc_now(), "id": int(cid)})

    def markout_diagnostics(self) -> dict[str, Any]:
        with self.engine.begin() as cx:
            attempts = cx.execute(text("""
                SELECT horizon_seconds, status, COUNT(*) AS n
                FROM markout_attempt GROUP BY horizon_seconds, status
            """)).mappings().all()
            markouts = cx.execute(text("""
                SELECT horizon_seconds, status, late, COUNT(*) AS n
                FROM candidate_markout GROUP BY horizon_seconds, status, late
            """)).mappings().all()
        out: dict[str, Any] = {}
        for r in attempts:
            out.setdefault(str(r["horizon_seconds"]), {}).setdefault("attempts", {})[str(r["status"])] = int(r["n"])
        for r in markouts:
            key = f"{r['status'] or 'LEGACY'}{'_LATE' if int(r['late'] or 0) else ''}"
            out.setdefault(str(r["horizon_seconds"]), {}).setdefault("markouts", {})[key] = int(r["n"])
        return out

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
