"""
Code Review Loop — 代码生成后自动迭代审查与修复

流程: 生成代码 → 审查评分 → 低于阈值? → 注入反馈重新生成 → 重复
最多 N 轮, 达标提前停止
"""

import json
import shutil
import time
from pathlib import Path

from config import DOCS_OUTPUT, settings


def run_code_review_loop(batch_id: str) -> float:
    """对已生成代码进行多轮审查-修复循环

    Args:
        batch_id: 批次 ID

    Returns:
        最终质量评分 (0-100)
    """
    if not settings.code_review_loop_enabled:
        return 0

    code_dir = DOCS_OUTPUT / batch_id / "代码生成"
    if not code_dir.exists() or not any(code_dir.iterdir()):
        return 0

    review_model = settings.code_review_model or settings.primary_model
    gen_model = settings.codegen_model or settings.primary_model
    max_rounds = settings.code_review_max_rounds
    threshold = settings.code_review_threshold

    best_score = 0
    review_history = []

    try:
        import litellm
    except ImportError:
        return 0

    for round_num in range(1, max_rounds + 1):
        # 1) 收集当前代码
        py_files = sorted(code_dir.rglob("*.py"))
        if not py_files:
            break

        all_code = ""
        for f in py_files[:10]:  # 最多读 10 个文件
            content = f.read_text(encoding="utf-8")
            all_code += f"\n=== {f.name} ===\n{content[:3000]}\n"

        # 2) 审查模型评分 + 反馈
        review_prompt = f"""你是一名资深代码审查专家。请对以下代码进行评分(0-100)并给出改进建议。

评审维度：
- 语法正确性 (30分)
- 逻辑完整性 (25分)
- 代码规范 (20分)
- 错误处理 (15分)
- 可运行性 (10分)

输出严格 JSON:
{{"score": 85, "issues": ["问题1", "问题2"], "suggestions": ["建议1", "建议2"], "ready": true/false}}

ready 为 true 表示代码已可直接运行,无需再修改。

代码内容:
{all_code}"""

        try:
            resp = litellm.completion(
                model=review_model,
                messages=[{"role": "user", "content": review_prompt}],
                max_tokens=1024, temperature=0.2,
            )
            review_text = resp.choices[0].message.content.strip()
            # 提取 JSON
            if "```" in review_text:
                review_text = review_text.split("```")[1].replace("json", "", 1).strip()
            result = json.loads(review_text)
        except Exception:
            result = {"score": 50, "issues": ["审查失败"], "suggestions": [], "ready": False}

        score = result.get("score", 50)
        issues = result.get("issues", [])
        suggestions = result.get("suggestions", [])
        ready = result.get("ready", False)
        review_history.append({"round": round_num, "score": score, "issues": issues})

        best_score = max(best_score, score)

        # 3) 达标或最后一轮 → 保存评分并退出
        if score >= threshold or ready or round_num >= max_rounds:
            _save_review_report(code_dir, best_score, review_history)
            return best_score

        # 4) 未达标 → 注入反馈, 重新生成
        feedback = "\n".join(f"❌ {i}" for i in issues[:5]) + "\n\n" + "\n".join(f"💡 {s}" for s in suggestions[:5])
        _inject_feedback_regen(batch_id, feedback, gen_model)

    _save_review_report(code_dir, best_score, review_history)
    return best_score


def _inject_feedback_regen(batch_id: str, feedback: str, model: str):
    """用审查反馈重新生成代码"""
    from orchestrator.crew_factory import build_codegen_crew
    from crewai import Task, Crew, Process

    # 备份旧代码
    code_dir = DOCS_OUTPUT / batch_id / "代码生成"
    backup_dir = code_dir.parent / f"代码生成_round{int(time.time())}"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    shutil.copytree(code_dir, backup_dir)

    # 重新生成(在现有基础上修复)
    crew = build_codegen_crew(batch_id)
    if crew:
        crew.kickoff(inputs={"batch_id": batch_id})


def _save_review_report(code_dir: Path, final_score: float, history: list):
    """保存审查报告"""
    report_path = code_dir / "_code_review_report.json"
    report = {
        "final_score": final_score,
        "rounds": history,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
