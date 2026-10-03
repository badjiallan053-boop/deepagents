from __future__ import annotations

import math
import random
import statistics
from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class Scorecard:
    n: int
    mean_bps: float | None
    median_bps: float | None
    positive_rate: float | None
    profit_factor: float | None
    large_loss_rate: float | None
    bootstrap_mean_lower_95_bps: float | None
    status: str
    # True when there were no losing outcomes: profit_factor is then reported
    # as PROFIT_FACTOR_CAP instead of inf so the card stays JSON-serializable.
    profit_factor_capped: bool = False

    def to_dict(self):
        return asdict(self)


# Same convention as grok_team's compact stats; a JSON-safe stand-in for inf.
PROFIT_FACTOR_CAP = 999.0


def _profit_factor(values: list[float]) -> float | None:
    gross_profit = sum(v for v in values if v > 0)
    gross_loss = abs(sum(v for v in values if v < 0))
    if gross_loss == 0:
        return math.inf if gross_profit > 0 else None
    return gross_profit / gross_loss


def _bootstrap_lower(values: list[float], *, samples: int = 2000, seed: int = 1337) -> float | None:
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    means = []
    n = len(values)
    for _ in range(samples):
        draw = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(draw) / n)
    means.sort()
    idx = max(0, min(len(means) - 1, int(0.025 * (len(means) - 1))))
    return means[idx]


def evaluate_outcomes(
    outcomes_bps: Iterable[float],
    *,
    min_samples: int = 20,
    min_profit_factor: float = 1.30,
    require_positive_ci: bool = True,
    large_loss_threshold_bps: float = -2000.0,
) -> Scorecard:
    values = [float(v) for v in outcomes_bps]
    if not values:
        return Scorecard(0, None, None, None, None, None, None, "NO_DATA")

    pf = _profit_factor(values)
    pf_capped = pf is not None and (math.isinf(pf) or pf > PROFIT_FACTOR_CAP)
    lower = _bootstrap_lower(values)
    n = len(values)
    positive_rate = sum(1 for v in values if v > 0) / n
    large_loss_rate = sum(1 for v in values if v <= large_loss_threshold_bps) / n

    passed = (
        n >= min_samples
        and pf is not None
        and pf > min_profit_factor
        and (not require_positive_ci or (lower is not None and lower > 0))
    )

    if passed:
        status = "PROMOTE"
    elif n < min_samples:
        status = "COLLECT"
    else:
        status = "REJECT_OR_REWORK"

    return Scorecard(
        n=n,
        mean_bps=sum(values) / n,
        median_bps=statistics.median(values),
        positive_rate=positive_rate,
        profit_factor=PROFIT_FACTOR_CAP if pf_capped else pf,
        large_loss_rate=large_loss_rate,
        bootstrap_mean_lower_95_bps=lower,
        status=status,
        profit_factor_capped=pf_capped,
    )
