"""Prompt Optimization API — LLM-based spec generation and refinement"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from config import settings

router = APIRouter(tags=["prompt"])


class OptimizeRequest(BaseModel):
    prompt: str
    mode: Literal["standard", "sisyphus"] = "standard"
    max_rounds: int = 8


class OptimizeResponse(BaseModel):
    spec: str
    questions: list[str]
    is_complete: bool = False
    round: int = 1
    readiness_score: int = 0
    coverage_summary: str = ""


class QuestionAnswer(BaseModel):
    question: str
    answer: str


class RefineRequest(BaseModel):
    spec: str
    answers: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    mode: Literal["standard", "sisyphus"] = "standard"
    round: int = 1
    max_rounds: int = 8
    qa_history: list[QuestionAnswer] = Field(default_factory=list)
    force_questions: bool = False


class RefineResponse(BaseModel):
    spec: str
    questions: list[str]
    is_complete: bool = False
    round: int = 1
    readiness_score: int = 0
    coverage_summary: str = ""


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

SYSTEM_PROMPT_SISYPHUS_OPTIMIZE = """你是一名资深产品经理和需求访谈专家。你正在使用“西西弗斯模式”把一句话想法反复追问、补全为可进入开发流水线的产品规格说明书。

工作方式：
1. 先基于当前信息生成一份可编辑的 Markdown 规格说明书草稿。
2. 再像启发式访谈一样找出最关键的不确定点，继续追问。
3. 每一轮问题必须推进规格书质量，不要重复已知信息。
4. 只在需求足够清晰、可验收、可设计、可编码、可测试时才标记完成。

追问优先覆盖：
- 目标用户、角色权限、核心场景
- 业务规则、状态流转、异常路径
- 数据实体、字段、约束、生命周期
- 集成系统、通知、支付、审批、设备等外部依赖
- 非功能需求、安全、性能、审计、部署约束
- 验收标准和边界条件

要求：
- 使用中文。
- 每轮生成 3-6 个高价值问题。
- 如果信息仍不足，is_complete 必须为 false。
- readiness_score 为 0-100，表示规格书进入后续 SDLC 流水线的准备程度。
- coverage_summary 用一句话说明当前最缺的需求信息。

输出格式：
```json
{
  "spec": "当前 Markdown 规格说明书",
  "questions": ["追问1", "追问2", "追问3"],
  "is_complete": false,
  "readiness_score": 45,
  "coverage_summary": "当前主要缺少角色权限和异常流程。"
}
```

只输出 JSON，不要输出其他内容。"""

SYSTEM_PROMPT_SISYPHUS_REFINE = """你是一名资深产品经理和需求访谈专家。你正在使用“西西弗斯模式”持续完善产品规格说明书。

你将收到：
- 当前规格说明书
- 历史问答
- 本轮新增回答
- 当前轮次和最大轮次
- 是否强制继续追问

请执行：
1. 将所有新回答整合进规格说明书，补充到正确章节。
2. 重新评估是否还存在会影响设计、编码、测试的不确定点。
3. 如果仍有不确定点，继续生成 3-6 个新的启发式追问。
4. 如果 force_questions 为 true，即使规格书已经较完整，也要继续提出更深入的边界、异常、验收或非功能问题。
5. 当需求已经足够清晰，或达到最大轮次且没有关键空洞时，返回空 questions 并将 is_complete 设为 true。

追问必须满足：
- 不重复历史问题。
- 不问宽泛问题，例如“还有其他需求吗？”。
- 每个问题都应能直接改善规格书、验收标准或后续实现。

输出格式：
```json
{
  "spec": "完善后的 Markdown 规格说明书",
  "questions": ["新追问1", "新追问2", "新追问3"],
  "is_complete": false,
  "readiness_score": 72,
  "coverage_summary": "当前主要缺少支付失败和审批撤回的异常处理。"
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
        max_tokens=min(settings.llm_max_tokens, 8192),
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
    elif "{" in raw and "}" in raw:
        raw = raw[raw.find("{"):raw.rfind("}") + 1]

    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else {}


def _normalize_questions(questions: list) -> list[str]:
    """Return non-empty unique questions while preserving order."""
    normalized = []
    seen = set()
    for question in questions or []:
        text = str(question).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _safe_int(value, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _safe_bool(value, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "完成", "是"}:
            return True
        if normalized in {"false", "no", "0", "未完成", "否"}:
            return False
    return fallback


def _build_response(result: dict, fallback_spec: str, round_no: int, mode: str) -> dict:
    spec = result.get("spec") or fallback_spec
    questions = _normalize_questions(result.get("questions", []))
    is_complete = _safe_bool(result.get("is_complete"), False)

    if mode == "standard":
        is_complete = len(questions) == 0
    elif questions:
        is_complete = False

    return {
        "spec": spec,
        "questions": questions,
        "is_complete": is_complete,
        "round": round_no,
        "readiness_score": _safe_int(result.get("readiness_score"), 100 if is_complete else 0),
        "coverage_summary": str(result.get("coverage_summary", "") or ""),
    }


@router.post("/prompt/optimize")
async def optimize_prompt(req: OptimizeRequest):
    """将一句话需求描述转化为完整的产品规格说明书"""
    if not req.prompt or len(req.prompt.strip()) < 5:
        raise HTTPException(400, "需求描述至少5个字符")

    try:
        max_rounds = max(1, min(req.max_rounds, 12))
        if req.mode == "sisyphus":
            system_prompt = SYSTEM_PROMPT_SISYPHUS_OPTIMIZE
            user_prompt = f"""用户的一句话需求：
{req.prompt}

当前轮次：1
最大轮次：{max_rounds}

请生成规格说明书草稿，并开启第一轮启发式追问。"""
        else:
            system_prompt = SYSTEM_PROMPT_OPTIMIZE
            user_prompt = f"请根据以下需求生成规格说明书：\n\n{req.prompt}"

        result = _call_llm(system_prompt, user_prompt)

        spec = result.get("spec", "")

        if not spec:
            raise HTTPException(500, "LLM 未能生成规格说明书")

        return _build_response(result, spec, 1, req.mode)
    except Exception as e:
        raise HTTPException(500, f"提示词优化失败: {str(e)}")


@router.post("/prompt/refine")
async def refine_spec(req: RefineRequest):
    """根据用户回答完善规格说明书"""
    if not req.spec:
        raise HTTPException(400, "规格说明书不可为空")
    if req.mode == "standard" and not req.answers:
        raise HTTPException(400, "规格说明书和答案不可为空")

    try:
        max_rounds = max(1, min(req.max_rounds, 12))
        new_qa_pairs = "\n".join(
            f"Q: {q}\nA: {a}"
            for q, a in zip(req.questions, req.answers)
            if a.strip()
        )
        history_pairs = "\n".join(
            f"Q: {qa.question}\nA: {qa.answer}"
            for qa in req.qa_history
            if qa.answer.strip()
        )

        if req.mode == "sisyphus":
            system_prompt = SYSTEM_PROMPT_SISYPHUS_REFINE
            next_round = min(req.round + 1, max_rounds)
            user_prompt = f"""当前规格说明书：
{req.spec}

历史问答：
{history_pairs or "暂无"}

本轮新增回答：
{new_qa_pairs or "用户要求继续深入追问，暂无新增回答。"}

当前轮次：{next_round}
最大轮次：{max_rounds}
是否强制继续追问：{req.force_questions}

请完善规格说明书，并判断是否继续追问。"""
        else:
            system_prompt = SYSTEM_PROMPT_REFINE
            next_round = req.round + 1
            user_prompt = f"""当前规格说明书：
{req.spec}

用户对追问的回答：
{new_qa_pairs}

请完善规格说明书。"""

        result = _call_llm(system_prompt, user_prompt)
        return _build_response(result, req.spec, next_round, req.mode)
    except Exception as e:
        raise HTTPException(500, f"规格说明书完善失败: {str(e)}")
