from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket

from app.core.utils import now_iso
from app.models.schemas import ProgressEvent


class ProgressHub:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[task_id].add(websocket)

    async def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[task_id].discard(websocket)

    async def emit(self, task_id: str, event: str, data: dict) -> None:
        payload = ProgressEvent(event=event, timestamp=now_iso(), data=data).model_dump()
        stale: list[WebSocket] = []
        async with self._lock:
            sockets = list(self._connections.get(task_id, set()))
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        if stale:
            async with self._lock:
                for ws in stale:
                    self._connections[task_id].discard(ws)
