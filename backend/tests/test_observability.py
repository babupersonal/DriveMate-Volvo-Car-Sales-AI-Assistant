"""Offline checks for architecture metadata, metrics and typed API errors."""
import httpx
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.components import load_components


def test_component_registry_is_valid_and_public():
    registry = load_components()
    ids = {component["id"] for component in registry["components"]}
    assert registry["architecture"] == "hybrid_single_agent"
    assert {"vehicle_specialist", "support_specialist", "safety_router"} <= ids
    with TestClient(main.app) as client:
        response = client.get("/api/system/components")
        assert response.status_code == 200
        assert response.json()["components"]


def test_successful_chat_records_anonymous_route_metric(monkeypatch):
    async def fake_chat(_messages):
        return "測試回答", ["get_vehicle_details"], "llm_tool_call"

    monkeypatch.setattr(main, "chat", fake_chat)
    with TestClient(main.app) as client:
        response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "EX30 售價"}]})
        assert response.status_code == 200
        assert response.json()["request_id"]
        metrics = client.get("/api/metrics/routes").json()
    assert metrics["total_requests"] >= 1
    assert metrics["tool_counts"]["get_vehicle_details"] >= 1
    assert "prompts and replies are not logged" in metrics["privacy"]


def test_ollama_connection_error_has_stable_code(monkeypatch):
    async def unavailable(_messages):
        request = httpx.Request("POST", "http://127.0.0.1:11434/api/chat")
        raise httpx.ConnectError("offline", request=request)

    monkeypatch.setattr(main, "chat", unavailable)
    with TestClient(main.app) as client:
        response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "EX30 售價"}]})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "OLLAMA_UNAVAILABLE"
