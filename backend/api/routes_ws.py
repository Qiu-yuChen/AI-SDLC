"""WebSocket Routes for Real-time Progress Streaming"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ws.manager import ws_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/batch/{batch_id}/stream")
async def batch_stream(websocket: WebSocket, batch_id: str):
    """实时批次执行流 — 推送节点状态、ReAct步骤、日志"""
    await ws_manager.connect(batch_id, websocket)
    try:
        while True:
            # Keep connection alive, wait for messages from orchestrator
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(batch_id, websocket)
    except Exception:
        ws_manager.disconnect(batch_id, websocket)
