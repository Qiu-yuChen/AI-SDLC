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


class _SafeDict(dict):
    """缺失 key 时返回原始 {key} 文本，避免 CrewAI 模板渲染 KeyError"""
    def __missing__(self, key):
        return "{" + key + "}"


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

            # 三阶段全部完成后 → 启动质量评分
            self._run_scoring()

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
            crew_output = crew.kickoff(inputs=_SafeDict(batch_id=self.batch_id))
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

            # 后台启动质量审查 + 技能存储（不阻塞流水线）
            threading.Thread(target=self._run_quality_review, args=(node_id, node_name), daemon=True).start()

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
            try:
                from skills.skill_store import save_failure_lesson
                save_failure_lesson(self.batch_id, node_id, error_msg)
            except Exception:
                pass
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

        # 后臺海報生成（不阻塞，SDXL subprocess 在 trellis2 環境）
        import threading
        threading.Thread(target=self._generate_poster, daemon=True).start()

    def _generate_poster_prompt(self, spec_text: str) -> str:
        """用本地 Qwen + system prompt 生成海报提示词"""
        try:
            import os
            os.environ.setdefault("OPENAI_API_BASE", "http://127.0.0.1:8002/v1")
            os.environ.setdefault("OPENAI_API_KEY", "not-needed")
            import litellm

            system_prompt = (
                "You are a professional poster prompt engineer. "
                "Generate a single English sentence for SDXL image generation. "
                "CRITICAL: The project domain keyword (e.g. library, vehicle, hospital, "
                "school) MUST appear prominently in your prompt — the image must visually "
                "represent the specific project type. "
                "Rules: NO text/letters/words in image. Focus on depth layers, "
                "lighting contrast, geometric composition, volumetric light, 8k cinematic. "
                "Style: dark tech, blueprint grid, glassmorphism UI elements. "
                "Output ONLY the prompt."
            )
            resp = litellm.completion(
                model="openai/qwen-input",
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": "Project: " + spec_text}],
                max_tokens=200, temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return ""

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

    def _run_quality_review(self, node_id: str, node_name: str):
        """后台线程：质量审查 + 技能存储（不改变节点状态，只追加评分）"""
        try:
            from agents.quality_agent import run_quality_review
            from skills.skill_store import save_skill
            quality = run_quality_review(self.batch_id, node_id)
            if isinstance(quality, dict) and "score" in quality:
                total = quality.get("total", 100)
                pct = round(quality["score"] / total * 100, 1) if total > 0 else 0
                # 直接更新 quality_score，不走 update_node（避免重置 duration）
                batch = self.sm.load()
                if batch and node_id in batch.get("nodes", {}):
                    batch["nodes"][node_id]["quality_score"] = pct
                    self.sm._write_status(batch)
                self._broadcast("quality_review", {
                    "node_id": node_id,
                    "name": node_name,
                    "score": pct,
                })
                save_skill(self.batch_id, node_id, pct)
        except Exception:
            pass

    def _generate_poster(self):
        """后台生成交付海报（SDXL）"""
        try:
            from config import DOCS_OUTPUT, WORKSPACE_ROOT
            from pathlib import Path

            batch_dir = DOCS_OUTPUT / self.batch_id
            poster_dir = batch_dir / "交付海报"
            poster_dir.mkdir(parents=True, exist_ok=True)
            poster_path = poster_dir / "poster.png"
            if poster_path.exists():
                return

            # 1. Qwen 生成海报提示词
            spec_content = ""
            status = self.sm.load()
            spec_file = status.get("spec_file", "") if status else ""
            if spec_file:
                spec_path = WORKSPACE_ROOT / "docs" / "待生成" / spec_file
                if spec_path.exists():
                    spec_content = spec_path.read_text(encoding="utf-8")[:2000]

            prompt = self._generate_poster_prompt(spec_content)
            if not prompt:
                prompt = "modern software engineering project delivery poster, tech blueprint style"

            # 2. SDXL subprocess（trellis2 env: torch + diffusers）
            import subprocess
            trellis_python = "/home/cqy/envs/trellis2/bin/python"
            script = str(
                Path(__file__).resolve().parent.parent / "tools" / "poster_generator.py"
            )
            result = subprocess.run(
                [trellis_python, script, "--prompt", prompt, "--output", str(poster_path)],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0 and poster_path.exists():
                self.sm.append_log({
                    "event": "poster_ready",
                    "path": str(poster_path.relative_to(batch_dir)),
                })
                self._broadcast("poster_ready", {
                    "path": str(poster_path.relative_to(batch_dir)),
                })
        except Exception:
            pass

    def _ensure_not_stopped(self):
        if self._stop_event and self._stop_event.is_set():
            raise StopRequested("Batch generation was stopped by the user")
        task_control.ensure_running(self.batch_id)
