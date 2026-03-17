from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def new_id() -> str:
    return str(uuid4())


def dedupe_segments(segments: list[str]) -> list[str]:
    """Remove duplicate segments while preserving order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for segment in segments:
        value = segment.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
