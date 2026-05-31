"""Batch Management REST API"""
import asyncio
import io
import json
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from config import DOCS_INPUT, DOCS_OUTPUT, SRC_OUTPUT, TEST_OUTPUT
from orchestrator.state_manager import StateManager
from orchestrator.engine import OrchestratorEngine
from orchestrator.task_control import task_control
from tools.document_tools import parse_document, get_file_type, SUPPORTED_EXTENSIONS

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
    poster_path = DOCS_OUTPUT / batch_id / "交付海报" / "poster.png"
    status["has_poster"] = poster_path.exists()
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


@router.post("/batches/{batch_id}/rollback/{node_id}")
async def rollback_node(batch_id: str, node_id: str):
    """回退到指定节点：重置该节点及后续所有节点，从该节点重新执行"""
    engine = OrchestratorEngine(batch_id)
    engine.set_loop(asyncio.get_running_loop())
    result = await asyncio.to_thread(engine.rollback_and_run, node_id)
    return result


@router.post("/upload-spec")
async def upload_specification(file: UploadFile = File(...)):
    """上传产品规格说明书（支持 15+ 格式，非 .md 自动解析 + AI 预处理）"""
    if not file.filename:
        raise HTTPException(400, "文件名不能为空")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(SUPPORTED_EXTENSIONS.keys())
        raise HTTPException(400, f"不支持的文件格式，仅支持: {allowed}")

    content = await file.read()
    original_dest = DOCS_INPUT / file.filename
    original_dest.write_bytes(content)

    if ext == ".md":
        return {
            "filename": file.filename,
            "size": len(content),
            "path": str(original_dest.relative_to(DOCS_INPUT.parent.parent)),
            "file_type": "markdown",
            "preprocessed": False,
        }

    # 非 .md → 解析 + AI 预处理
    file_type = get_file_type(file.filename)
    md_filename = Path(file.filename).stem + ".md"
    md_dest = DOCS_INPUT / md_filename

    parsed = parse_document(str(original_dest))
    if "error" in parsed and not parsed.get("raw"):
        raise HTTPException(500, f"文档解析失败: {parsed['error']}")

    from agents.spec_preprocessor import preprocess_document
    spec_md = preprocess_document(
        file_path=str(original_dest),
        file_type=file_type,
        doc_title=parsed.get("title", Path(file.filename).stem),
        raw_content=parsed.get("raw", ""),
    )
    md_dest.write_text(spec_md, encoding="utf-8")

    return {
        "filename": md_filename,
        "original_filename": file.filename,
        "size": len(spec_md.encode("utf-8")),
        "path": str(md_dest.relative_to(DOCS_INPUT.parent.parent)),
        "file_type": file_type,
        "preprocessed": True,
        "parsed_info": {
            "title": parsed.get("title"),
            "slide_count": parsed.get("slide_count"),
            "paragraph_count": parsed.get("paragraph_count"),
            "table_count": parsed.get("table_count"),
        },
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


@router.delete("/batches/{batch_id}")
async def delete_batch(batch_id: str):
    """删除批次及其所有产物"""
    sm = StateManager(batch_id)
    if not sm.load():
        raise HTTPException(404, "批次不存在")
    batch_dir = DOCS_OUTPUT / batch_id
    if batch_dir.exists():
        shutil.rmtree(batch_dir)
    return {"batch_id": batch_id, "status": "deleted"}


@router.post("/batches/{batch_id}/archive")
async def archive_batch(batch_id: str):
    """归档批次（标记为 archived，不从磁盘删除）"""
    sm = StateManager(batch_id)
    status = sm.load()
    if not status:
        raise HTTPException(404, "批次不存在")
    status["archived"] = True
    status["updated_at"] = datetime.now(timezone.utc).isoformat()
    sm._write_status(status)
    return {"batch_id": batch_id, "status": "archived"}


# ── ZIP Export ───────────────────────────────────────────

SKIP_EXPORT_FILES = {"batch_status.json", "execution_log.json", ".gitkeep"}


def _safe_zip_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value)
    return safe.strip("._") or "artifacts"


def _iter_artifact_files(batch_dir: Path) -> list:
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


@router.get("/batches/{batch_id}/artifacts")
async def get_batch_artifacts(batch_id: str):
    """获取批次产物清单（按节点分组）"""
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
        group = grouped.setdefault(group_id, {
            "node_id": group_id, "count": 0, "size": 0, "files": [],
        })
        group["count"] += 1
        group["size"] += stat.st_size
        group["files"].append({
            "path": str(rel), "name": file_path.name, "size": stat.st_size,
        })

    groups = sorted(grouped.values(), key=lambda item: item["node_id"])
    return {
        "batch_id": batch_id,
        "project_name": status.get("project_name", ""),
        "status": status.get("status", "unknown"),
        "total_files": sum(g["count"] for g in groups),
        "total_size": total_size,
        "groups": groups,
    }


@router.get("/batches/{batch_id}/export")
async def export_batch_artifacts(batch_id: str):
    """一键下载所有产物为 ZIP"""
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
            "files": [str(p.relative_to(batch_dir)) for p in files],
        }
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
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
            ),
        },
    )


@router.get("/batches/{batch_id}/poster")
async def get_poster(batch_id: str):
    """获取交付海报图片"""
    from pathlib import Path as P
    poster_dir = DOCS_OUTPUT / batch_id / "交付海报"
    if not poster_dir.exists():
        raise HTTPException(404, "海报尚未生成")
    poster_path = poster_dir / "poster.png"
    if not poster_path.exists():
        raise HTTPException(404, "海报文件不存在")
    return FileResponse(
        str(poster_path),
        media_type="image/png",
        filename=f"{batch_id}_poster.png",
    )


@router.get("/batches/{batch_id}/file/{file_path:path}")
async def get_batch_file(batch_id: str, file_path: str):
    """获取批次内任意文件（解决中文路径问题）"""
    full_path = DOCS_OUTPUT / batch_id / file_path
    if not full_path.exists():
        raise HTTPException(404, "文件不存在")
    if not str(full_path).startswith(str(DOCS_OUTPUT / batch_id)):
        raise HTTPException(403, "无权访问")
    import mimetypes
    mime, _ = mimetypes.guess_type(str(full_path))
    return FileResponse(str(full_path), media_type=mime or "application/octet-stream")
