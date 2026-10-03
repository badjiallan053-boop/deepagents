from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable

BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
MINT_RE = re.compile(r"(?<![A-Za-z0-9])([1-9A-HJ-NP-Za-km-z]{32,44})(?![A-Za-z0-9])")
PUMP_URL_RE = re.compile(r"(?:pump\.fun/(?:coin|board)/)([1-9A-HJ-NP-Za-km-z]{32,44})", re.I)
DEX_URL_RE = re.compile(r"(?:dexscreener\.com/solana/)([1-9A-HJ-NP-Za-km-z]{32,44})", re.I)
CA_RE = re.compile(r"(?:\bCA\b|contract(?:\s+address)?|mint)\s*[:=\-]?\s*([1-9A-HJ-NP-Za-km-z]{32,44})", re.I)

BUY_WORDS = re.compile(r"\b(buy|entry|ape|call|gem|launch|send|long)\b", re.I)
SELL_WORDS = re.compile(r"\b(sell|exit|close|take\s*profit|tp\b)\b", re.I)
HOLD_WORDS = re.compile(r"\b(hold|holding|moonbag|runner)\b", re.I)


def _base58_decode(value: str) -> bytes:
    n = 0
    for ch in value:
        idx = BASE58.find(ch)
        if idx < 0:
            return b""
        n = n * 58 + idx
    raw = b"" if n == 0 else n.to_bytes((n.bit_length() + 7) // 8, "big")
    leading = len(value) - len(value.lstrip("1"))
    return b"\x00" * leading + raw


def is_solana_pubkey(value: str) -> bool:
    try:
        return len(_base58_decode(value)) == 32
    except Exception:
        return False


def content_fingerprint(text: str) -> str:
    normalized = re.sub(r"https?://\S+", " ", text.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TelegramCall:
    channel: str
    message_id: int
    published_at_utc: str
    mint: str
    call_type: str
    parse_confidence: float
    fingerprint: str
    source_url: str = ""

    def to_dict(self):
        return asdict(self)


def _call_type(text: str) -> str:
    if SELL_WORDS.search(text):
        return "SELL"
    if HOLD_WORDS.search(text):
        return "HOLD"
    if BUY_WORDS.search(text):
        return "BUY"
    return "MENTION"


def extract_mints(text: str) -> list[tuple[str, float]]:
    """
    Ordered candidates with parser confidence.
    Explicit CA/mint label > Pump URL > Dex URL > generic base58 token.
    """
    found: dict[str, float] = {}
    for pattern, confidence in (
        (CA_RE, 1.00),
        (PUMP_URL_RE, 0.98),
        (DEX_URL_RE, 0.95),
        (MINT_RE, 0.75),
    ):
        for m in pattern.finditer(text or ""):
            mint = m.group(1)
            if is_solana_pubkey(mint):
                found[mint] = max(found.get(mint, 0.0), confidence)
    return sorted(found.items(), key=lambda kv: -kv[1])


def parse_telegram_message(
    *,
    channel: str,
    message_id: int,
    published_at,
    text: str,
    source_url: str = "",
) -> list[TelegramCall]:
    if not text:
        return []
    if isinstance(published_at, datetime):
        dt = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
    elif isinstance(published_at, (int, float)):
        dt = datetime.fromtimestamp(float(published_at), tz=timezone.utc)
    else:
        s = str(published_at).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

    typ = _call_type(text)
    fp = content_fingerprint(text)
    calls = []
    for mint, conf in extract_mints(text):
        calls.append(TelegramCall(
            channel=channel,
            message_id=int(message_id),
            published_at_utc=dt.astimezone(timezone.utc).isoformat(),
            mint=mint,
            call_type=typ,
            parse_confidence=conf,
            fingerprint=fp,
            source_url=source_url,
        ))
    return calls
