"""
Code Review Loop — 代码生成后自动迭代审查与修复

流程: 生成代码 → 审查评分 → 低于阈值? → 单次LLM修复 → 重复
最多 N 轮, 达标提前停止
"""

import json
import shutil
import time
from pathlib import Path

from config import DOCS_OUTPUT, settings


def run_code_review_loop(batch_id: str) -> float:
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
        py_files = sorted(f for f in code_dir.rglob("*.py") if "__pycache__" not in str(f))
        if not py_files:
            break

        all_code = ""
        for f in py_files[:10]:
            content = f.read_text(encoding="utf-8")
            all_code += f"\n=== {f.name} ===\n{content[:3000]}\n"

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

        if score >= threshold or ready or round_num >= max_rounds:
            _save_review_report(code_dir, best_score, review_history)
            return best_score

        feedback = "\n".join(f"- {i}" for i in issues[:5]) + "\n" + "\n".join(f"- {s}" for s in suggestions[:5])
        _quick_fix(batch_id, feedback, gen_model, code_dir, py_files)

    _save_review_report(code_dir, best_score, review_history)
    return best_score


def _quick_fix(batch_id: str, feedback: str, model: str, code_dir: Path, py_files: list):
    """单次 LLM 调用修复问题，不重跑 CrewAI Agent"""
    import litellm

    backup_dir = code_dir.parent / f"代码生成_round{int(time.time())}"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    shutil.copytree(code_dir, backup_dir)

    file_summaries = []
    for f in py_files[:8]:
        content = f.read_text(encoding="utf-8")
        file_summaries.append(f"--- {f.name} ---\n{content[:4000]}")

    fix_prompt = f"""你是代码修复专家。以下代码存在这些问题：

{feedback}

请直接输出修复后的完整代码。每个文件用以下格式包裹：
===FILE: 文件名.py===
(完整修复后的代码)
===END===

需要修复的代码:
{chr(10).join(file_summaries)}"""

    try:
        resp = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": fix_prompt}],
            max_tokens=8192, temperature=0.2,
        )
        text = resp.choices[0].message.content.strip()
        import re
        pattern = r'===FILE:\s*(.+?)===\n(.*?)===END==='
        for m in re.finditer(pattern, text, re.DOTALL):
            fname = m.group(1).strip()
            new_code = m.group(2).strip()
            target = code_dir / fname
            if target.exists() and new_code:
                target.write_text(new_code, encoding="utf-8")
    except Exception:
        pass
