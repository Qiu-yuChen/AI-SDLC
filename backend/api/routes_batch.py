"""Batch Management REST API"""
import uuid
import json
import os
import traceback
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from pydantic import BaseModel

from config import DOCS_INPUT, DOCS_OUTPUT, SRC_OUTPUT, TEST_OUTPUT
from orchestrator.state_manager import StateManager, NODE_ORDER
from orchestrator.engine import OrchestratorEngine

router = APIRouter(tags=["batches"])


def _run_batch_pipeline(batch_id: str):
    """Run the long CrewAI pipeline without streaming noisy model logs to console."""
    sm = StateManager(batch_id)
    try:
        with open(os.devnull, "w", encoding="utf-8", errors="ignore") as sink:
            with redirect_stdout(sink), redirect_stderr(sink):
                OrchestratorEngine(batch_id).run_auto()
    except Exception as exc:
        sm.update_node(sm.get_current_node() or NODE_ORDER[0], "failed", error=str(exc))
        sm.append_log({
            "event": "pipeline_background_failed",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })


# ── Schemas ──────────────────────────────────────────────

class BatchCreateRequest(BaseModel):
    spec_filename: str  # 已上传的规格书文件名
    project_name: str = "未命名项目"

class BatchResponse(BaseModel):
    batch_id: str
    project_name: str
    spec_file: str
    status: str
    current_node: Optional[str]
    nodes: dict
    created_at: str

class NodeActionRequest(BaseModel):
    batch_id: str


# ── Routes ────────────────────────────────────────────────

@router.post("/batches")
async def create_batch(req: BatchCreateRequest, background_tasks: BackgroundTasks):
    """创建新批次"""
    spec_path = DOCS_INPUT / req.spec_filename
    if not spec_path.exists():
        raise HTTPException(404, f"规格说明书不存在: {req.spec_filename}")

    batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    sm = StateManager(batch_id)
    sm.init_batch(
        project_name=req.project_name,
        spec_file=req.spec_filename,
    )

    return {
        "batch_id": batch_id,
        "status": "created",
        "spec_file": req.spec_filename,
    }


@router.get("/batches")
async def list_batches():
    """列出所有批次"""
    batches = []
    if DOCS_OUTPUT.exists():
        for d in sorted(DOCS_OUTPUT.iterdir(), reverse=True):
            if not d.is_dir():
                continue

            sf = d / "batch_status.json"
            if not sf.exists():
                continue

            try:
                status = json.loads(sf.read_text(encoding="utf-8"))
            except Exception as exc:
                batches.append({
                    "batch_id": d.name,
                    "project_name": d.name,
                    "status": "failed",
                    "current_node": None,
                    "created_at": "",
                    "error": f"状态文件读取失败: {exc}",
                })
                continue

            batches.append({
                "batch_id": d.name,
                "project_name": status.get("project_name", ""),
                "status": status.get("status", "unknown"),
                "current_node": status.get("current_node"),
                "created_at": status.get("created_at", ""),
            })
    return sorted(batches, key=lambda x: x.get("created_at") or "", reverse=True)


@router.get("/batches/{batch_id}")
async def get_batch(batch_id: str):
    """获取批次详情"""
    sm = StateManager(batch_id)
    status = sm.load()
    if not status:
        raise HTTPException(404, "批次不存在")
    return status


@router.post("/batches/{batch_id}/start")
def start_batch(batch_id: str, background_tasks: BackgroundTasks):
    """启动自动执行：立即返回，流水线在后台运行。"""
    sm = StateManager(batch_id)
    status = sm.load()
    if not status:
        raise HTTPException(404, "批次不存在")
    if status.get("status") in ("running", "completed"):
        raise HTTPException(400, f"批次当前状态: {status.get('status')}")

    sm.update_node(NODE_ORDER[0], "running")
    sm.append_log({"event": "pipeline_queued", "mode": "auto"})
    background_tasks.add_task(_run_batch_pipeline, batch_id)
    return {"batch_id": batch_id, "status": "running"}


@router.post("/batches/{batch_id}/next")
async def execute_next_node(batch_id: str):
    """手动模式：执行下一个节点"""
    engine = OrchestratorEngine(batch_id)
    result = engine.run_manual_step()
    return result


@router.post("/batches/{batch_id}/retry/{node_id}")
async def retry_node(batch_id: str, node_id: str):
    """增量重试：重新执行指定节点"""
    engine = OrchestratorEngine(batch_id)
    result = engine.retry_node(node_id)
    return result


@router.post("/upload-spec")
async def upload_specification(file: UploadFile = File(...)):
    """上传产品规格说明书"""
    if not file.filename or not file.filename.endswith(".md"):
        raise HTTPException(400, "仅支持 .md 格式")

    content = await file.read()
    dest = DOCS_INPUT / file.filename
    dest.write_bytes(content)

    return {
        "filename": file.filename,
        "size": len(content),
        "path": str(dest.relative_to(DOCS_INPUT.parent.parent)),
    }


@router.get("/batches/{batch_id}/outputs/{node_id}")
async def get_node_outputs(batch_id: str, node_id: str):
    """获取某个节点的产出物文件列表"""
    batch_dir = DOCS_OUTPUT / batch_id
    node_dir = batch_dir / node_id
    if not node_dir.exists():
        return {"files": []}

    files = []
    for f in node_dir.rglob("*"):
        if f.is_file():
            files.append({
                "path": str(f.relative_to(batch_dir)),
                "size": f.stat().st_size,
                "name": f.name,
            })
    return {"files": sorted(files, key=lambda x: x["path"])}
