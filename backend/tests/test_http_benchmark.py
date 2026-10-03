import httpx
from fastapi.testclient import TestClient

from app.agents.experience.provider import DeepSeekProvider
from scripts.http_plan_bench import summarize
from scripts.real_http_comparison import service_dependency
from app.main import create_app
from app.services.rest_service import get_rest_service


def test_http_summary_keeps_failed_requests_in_tail_latency():
    report = summarize([{"elapsed_ms": 10, "valid": True, "error": None},
                        {"elapsed_ms": 1000, "valid": False, "error": "timeout"}])
    assert report == {"requests": 2, "valid_plans": 1, "errors": 1, "p50_ms": 10, "p95_ms": 1000}


def test_real_comparison_injects_service_without_fastapi_copying_locks(service):
    app = create_app()
    app.dependency_overrides[get_rest_service] = service_dependency(service)
    with TestClient(app) as client:
        assert client.get("/api/bootstrap", params={"accountId": "demo-account"}).status_code == 200


def test_pooled_provider_reuses_client_and_closes_it(monkeypatch):
    clients, calls = [], []

    class Client:
        closed = False

        def __init__(self, **kwargs):
            clients.append(self)

        def post(self, url, **kwargs):
            calls.append(kwargs)
            return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

        def close(self):
            self.closed = True

    monkeypatch.setattr(httpx, "Client", Client)
    provider = DeepSeekProvider("secret", "test", reuse_connections=True)
    assert provider.complete_json("system", "a", 1) == "{}"
    assert provider.complete_json("system", "b", 1) == "{}"
    assert len(clients) == 1 and len(calls) == 2
    assert calls[0]["json"]["messages"][-1]["content"] == "a"
    assert calls[1]["json"]["messages"][-1]["content"] == "b"
    provider.close()
    assert clients[0].closed
