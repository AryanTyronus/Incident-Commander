from __future__ import annotations

import json
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.events.model import IncidentEvent
from backend.app.events.publisher import event_publisher

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stream"])


class ConnectionManager:
    """Manages WebSocket connections for incident streams."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, incident_id: str) -> None:
        await websocket.accept()
        if incident_id not in self._connections:
            self._connections[incident_id] = []
        self._connections[incident_id].append(websocket)

    def disconnect(self, websocket: WebSocket, incident_id: str) -> None:
        if incident_id in self._connections:
            self._connections[incident_id] = [
                ws for ws in self._connections[incident_id] if ws != websocket
            ]

    async def broadcast(self, incident_id: str, event: IncidentEvent) -> None:
        if incident_id not in self._connections:
            return
        message = event.model_dump_json()
        dead = []
        for ws in self._connections[incident_id]:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections[incident_id] = [
                w for w in self._connections[incident_id] if w != ws
            ]


manager = ConnectionManager()


@router.websocket("/api/incidents/{incident_id}/stream")
async def incident_stream(websocket: WebSocket, incident_id: str) -> None:
    """WebSocket endpoint for real-time incident event streaming."""
    await manager.connect(websocket, incident_id)

    def on_event(event: IncidentEvent) -> None:
        """Callback for event publisher."""
        import asyncio

        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(manager.broadcast(incident_id, event))

    event_publisher.subscribe(UUID(incident_id), on_event)

    try:
        while True:
            data = await websocket.receive_text()
            # Client can send ping/pong or commands
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        event_publisher.unsubscribe(UUID(incident_id), on_event)
        manager.disconnect(websocket, incident_id)
