"""Skill Store — 存储高质量 Agent 产出作为后续批次的参考范例

每个子任务完成后，如果质量评分 ≥ 阈值，自动保存输入→输出对。
后续批次运行时，自动检索最相关的范例注入到 Agent prompt 中。
"""

import json
from pathlib import Path
from typing import Optional

from config import DOCS_OUTPUT, WORKSPACE_ROOT

SKILLS_DIR = WORKSPACE_ROOT / "skills"
SKILLS_FILE = SKILLS_DIR / "skills.json"
QUALITY_THRESHOLD = 50  # 质量评分 ≥ 50 才保存为技能
MAX_SKILL_CONTENT = 3000  # 范例内容最大字符数（避免 prompt 过长）


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


def save_skill(batch_id: str, node_id: str, quality_score: float) -> bool:
    """节点完成后保存技能到技能库

    Args:
        batch_id: 批次 ID
        node_id: 节点名（概要设计/代码生成/单元测试）
        quality_score: 质量评分（0-100）

    Returns:
        True if saved, False if quality too low
    """
    if quality_score < QUALITY_THRESHOLD:
        return False

    batch_dir = DOCS_OUTPUT / batch_id
    node_dir = batch_dir / node_id
    if not node_dir.exists():
        return False

    # 读取产出物内容
    outputs = []
    for f in sorted(node_dir.rglob("*.md")) + sorted(node_dir.rglob("*.py")):
        try:
            content = f.read_text(encoding="utf-8")
            if len(content) > MAX_SKILL_CONTENT:
                content = content[:MAX_SKILL_CONTENT] + "\n... (已截断)"
            outputs.append({
                "path": str(f.relative_to(batch_dir)),
                "content": content,
            })
        except Exception:
            continue

    if not outputs:
        return False

    # 读取输入（规格说明书或设计文档）
    # 对于概要设计节点，输入是规格说明书；对于代码生成/单元测试，输入是设计文档+代码
    inputs = _find_inputs(batch_id, node_id, batch_dir)

    skills = _load()
    skills.append({
        "batch_id": batch_id,
        "node_id": node_id,
        "quality_score": quality_score,
        "inputs": inputs,
        "outputs": outputs,
    })

    # 每个节点类型最多保留 20 个技能
    node_skills = [s for s in skills if s["node_id"] == node_id]
    if len(node_skills) > 20:
        node_skills.sort(key=lambda s: s["quality_score"], reverse=True)
        kept_ids = {s["batch_id"] for s in node_skills[:20]}
        skills = [s for s in skills if s["node_id"] != node_id or s["batch_id"] in kept_ids]

    _save(skills)
    return True


def _find_inputs(batch_id: str, node_id: str, batch_dir: Path) -> list:
    """找到节点的输入上下文"""
    inputs = []

    # 尝试读取规格说明书
    status_file = batch_dir / "batch_status.json"
    if status_file.exists():
        try:
            status = json.loads(status_file.read_text())
            spec_file = status.get("spec_file", "")
            if spec_file:
                spec_path = WORKSPACE_ROOT / "docs" / "待生成" / spec_file
                if spec_path.exists():
                    content = spec_path.read_text(encoding="utf-8")
                    inputs.append({
                        "type": "产品规格说明书",
                        "content": content[:MAX_SKILL_CONTENT],
                    })
        except Exception:
            pass

    # 尝试读取设计文档
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

    return inputs[:3]  # 最多 3 个


def get_examples(node_id: str, top_k: int = 2) -> str:
    """获取指定节点类型的最佳范例（作为 prompt 注入）

    Args:
        node_id: 节点名（概要设计/代码生成/单元测试）
        top_k: 返回前 K 个最佳范例

    Returns:
        格式化的范例文本，可直接注入 prompt；若无范例则返回空字符串
    """
    skills = _load()
    node_skills = [s for s in skills if s["node_id"] == node_id]
    if not node_skills:
        return ""

    # 按质量评分排序，取最佳
    node_skills.sort(key=lambda s: s["quality_score"], reverse=True)
    best = node_skills[:top_k]

    lines = ["\n## 参考范例（来自历史高质量批次，请参考其结构和质量水平）\n"]
    for i, skill in enumerate(best, 1):
        lines.append(f"### 范例 {i}（质量评分: {skill['quality_score']}%）\n")
        for inp in skill.get("inputs", [])[:1]:
            lines.append(f"**输入 — {inp['type']}**:\n```markdown\n{inp['content'][:1500]}\n```\n")
        for out in skill.get("outputs", [])[:2]:
            lines.append(f"**输出 — {out['path']}**:\n```\n{out['content'][:2000]}\n```\n")

    return "\n".join(lines)


def get_skill_count(node_id: str = "") -> int:
    """获取技能库中技能数量"""
    skills = _load()
    if node_id:
        return len([s for s in skills if s["node_id"] == node_id])
    return len(skills)
