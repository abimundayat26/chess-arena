"""Provider discovery and real adapter draw requests use intercepted HTTP."""

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.game import GameStore
from backend.providers import AnthropicAdapter, GeminiAdapter, OpenAIAdapter, OpenRouterAdapter, ProviderBinding, ProviderError
from backend.live_context import ModelPosition


def test_provider_discovery_exposes_only_names_and_model_ids():
    class Fake:
        pass

    with TestClient(create_app(GameStore(), {"openai": ProviderBinding("local-test-model", Fake())})) as client:
        response = client.get("/providers")
        assert response.json() == [{"provider": "openai", "model": "local-test-model"}]
        assert "api_key" not in response.text


@pytest.mark.parametrize("adapter_type,wrap", [
    (OpenAIAdapter, lambda text: {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}),
    (AnthropicAdapter, lambda text: {"content": [{"type": "text", "text": text}]}),
    (GeminiAdapter, lambda text: {"candidates": [{"content": {"parts": [{"text": text}]}}]}),
    (OpenRouterAdapter, lambda text: {"choices": [{"message": {"content": text}}]}),
])
def test_provider_draw_prompt_and_strict_decision(adapter_type, wrap):
    payloads = []
    answers = iter(["ACCEPT", "DECLINE", "ACCEPT because I should", "unknown"])

    def respond(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json=wrap(next(answers)))

    adapter = adapter_type("server-secret", "test-model", httpx.MockTransport(respond))
    position = ModelPosition("valid-fen", "white", ("e2e4",), model_color="black")
    assert asyncio.run(adapter.choose_draw(position)) is True
    assert asyncio.run(adapter.choose_draw(position)) is False
    with pytest.raises(ProviderError):
        asyncio.run(adapter.choose_draw(position))
    with pytest.raises(ProviderError):
        asyncio.run(adapter.choose_draw(position))
    assert all("exactly accept or decline" in json.dumps(payload).lower() for payload in payloads)
    assert all("your color: black" in json.dumps(payload).lower() for payload in payloads)
    assert all("server-secret" not in json.dumps(payload) for payload in payloads)


def test_empty_text_is_counted_as_illegal_proposal():
    def respond(_request):
        return httpx.Response(200, json={"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": ""}]}]})

    adapter = OpenAIAdapter("server-secret", "test-model", httpx.MockTransport(respond))
    with TestClient(create_app(GameStore(), {"openai": ProviderBinding("test-model", adapter)})) as client:
        game_id = client.post("/games", json={"model_provider": "openai", "model_color": "black"}).json()["game_id"]
        client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"})
        result = client.post(f"/games/{game_id}/model-turn")
        assert result.status_code == 200
        assert result.json()["termination_reason"] == "model_forfeit"
        assert result.json()["illegal_model_move_count"] == 5
