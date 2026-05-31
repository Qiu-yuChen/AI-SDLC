"""Orchestrator Engine — Manages multi-agent pipeline execution"""

import asyncio
import traceback
from datetime import datetime, timezone
from typing import Optional

from .state_manager import StateManager, NODE_ORDER, NODE_NAMES
from .crew_factory import CREW_BUILDERS, build_design_crew
from ws.manager import ws_manager


class OrchestratorEngine:
    """Core pipeline orchestrator with auto/manual/retry modes"""

    def __init__(self, batch_id: str):
        self.batch_id = batch_id
        self.sm = StateManager(batch_id)

    # ── Auto Mode ──────────────────────────────────────────

    def run_auto(self):
        """Execute all nodes sequentially (auto mode)"""
        state = self.sm.load()
        if not state:
            raise ValueError(f"Batch {self.batch_id} not found")

        spec_file = state.get("spec_file")
        self.sm.append_log({"event": "pipeline_start", "mode": "auto"})

        for node_id in NODE_ORDER:
            try:
                self._execute_node(node_id, spec_file)
            except Exception as e:
                # Node failed — stop pipeline, allow retry
                self.sm.append_log({
                    "event": "pipeline_halted",
                    "node": node_id,
                    "error": str(e),
                })
                break

        final_state = self.sm.load()
        self.sm.append_log({
            "event": "pipeline_end",
            "final_status": final_state.get("status"),
        })

    # ── Manual Mode ────────────────────────────────────────

    def run_manual_step(self) -> dict:
        """Execute the next pending node (manual mode)"""
        node_id = self.sm.get_current_node()
        if not node_id:
            return {"status": "all_completed", "message": "所有节点已完成"}

        state = self.sm.load()
        spec_file = state.get("spec_file")
        self._execute_node(node_id, spec_file)

        return {
            "status": "completed",
            "node": node_id,
            "next": self.sm.get_current_node(),
        }

    # ── Retry ──────────────────────────────────────────────

    def retry_node(self, node_id: str) -> dict:
        """Retry a failed node (incremental retry)"""
        state = self.sm.load()
        if node_id not in state["nodes"]:
            return {"status": "error", "message": f"Unknown node: {node_id}"}

        current_status = state["nodes"][node_id]["status"]
        if current_status not in ("failed", "pending"):
            return {"status": "error", "message": f"Node {node_id} status is '{current_status}', not retryable"}

        spec_file = state.get("spec_file")
        self._execute_node(node_id, spec_file)

        return {"status": "completed", "node": node_id}

    # ── Internal: Execute Single Node ──────────────────────

    def _execute_node(self, node_id: str, spec_file: str):
        """Execute a single agent node with state tracking and WS broadcast"""
        node_name = NODE_NAMES[node_id]

        # Update state → running
        self.sm.update_node(node_id, "running")
        self._broadcast("node_start", {"node_id": node_id, "name": node_name})

        start = datetime.now(timezone.utc)

        try:
            # ── 质量评分节点：纯 Python 计算，不走 CrewAI ──
            if node_id == "质量评分":
                self._run_scoring()
                return

            # Build and run the crew for this node
            builder = CREW_BUILDERS[node_id]
            if node_id == "概要设计":
                crew = builder(self.batch_id, spec_file)
            else:
                crew = builder(self.batch_id)

            # Execute with ReAct callback
            crew_output = crew.kickoff(
                inputs={"batch_id": self.batch_id}
            )

            # Convert crew output to string
            output_text = str(crew_output) if crew_output else ""
            duration = (datetime.now(timezone.utc) - start).total_seconds()

            # Collect output files
            from config import DOCS_OUTPUT
            node_dir = DOCS_OUTPUT / self.batch_id / node_id
            output_files = []
            if node_dir.exists():
                for f in node_dir.rglob("*"):
                    if f.is_file():
                        output_files.append(str(f.relative_to(DOCS_OUTPUT / self.batch_id)))

            # Update state → completed
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

            # Run quality review after node completion
            try:
                from agents.quality_agent import run_quality_review
                quality = run_quality_review(self.batch_id, node_id)
                if isinstance(quality, dict) and "score" in quality:
                    total = quality.get("total", 100)
                    pct = round(quality["score"] / total * 100, 1) if total > 0 else 0
                    self.sm.update_node(node_id, "completed", quality_score=pct)
                    self._broadcast("quality_review", {
                        "node_id": node_id,
                        "name": node_name,
                        "score": pct,
                        "details": quality.get("issues", []),
                    })
            except Exception:
                pass  # Quality review is non-critical

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
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

    # ── Scoring Stage ──────────────────────────────────────

    def _run_scoring(self):
        """
        阶段4: 质量评分 (纯 Python，不使用 LLM/CrewAI)

        四维度评分：
          - DesignScorer   : 概要设计文档质量 (20%)
          - CodeScorer     : 代码质量 radon CC/MI (30%)
          - TestScorer     : 测试质量 F2P/P2P   (30%)
          - RepoZeroScorer : BOV + API 覆盖度   (20%)

        参考: SWE-bench (ICLR 2024) + RepoZero (NeurIPS 2026)
        """
        from config import DOCS_OUTPUT
        from scoring import DesignScorer, CodeScorer, TestScorer, RepoZeroScorer
        from scoring.report_generator import generate_reports

        batch_dir = DOCS_OUTPUT / self.batch_id

        self.sm.append_log({"event": "scoring_start"})

        # ── 执行四维度评分 ──
        design_r   = DesignScorer(batch_dir / "概要设计").evaluate()
        code_r     = CodeScorer(batch_dir / "代码生成").evaluate()
        test_r     = TestScorer(
            batch_dir / "单元测试",
            batch_dir / "代码生成"
        ).evaluate()
        repozero_r = RepoZeroScorer(
            batch_dir / "概要设计",
            batch_dir / "代码生成",
            batch_dir / "单元测试",
        ).evaluate()

        # ── 加权综合 ──
        d_score  = design_r["total_score"]
        c_score  = code_r["total_score"]
        t_score  = test_r["total_score"]
        rz_score = repozero_r["total_score"]

        composite = round(
            d_score  * 0.25 +
            c_score  * 0.35 +
            t_score  * 0.15 +
            rz_score * 0.25, 1
        )

        # ── 组装报告 ──
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
                "概要设计": {
                    "weight": 0.25,
                    "score": d_score,
                    "contribution": round(d_score * 0.25, 1),
                },
                "代码生成": {
                    "weight": 0.35,
                    "score": c_score,
                    "contribution": round(c_score * 0.35, 1),
                },
                "单元测试": {
                    "weight": 0.15,
                    "score": t_score,
                    "contribution": round(t_score * 0.15, 1),
                },
                "RepoZero验证": {
                    "weight": 0.25,
                    "score": rz_score,
                    "contribution": round(rz_score * 0.25, 1),
                },
            },
            "sweb_ref": (
                "SWE-bench (Jimenez et al., ICLR 2024) — "
                "F2P/P2P + radon Cyclomatic/Maintainability"
            ),
            "repozero_ref": (
                "RepoZero (Zhang et al., NeurIPS 2026) — "
                "Black-box Output Verification + API Coverage"
            ),
        }

        # ── 生成报告文件（放入质量评分/目录）──
        quality_dir = batch_dir / "质量评分"
        quality_dir.mkdir(parents=True, exist_ok=True)
        generate_reports(quality_dir, report)

        # ── 更新状态 ──
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

    # ── WebSocket Broadcast Helper ─────────────────────────

    def _broadcast(self, event_type: str, data: dict):
        """Push event to WebSocket clients"""
        event = {"type": event_type, "batch_id": self.batch_id, **data}
        # Run async broadcast in sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(ws_manager.broadcast(self.batch_id, event))
            else:
                loop.run_until_complete(ws_manager.broadcast(self.batch_id, event))
        except RuntimeError:
            # No event loop — run in new one
            asyncio.run(ws_manager.broadcast(self.batch_id, event))
