"""Adversarial Phase 4 checks using only fake models and intercepted HTTP."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Event

import chess
import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.game import GameStore
from backend.providers import (
    AnthropicAdapter,
    GeminiAdapter,
    ModelPosition,
    OpenAIAdapter,
    OpenRouterAdapter,
    ProviderBinding,
    ProviderError,
)


ADAPTERS = (OpenAIAdapter, AnthropicAdapter, GeminiAdapter, OpenRouterAdapter)
POSITION = ModelPosition(chess.STARTING_FEN, "white", ("e2e4", "g1f3"))


@pytest.mark.parametrize("adapter_type", ADAPTERS)
@pytest.mark.parametrize("response", [
    httpx.Response(200, text="not json"),
    httpx.Response(200, json=["e2e4"]),
    httpx.Response(200, json={"error": "secret-key upstream detail"}),
    httpx.Response(429, json={"error": "secret-key upstream detail"}),
])
def test_adapter_rejects_bad_http_bodies_without_exposing_upstream(adapter_type, response):
    adapter = adapter_type("secret-key", "server-model", httpx.MockTransport(lambda _: response))
    with pytest.raises(ProviderError) as caught:
        asyncio.run(adapter.choose_move(POSITION))
    assert "secret-key" not in str(caught.value)
    assert "upstream detail" not in str(caught.value)


@pytest.mark.parametrize("adapter_type,payloads", [
    (OpenAIAdapter, [
        {"status": "incomplete", "output": [{"type": "message", "content": [{"type": "output_text", "text": "e2e4"}]}]},
        {"status": "completed", "output": [None]},
        {"status": "completed", "output": [{"type": "message", "content": [None]}]},
        {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}]},
    ]),
    (AnthropicAdapter, [
        {"content": None}, {"content": [None]},
        {"content": [{"type": "tool_use", "input": {"move": "e2e4"}}]},
    ]),
    (GeminiAdapter, [
        {"candidates": []}, {"candidates": [None]},
        {"candidates": [{"content": {"parts": []}}]},
        {"promptFeedback": {"blockReason": "SAFETY"}},
    ]),
    (OpenRouterAdapter, [
        {"choices": []}, {"choices": [None]},
        {"choices": [{"message": {"content": None}}]},
    ]),
])
def test_adapter_rejects_unexpected_response_shapes(adapter_type, payloads):
    for payload in payloads:
        adapter = adapter_type("secret-key", "server-model", httpx.MockTransport(
            lambda _, body=payload: httpx.Response(200, json=body)
        ))
        with pytest.raises(ProviderError) as caught:
            asyncio.run(adapter.choose_move(POSITION))
        assert "secret-key" not in str(caught.value)


@pytest.mark.parametrize("adapter_type,payload", [
    (AnthropicAdapter, {"stop_reason": "max_tokens", "content": [{"type": "text", "text": "e2e4"}]}),
    (GeminiAdapter, {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "e2e4"}]}}]}),
    (OpenRouterAdapter, {"choices": [{"finish_reason": "length", "message": {"content": "e2e4"}}]}),
])
def test_adapter_rejects_explicitly_truncated_output(adapter_type, payload):
    adapter = adapter_type("secret-key", "server-model", httpx.MockTransport(
        lambda _: httpx.Response(200, json=payload)
    ))
    with pytest.raises(ProviderError):
        asyncio.run(adapter.choose_move(POSITION))


@pytest.mark.parametrize("adapter_type", ADAPTERS)
def test_adapter_transport_error_is_sanitized(adapter_type):
    def fail(request):
        raise httpx.ConnectError("secret-key upstream detail", request=request)

    adapter = adapter_type("secret-key", "server-model", httpx.MockTransport(fail))
    with pytest.raises(ProviderError) as caught:
        asyncio.run(adapter.choose_move(POSITION))
    assert str(caught.value) == "Model provider failed"


@pytest.mark.parametrize("adapter_type", ADAPTERS)
def test_adapter_request_does_not_put_key_in_url_or_body(adapter_type):
    requests = []
    payloads = {
        OpenAIAdapter: {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "e2e4"}]}]},
        AnthropicAdapter: {"content": [{"type": "text", "text": "e2e4"}]},
        GeminiAdapter: {"candidates": [{"content": {"parts": [{"text": "e2e4"}]}}]},
        OpenRouterAdapter: {"choices": [{"message": {"content": "e2e4"}}]},
    }

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=payloads[adapter_type])

    adapter = adapter_type("secret-key", "server-model", httpx.MockTransport(respond))
    assert asyncio.run(adapter.choose_move(POSITION)) == "e2e4"
    request = requests[0]
    body = json.loads(request.content)
    assert request.method == "POST"
    assert "secret-key" not in str(request.url)
    assert "secret-key" not in request.content.decode()
    if adapter_type is GeminiAdapter:
        assert "server-model" in str(request.url)
    else:
        assert body["model"] == "server-model"
    assert POSITION.fen in request.content.decode()
    assert "e2e4" in request.content.decode()
    assert "g1f3" in request.content.decode()


class Clock:
    now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeModel:
    def __init__(self, clock, result="e7e5", delay=0, error=None):
        self.clock, self.result, self.delay, self.error = clock, result, delay, error
        self.calls = 0

    async def choose_move(self, position):
        self.calls += 1
        self.clock.advance(self.delay)
        if self.error:
            raise self.error
        return self.result


def client_for(model, clock):
    return TestClient(create_app(GameStore(clock=clock), {"openai": ProviderBinding("server-model", model)}))


def model_to_move(client):
    game_id = client.post("/games", json={"model_provider": "openai", "model_color": "black", "time_control": "3+2"}).json()["game_id"]
    assert client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).status_code == 200
    return game_id


@pytest.mark.parametrize("result", [None, 42, {"move": "e7e5"}, ["e7e5"], "e7e6q", "e2e4", "e7e5 then prose"])
def test_invalid_model_results_are_502_and_leave_board_unchanged(result):
    clock = Clock()
    with client_for(FakeModel(clock, result=result, delay=4), clock) as client:
        game_id = model_to_move(client)
        response = client.post(f"/games/{game_id}/model-turn")
        assert response.status_code == 502
        assert response.json() == {"detail": "Model turn failed"}
        state = client.get(f"/games/{game_id}").json()
        assert state["pgn"] == "1. e4 *"
        assert state["black_clock_ms"] == (172000 if isinstance(result, str) else 176000)
        assert state["active_clock"] == "black"


def test_game_creation_rejects_client_credentials_and_provider_url():
    clock = Clock()
    with client_for(FakeModel(clock), clock) as client:
        for extra in ({"api_key": "secret-key"}, {"provider_url": "https://example.invalid"}):
            payload = {"model_provider": "openai", "model_color": "black", **extra}
            response = client.post("/games", json=payload)
            assert response.status_code == 422
            assert "secret-key" not in response.text


@pytest.mark.parametrize("action", ["draw", "resign", "timeout"])
def test_pending_model_result_cannot_change_terminal_game(action):
    clock = Clock()
    started, release = Event(), Event()

    class WaitingModel:
        async def choose_move(self, position):
            started.set()
            await asyncio.to_thread(release.wait)
            return "e7e5"

    with client_for(WaitingModel(), clock) as client:
        game_id = model_to_move(client)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(client.post, f"/games/{game_id}/model-turn")
            try:
                assert started.wait(2)
                assert client.post(f"/games/{game_id}/model-turn").status_code == 409
                if action == "draw":
                    terminal = client.post(f"/games/{game_id}/draw-offer", json={"accepted": True}).json()
                elif action == "resign":
                    terminal = client.post(f"/games/{game_id}/resign", json={"color": "white"}).json()
                else:
                    clock.advance(180)
                    terminal = client.get(f"/games/{game_id}").json()
                assert terminal["game_status"] == "game-over"
            finally:
                release.set()
            response = pending.result(2)
        assert response.status_code == (200 if action == "timeout" else 409)
        state = client.get(f"/games/{game_id}").json()
        assert state["fen"] == terminal["fen"]
        assert state["result"] == terminal["result"]
        assert state["termination_reason"] == terminal["termination_reason"]
        assert state["active_clock"] is None


def test_success_adds_one_increment_after_provider_latency():
    clock = Clock()
    model = FakeModel(clock, result="a7a5", delay=3)
    with client_for(model, clock) as client:
        game_id = model_to_move(client)
        assert client.post(f"/games/{game_id}/model-turn").status_code == 200
        state = client.get(f"/games/{game_id}").json()
        assert state["black_clock_ms"] == 179000
        assert model.calls == 1


def test_failed_turn_retries_within_original_budget():
    clock = Clock()

    class SequenceModel:
        calls = 0

        async def choose_move(self, position):
            self.calls += 1
            clock.advance(1)
            return "not-a-move" if self.calls == 1 else "e7e5"

    model = SequenceModel()
    with client_for(model, clock) as client:
        game_id = model_to_move(client)
        retried = client.post(f"/games/{game_id}/model-turn").json()
        assert model.calls == 2
        assert retried["black_clock_ms"] == 180000
        assert retried["illegal_model_move_count"] == 1
        assert retried["pgn"] == "1. e4 e5 *"


def test_terminal_game_rejects_model_turn_without_calling_provider():
    clock = Clock()
    model = FakeModel(clock)
    with client_for(model, clock) as client:
        game_id = model_to_move(client)
        terminal = client.post(f"/games/{game_id}/draw-offer", json={"accepted": True}).json()
        assert terminal["game_status"] == "game-over"
        assert client.post(f"/games/{game_id}/model-turn").status_code == 409
        assert model.calls == 0
