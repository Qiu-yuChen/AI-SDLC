"""Orchestrator Engine - manages multi-agent pipeline execution."""

import asyncio
import threading
import traceback
from datetime import datetime, timezone
from typing import Optional

from .crew_factory import CREW_BUILDERS
from .state_manager import NODE_NAMES, NODE_ORDER, StateManager
from .task_control import StopRequested, task_control
from ws.manager import ws_manager


class OrchestratorEngine:
    """Core pipeline orchestrator with auto/manual/retry modes."""

    def __init__(self, batch_id: str, stop_event: Optional[threading.Event] = None):
        self.batch_id = batch_id
        self.sm = StateManager(batch_id)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event = stop_event

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def run_auto(self):
        """Execute unfinished nodes sequentially."""
        state = self.sm.load()
        if not state:
            raise ValueError(f"Batch {self.batch_id} not found")

        spec_file = state.get("spec_file")
        self.sm.append_log({"event": "pipeline_start", "mode": "auto"})

        try:
            for node_id in NODE_ORDER:
                state = self.sm.load() or {}
                node_state = state.get("nodes", {}).get(node_id, {})
                if node_state.get("status") == "completed":
                    continue
                self._ensure_not_stopped()
                self._execute_node(node_id, spec_file)
        except StopRequested as exc:
            current = self.sm.get_current_node()
            self.sm.stop_batch(str(exc))
            self.sm.append_log({
                "event": "pipeline_stopped",
                "node": current,
                "message": str(exc),
            })
            self._broadcast("batch_stopped", {
                "node_id": current,
                "name": NODE_NAMES.get(current, current),
                "message": str(exc),
            })
        except Exception as exc:
            self.sm.append_log({
                "event": "pipeline_halted",
                "node": self.sm.get_current_node(),
                "error": str(exc),
            })
        finally:
            final_state = self.sm.load() or {}
            self.sm.append_log({
                "event": "pipeline_end",
                "final_status": final_state.get("status"),
            })
            if self._stop_event:
                task_control.finish(self.batch_id, self._stop_event)

    def run_manual_step(self) -> dict:
        """Execute the next unfinished node."""
        node_id = self.sm.get_current_node()
        if not node_id:
            return {"status": "all_completed", "message": "所有节点已完成"}

        state = self.sm.load()
        spec_file = state.get("spec_file")
        self._ensure_not_stopped()
        self._execute_node(node_id, spec_file)

        return {
            "status": "completed",
            "node": node_id,
            "next": self.sm.get_current_node(),
        }

    def retry_node(self, node_id: str) -> dict:
        """Retry a failed or pending node."""
        state = self.sm.load()
        if node_id not in state["nodes"]:
            return {"status": "error", "message": f"Unknown node: {node_id}"}

        current_status = state["nodes"][node_id]["status"]
        if current_status not in ("failed", "pending", "stopped"):
            return {"status": "error", "message": f"Node {node_id} status is '{current_status}', not retryable"}

        spec_file = state.get("spec_file")
        self._ensure_not_stopped()
        self._execute_node(node_id, spec_file)

        return {"status": "completed", "node": node_id}

    def _execute_node(self, node_id: str, spec_file: str):
        """Execute a single agent node with state tracking and WS broadcast."""
        node_name = NODE_NAMES[node_id]
        self._ensure_not_stopped()

        self.sm.update_node(node_id, "running")
        self.sm.append_log({
            "event": "node_start",
            "node": node_id,
            "name": node_name,
        })
        self._broadcast("node_start", {"node_id": node_id, "name": node_name})
        self._emit_react_step(node_id, node_name, {
            "thought": f"{node_name} 已开始，正在准备任务上下文和可用工具。",
        })

        start = datetime.now(timezone.utc)

        try:
            if node_id == "质量评分":
                self._emit_react_step(node_id, node_name, {
                    "action": "run_quality_scoring",
                    "observation": "正在读取设计、代码和测试产物并计算质量评分。",
                })
                self._ensure_not_stopped()
                self._run_scoring()
                self._ensure_not_stopped()
                return

            builder = CREW_BUILDERS[node_id]
            if node_id == "概要设计":
                crew = builder(self.batch_id, spec_file, self._emit_react_step)
            else:
                crew = builder(self.batch_id, self._emit_react_step)

            self._ensure_not_stopped()
            self._emit_react_step(node_id, node_name, {
                "action": "crew.kickoff",
                "observation": "已提交给模型执行，等待模型规划、调用工具并返回阶段结果。",
            })
            crew_output = crew.kickoff(inputs={"batch_id": self.batch_id})
            self._ensure_not_stopped()

            _ = str(crew_output) if crew_output else ""
            duration = (datetime.now(timezone.utc) - start).total_seconds()

            from config import DOCS_OUTPUT
            node_dir = DOCS_OUTPUT / self.batch_id / node_id
            output_files = []
            if node_dir.exists():
                for f in node_dir.rglob("*"):
                    if f.is_file():
                        output_files.append(str(f.relative_to(DOCS_OUTPUT / self.batch_id)))

            self.sm.update_node(node_id, "completed", output_files=output_files)
            self.sm.append_log({
                "event": "node_completed",
                "node": node_id,
                "name": node_name,
                "duration_seconds": duration,
                "output_files": output_files,
            })
            self._broadcast("node_completed", {
                "node_id": node_id,
                "name": node_name,
                "duration_seconds": duration,
                "output_files": output_files,
            })

        except StopRequested as exc:
            self.sm.update_node(node_id, "stopped", error=str(exc))
            self.sm.append_log({
                "event": "node_stopped",
                "node": node_id,
                "name": node_name,
                "message": str(exc),
            })
            self._broadcast("node_stopped", {
                "node_id": node_id,
                "name": node_name,
                "message": str(exc),
            })
            raise
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {str(exc)}"
            trace = traceback.format_exc()

            self.sm.update_node(node_id, "failed", error=error_msg)
            self.sm.append_log({
                "event": "node_failed",
                "node": node_id,
                "name": node_name,
                "error": error_msg,
                "traceback": trace,
            })
            self._broadcast("node_failed", {
                "node_id": node_id,
                "name": node_name,
                "error": error_msg,
            })
            raise

    def _run_scoring(self):
        """Stage 4: quality scoring without LLM calls."""
        from config import DOCS_OUTPUT
        from scoring import CodeScorer, DesignScorer, RepoZeroScorer, TestScorer
        from scoring.report_generator import generate_reports

        batch_dir = DOCS_OUTPUT / self.batch_id
        self.sm.append_log({"event": "scoring_start"})

        design_r = DesignScorer(batch_dir / "概要设计").evaluate()
        self._ensure_not_stopped()
        code_r = CodeScorer(batch_dir / "代码生成").evaluate()
        self._ensure_not_stopped()
        test_r = TestScorer(
            batch_dir / "单元测试",
            batch_dir / "代码生成"
        ).evaluate()
        self._ensure_not_stopped()
        repozero_r = RepoZeroScorer(
            batch_dir / "概要设计",
            batch_dir / "代码生成",
            batch_dir / "单元测试",
        ).evaluate()
        self._ensure_not_stopped()

        d_score = design_r["total_score"]
        c_score = code_r["total_score"]
        t_score = test_r["total_score"]
        rz_score = repozero_r["total_score"]

        composite = round(
            d_score * 0.25 +
            c_score * 0.35 +
            t_score * 0.15 +
            rz_score * 0.25, 1
        )

        report = {
            "composite_score": composite,
            "stars": (
                "★" * max(1, int(composite // 20))
                + "☆" * max(0, 4 - int(composite // 20))
            ),
            "design_score": design_r,
            "code_score": code_r,
            "test_score": test_r,
            "repozero_score": repozero_r,
            "weights": {
                "概要设计": {"weight": 0.25, "score": d_score, "contribution": round(d_score * 0.25, 1)},
                "代码生成": {"weight": 0.35, "score": c_score, "contribution": round(c_score * 0.35, 1)},
                "单元测试": {"weight": 0.15, "score": t_score, "contribution": round(t_score * 0.15, 1)},
                "RepoZero验证": {"weight": 0.25, "score": rz_score, "contribution": round(rz_score * 0.25, 1)},
            },
            "sweb_ref": "SWE-bench (Jimenez et al., ICLR 2024) - F2P/P2P + radon Cyclomatic/Maintainability",
            "repozero_ref": "RepoZero (Zhang et al., NeurIPS 2026) - Black-box Output Verification + API Coverage",
        }

        quality_dir = batch_dir / "质量评分"
        quality_dir.mkdir(parents=True, exist_ok=True)
        generate_reports(quality_dir, report)

        self.sm.update_node(
            "质量评分",
            "completed",
            output_files=["质量评分/scoring_report.json", "质量评分/scoring_report.md"],
            quality_score=composite,
        )

        self.sm.append_log({
            "event": "scoring_completed",
            "composite_score": composite,
            "design_score": d_score,
            "code_score": c_score,
            "test_score": t_score,
            "repozero_score": rz_score,
        })

        self._broadcast("scoring_completed", {
            "composite_score": composite,
            "stars": report["stars"],
            "design": d_score,
            "code": c_score,
            "test": t_score,
            "repozero": rz_score,
            "output_files": ["质量评分/scoring_report.json", "质量评分/scoring_report.md"],
        })

    def _broadcast(self, event_type: str, data: dict):
        """Push event to WebSocket clients."""
        event = {"type": event_type, "batch_id": self.batch_id, **data}
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(ws_manager.broadcast(self.batch_id, event))
        except RuntimeError:
            loop = self._loop
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast(self.batch_id, event), loop
                )

    def _emit_react_step(self, node_id: str, node_name: str, step: dict):
        self.sm.append_log({
            "event": "react_step",
            "node": node_id,
            "name": node_name,
            "step": step,
        })
        self._broadcast("react_step", {
            "node_id": node_id,
            "name": node_name,
            "step": step,
        })

    def _ensure_not_stopped(self):
        if self._stop_event and self._stop_event.is_set():
            raise StopRequested("Batch generation was stopped by the user")
        task_control.ensure_running(self.batch_id)
