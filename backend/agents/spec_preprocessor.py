"""Specification Preprocessor — Convert docx/pptx to structured Markdown spec

Uses Qwen (or the configured primary model) to analyze document content,
recognize user intent, and generate a structured product specification in
Markdown format compatible with the existing Design Agent pipeline.
"""

import os
from pathlib import Path
from typing import Optional

from config import settings


def _build_llm_client():
    """Build a LiteLLM-compatible client for the preprocessor.

    Prefer Qwen (local vLLM) for cost-saving, fallback to primary_model.
    """
    import litellm

    # Use the design model (typically Qwen) if available, else primary
    model = settings.design_model or settings.primary_model

    # Prepare completion kwargs
    kwargs = {
        "model": model,
        "temperature": 0.3,
        "max_tokens": 4096,
        "timeout": settings.llm_timeout,
    }

    # For local Qwen vLLM, set api_base
    if "qwen" in model.lower():
        kwargs["api_base"] = settings.qwen_vllm_api_base
        if not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = "not-needed"
    elif "kimi" in model.lower() and settings.moonshot_api_base:
        kwargs["api_base"] = settings.moonshot_api_base

    return model, kwargs


# ── Prompt Templates ────────────────────────────────────

SYSTEM_PROMPT = """你是一名资深的IT产品需求分析师，擅长从文档和PPT中提取关键信息，
并按照标准格式撰写产品规格说明书。

你的任务：
1. 仔细阅读用户提供的文档/PPT内容
2. 识别项目的类型、目标用户、核心功能
3. 按照以下标准格式输出完整的 Markdown 产品规格说明书

输出格式要求（严格遵守）：

# {项目名称} - 产品规格说明书

## 1. 产品概述
- 产品名称
- 产品定位
- 目标用户

## 2. 功能需求
### 2.1 核心功能
- 每个功能点列出名称、描述、优先级（P0/P1/P2）

### 2.2 辅助功能
- 列出辅助功能

## 3. 用户角色
- 每种用户角色及其权限

## 4. 页面/界面规划
- 列出主要页面或界面
- 每个页面的功能描述
- 页面间的导航关系

## 5. 数据需求
- 需要存储的数据类型
- 数据之间的关系
- 数据约束

## 6. 非功能性需求
- 性能指标
- 安全要求
- 兼容性
- 可用性

## 7. 约束与假设
- 技术约束（如：使用CSV模拟数据库）
- 业务约束

重要约束：
- 所有内容必须是中文
- 必须用 Markdown 格式输出
- 如果有表格数据，使用 Markdown 表格
- 务必从文档内容中提取真实信息，不要编造
- 功能点要具体、可执行、可验证
"""


def build_preprocessor_prompt(doc_title: str, raw_content: str, file_type: str) -> str:
    """Build the user prompt for spec generation from parsed document."""

    # Truncate content if too long (safety for LLM context)
    max_chars = 12000
    if len(raw_content) > max_chars:
        raw_content = raw_content[:max_chars] + f"\n\n...(内容已截断，原文共 {len(raw_content)} 字符)"

    return f"""请根据以下从 {file_type.upper()} 文件中提取的内容，生成一份标准的产品规格说明书。

文档标题：{doc_title}
文件类型：{file_type}

=== 文档原始内容开始 ===
{raw_content}
=== 文档原始内容结束 ===

请严格按照系统提示中指定的格式输出完整的产品规格说明书（Markdown 格式）。
"""


def preprocess_document(
    file_path: str, file_type: str, doc_title: str, raw_content: str
) -> str:
    """
    Use LLM to convert parsed document content into structured Markdown spec.

    Args:
        file_path: original file path
        file_type: 'docx', 'pptx', etc.
        doc_title: extracted document title
        raw_content: raw text extracted from the document

    Returns:
        Generated Markdown specification string
    """
    try:
        import litellm
    except ImportError:
        # Fallback: return raw content with basic formatting
        return _fallback_spec(doc_title, raw_content, file_type)

    model, kwargs = _build_llm_client()
    user_prompt = build_preprocessor_prompt(doc_title, raw_content, file_type)

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        response = litellm.completion(
            messages=messages,
            **kwargs,
        )

        result = response.choices[0].message.content
        return result if result else _fallback_spec(doc_title, raw_content, file_type)

    except Exception as e:
        print(f"[SpecPreprocessor] LLM call failed: {e}, using fallback")
        return _fallback_spec(doc_title, raw_content, file_type)


def _fallback_spec(title: str, raw_content: str, file_type: str) -> str:
    """Fallback: generate a basic spec when LLM is unavailable."""
    return f"""# {title} - 产品规格说明书

> 自动从 {file_type.upper()} 文件生成（未使用 AI 增强）

## 1. 产品概述
- 产品名称：{title}
- 来源文件类型：{file_type}

## 2. 原始内容

{raw_content}

## 3. 备注
此规格说明书为原始内容直接转换，未经过 AI 分析和结构化。
建议配置 Qwen 或其他 LLM 以获得更好的结构化结果。
"""
