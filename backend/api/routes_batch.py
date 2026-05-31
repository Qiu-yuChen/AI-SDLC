"""Batch Management REST API"""
import asyncio
import io
import uuid
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import DOCS_INPUT, DOCS_OUTPUT, SRC_OUTPUT, TEST_OUTPUT
from orchestrator.state_manager import StateManager
from orchestrator.engine import OrchestratorEngine
from orchestrator.task_control import task_control

router = APIRouter(tags=["batches"])


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

class BatchResumeRequest(BaseModel):
    guidance: str = ""


SKIP_EXPORT_FILES = {"batch_status.json", "execution_log.json", ".gitkeep"}


def _safe_zip_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value)
    return safe.strip("._") or "artifacts"


def _iter_artifact_files(batch_dir: Path) -> list[Path]:
    """Return generated artifact files, excluding runtime metadata."""
    files = []
    for path in batch_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.name in SKIP_EXPORT_FILES or path.suffix == ".zip":
            continue
        if "__pycache__" in path.parts:
            continue
        files.append(path)
    return sorted(files, key=lambda p: str(p.relative_to(batch_dir)))


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
            if d.is_dir():
                sf = d / "batch_status.json"
                if sf.exists():
                    status = json.loads(sf.read_text(encoding="utf-8"))
                    batches.append({
                        "batch_id": d.name,
                        "project_name": status.get("project_name", ""),
                        "status": status.get("status", "unknown"),
                        "current_node": status.get("current_node"),
                        "created_at": status.get("created_at", ""),
                    })
    return batches


@router.get("/batches/{batch_id}")
async def get_batch(batch_id: str):
    """获取批次详情"""
    sm = StateManager(batch_id)
    status = sm.load()
    if not status:
        raise HTTPException(404, "批次不存在")
    return status


@router.post("/batches/{batch_id}/start")
async def start_batch(batch_id: str):
    """启动自动执行（后台线程运行，立即返回）"""
    sm = StateManager(batch_id)
    status = sm.load()
    if not status:
        raise HTTPException(404, "批次不存在")
    if status.get("status") in ("running", "completed", "stopped"):
        raise HTTPException(400, f"批次当前状态: {status.get('status')}")

    if task_control.is_active(batch_id):
        raise HTTPException(409, "批次仍在运行中")

    stop_event = task_control.start(batch_id)
    engine = OrchestratorEngine(batch_id, stop_event=stop_event)
    engine.set_loop(asyncio.get_running_loop())
    asyncio.create_task(asyncio.to_thread(engine.run_auto))
    return {"batch_id": batch_id, "status": "running"}


@router.post("/batches/{batch_id}/stop")
async def stop_batch(batch_id: str):
    """Stop the current batch run."""
    sm = StateManager(batch_id)
    status = sm.load()
    if not status:
        raise HTTPException(404, "批次不存在")
    if status.get("status") not in ("created", "running"):
        return {"batch_id": batch_id, "status": status.get("status")}

    task_control.stop(batch_id)
    stopped = sm.stop_batch("用户手动停止生成")
    engine = OrchestratorEngine(batch_id)
    engine.set_loop(asyncio.get_running_loop())
    engine._broadcast("batch_stopped", {
        "node_id": stopped.get("current_node"),
        "name": stopped.get("current_node"),
        "message": "用户手动停止生成",
    })
    return {"batch_id": batch_id, "status": "stopped"}


@router.post("/batches/{batch_id}/resume")
async def resume_batch(batch_id: str, req: BatchResumeRequest):
    """Resume a stopped batch from the first unfinished node."""
    sm = StateManager(batch_id)
    status = sm.load()
    if not status:
        raise HTTPException(404, "批次不存在")
    if task_control.is_active(batch_id):
        raise HTTPException(409, "批次仍在停止中，请稍后继续")
    if status.get("status") not in ("stopped", "failed", "created"):
        raise HTTPException(400, f"当前状态不支持继续: {status.get('status')}")

    sm.resume_batch(req.guidance)
    stop_event = task_control.start(batch_id)
    engine = OrchestratorEngine(batch_id, stop_event=stop_event)
    engine.set_loop(asyncio.get_running_loop())
    engine._broadcast("batch_resumed", {
        "message": "继续执行生成任务",
        "guidance": req.guidance,
    })
    asyncio.create_task(asyncio.to_thread(engine.run_auto))
    return {"batch_id": batch_id, "status": "running"}


@router.post("/batches/{batch_id}/next")
async def execute_next_node(batch_id: str):
    """手动模式：执行下一个节点"""
    engine = OrchestratorEngine(batch_id)
    engine.set_loop(asyncio.get_running_loop())
    result = await asyncio.to_thread(engine.run_manual_step)
    return result


@router.post("/batches/{batch_id}/retry/{node_id}")
async def retry_node(batch_id: str, node_id: str):
    """增量重试：重新执行指定节点"""
    engine = OrchestratorEngine(batch_id)
    engine.set_loop(asyncio.get_running_loop())
    result = await asyncio.to_thread(engine.retry_node, node_id)
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


@router.get("/batches/{batch_id}/artifacts")
async def get_batch_artifacts(batch_id: str):
    """Get a visualizable summary of all generated artifacts for a batch."""
    sm = StateManager(batch_id)
    status = sm.load()
    if not status:
        raise HTTPException(404, "批次不存在")

    batch_dir = DOCS_OUTPUT / batch_id
    if not batch_dir.exists():
        raise HTTPException(404, "产物目录不存在")

    grouped: dict[str, dict] = {}
    total_size = 0
    for file_path in _iter_artifact_files(batch_dir):
        rel = file_path.relative_to(batch_dir)
        parts = rel.parts
        group_id = parts[0] if parts else "产物"
        stat = file_path.stat()
        total_size += stat.st_size
        group = grouped.setdefault(
            group_id,
            {
                "node_id": group_id,
                "count": 0,
                "size": 0,
                "files": [],
            },
        )
        group["count"] += 1
        group["size"] += stat.st_size
        group["files"].append({
            "path": str(rel),
            "name": file_path.name,
            "size": stat.st_size,
        })

    groups = sorted(grouped.values(), key=lambda item: item["node_id"])
    return {
        "batch_id": batch_id,
        "project_name": status.get("project_name", ""),
        "status": status.get("status", "unknown"),
        "total_files": sum(group["count"] for group in groups),
        "total_size": total_size,
        "groups": groups,
    }


@router.get("/batches/{batch_id}/export")
async def export_batch_artifacts(batch_id: str):
    """Download all generated artifacts as one ZIP file."""
    sm = StateManager(batch_id)
    status = sm.load()
    if not status:
        raise HTTPException(404, "批次不存在")

    batch_dir = DOCS_OUTPUT / batch_id
    if not batch_dir.exists():
        raise HTTPException(404, "产物目录不存在")

    files = _iter_artifact_files(batch_dir)
    if not files:
        raise HTTPException(404, "暂无可导出的产物")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        manifest = {
            "batch_id": batch_id,
            "project_name": status.get("project_name", ""),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "file_count": len(files),
            "files": [str(path.relative_to(batch_dir)) for path in files],
        }
        zf.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
        for file_path in files:
            zf.write(file_path, arcname=str(file_path.relative_to(batch_dir)))

    buffer.seek(0)
    display_name = f"{_safe_zip_name(status.get('project_name') or batch_id)}_{batch_id}_artifacts.zip"
    ascii_filename = f"{batch_id}_artifacts.zip"
    encoded_filename = quote(display_name)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename={ascii_filename}; "
                f"filename*=UTF-8''{encoded_filename}"
            )
        },
    )
