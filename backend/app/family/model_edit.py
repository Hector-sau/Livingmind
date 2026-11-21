"""Optional interpretation of one explicit device edit. No action execution tools."""
import json
import os
import re


def configured_provider():
    if os.getenv("LIVINGMIND_FAMILY_EDITOR", "rule") != "model" or not os.getenv("DEEPSEEK_API_KEY"):
        return None
    # Import only for opt-in deployments with the existing backend dependencies.
    from app.agents.experience.provider import DeepSeekProvider
    from app import config
    return DeepSeekProvider(config.DEEPSEEK_API_KEY, config.DEEPSEEK_MODEL, config.DEEPSEEK_BASE_URL)


def interpret(provider, text, devices):
    """Treat uncertain, unsupported, ambiguous or negative requests as clarification."""
    matched = [d for d in devices if d["name"] in text]
    if len(matched) != 1 or re.search(r"不|别|勿|禁止|取消|不要|暂停|停止", text):
        return None
    device = matched[0]
    prompt = ("你只解释今晚一台设备的修改请求。仅在输入明确要求调整列出的设备时输出"
              '{"deviceId":"...","value":整数或null}。不能确定时输出 {"clarify":true}。'
              "没有执行工具，不得添加或猜测其他设备。")
    try:
        raw = provider.complete_json(prompt, json.dumps({"text": text, "device": device}, ensure_ascii=False), 6.0)
        result = json.loads(raw)
    except Exception:
        # An unavailable provider or malformed answer leaves the standing proposal untouched.
        return None
    if not isinstance(result, dict) or set(result) != {"deviceId", "value"}:
        return None
    if result["deviceId"] != device["id"] or not (result["value"] is None or type(result["value"]) is int):
        return None
    return {"onlyDeviceId": result["deviceId"], "value": result["value"]}
