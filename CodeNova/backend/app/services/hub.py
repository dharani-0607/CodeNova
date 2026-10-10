"""WebSocket hub: pushes live events to connected dashboards.

Callable from sync request handlers (which run in a thread pool) and from async code.
"""
import asyncio
import json
import logging

from fastapi import WebSocket

from ..models import STAFF_ROLES

log = logging.getLogger(__name__)


class Hub:
    def __init__(self) -> None:
        self._clients: dict[WebSocket, str] = {}  # socket -> role
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, ws: WebSocket, role: str) -> None:
        await ws.accept()
        self._clients[ws] = role

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.pop(ws, None)

    @property
    def online(self) -> int:
        return len(self._clients)

    async def _send_all(self, text: str, audience: str) -> None:
        dead = []
        for ws, role in list(self._clients.items()):
            if audience == "staff" and role not in STAFF_ROLES:
                continue
            try:
                await ws.send_text(text)
            except Exception:  # noqa: BLE001 - a dropped socket must not stop the broadcast
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def publish(self, msg_type: str, data: dict, audience: str = "all") -> None:
        """Thread-safe fire-and-forget broadcast. audience: 'all' or 'staff'."""
        if self._loop is None or not self._clients:
            return
        text = json.dumps({"type": msg_type, "data": data}, default=str)
        try:
            asyncio.run_coroutine_threadsafe(self._send_all(text, audience), self._loop)
        except RuntimeError:
            log.debug("Event loop not running; dropped %s", msg_type)


hub = Hub()
