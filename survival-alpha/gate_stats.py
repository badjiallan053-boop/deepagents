"""
Shared gate statistics for every Survival Alpha desk (paper research only).

One helper so that "n >= 30 / 300, PF > 1.30, 95% lower bound > 0, nothing
dominating" means the same thing on every scorecard (Risk red-team X4, N1-3).

* Samples are clustered (token, deal, symbol-week, UTC day, ...). The unit of
  evidence is the CLUSTER, not the row: min-n gates count clusters, and the
  lower bound comes from a cluster (block) bootstrap that resamples whole
  clusters. Without cluster ids every row is its own cluster (iid bootstrap).
* Profit factor is capped (PF_CAP) and flagged, so it stays JSON-safe.
* Dominance check: PF and mean are recomputed without the single best cluster;
  a card whose edge disappears without one token/day is not a candidate.
* Exclusions (failed/late/missed marks, unresolved deals) are reported and a
  rate above max_exclusion_rate turns the status into DATA_QUALITY.

Statuses: NO_DATA, COLLECT (clusters < min_n_research), DATA_QUALITY,
REJECT_OR_REWORK, DOMINATED, RESEARCH_CANDIDATE (>= min_n_research clusters,
PF > threshold, cluster LB > 0, not dominated), GATE4_ELIGIBLE (same with
>= min_n_gate clusters). Multiple-testing control across buckets is NOT done
here; callers comparing many buckets must pre-register a primary bucket or
apply Holm.
"""
from __future__ import annotations

import math
import random
import statistics
from datetime import datetime, timezone
from typing import Any, Hashable, Iterable, Optional, Sequence

PF_CAP = 999.0
MIN_N_RESEARCH = 30   # MASTER_PLAYBOOK §18 promoted research
MIN_N_GATE = 300      # MASTER_PLAYBOOK Gate 4
PF_THRESHOLD = 1.30
MAX_EXCLUSION_RATE = 0.05


def capped_profit_factor(values: Sequence[float], cap: float = PF_CAP) -> tuple[Optional[float], bool]:
    """(profit_factor, capped). None when there are no wins and no losses."""
    wins = sum(v for v in values if v > 0)
    losses = -sum(v for v in values if v < 0)
    if losses <= 0:
        return (cap, True) if wins > 0 else (None, False)
    pf = wins / losses
    return (min(pf, cap), pf > cap)


def utc_day(ts: Any) -> str:
    """Cluster key helper: UTC calendar day of an ISO timestamp / epoch seconds."""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(float(ts), timezone.utc).date().isoformat()
    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date().isoformat()


def iso_week(ts: Any) -> str:
    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    y, w, _ = dt.astimezone(timezone.utc).isocalendar()
    return f"{y}-W{w:02d}"


def _group(values: Sequence[float], cluster_ids: Optional[Sequence[Hashable]]) -> list[list[float]]:
    if cluster_ids is None:
        return [[v] for v in values]
    if len(cluster_ids) != len(values):
        raise ValueError("cluster_ids must align with outcomes")
    groups: dict[Hashable, list[float]] = {}
    for v, c in zip(values, cluster_ids):
        groups.setdefault(c, []).append(v)
    return list(groups.values())


def cluster_bootstrap_lower(groups: list[list[float]], *, resamples: int = 2000, seed: int = 1337,
                            alpha: float = 0.05) -> Optional[float]:
    """Lower (alpha/2) percentile of the pooled mean when whole clusters are
    resampled with replacement."""
    k = len(groups)
    if k < 2:
        return None
    rng = random.Random(seed)
    sums = [sum(g) for g in groups]
    sizes = [len(g) for g in groups]
    means = []
    for _ in range(resamples):
        s = n = 0
        for _ in range(k):
            j = rng.randrange(k)
            s += sums[j]
            n += sizes[j]
        means.append(s / n)
    means.sort()
    return means[max(0, min(resamples - 1, int((alpha / 2) * (resamples - 1))))]


def gate_stats(
    outcomes: Iterable[float],
    cluster_ids: Optional[Sequence[Hashable]] = None,
    *,
    min_n_research: int = MIN_N_RESEARCH,
    min_n_gate: int = MIN_N_GATE,
    pf_threshold: float = PF_THRESHOLD,
    pf_cap: float = PF_CAP,
    exclusions: Optional[dict[str, int]] = None,
    max_exclusion_rate: float = MAX_EXCLUSION_RATE,
    resamples: int = 2000,
    seed: int = 1337,
) -> dict[str, Any]:
    values = [float(v) for v in outcomes]
    ids = list(cluster_ids) if cluster_ids is not None else None
    excl = {k: int(v) for k, v in (exclusions or {}).items() if v}
    n_excl = sum(excl.values())
    out: dict[str, Any] = {
        "n": len(values), "n_clusters": 0, "mean_bps": None, "median_bps": None, "hit_rate": None,
        "profit_factor": None, "profit_factor_capped": False,
        "cluster_bootstrap_mean_lower95_bps": None, "iid_bootstrap_mean_lower95_bps": None,
        "pf_without_top_cluster": None, "mean_without_top_cluster_bps": None, "top_cluster_profit_share": None,
        "n_excluded_by_reason": excl,
        "exclusion_rate": (n_excl / (n_excl + len(values))) if (n_excl + len(values)) else None,
        "min_n_research": min_n_research, "min_n_gate": min_n_gate, "pf_threshold": pf_threshold,
        "clustered": ids is not None, "status": "NO_DATA",
    }
    if not values:
        return out
    groups = _group(values, ids)
    k = len(groups)
    pf, capped = capped_profit_factor(values, pf_cap)
    lb = cluster_bootstrap_lower(groups, resamples=resamples, seed=seed)
    iid = cluster_bootstrap_lower([[v] for v in values], resamples=resamples, seed=seed)
    # dominance: drop the single best cluster by total P&L
    top = max(range(k), key=lambda j: sum(groups[j]))
    rest = [v for j, g in enumerate(groups) if j != top for v in g]
    gross_profit = sum(v for v in values if v > 0)
    top_profit = sum(v for v in groups[top] if v > 0)
    pf_rest, _ = capped_profit_factor(rest, pf_cap) if rest else (None, False)
    out.update(
        n_clusters=k, mean_bps=sum(values) / len(values), median_bps=statistics.median(values),
        hit_rate=sum(1 for v in values if v > 0) / len(values),
        profit_factor=pf, profit_factor_capped=capped,
        cluster_bootstrap_mean_lower95_bps=lb, iid_bootstrap_mean_lower95_bps=iid,
        pf_without_top_cluster=pf_rest,
        mean_without_top_cluster_bps=(sum(rest) / len(rest)) if rest else None,
        top_cluster_profit_share=(top_profit / gross_profit) if gross_profit > 0 else None,
    )
    passes = pf is not None and pf > pf_threshold and lb is not None and lb > 0
    dominated = passes and (pf_rest is None or pf_rest <= pf_threshold or
                            (out["mean_without_top_cluster_bps"] or 0) <= 0)
    if out["exclusion_rate"] is not None and out["exclusion_rate"] > max_exclusion_rate:
        status = "DATA_QUALITY"
    elif k < min_n_research:
        status = "COLLECT"
    elif not passes:
        status = "REJECT_OR_REWORK"
    elif dominated:
        status = "DOMINATED"
    elif k >= min_n_gate:
        status = "GATE4_ELIGIBLE"
    else:
        status = "RESEARCH_CANDIDATE"
    out["status"] = status
    if math.isnan(out["mean_bps"]):  # defensive; never expected
        out["status"] = "DATA_QUALITY"
    return out
