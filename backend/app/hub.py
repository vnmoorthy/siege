"""WebSocket fan-out for the war room."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class Hub:
    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        if not self.clients:
            return
        data = json.dumps(payload, default=str)
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_text(data)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def emit(self, payload: dict[str, Any]) -> None:
        """Fire-and-forget from any coroutine or thread."""
        loop = self.loop or asyncio.get_event_loop()
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            asyncio.ensure_future(self.broadcast(payload))
        else:
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), loop)


HUB = Hub()
