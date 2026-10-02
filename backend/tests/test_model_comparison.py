"""Benchmark bookkeeping is deterministic; these tests do not call a paid model."""

import json

import httpx

from app.agents.experience.provider import DeepSeekProvider
from scripts.compare_models import summarize


def test_summary_separates_fallbacks_and_reports_inclusive_latency():
    rows = [
        {"model": "a", "verdict": "pass", "wall_ms": 100, "usage": {"total_tokens": 20}},
        {"model": "b", "verdict": "pass", "wall_ms": 200, "usage": {"total_tokens": 30}},
        {"model": "a", "verdict": "fallback", "wall_ms": 6000, "usage": None},
    ]
    assert summarize(rows, "a") == {
        "model": "a", "total": 2, "semantic_pass": 1, "semantic_fail": 0,
        "fallback": 1, "p50_ms": 100, "p95_ms": 6000,
        "total_tokens_reported": 20, "usage_reported_count": 1,
    }


def test_provider_emits_token_counts_without_prompt_or_key(monkeypatch):
    usage = []
    response = httpx.Response(200, json={
        "choices": [{"message": {"content": json.dumps({"goal": "ok"})}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30, "other": "not needed"},
    }, request=httpx.Request("POST", "https://example.test/chat/completions"))
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)
    provider = DeepSeekProvider("secret", "test-model", "https://example.test", usage_sink=usage.append)
    assert provider.complete_json("private system", "private user", 1) == '{"goal": "ok"}'
    assert usage == [{"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}]
