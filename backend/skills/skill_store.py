"""Skill Store — 存储 Agent 产出作为后续批次的参考范例

包含两类技能：
- 成功范例（高分产出）：正面参考，提示 Agent "应该怎么做"
- 失败教训（低分/失败产出）：负面参考，提示 Agent "避免怎么做"
"""

import json
from pathlib import Path
from typing import Optional

from config import DOCS_OUTPUT, WORKSPACE_ROOT

SKILLS_DIR = WORKSPACE_ROOT / "skills"
SKILLS_FILE = SKILLS_DIR / "skills.json"
QUALITY_THRESHOLD = 50  # 质量评分 ≥ 50 才保存为成功技能
MAX_SKILL_CONTENT = 3000  # 范例内容最大字符数


def _load() -> list:
    if not SKILLS_FILE.exists():
        return []
    try:
        return json.loads(SKILLS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, Exception):
        return []


def _save(skills: list):
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    SKILLS_FILE.write_text(
        json.dumps(skills, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ═══════════════════════════════════════════════════════════
#  成功范例（正向学习）
# ═══════════════════════════════════════════════════════════

def save_skill(batch_id: str, node_id: str, quality_score: float) -> bool:
    """节点完成后保存成功技能到技能库"""
    if quality_score < QUALITY_THRESHOLD:
        return False

    batch_dir = DOCS_OUTPUT / batch_id
    node_dir = batch_dir / node_id
    if not node_dir.exists():
        return False

    outputs = []
    for f in sorted(node_dir.rglob("*.md")) + sorted(node_dir.rglob("*.py")):
        try:
            content = f.read_text(encoding="utf-8")
            if len(content) > MAX_SKILL_CONTENT:
                content = content[:MAX_SKILL_CONTENT] + "\n... (已截断)"
            outputs.append({"path": str(f.relative_to(batch_dir)), "content": content})
        except Exception:
            continue

    if not outputs:
        return False

    inputs = _find_inputs(batch_id, node_id, batch_dir)
    keywords = _extract_keywords(inputs)

    skills = _load()
    skills.append({
        "skill_type": "success",
        "batch_id": batch_id,
        "node_id": node_id,
        "quality_score": quality_score,
        "keywords": keywords,
        "inputs": inputs,
        "outputs": outputs,
    })

    _prune_skills(skills, node_id, "success", max_count=20)
    _save(skills)
    return True


def _extract_keywords(inputs: list) -> list:
    """从输入中提取业务关键词，用于跨域过滤"""
    import re
    text = " ".join(inp.get("content", "") for inp in inputs)
    # 提取中文和英文关键词
    chinese_words = re.findall(r'[\u4e00-\u9fff]{2,}', text)
    # 去重，取前50个
    seen = set()
    keywords = []
    for w in chinese_words:
        if w not in seen and len(w) >= 2:
            seen.add(w)
            keywords.append(w)
            if len(keywords) >= 50:
                break
    return keywords


# ═══════════════════════════════════════════════════════════
#  失败教训（反向学习）
# ═══════════════════════════════════════════════════════════

def save_failure_lesson(
    batch_id: str,
    node_id: str,
    error: str,
    quality_score: float = 0,
) -> bool:
    """保存失败教训——记录失败原因，帮助后续 Agent 避免同类错误"""
    if not error:
        return False

    batch_dir = DOCS_OUTPUT / batch_id
    inputs = _find_inputs(batch_id, node_id, batch_dir)

    # 提取错误的关键信息（截断）
    error_summary = error[:1000]
    if len(error) > 1000:
        error_summary += "\n... (已截断)"

    # 尝试读取失败节点的部分产出物
    outputs = []
    node_dir = batch_dir / node_id
    if node_dir.exists():
        for f in sorted(node_dir.rglob("*.md")) + sorted(node_dir.rglob("*.py")):
            try:
                content = f.read_text(encoding="utf-8")
                outputs.append({
                    "path": str(f.relative_to(batch_dir)),
                    "content": content[:1000],
                })
            except Exception:
                continue

    skills = _load()
    skills.append({
        "skill_type": "failure",
        "batch_id": batch_id,
        "node_id": node_id,
        "quality_score": quality_score,
        "error": error_summary,
        "inputs": inputs,
        "outputs": outputs,
    })

    _prune_skills(skills, node_id, "failure", max_count=10)
    _save(skills)
    return True


# ═══════════════════════════════════════════════════════════
#  检索 & 注入
# ═══════════════════════════════════════════════════════════

def _prune_skills(skills: list, node_id: str, skill_type: str, max_count: int):
    """限制每种类型/节点的技能数量"""
    node_skills = [s for s in skills if s["node_id"] == node_id and s.get("skill_type") == skill_type]
    if len(node_skills) > max_count:
        node_skills.sort(key=lambda s: s.get("quality_score", 0), reverse=True)
        kept_ids = {s["batch_id"] for s in node_skills[:max_count]}
        for i in range(len(skills) - 1, -1, -1):
            s = skills[i]
            if (s["node_id"] == node_id and s.get("skill_type") == skill_type
                    and s["batch_id"] not in kept_ids):
                skills.pop(i)


def _find_inputs(batch_id: str, node_id: str, batch_dir: Path) -> list:
    """找到节点的输入上下文"""
    inputs = []

    status_file = batch_dir / "batch_status.json"
    if status_file.exists():
        try:
            status = json.loads(status_file.read_text())
            spec_file = status.get("spec_file", "")
            if spec_file:
                spec_path = WORKSPACE_ROOT / "docs" / "待生成" / spec_file
                if spec_path.exists():
                    inputs.append({
                        "type": "产品规格说明书",
                        "content": spec_path.read_text(encoding="utf-8")[:MAX_SKILL_CONTENT],
                    })
        except Exception:
            pass

    design_dir = batch_dir / "概要设计"
    if not design_dir.exists():
        design_dir = batch_dir / "design"
    for f in sorted(design_dir.rglob("*.md")) if design_dir.exists() else []:
        try:
            inputs.append({
                "type": "概要设计文档",
                "content": f.read_text(encoding="utf-8")[:MAX_SKILL_CONTENT],
            })
        except Exception:
            continue

    return inputs[:3]


def _format_skills(skills: list, title: str) -> str:
    """将技能列表格式化为 prompt 文本"""
    if not skills:
        return ""

    lines = [f"\n## {title}\n"]
    for i, skill in enumerate(skills, 1):
        score = skill.get("quality_score", 0)
        lines.append(f"### 参考 {i}（评分: {score}%）\n")
        for inp in skill.get("inputs", [])[:1]:
            lines.append(f"**输入**:\n```markdown\n{inp['content'][:1500]}\n```\n")
        for out in skill.get("outputs", [])[:2]:
            lines.append(f"**输出**:\n```\n{out['content'][:2000]}\n```\n")
    return "\n".join(lines)


def _format_failures(failures: list) -> str:
    """将失败教训格式化为 prompt 文本"""
    if not failures:
        return ""

    lines = ["\n## ⚠️ 历史失败教训（请务必避免以下错误）\n"]
    for i, f in enumerate(failures, 1):
        error = f.get("error", "未知错误")
        lines.append(f"### 教训 {i}\n")
        # 提取前 500 字符的错误信息
        lines.append(f"**失败原因**: {error[:500]}\n")
        for inp in f.get("inputs", [])[:1]:
            lines.append(f"**当时输入**: \n```\n{inp['content'][:800]}\n```\n")
        for out in f.get("outputs", [])[:1]:
            if out.get("content"):
                lines.append(f"**当时产出（可能不完整/有错误）**: \n```\n{out['content'][:1000]}\n```\n")

    lines.append("**请确保你的输出不会出现上述错误。**\n")
    return "\n".join(lines)


def get_examples(node_id: str, top_k: int = 2, task_context: str = "") -> str:
    """获取指定节点的最佳范例 + 失败教训

    Args:
        node_id: 节点名
        top_k: 成功范例数量
        task_context: 当前任务描述（用于过滤不相关的历史技能；为空就全取）
    """
    all_skills = _load()

    # 成功范例
    success = [s for s in all_skills if s["node_id"] == node_id and s.get("skill_type") != "failure"]

    # 如果传了 task_context，按关键词重叠度排序（相关性 × 0.3 + 评分 × 0.7）
    if task_context:
        import re
        current_words = set(re.findall(r'[\u4e00-\u9fff]{2,}', task_context))
        if current_words:
            def relevance(skill):
                skill_words = set(skill.get("keywords", []))
                overlap = len(current_words & skill_words) / max(len(current_words | skill_words), 1)
                score = skill.get("quality_score", 0) or 0
                return overlap * 0.3 + (score / 100) * 0.7
            success.sort(key=relevance, reverse=True)
        else:
            success.sort(key=lambda s: s.get("quality_score", 0) or 0, reverse=True)
    else:
        success.sort(key=lambda s: s.get("quality_score", 0) or 0, reverse=True)

    # 失败教训（不按相关性过滤——所有教训都有参考价值）
    failures = [s for s in all_skills if s["node_id"] == node_id and s.get("skill_type") == "failure"]

    result = []
    if success:
        result.append(_format_skills(success[:top_k], "参考范例（来自历史高质量批次，请参考其结构和质量水平）"))
    if failures:
        result.append(_format_failures(failures[:2]))

    return "\n".join(result)


def get_skill_count(node_id: str = "") -> int:
    """获取技能库中技能数量"""
    skills = _load()
    if node_id:
        return len([s for s in skills if s["node_id"] == node_id])
    return len(skills)
