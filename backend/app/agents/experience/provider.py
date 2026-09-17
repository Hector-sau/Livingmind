"""Chat providers. Only the HTTP shape lives here; prompts and validation live in agent.py.

Errors never include request headers or the API key.
"""

from __future__ import annotations

from typing import Literal, Protocol

import httpx

ProviderErrorKind = Literal["not_configured", "timeout", "network", "http", "empty"]


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

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.deepseek.com"):
        self._api_key = api_key
        self.model = model
        self._base_url = base_url.rstrip("/")

    def complete_json(self, system: str, user: str, timeout_s: float) -> str:
        if not self._api_key:
            raise ProviderError("not_configured", "DEEPSEEK_API_KEY 未配置")
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": 400,
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
            content = res.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("empty", "模型响应格式异常") from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("empty", "模型没有返回内容")
        return content
