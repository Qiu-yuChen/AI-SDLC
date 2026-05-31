"""
Feishu Bot webhook — 接收消息并触发 AI-SDLC 流水线

飞书开放平台配置:
  1. https://open.feishu.cn → 创建企业自建应用 → 机器人
  2. 事件订阅 → 请求网址: https://your-domain/api/feishu
  3. 订阅事件: im.message.receive_v1
  4. 获取 App ID + App Secret → 填入 .env

比公众号简单: 不用备案、JSON 格式、无需 XML 解析
"""

import json
import hashlib
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from config import settings

router = APIRouter(tags=["feishu"])

FEISHU_APP_ID = getattr(settings, "feishu_app_id", "")
FEISHU_APP_SECRET = getattr(settings, "feishu_app_secret", "")


async def _get_tenant_token() -> str:
    """获取飞书 tenant_access_token"""
    import httpx
    resp = await httpx.AsyncClient().post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
    )
    data = resp.json()
    if data.get("code") != 0:
        raise HTTPException(500, f"Feishu auth failed: {data}")
    return data["tenant_access_token"]


async def _send_feishu_message(open_id: str, content: str):
    """发送消息给飞书用户"""
    token = await _get_tenant_token()
    import httpx
    await httpx.AsyncClient().post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "receive_id": open_id,
            "msg_type": "text",
            "content": json.dumps({"text": content}),
        },
    )


async def _process_spec_request(text: str, open_id: str):
    """处理用户需求 → 创建批次 → 回复"""
    await _send_feishu_message(open_id, f"⏳ 收到需求，正在生成规格书...\n📝 {text[:50]}...")

    try:
        # 调 LLM 生成规格书
        import litellm
        model = settings.prompt_model or settings.primary_model
        api_base = None
        api_key = None
        if "qwen" in model:
            api_base = settings.qwen_vllm_api_base
            api_key = "not-needed"

        resp = litellm.completion(
            model=model,
            messages=[{
                "role": "system",
                "content": "根据用户的一句话需求，生成完整的产品规格说明书（Markdown格式，含7个标准章节）。只输出Markdown。",
            }, {
                "role": "user",
                "content": text,
            }],
            max_tokens=4096, temperature=0.3,
            api_base=api_base, api_key=api_key,
        )
        spec_md = resp.choices[0].message.content.strip()
    except Exception:
        spec_md = f"# 项目概述\n\n{text}\n\n## 功能需求\n\n待补充..."

    from config import DOCS_INPUT
    filename = f"feishu_spec_{uuid.uuid4().hex[:8]}.md"
    (DOCS_INPUT / filename).write_text(spec_md, encoding="utf-8")

    from orchestrator.state_manager import StateManager
    project_name = text.strip()[:30]
    batch_id = f"batch_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    sm = StateManager(batch_id)
    sm.create(filename, project_name)

    import asyncio
    from orchestrator.engine import OrchestratorEngine
    async def _run():
        import threading
        def _blocking():
            engine = OrchestratorEngine(batch_id)
            engine.run_auto()
        threading.Thread(target=_blocking, daemon=True).start()
    asyncio.create_task(_run())

    await _send_feishu_message(open_id, (
        f"✅ 已收到需求，开始自动开发!\n"
        f"📋 项目: {project_name}\n"
        f"🔢 批次: {batch_id[-10:]}\n\n"
        f"⚙️ 流水线: 概要设计 → 代码生成 → 单元测试\n"
        f"⏱️ 预计 3-5 分钟完成"
    ))


@router.post("/feishu")
async def feishu_webhook(request: Request):
    """飞书事件回调"""
    body = await request.json()

    # URL 验证 (飞书首次配置时)
    if body.get("type") == "url_verification":
        return JSONResponse({"challenge": body.get("challenge", "")})

    # 消息事件
    event = body.get("event", {})
    msg_type = event.get("message", {}).get("message_type", "")

    if msg_type == "text":
        content = json.loads(event["message"]["content"]).get("text", "")
        open_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "")
        if content and open_id:
            # 后台异步处理（先回 200 避免飞书重试）
            import asyncio
            asyncio.create_task(_process_spec_request(content, open_id))

    return JSONResponse({"code": 0})
