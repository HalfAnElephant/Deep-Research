from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def new_id() -> str:
    return str(uuid4())
