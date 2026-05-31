"""
Feishu Bot — 官方 SDK 长连接模式 + 进度回推
"""

import asyncio
import json
import threading
import time
import uuid

import lark_oapi as lark
from config import DOCS_INPUT, settings

FEISHU_APP_ID = settings.feishu_app_id
FEISHU_APP_SECRET = settings.feishu_app_secret

# batch_id → open_id 映射（用于进度回推）
_contact_map: dict[str, str] = {}


def _get_token() -> str:
    import httpx
    r = httpx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                    json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET})
    return r.json()["tenant_access_token"]


def _reply_text(open_id: str, text: str):
    import httpx
    token = _get_token()
    httpx.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        headers={"Authorization": f"Bearer {token}"},
        json={"receive_id": open_id, "msg_type": "text",
              "content": json.dumps({"text": text})},
    )


def push_feishu_progress(batch_id: str, message: str):
    """外部调用——流水线进度回推飞书"""
    open_id = _contact_map.get(batch_id)
    if open_id:
        _reply_text(open_id, message)


def _on_receive_message(data: lark.im.v1.P2ImMessageReceiveV1):
    msg = data.event.message
    if msg.message_type != "text":
        return
    content = json.loads(msg.content)
    text = content.get("text", "")
    open_id = data.event.sender.sender_id.open_id
    if not text or not open_id:
        return
    if len(text.strip()) < 5:
        _reply_text(open_id, "请详细描述～\n例如：做一个员工临时车辆预约系统")
        return

    _reply_text(open_id, f"⏳ 收到，正在生成规格书...\n📝 {text[:40]}...")

    # 调 LLM 生成规格书
    try:
        import litellm
        model = settings.prompt_model or settings.primary_model
        extra = {}
        if "qwen" in model:
            extra = {"api_base": settings.qwen_vllm_api_base, "api_key": "not-needed"}
        resp = litellm.completion(model=model, messages=[
            {"role":"system","content":"根据用户的一句话需求，生成完整的产品规格说明书（Markdown，7章）。只输出Markdown。"},
            {"role":"user","content": text}], max_tokens=4096, temperature=0.3, **extra)
        spec_md = resp.choices[0].message.content.strip()
    except Exception:
        spec_md = f"# 项目概述\n\n{text}\n\n## 功能需求\n\n待补充..."

    fname = f"feishu_{uuid.uuid4().hex[:8]}.md"
    (DOCS_INPUT / fname).write_text(spec_md, encoding="utf-8")

    pname = text.strip()[:30]
    bid = f"batch_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    from orchestrator.state_manager import StateManager
    StateManager(bid).init_batch(pname, fname)
    _contact_map[bid] = open_id  # 记录映射，用于进度回推

    from orchestrator.engine import OrchestratorEngine
    threading.Thread(target=lambda: OrchestratorEngine(bid).run_auto(), daemon=True).start()

    _reply_text(open_id, (
        f"✅ 已开始!\n📋 {pname}\n🔢 {bid[-10:]}\n"
        f"⚙️ 概要设计 → 代码生成 → 单元测试\n⏱️ 3-5 min"
    ))


def _start_lark_client():
    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(_on_receive_message)
        .build())
    client = lark.ws.Client(FEISHU_APP_ID, FEISHU_APP_SECRET,
                            event_handler=event_handler, log_level=lark.LogLevel.INFO)
    print("[Feishu] Starting WSS...")
    client.start()


def start_feishu_wss():
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("[Feishu] Skipped")
        return
    threading.Thread(target=_start_lark_client, daemon=True).start()
