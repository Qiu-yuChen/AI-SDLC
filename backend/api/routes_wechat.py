"""
WeChat Official Account webhook — 一句话生成项目
配置：微信公众平台 → 开发 → 基本配置 → 服务器配置
  URL: https://your-domain/api/wechat
  Token: 与 .env 中的 WECHAT_TOKEN 一致
"""

import hashlib
import time
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse, Response

from config import settings

router = APIRouter(tags=["wechat"])

WECHAT_TOKEN = settings.wechat_token
WECHAT_AES_KEY = getattr(settings, "wechat_aes_key", "")


def _check_signature(signature: str, timestamp: str, nonce: str) -> bool:
    tmp = sorted([WECHAT_TOKEN, timestamp, nonce])
    tmp_str = "".join(tmp)
    return hashlib.sha1(tmp_str.encode()).hexdigest() == signature


def _build_text_reply(from_user: str, to_user: str, content: str) -> str:
    return f"""<xml>
<ToUserName><![CDATA[{from_user}]]></ToUserName>
<FromUserName><![CDATA[{to_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""


def _parse_text(xml: str) -> tuple[str, str, str]:
    """Extract from_user, to_user, content from WeChat XML"""
    import re
    from_user = re.search(r"<FromUserName><!\[CDATA\[(.*?)\]\]></FromUserName>", xml)
    to_user = re.search(r"<ToUserName><!\[CDATA\[(.*?)\]\]></ToUserName>", xml)
    content = re.search(r"<Content><!\[CDATA\[(.*?)\]\]></Content>", xml)
    return (
        from_user.group(1) if from_user else "",
        to_user.group(1) if to_user else "",
        content.group(1) if content else "",
    )


async def _process_spec_request(text: str) -> str:
    """将微信消息作为需求，走提示词优化 + 创建批次流水线"""
    try:
        import litellm
        from agents.spec_preprocessor import preprocess_prompt_only
    except Exception:
        return "AI-SDLC 后端未就绪，请稍后再试"

    if len(text.strip()) < 3:
        return "请详细描述你想要开发的应用～\n\n例如：做一个员工临时车辆预约系统"

    try:
        # 调 AI 生成 Markdown 规格书
        resp = litellm.completion(
            model=settings.prompt_model or settings.primary_model,
            messages=[{
                "role": "system",
                "content": "根据用户的一句话需求，生成完整的产品规格说明书（Markdown格式，含7个标准章节）。只输出Markdown。",
            }, {
                "role": "user",
                "content": text,
            }],
            max_tokens=4096, temperature=0.3,
        )
        spec_md = resp.choices[0].message.content.strip()
    except Exception:
        spec_md = f"# 项目概述\n\n{text}\n\n## 功能需求\n\n待补充..."

    # 保存规格书
    from config import DOCS_INPUT
    import uuid
    filename = f"wechat_spec_{uuid.uuid4().hex[:8]}.md"
    (DOCS_INPUT / filename).write_text(spec_md, encoding="utf-8")

    # 创建批次
    from orchestrator.state_manager import StateManager
    project_name = text.strip()[:30]
    batch_id = f"batch_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    sm = StateManager(batch_id)
    sm.create(filename, project_name)

    # 异步启动
    import asyncio
    from orchestrator.engine import OrchestratorEngine
    async def _run():
        engine = OrchestratorEngine(batch_id)
        engine.run_auto()
    asyncio.create_task(_run())

    return (
        f"✅ 已收到需求，开始自动开发：\n"
        f"📋 {project_name}\n"
        f"🔢 批次：{batch_id[-10:]}\n\n"
        f"流水线：概要设计 → 代码生成 → 单元测试\n"
        f"预计 3-5 分钟完成，可在 Web UI 查看进度"
    )


@router.get("/wechat")
async def wechat_verify(signature: str = "", timestamp: str = "", nonce: str = "", echostr: str = ""):
    """微信服务器配置验证（GET）"""
    if _check_signature(signature, timestamp, nonce):
        return PlainTextResponse(echostr)
    raise HTTPException(403, "Signature verification failed")


@router.post("/wechat")
async def wechat_message(request: Request):
    """接收微信用户消息（POST），处理并回复"""
    try:
        body = await request.body()
        xml_text = body.decode("utf-8")
    except Exception:
        raise HTTPException(400, "Invalid request body")

    msg_type_match = __import__("re").search(r"<MsgType><!\[CDATA\[(.*?)\]\]></MsgType>", xml_text)
    msg_type = msg_type_match.group(1) if msg_type_match else ""

    if msg_type == "text":
        from_user, to_user, content = _parse_text(xml_text)
        reply = await _process_spec_request(content)
        return Response(
            content=_build_text_reply(from_user, to_user, reply),
            media_type="application/xml",
        )

    if msg_type == "event":
        return PlainTextResponse("success")

    # 非文本消息：返回引导
    from_user, to_user, _ = _parse_text(xml_text)
    return Response(
        content=_build_text_reply(from_user, to_user, "📎 请用文字描述你想要开发的应用～"),
        media_type="application/xml",
    )
