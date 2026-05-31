"""
LiteLLM patches — fix GLM-5.1 thinking mode (empty content + reasoning_content).

GLM-5.x returns actual output in `reasoning_content` and `content=""` when
thinking mode is active.  We apply two fixes:

1. Inject `extra_body={"thinking": {"type": "disabled"}}` for GLM models
   so the API returns content directly (requires `litellm.drop_params=True`).

2. Fallback: if content is still empty but reasoning_content exists,
   copy reasoning_content into content so CrewAI / downstream code works.
"""

import litellm

_original_completion = litellm.completion


def _is_glm_model(model: str) -> bool:
    return "glm" in model.lower()


def _patched_completion(*args, **kwargs):
    model = kwargs.get("model", args[0] if args else "")
    if _is_glm_model(model):
        eb = kwargs.get("extra_body", {})
        if "thinking" not in eb:
            eb["thinking"] = {"type": "disabled"}
            kwargs["extra_body"] = eb

    resp = _original_completion(*args, **kwargs)

    for choice in resp.choices:
        msg = choice.message
        rc = getattr(msg, "reasoning_content", None)
        if not rc:
            extra = getattr(msg, "model_extra", None) or {}
            rc = extra.get("reasoning_content")
        if rc and not (msg.content and msg.content.strip()):
            msg.content = rc
            if hasattr(msg, "reasoning_content"):
                msg.reasoning_content = None

    return resp


def apply_llm_patches():
    litellm.drop_params = True
    litellm.completion = _patched_completion
