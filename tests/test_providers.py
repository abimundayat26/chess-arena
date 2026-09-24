"""Provider adapters and one-turn API, without external credentials or network calls."""

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
    AnthropicAdapter, GeminiAdapter, ModelPosition, OpenAIAdapter,
    OpenRouterAdapter, ProviderBinding, ProviderError,
)


class Clock:
    now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeModel:
    def __init__(self, clock, result="e7e5", delay=0, error=None):
        self.clock = clock
        self.result = result
        self.delay = delay
        self.error = error
        self.positions = []

    async def choose_move(self, position):
        self.positions.append(position)
        self.clock.advance(self.delay)
        if self.error:
            raise self.error
        return self.result


def client_with_model(model, clock):
    return TestClient(create_app(GameStore(clock=clock), {
        "openai": ProviderBinding("server-model", model),
    }))


def bound_game(client, color="black"):
    response = client.post("/games", json={
        "time_control": "3+2", "model_provider": "openai", "model_color": color,
    })
    assert response.status_code == 201
    return response.json()["game_id"]


@pytest.mark.parametrize("adapter_type,payload", [
    (OpenAIAdapter, {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": " e7e5 "}]}]}),
    (AnthropicAdapter, {"content": [{"type": "text", "text": " e7e5 "}]}),
    (GeminiAdapter, {"candidates": [{"content": {"parts": [{"text": " e7e5 "}]}}]}),
    (OpenRouterAdapter, {"choices": [{"message": {"content": " e7e5 "}}]}),
])
def test_adapters_send_position_and_extract_uci(adapter_type, payload):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=payload)

    adapter = adapter_type("secret-key", "server-model", httpx.MockTransport(respond))
    position = ModelPosition(chess.STARTING_FEN, "white", ("e2e4", "g1f3"))
    assert asyncio.run(adapter.choose_move(position)) == "e7e5"
    request = requests[0]
    body = json.loads(request.content)
    assert "e2e4" in json.dumps(body)
    assert chess.STARTING_FEN in json.dumps(body)
    assert "secret-key" not in json.dumps(body)
    assert "secret-key" in list(request.headers.values()) or "Bearer secret-key" in list(request.headers.values())
    if adapter_type is not GeminiAdapter:
        assert "secret-key" not in str(request.headers)
    assert request.url.host in {
        "api.openai.com", "api.anthropic.com",
        "generativelanguage.googleapis.com", "openrouter.ai",
    }


@pytest.mark.parametrize("adapter_type", [OpenAIAdapter, AnthropicAdapter, GeminiAdapter, OpenRouterAdapter])
def test_adapters_sanitize_upstream_failures(adapter_type):
    adapter = adapter_type("secret-key", "server-model", httpx.MockTransport(
        lambda request: httpx.Response(401, json={"error": "secret-key upstream detail"})
    ))
    with pytest.raises(ProviderError) as caught:
        asyncio.run(adapter.choose_move(ModelPosition(chess.STARTING_FEN, "white", ("e2e4",))))
    assert "secret-key" not in str(caught.value)
    assert "upstream detail" not in str(caught.value)


@pytest.mark.parametrize("adapter_type", [OpenAIAdapter, AnthropicAdapter, GeminiAdapter, OpenRouterAdapter])
def test_adapters_reject_missing_move_text(adapter_type):
    adapter = adapter_type("secret-key", "server-model", httpx.MockTransport(
        lambda request: httpx.Response(200, json={})
    ))
    with pytest.raises(ProviderError):
        asyncio.run(adapter.choose_move(ModelPosition(chess.STARTING_FEN, "white", ("e2e4",))))


def test_model_turn_applies_one_valid_move_and_charges_latency():
    clock = Clock()
    model = FakeModel(clock, delay=4.25)
    with client_with_model(model, clock) as client:
        game_id = bound_game(client)
        first = client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).json()
        assert first["white_clock_ms"] == 182000
        state = client.post(f"/games/{game_id}/model-turn").json()
        assert state["pgn"] == "1. e4 e5 *"
        assert state["black_clock_ms"] == 177750
        assert state["active_clock"] == "white"
        assert model.positions == [ModelPosition(first["fen"], "black", tuple(first["legal_moves"]))]
        assert client.post(f"/games/{game_id}/model-turn").status_code == 409


@pytest.mark.parametrize("result", ["e7e6q", "bad", "e2e4", "", "e7e5 and prose"])
def test_illegal_model_output_keeps_board_and_charges_clock(result):
    clock = Clock()
    with client_with_model(FakeModel(clock, result=result, delay=3), clock) as client:
        game_id = bound_game(client)
        client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"})
        response = client.post(f"/games/{game_id}/model-turn")
        assert response.status_code == 502
        state = client.get(f"/games/{game_id}").json()
        assert state["pgn"] == "1. e4 *"
        assert state["black_clock_ms"] == 174000
        assert state["active_clock"] == "black"


def test_provider_exception_is_sanitized_and_charged():
    clock = Clock()
    with client_with_model(FakeModel(clock, delay=7, error=RuntimeError("secret-key leaked")), clock) as client:
        game_id = bound_game(client)
        client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"})
        response = client.post(f"/games/{game_id}/model-turn")
        assert response.status_code == 502
        assert "secret-key" not in response.text
        assert client.get(f"/games/{game_id}").json()["black_clock_ms"] == 173000


def test_timeout_during_provider_call_wins_over_returned_move_or_error():
    for error in (None, RuntimeError("provider failed")):
        clock = Clock()
        with client_with_model(FakeModel(clock, delay=181, error=error), clock) as client:
            game_id = bound_game(client)
            client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"})
            response = client.post(f"/games/{game_id}/model-turn")
            assert response.status_code == 200
            state = response.json()
            assert state["game_status"] == "game-over"
            assert state["termination_reason"] == "timeout"
            assert state["result"] == "1-0"
            assert state["pgn"] == "1. e4 1-0"
            assert state["black_clock_ms"] == 0


def test_model_turn_api_rejects_unbound_wrong_turn_unknown_and_client_move():
    clock = Clock()
    with client_with_model(FakeModel(clock), clock) as client:
        assert client.post("/games/missing/model-turn").status_code == 404
        unbound = client.post("/games").json()["game_id"]
        assert client.post(f"/games/{unbound}/model-turn").status_code == 409
        game_id = bound_game(client)
        assert client.post(f"/games/{game_id}/model-turn").status_code == 409
        client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"})
        assert client.post(f"/games/{game_id}/moves", json={"uci": "e7e5"}).status_code == 409
        assert client.post(f"/games/{game_id}/model-turn").status_code == 200


def test_creation_requires_configured_provider_and_pairing():
    with TestClient(create_app(GameStore(clock=Clock()), providers={})) as client:
        for payload in (
            {"model_provider": "openai", "model_color": "black"},
            {"model_provider": "openai"},
            {"model_color": "black"},
        ):
            response = client.post("/games", json=payload)
            assert response.status_code in (422, 503)
        assert client.post("/games", json={"model_provider": "unknown", "model_color": "black"}).status_code == 422
        assert client.post("/games").status_code == 201


def test_concurrent_model_turn_is_rejected_and_resignation_prevents_stale_move():
    clock = Clock()
    started = Event()
    release = Event()

    class WaitingModel:
        async def choose_move(self, position):
            started.set()
            await asyncio.to_thread(release.wait)
            clock.advance(5)
            return "e7e5"

    with client_with_model(WaitingModel(), clock) as client:
        game_id = bound_game(client)
        client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"})
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(client.post, f"/games/{game_id}/model-turn")
            try:
                assert started.wait(timeout=2)
                assert client.post(f"/games/{game_id}/model-turn").status_code == 409
                resignation = client.post(f"/games/{game_id}/resign", json={"color": "white"})
                assert resignation.status_code == 200
            finally:
                release.set()
            assert pending.result(timeout=2).status_code == 409
        state = client.get(f"/games/{game_id}").json()
        assert state["pgn"] == "1. e4 0-1"
        assert state["termination_reason"] == "resignation"
