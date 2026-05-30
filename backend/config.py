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

    # LLM
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    primary_model: str = "deepseek/deepseek-chat"
    fallback_model: str = "openai/gpt-4o-mini"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 8192
    llm_timeout: int = 120

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # ReAct
    react_max_iter: int = 15
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
