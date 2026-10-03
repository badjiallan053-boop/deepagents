from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Iterable

URL_RE = re.compile(r"https?://\\S+", re.I)
WS_RE = re.compile(r"\\s+")


def parse_utc(value: str) -> float:
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def content_fingerprint(text: str) -> str:
    # Remove URLs and collapse whitespace so copy/paste promotion clusters together.
    normalized = URL_RE.sub(" ", text.lower())
    normalized = WS_RE.sub(" ", normalized).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def source_weight(source: str) -> float:
    return {"x": 1.0, "reddit": 1.0}.get(source.lower(), 0.5)


def compute_features(events: Iterable[dict], now_ts: float) -> dict:
    rows = list(events)
    if not rows:
        return {
            "posts_5m": 0,
            "posts_prev_15m": 0,
            "unique_authors_5m": 0,
            "source_count_5m": 0,
            "duplicate_ratio_5m": 0.0,
            "new_account_share_5m": 0.0,
            "verified_share_5m": 0.0,
            "contract_present_share_5m": 0.0,
            "mention_acceleration": 0.0,
            "social_heat": 0.0,
            "manipulation_risk": 1.0,
            "social_candidate": False,
        }

    recent = []
    prev = []
    for r in rows:
        try:
            ts = parse_utc(r["published_at_utc"])
        except Exception:
            continue
        age = now_ts - ts
        if 0 <= age <= 300:
            recent.append(r)
        elif 300 < age <= 1200:
            prev.append(r)

    authors = {str(r.get("author_id") or "") for r in recent if r.get("author_id")}
    sources = {str(r.get("source") or "").lower() for r in recent}
    fps = [r.get("content_fingerprint") for r in recent if r.get("content_fingerprint")]
    counts = Counter(fps)
    duplicate_posts = sum(max(0, n - 1) for n in counts.values())
    duplicate_ratio = duplicate_posts / max(1, len(recent))

    new_accounts = 0
    verified = 0
    contract_present = 0
    weighted_engagement = 0.0
    for r in recent:
        age_days = r.get("author_age_days")
        if age_days is not None and float(age_days) < 30:
            new_accounts += 1
        if bool(r.get("is_verified")):
            verified += 1
        if bool(r.get("contract_present")):
            contract_present += 1
        eng = max(0.0, float(r.get("engagement_count") or 0))
        weighted_engagement += math.log1p(eng) * source_weight(str(r.get("source") or ""))

    recent_rate = len(recent) / 5.0
    prev_rate = len(prev) / 15.0
    acceleration = recent_rate / max(0.1, prev_rate)

    source_diversity = min(1.0, len(sources) / 2.0)
    author_diversity = min(1.0, len(authors) / 5.0)
    engagement_component = min(1.0, weighted_engagement / 25.0)
    contract_share = contract_present / max(1, len(recent))
    accel_component = min(1.0, max(0.0, math.log2(max(acceleration, 1.0))) / 3.0)

    social_heat = (
        0.30 * author_diversity
        + 0.20 * source_diversity
        + 0.20 * engagement_component
        + 0.15 * contract_share
        + 0.15 * accel_component
    )

    new_share = new_accounts / max(1, len(recent))
    verified_share = verified / max(1, len(recent))

    # Risk is intentionally dominated by duplication/concentration, not sentiment.
    concentration = 1.0 - author_diversity
    manipulation_risk = min(
        1.0,
        0.45 * duplicate_ratio
        + 0.30 * concentration
        + 0.20 * new_share
        + 0.05 * (1.0 - contract_share),
    )

    # Social can nominate a candidate only. It can never authorize a trade.
    candidate = (
        len(recent) >= 2
        and len(authors) >= 2
        and manipulation_risk < 0.70
        and social_heat >= 0.35
    )

    return {
        "posts_5m": len(recent),
        "posts_prev_15m": len(prev),
        "unique_authors_5m": len(authors),
        "source_count_5m": len(sources),
        "duplicate_ratio_5m": round(duplicate_ratio, 6),
        "new_account_share_5m": round(new_share, 6),
        "verified_share_5m": round(verified_share, 6),
        "contract_present_share_5m": round(contract_share, 6),
        "mention_acceleration": round(acceleration, 6),
        "social_heat": round(social_heat, 6),
        "manipulation_risk": round(manipulation_risk, 6),
        "social_candidate": candidate,
    }
