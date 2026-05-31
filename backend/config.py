"""AI-SDLC Configuration Management"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

# Project root
ROOT_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = ROOT_DIR / os.getenv("WORKSPACE_ROOT", "workspace")
DOCS_INPUT = WORKSPACE_ROOT / "docs" / "待生成"
DOCS_OUTPUT = WORKSPACE_ROOT / "docs" / "已生成"
SRC_OUTPUT = WORKSPACE_ROOT / "src"
TEST_OUTPUT = WORKSPACE_ROOT / "tests"


class Settings(BaseSettings):
    """Application settings loaded from .env"""

    # LLM — API Keys（LiteLLM 根据 model 前缀自动匹配环境变量）
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    moonshot_api_key: str = ""   # Kimi = 月之暗面 (Moonshot)

    # LLM — 默认模型（所有 Agent 的兜底，未被 per-agent 覆盖时使用）
    primary_model: str = "deepseek/deepseek-chat"

    # LLM — 每个 Agent 独立模型（为空则用 primary_model）
    design_model: str = ""
    codegen_model: str = ""
    test_model: str = ""

    # LLM — 提示词优化专用模型（为空则用 primary_model）
    prompt_model: str = ""

    # LLM — 本地 Qwen vLLM 配置（供 design_model="openai/qwen-input" 时使用）
    qwen_vllm_api_base: str = "http://127.0.0.1:8001/v1"

    # LLM — Kimi Code API 专用 Base URL（Kimi Code API 与标准 Moonshot 端点不同）
    moonshot_api_base: str = ""

    # LLM — 公共参数
    llm_temperature: float = 0.3
    llm_max_tokens: int = 8192
    llm_timeout: int = 120

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # ReAct
    react_max_iter: int = 25
    react_verbose: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()


# LiteLLM model config with fallback
def get_llm_config():
    """Return LiteLLM-compatible LLM configuration"""
    return {
        "model": f"openai/{settings.primary_model.split('/')[-1]}",
        "api_key": settings.deepseek_api_key or settings.openai_api_key,
        "api_base": (
            "https://api.deepseek.com/v1"
            if "deepseek" in settings.primary_model
            else None
        ),
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
        "timeout": settings.llm_timeout,
    }


# Ensure workspace directories exist
for d in [DOCS_INPUT, DOCS_OUTPUT, SRC_OUTPUT, TEST_OUTPUT]:
    d.mkdir(parents=True, exist_ok=True)
