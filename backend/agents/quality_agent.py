"""Quality Review Agent — reads node outputs and returns structured quality assessment"""

import json
from crewai import Agent
from config import DOCS_OUTPUT, settings
from tools.quality_tools import lint_check, coverage_check, calculate_quality_score


class _SafeDict(dict):
    """缺失 key 时返回原始标记"""
    def __missing__(self, key):
        return "{" + key + "}"


def build_quality_review_prompt(node_id: str, batch_id: str) -> str:
    """Build the task description for the Quality Review Agent"""
    node_dir = DOCS_OUTPUT / batch_id / node_id
    return f"""
## 任务：审查节点产出物质量

### 审查对象
节点：{node_id}
产出目录：{node_dir}

### 审查流程
1. 列出产出目录中的所有文件
2. 读取关键文件（设计文档、源代码、测试代码）
3. 对每个文件进行质量评估
4. 汇总质量评分

### 审查标准
- **设计文档（概要设计）**：完整性（是否覆盖系统概述、架构设计、模块划分、API接口、数据模型、非功能需求）、清晰度、可执行性
- **源代码（代码生成）**：语法正确性、代码规范（PEP 8）、类型注解完整性、错误处理完善度、文档注释质量
- **测试代码（单元测试）**：测试覆盖率、边界条件覆盖、异常场景覆盖、断言质量

### 输出格式
返回严格的 JSON 格式（不要包含其他文字）：
```json
{{
  "score": 35,
  "total": 40,
  "issues": ["缺少 API 接口定义", "部分函数没有类型注解"],
  "suggestions": ["建议补充认证流程说明", "建议为 utils.py 添加单元测试"]
}}
```

注意：
- score 和 total 必须是整数
- issues 列出发现的具体问题
- suggestions 列出改进建议
- 只输出 JSON，不要输出其他任何内容
"""


def create_quality_agent() -> Agent:
    """质量审查 Agent — 审查节点产出物质量"""
    return Agent(
        role="资深质量审查专家",
        goal="审查节点产出物，返回结构化质量评估（评分 + 问题 + 建议）",
        backstory="""你是一名资深软件质量审查专家，拥有10年以上的代码审查和软件质量保障经验。
你擅长：
- 审查设计文档的完整性和可执行性
- 审查代码的规范性和健壮性
- 审查测试用例的覆盖率和有效性
- 给出可操作的改进建议

你的工作流程（ReAct）：
1. 💭 列出产出目录中的所有文件
2. 🎬 逐个读取关键文件
3. 👁️ 评估每个文件的质量
4. 💭 汇总问题和改进建议
5. 🎬 输出结构化 JSON 质量报告""",
        tools=[lint_check, coverage_check, calculate_quality_score],
        llm=settings.primary_model,
        verbose=settings.react_verbose,
        allow_delegation=False,
        max_iter=settings.react_max_iter,
        max_rpm=10,
    )


def run_quality_review(batch_id: str, node_id: str) -> dict:
    """Run quality review for a node's outputs and return a structured result"""
    from crewai import Task, Crew, Process

    node_dir = DOCS_OUTPUT / batch_id / node_id
    if not node_dir.exists() or not any(node_dir.iterdir()):
        return {"score": 0, "total": 100, "issues": ["节点无产出物"], "suggestions": []}

    agent = create_quality_agent()
    task_desc = build_quality_review_prompt(node_id, batch_id)

    task = Task(
        description=task_desc.replace("{", "{{").replace("}", "}}"),
        agent=agent,
        expected_output="Strict JSON: {{ score, total, issues, suggestions }}",
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=settings.react_verbose,
    )

    try:
        result = crew.kickoff(inputs=_SafeDict(batch_id=batch_id))
        raw = str(result) if result else "{}"

        # Try to extract JSON from the output (may contain surrounding text)
        raw = raw.strip()
        if raw.startswith("```"):
            # Strip markdown code fences
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw

        return json.loads(raw)
    except (json.JSONDecodeError, Exception):
        # Fallback: calculate basic quality score from node outputs
        score = _calculate_fallback_score(batch_id, node_id)
        return score


def _calculate_fallback_score(batch_id: str, node_id: str) -> dict:
    """Fallback quality score using tools when LLM review fails"""
    node_dir = DOCS_OUTPUT / batch_id / node_id
    files = list(node_dir.rglob("*.py")) if node_dir.exists() else []
    total_score = 0
    max_score = len(files) * 20 if files else 20
    issues = []
    suggestions = []

    for f in files:
        lint_result = lint_check(str(f))
        if "❌" in lint_result:
            issues.append(f"语法错误: {f.name}")
            suggestions.append(f"修复 {f.name} 的语法错误")

    if not files:
        total_score = 5
        issues.append("未发现代码文件")
        suggestions.append("检查节点是否正确生成产出物")
    else:
        total_score = max(5, max_score - len(issues) * 10)

    return {
        "score": total_score,
        "total": max_score,
        "issues": issues,
        "suggestions": suggestions,
    }
