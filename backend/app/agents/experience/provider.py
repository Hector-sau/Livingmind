"""Chat providers. Only the HTTP shape lives here; prompts and validation live in agent.py.

Errors never include request headers or the API key.
"""

from __future__ import annotations

from typing import Callable, Literal, Protocol

import httpx

ProviderErrorKind = Literal["not_configured", "timeout", "network", "http", "empty", "truncated"]


class ProviderError(Exception):
    def __init__(self, kind: ProviderErrorKind, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


class ChatProvider(Protocol):
    name: str
    model: str

    def complete_json(self, system: str, user: str, timeout_s: float) -> str:
        """Return the model's raw text, which should be a JSON object."""


class DeepSeekProvider:
    """OpenAI-compatible chat completions at https://api.deepseek.com (docs: api-docs.deepseek.com)."""

    name = "deepseek"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.deepseek.com",
        max_tokens: int = 2000,
        usage_sink: Callable[[dict], None] | None = None,
    ):
        self._api_key = api_key
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._max_tokens = max_tokens
        self._usage_sink = usage_sink

    def complete_json(self, system: str, user: str, timeout_s: float) -> str:
        if not self._api_key:
            raise ProviderError("not_configured", "DEEPSEEK_API_KEY 未配置")
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": self._max_tokens,
            "stream": False,
        }
        try:
            res = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=timeout_s,
            )
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", f"模型响应超过 {timeout_s:g} 秒") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("network", f"无法连接模型服务：{type(exc).__name__}") from exc
        if res.status_code != 200:
            raise ProviderError("http", f"模型服务返回 HTTP {res.status_code}")
        try:
            payload = res.json()
            choice = payload["choices"][0]
            content = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("empty", "模型响应格式异常") from exc
        # Optional benchmark-only sink. Never send prompts, completions or credentials to it.
        if self._usage_sink is not None and isinstance(payload.get("usage"), dict):
            try:
                self._usage_sink({key: payload["usage"].get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens")})
            except Exception:
                pass  # accounting must not change the user-facing plan result
        # A completion cut off at the budget is not a usable answer even when it happens to
        # parse: the model was still writing. Reported separately from a genuinely empty reply
        # because the fix is different -- raise LIVINGMIND_MODEL_MAX_TOKENS, not retry.
        if isinstance(choice, dict) and choice.get("finish_reason") == "length":
            raise ProviderError("truncated", f"模型输出在预算内没写完（{describe_empty(choice)}）")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("empty", f"模型没有返回内容（{describe_empty(choice)}）")
        return content


def describe_empty(choice: object) -> str:
    """Why an empty completion came back, in shape only.

    A blank `content` is not one failure but several: the token budget spent before any
    answer was written (`finish_reason=length`), a filtered response, or a genuinely empty
    reply. Operators and the latency benchmark both need to tell them apart. This reports
    the finish reason and whether a reasoning field was present — never any model or user
    text, which would put the utterance into logs and activity records.
    """
    if not isinstance(choice, dict):
        return "响应结构异常"
    parts = [f"finish_reason={choice.get('finish_reason') or '未给出'}"]
    message = choice.get("message")
    if isinstance(message, dict):
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning.strip():
            parts.append(f"另有 reasoning_content {len(reasoning)} 字")
    return "，".join(parts)
