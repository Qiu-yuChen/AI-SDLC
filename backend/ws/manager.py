"""WebSocket Connection Manager"""
import asyncio
import json
from typing import Dict, List
from fastapi import WebSocket


class WebSocketManager:
    """Manages WebSocket connections grouped by batch_id"""

    def __init__(self):
        # {batch_id: [WebSocket, ...]}
        self.connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, batch_id: str, websocket: WebSocket):
        await websocket.accept()
        if batch_id not in self.connections:
            self.connections[batch_id] = []
        self.connections[batch_id].append(websocket)

    def disconnect(self, batch_id: str, websocket: WebSocket):
        if batch_id in self.connections:
            self.connections[batch_id] = [
                ws for ws in self.connections[batch_id] if ws != websocket
            ]
            if not self.connections[batch_id]:
                del self.connections[batch_id]

    async def broadcast(self, batch_id: str, event: dict):
        """Push event to all WebSocket clients watching this batch"""
        if batch_id not in self.connections:
            return
        message = json.dumps(event, ensure_ascii=False, default=str)
        disconnected = []
        for ws in self.connections[batch_id]:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(batch_id, ws)


# Singleton
ws_manager = WebSocketManager()
