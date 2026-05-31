"""Batch Management REST API"""
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from pydantic import BaseModel

from config import DOCS_INPUT, DOCS_OUTPUT, SRC_OUTPUT, TEST_OUTPUT
from orchestrator.state_manager import StateManager
from orchestrator.engine import OrchestratorEngine
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
                    status = json.loads(sf.read_text())
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
def start_batch(batch_id: str):
    """启动自动执行（同步端点，在新线程中执行避免事件循环冲突）"""
    import concurrent.futures

    sm = StateManager(batch_id)
    status = sm.load()
    if not status:
        raise HTTPException(404, "批次不存在")
    if status.get("status") in ("running", "completed"):
        raise HTTPException(400, f"批次当前状态: {status.get('status')}")

    def _run():
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())
        engine = OrchestratorEngine(batch_id)
        engine.run_auto()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        future.result(timeout=3600)

    return {"batch_id": batch_id, "status": "completed"}


@router.post("/batches/{batch_id}/next")
async def execute_next_node(batch_id: str):
    """手动模式：执行下一个节点"""
    def _run():
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())
        engine = OrchestratorEngine(batch_id)
        return engine.run_manual_step()

    loop = __import__('asyncio').get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return await loop.run_in_executor(executor, _run)


@router.post("/batches/{batch_id}/retry/{node_id}")
async def retry_node(batch_id: str, node_id: str):
    """增量重试：重新执行指定节点"""
    def _run():
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())
        engine = OrchestratorEngine(batch_id)
        return engine.retry_node(node_id)

    loop = __import__('asyncio').get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        result = await loop.run_in_executor(executor, _run)
    return result


@router.post("/batches/{batch_id}/stop")
async def stop_batch(batch_id: str):
    """手动停止批次"""
    sm = StateManager(batch_id)
    status = sm.load()
    if not status:
        raise HTTPException(404, "批次不存在")

    # Mark running nodes as failed
    for node_id, node in status.get("nodes", {}).items():
        if node.get("status") in ("running", "pending"):
            sm.update_node(node_id, "failed", error="用户手动停止")

    # Mark batch as failed
    status["status"] = "failed"
    status["updated_at"] = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
    sm._write_status(status)

    return {"batch_id": batch_id, "status": "stopped", "message": "批次已手动停止"}


@router.post("/upload-spec")
async def upload_specification(file: UploadFile = File(...)):
    """上传产品规格说明书（支持 .md / .docx / .pptx）

    - .md 文件：直接存储
    - .docx / .pptx 文件：自动解析 + AI 预处理 → 生成 .md 规格书
    """
    if not file.filename:
        raise HTTPException(400, "文件名不能为空")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(SUPPORTED_EXTENSIONS.keys())
        raise HTTPException(400, f"不支持的文件格式，仅支持: {allowed}")

    content = await file.read()

    # Save original file
    original_dest = DOCS_INPUT / file.filename
    original_dest.write_bytes(content)

    # If it's already markdown, return directly
    if ext == ".md":
        return {
            "filename": file.filename,
            "size": len(content),
            "path": str(original_dest.relative_to(DOCS_INPUT.parent.parent)),
            "file_type": "markdown",
            "preprocessed": False,
        }

    # ── For docx/pptx: parse → preprocess → generate .md ──
    file_type = get_file_type(file.filename)
    md_filename = Path(file.filename).stem + ".md"
    md_dest = DOCS_INPUT / md_filename

    # Step 1: Parse the document
    parsed = parse_document(str(original_dest))

    if "error" in parsed and not parsed.get("raw"):
        raise HTTPException(500, f"文档解析失败: {parsed['error']}")

    raw_content = parsed.get("raw", "")
    doc_title = parsed.get("title", Path(file.filename).stem)

    # Step 2: Use AI preprocessor to generate structured spec
    from agents.spec_preprocessor import preprocess_document
    spec_md = preprocess_document(
        file_path=str(original_dest),
        file_type=file_type,
        doc_title=doc_title,
        raw_content=raw_content,
    )

    # Step 3: Save the generated markdown
    md_dest.write_text(spec_md, encoding="utf-8")

    return {
        "filename": md_filename,
        "original_filename": file.filename,
        "size": len(spec_md.encode("utf-8")),
        "path": str(md_dest.relative_to(DOCS_INPUT.parent.parent)),
        "file_type": file_type,
        "preprocessed": True,
        "parsed_info": {
            "title": doc_title,
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
