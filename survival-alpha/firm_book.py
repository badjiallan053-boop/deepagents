from __future__ import annotations

import json
import os
import re
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
CONFIG_ERROR = "CONFIG_ERROR"  # 401/403 or a malformed-request 4xx: our problem, never a loss
PENDING = "PENDING"
DONE = "DONE"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except ValueError:
        return default


class QuoteUnavailable(Exception):
    """
    The quote venue for this token could not be confirmed (e.g. the Pump sidecar
    errored, timed out or is down, and the Jupiter fallback found no route).
    A "no route" from the wrong venue is not evidence the token is unsellable,
    so this is always TRANSIENT, never a -100% markout.
    """


# Jupiter documents "no liquidity" as HTTP 400 {"error": "No routes found"}.
# Only an explicit no-route body counts; any other 4xx (bad params, API schema
# change) is a CONFIG_ERROR and must never be booked as a rug.
_NO_ROUTE_BODY = re.compile(
    r"no route|routes? not found|could not find any route|no liquidity|"
    r"not tradable|token_not_tradable|COULD_NOT_FIND_ANY_ROUTE",
    re.IGNORECASE,
)


def _response_text(resp: httpx.Response) -> str:
    try:
        return resp.text or ""
    except Exception:
        return ""


def classify_quote_exception(exc: BaseException) -> str:
    """
    A sell quote that errors is NOT automatically a rug. Only an explicit
    "cannot route this sell" answer (400/404/422 whose body says no route)
    counts towards UNSELLABLE. 401/403 and other 4xx are CONFIG_ERROR (our
    side is broken). Rate limits, server errors, timeouts, transport errors
    and unconfirmed-venue fallbacks are TRANSIENT. None of those are -100%.
    """
    if isinstance(exc, QuoteUnavailable):
        return TRANSIENT
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (400, 404, 422):
            return NO_ROUTE if _NO_ROUTE_BODY.search(_response_text(exc.response)) else CONFIG_ERROR
        if code in (401, 403) or (400 <= code < 500 and code not in (408, 425, 429)):
            return CONFIG_ERROR
        return TRANSIENT
    return TRANSIENT


async def classify_sell_quote(
    quote_sell: Callable[..., Awaitable[dict[str, Any]]],
    mint: str,
    token_amount: int,
    entry_phase: Optional[str] = None,
) -> tuple[str, int, str]:
    """Returns (SOLD | NO_ROUTE | TRANSIENT | CONFIG_ERROR, value_lamports, error).
    entry_phase (the market phase the entry was quoted on) lets the quoter exit
    on the same venue the entry used."""
    try:
        if entry_phase:
            q = await quote_sell(mint, int(token_amount), entry_phase=entry_phase)
        else:
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
            gross_pnl_bps DOUBLE PRECISION,
            network_fee_lamports BIGINT,
            first_attempt_age_seconds DOUBLE PRECISION,
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
        "ALTER TABLE candidate_markout ADD COLUMN gross_pnl_bps DOUBLE PRECISION",
        "ALTER TABLE candidate_markout ADD COLUMN network_fee_lamports BIGINT",
        "ALTER TABLE candidate_markout ADD COLUMN first_attempt_age_seconds DOUBLE PRECISION",
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
        # Estimated Solana network cost per transaction (base signature fee +
        # priority fee / Jito tip), charged on the buy and on the sell. The
        # default (5,000 base + 500,000 priority = 0.000505 SOL per tx, ~252 bps
        # round trip on the 0.04 SOL paper notional) is a deliberately
        # conservative ASSUMPTION, not a measured figure. Token-account rent is
        # refundable on close and is not charged here.
        self.network_fee_lamports_per_tx = int(
            _env_float("MARKOUT_NETWORK_FEE_LAMPORTS_PER_TX", 505_000.0)
        )
        # Set when a quote returns 401/403 or a malformed-request 4xx: marking
        # results would be meaningless, so it is surfaced in degraded_reasons.
        self.last_config_error: Optional[str] = None

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

    def assumptions(self, notional_lamports: Optional[int] = None) -> dict[str, Any]:
        """Labeled cost assumptions behind every markout (shown in status and
        scorecards so nobody reads net P&L without knowing what it assumes)."""
        n = int(notional_lamports or int(_env_float("PAPER_NOTIONAL_LAMPORTS", 40_000_000)))
        fee = self.network_fee_lamports_per_tx
        return {
            "label": "ASSUMPTION (not measured): conservative estimate, set MARKOUT_NETWORK_FEE_LAMPORTS_PER_TX",
            "network_fee_lamports_per_tx": fee,
            "txs_charged": {"sold": 2, "unsellable": 1},
            "paper_notional_lamports": n,
            "roundtrip_network_fee_bps_at_notional": round(2 * fee / n * 10_000, 2) if n > 0 else None,
            "pnl_bps_is": "net of the network fee; gross_pnl_bps is stored per markout",
            "pretrade_roundtrip_bps_excludes_network_fee": True,
        }

    def net_pnl_bps(self, value_lamports: int, cost_lamports: int, sold: bool) -> tuple[float, float, int]:
        """
        Returns (net_pnl_bps, gross_pnl_bps, network_fee_lamports). The buy tx
        fee is always paid; the sell tx fee only when there was a sell.
        """
        fee = self.network_fee_lamports_per_tx * (2 if sold else 1)
        if cost_lamports <= 0:
            return -10_000.0, -10_000.0, fee
        gross = ((value_lamports / cost_lamports) - 1.0) * 10_000
        net = (((value_lamports - fee) / cost_lamports) - 1.0) * 10_000
        return net, gross, fee

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
                SELECT c.id, c.created_at_utc, c.entry_quote_at_utc, c.mint,
                       c.notional_lamports, c.buy_out_amount, c.market_phase
                FROM realtime_candidate c
                WHERE c.buy_out_amount IS NOT NULL
                  AND (c.episode_primary=1 OR c.firm_primary=1)
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
            # The markout clock starts at the entry quote (first executable
            # quote after the decision), not at row insert time.
            created = datetime.fromisoformat(
                str(row.get("entry_quote_at_utc") or row["created_at_utc"]).replace("Z", "+00:00")
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
                    quote_sell, str(row["mint"]), int(row["buy_out_amount"]),
                    entry_phase=row.get("market_phase") or None,
                )
                now = clock()
                age = now - created.timestamp()
                cost = int(row["notional_lamports"])
                first_no_route = st.get("first_no_route_age_seconds") if st else None
                if kind == NO_ROUTE and first_no_route is None:
                    first_no_route = age
                if kind == CONFIG_ERROR:
                    self.last_config_error = f"{utc_now()} {err}"[:300]
                first_attempt_age = (
                    float(st["first_attempt_age_seconds"])
                    if st and st.get("first_attempt_age_seconds") is not None else age
                )

                if kind == SOLD:
                    pnl_bps, gross, fee = self.net_pnl_bps(value, cost, True)
                    self._record_markout(cid, h, SOLD, value, pnl_bps, 1, age,
                                         gross_pnl_bps=gross, fee_lamports=fee,
                                         first_attempt_age=first_attempt_age)
                    self._finish_attempt(cid, h, DONE, st, age, kind, "", first_no_route)
                elif age >= deadline_age:
                    if first_no_route is not None:
                        # Confirmed unroutable on the right venue and never sold
                        # inside the window: book -100% (plus the buy tx fee) at
                        # the age it was first observed unsellable.
                        pnl_bps, gross, fee = self.net_pnl_bps(0, cost, False)
                        self._record_markout(cid, h, UNSELLABLE, 0, pnl_bps, 0, float(first_no_route),
                                             gross_pnl_bps=gross, fee_lamports=fee,
                                             first_attempt_age=first_attempt_age)
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

    def _record_markout(self, cid, h, status, value, pnl_bps, sellable, observed_age,
                        gross_pnl_bps=None, fee_lamports=None, first_attempt_age=None) -> None:
        lateness = float(observed_age) - h
        # Lateness is judged on when we FIRST tried this horizon (scheduling
        # delay), the same way for recoveries and for rugs; a retry that only
        # succeeds later must not be excluded while a persistent no-route at
        # the same horizon is included.
        judged = float(first_attempt_age) if first_attempt_age is not None else float(observed_age)
        late = 1 if (judged - h) > self.late_tolerance(h) else 0
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
                    observed_age_seconds, lateness_seconds, late, status,
                    gross_pnl_bps, network_fee_lamports, first_attempt_age_seconds
                ) VALUES (
                    :candidate_id, :horizon_seconds, :checked_at_utc,
                    :value_lamports, :pnl_bps, :sellable,
                    :age, :lateness, :late, :status,
                    :gross, :fee, :faa
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
                "gross": None if gross_pnl_bps is None else float(gross_pnl_bps),
                "fee": None if fee_lamports is None else int(fee_lamports),
                "faa": None if first_attempt_age is None else float(first_attempt_age),
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
