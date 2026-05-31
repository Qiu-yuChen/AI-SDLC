"""State Manager — JSON-based batch/node state persistence"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from config import DOCS_OUTPUT, DOCS_INPUT

NODE_ORDER = ["概要设计", "代码生成", "单元测试", "质量评分"]
NODE_NAMES = {
    "概要设计": "概要设计",
    "代码生成": "代码生成",
    "单元测试": "单元测试",
    "质量评分": "质量评分",
}


class StateManager:
    """Read/write batch and node states as JSON files"""

    def __init__(self, batch_id: str):
        self.batch_id = batch_id
        self.batch_dir = DOCS_OUTPUT / batch_id
        self.status_file = self.batch_dir / "batch_status.json"
        self.log_file = self.batch_dir / "execution_log.json"

    def init_batch(self, project_name: str, spec_file: str) -> dict:
        """Initialize a new batch with empty node states"""
        self.batch_dir.mkdir(parents=True, exist_ok=True)
        for node in NODE_ORDER:
            (self.batch_dir / node).mkdir(parents=True, exist_ok=True)

        status = {
            "batch_id": self.batch_id,
            "project_name": project_name,
            "spec_file": spec_file,
            "status": "created",     # created | running | completed | failed | stopped
            "current_node": None,
            "mode": "auto",          # auto | manual
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "nodes": {
                node: {
                    "node_id": node,
                    "name": NODE_NAMES[node],
                    "status": "pending",  # pending | running | completed | failed | stopped
                    "started_at": None,
                    "finished_at": None,
                    "duration_seconds": None,
                    "error": None,
                    "quality_score": None,
                    "output_files": [],
                }
                for node in NODE_ORDER
            },
        }
        self._write_status(status)
        self._init_log()
        return status

    def load(self) -> Optional[dict]:
        """Load current batch status"""
        if not self.status_file.exists():
            return None
        return json.loads(self.status_file.read_text(encoding="utf-8"))

    def update_node(
        self,
        node_id: str,
        status: str,
        output_files: list = None,
        error: str = None,
        quality_score: float = None,
    ):
        """Update a single node's state"""
        batch = self.load()
        if not batch:
            return

        now = datetime.now(timezone.utc).isoformat()
        node = batch["nodes"][node_id]
        node["status"] = status
        node["updated_at"] = now

        if status == "running":
            node["started_at"] = now
            batch["status"] = "running"
            batch["current_node"] = node_id

        elif status == "completed":
            node["finished_at"] = now
            if node["started_at"]:
                start = datetime.fromisoformat(node["started_at"])
                end = datetime.fromisoformat(now)
                node["duration_seconds"] = (end - start).total_seconds()
            if output_files:
                node["output_files"] = output_files
            if quality_score is not None:
                node["quality_score"] = quality_score
            # Advance to next node or mark completed
            next_idx = NODE_ORDER.index(node_id) + 1
            if next_idx < len(NODE_ORDER):
                batch["current_node"] = NODE_ORDER[next_idx]
            else:
                batch["status"] = "completed"
                batch["current_node"] = None

        elif status == "failed":
            node["finished_at"] = now
            if error:
                node["error"] = error
            batch["status"] = "failed"

        elif status == "stopped":
            node["finished_at"] = now
            if error:
                node["error"] = error
            batch["status"] = "stopped"
            batch["current_node"] = node_id

        batch["updated_at"] = now
        self._write_status(batch)

    def append_log(self, entry: dict):
        """Append an entry to execution_log.json"""
        logs = self._read_log()
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        logs.append(entry)
        self._write_log(logs)

    def stop_batch(self, reason: str = "Stopped by user") -> dict:
        """Mark the batch and its active node as stopped."""
        batch = self.load()
        if not batch:
            return {}
        now = datetime.now(timezone.utc).isoformat()
        current_node = batch.get("current_node") or self.get_current_node()
        if current_node and current_node in batch["nodes"]:
            node = batch["nodes"][current_node]
            if node["status"] in ("pending", "running", "stopped"):
                node["status"] = "stopped"
                node["finished_at"] = now
                node["updated_at"] = now
                node["error"] = reason
        batch["status"] = "stopped"
        batch["current_node"] = current_node
        batch["updated_at"] = now
        batch["stopped_at"] = now
        self._write_status(batch)
        return batch

    def resume_batch(self, guidance: str = "") -> dict:
        """Prepare a stopped batch to continue from the first unfinished node."""
        batch = self.load()
        if not batch:
            return {}
        spec_file = batch.get("spec_file", "")
        if guidance and spec_file:
            spec_path = DOCS_INPUT / spec_file
            if spec_path.exists():
                spec_path.write_text(
                    f"{spec_path.read_text(encoding='utf-8').strip()}\n\n## 补充指引\n\n{guidance}",
                    encoding="utf-8",
                )
        for node_id, node in batch.get("nodes", {}).items():
            if node.get("status") in ("stopped",):
                node["status"] = "pending"
                node["error"] = None
            if node.get("status") in ("running",):
                node["status"] = "stopped"
        batch["status"] = "created"
        batch["current_node"] = self._first_unfinished_node(batch)
        batch["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_status(batch)
        return batch

    def _first_unfinished_node(self, batch: dict) -> Optional[str]:
        for n in NODE_ORDER:
            node = batch.get("nodes", {}).get(n, {})
            if node.get("status") in ("pending", "stopped", "failed"):
                 return n
        return None

    def get_current_node(self) -> Optional[str]:
        """Get the next pending node"""
        batch = self.load()
        if not batch:
            return None
        for node in NODE_ORDER:
            status = batch.get("nodes", {}).get(node, {}).get("status", "completed")
            if status in ("pending", "running", "failed", "stopped"):
                return node
        return None
        """Get the next pending node"""
        batch = self.load()
        if not batch:
            return None
        # Return first non-completed node
        for node_id in NODE_ORDER:
            if batch["nodes"][node_id]["status"] != "completed":
                return node_id
        return None

    # ── Private helpers ──

    def _write_status(self, data: dict):
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        self.status_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def _init_log(self):
        self._write_log([])

    def _read_log(self) -> list:
        if not self.log_file.exists():
            return []
        return json.loads(self.log_file.read_text(encoding="utf-8"))

    def _write_log(self, entries: list):
        self.log_file.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
