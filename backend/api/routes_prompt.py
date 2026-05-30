"""Prompt Optimization API — LLM-based spec generation and refinement"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from config import settings

router = APIRouter(tags=["prompt"])


class OptimizeRequest(BaseModel):
    prompt: str


class OptimizeResponse(BaseModel):
    spec: str
    questions: list[str]


class RefineRequest(BaseModel):
    spec: str
    answers: list[str]
    questions: list[str]


class RefineResponse(BaseModel):
    spec: str
    questions: list[str]


SYSTEM_PROMPT_OPTIMIZE = """你是一名资深产品经理，擅长将一句话的需求描述转化为完整的产品规格说明书。

请根据用户的一句话需求描述，生成一份完整的产品规格说明书（Markdown 格式），包含以下章节：
1. 项目概述（背景、目标、范围）
2. 功能需求（核心功能、用户角色、业务流程）
3. 非功能性需求（性能、安全、可用性）
4. 数据模型设计（主要数据实体及字段）
5. API 接口设计（主要端点列表）
6. 技术约束与假设
7. 验收标准

要求：
- 内容专业、结构清晰
- 使用中文
- 覆盖常见的功能点
- 如果是 Web 应用，默认包含前后端分离架构

同时，生成 2-3 个追问问题，帮助进一步明确需求。问题要具体、有针对性。

输出格式：
```json
{
  "spec": "完整的 Markdown 规格说明书",
  "questions": ["追问1", "追问2", "追问3"]
}
```

只输出 JSON，不要输出其他内容。"""

SYSTEM_PROMPT_REFINE = """你是一名资深产品经理。根据用户对追问的回答，完善产品规格说明书。

你将收到：
- 当前的规格说明书
- 用户对之前追问的回答

请更新规格说明书，将用户的回答整合进去，补充相应的功能描述、约束条件等内容。

同时，如果还有不明确的地方，生成新的追问问题（最多2个）。如果已经很完善，返回空数组。

输出格式：
```json
{
  "spec": "完善后的 Markdown 规格说明书",
  "questions": ["新追问1", "新追问2"]
}
```

只输出 JSON，不要输出其他内容。"""


def _call_llm(system_prompt: str, user_prompt: str) -> dict:
    """Call LLM via litellm and parse JSON response"""
    import json
    import re
    from litellm import completion

    response = completion(
        model=settings.primary_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=4096,
    )

    raw = response.choices[0].message.content or ""
    raw = raw.strip()

    # Try to extract JSON from code blocks
    if raw.startswith("```"):
        lines = raw.split("\n")
        if len(lines) > 2:
            raw = "\n".join(lines[1:-1])
        else:
            raw = re.sub(r'^```\w*\n?|\n?```$', '', raw)

    return json.loads(raw)


@router.post("/prompt/optimize")
async def optimize_prompt(req: OptimizeRequest):
    """将一句话需求描述转化为完整的产品规格说明书"""
    if not req.prompt or len(req.prompt.strip()) < 5:
        raise HTTPException(400, "需求描述至少5个字符")

    try:
        user_prompt = f"请根据以下需求生成规格说明书：\n\n{req.prompt}"
        result = _call_llm(SYSTEM_PROMPT_OPTIMIZE, user_prompt)

        spec = result.get("spec", "")
        questions = result.get("questions", [])

        if not spec:
            raise HTTPException(500, "LLM 未能生成规格说明书")

        return {"spec": spec, "questions": questions}
    except Exception as e:
        raise HTTPException(500, f"提示词优化失败: {str(e)}")


@router.post("/prompt/refine")
async def refine_spec(req: RefineRequest):
    """根据用户回答完善规格说明书"""
    if not req.spec or not req.answers:
        raise HTTPException(400, "规格说明书和答案不可为空")

    try:
        qa_pairs = "\n".join(
            f"Q: {q}\nA: {a}"
            for q, a in zip(req.questions, req.answers)
        )

        user_prompt = f"""当前规格说明书：
{req.spec}

用户对追问的回答：
{qa_pairs}

请完善规格说明书。"""

        result = _call_llm(SYSTEM_PROMPT_REFINE, user_prompt)

        spec = result.get("spec", req.spec)
        questions = result.get("questions", [])

        return {"spec": spec, "questions": questions}
    except Exception as e:
        raise HTTPException(500, f"规格说明书完善失败: {str(e)}")
