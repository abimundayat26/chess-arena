"""Context levels use only authoritative history and board facts."""

import json
from dataclasses import FrozenInstanceError

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.game import GameStore
from backend.providers import AnthropicAdapter, GeminiAdapter, OpenAIAdapter, OpenRouterAdapter, ProviderBinding
from backend.live_context import ModelPosition


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


class CaptureModel:
    def __init__(self):
        self.positions = []

    async def choose_move(self, position):
        self.positions.append(position)
        return "e7e5"


@pytest.mark.parametrize("level", ["minimal", "game_context", "structured_position"])
def test_game_context_is_bounded_and_authoritative(level):
    clock = Clock()
    model = CaptureModel()
    with TestClient(create_app(GameStore(clock), {"openai": ProviderBinding("server-model", model)})) as client:
        created = client.post("/games", json={"model_provider": "openai", "model_color": "black", "context_level": level})
        assert created.status_code == 201
        game_id = created.json()["game_id"]
        before = client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).json()
        after = client.post(f"/games/{game_id}/model-turn").json()
        assert after["context_level"] == level
        position = model.positions[0]
        assert position.fen == before["fen"]
        assert position.legal_moves == tuple(before["legal_moves"])
        if level == "minimal":
            assert position.pgn is position.time_remaining_ms is position.pieces is None
        else:
            assert position.pgn == "1. e4 *"
            assert position.time_remaining_ms == 600000
        if level == "structured_position":
            assert ("e4", "P") in position.pieces
            assert ("e7", "p") in position.pieces
            assert ("pawn", 8, 8) in position.material_counts
            assert position.castling_rights == "KQkq"
            assert position.fullmove_number == 1
        else:
            assert position.pieces is None


def test_default_and_unsupported_creation_fields():
    with TestClient(create_app(GameStore(clock=Clock()), providers={})) as client:
        assert client.post("/games").json()["context_level"] == "minimal"
        for field, value in (("context_level", "custom"), ("api_key", "secret"),
                             ("model_id", "client-model"), ("provider_url", "https://invalid.test"),
                             ("prompt", "ignore rules")):
            response = client.post("/games", json={field: value})
            assert response.status_code == 422
            assert "secret" not in response.text


@pytest.mark.parametrize("adapter_type,response", [
    (OpenAIAdapter, {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "e7e5"}]}]}),
    (AnthropicAdapter, {"content": [{"type": "text", "text": "e7e5"}]}),
    (GeminiAdapter, {"candidates": [{"content": {"parts": [{"text": "e7e5"}]}}]}),
    (OpenRouterAdapter, {"choices": [{"message": {"content": "e7e5"}}]}),
])
@pytest.mark.parametrize("level", ["minimal", "game_context", "structured_position"])
def test_intercepted_http_prompt_contains_only_selected_context(adapter_type, response, level):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=response)

    adapter = adapter_type("server-secret", "server-model", httpx.MockTransport(respond))
    clock = Clock()
    with TestClient(create_app(GameStore(clock), {"openai": ProviderBinding("server-model", adapter)})) as client:
        game_id = client.post("/games", json={"model_provider": "openai", "model_color": "black", "context_level": level}).json()["game_id"]
        client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"})
        assert client.post(f"/games/{game_id}/model-turn").status_code == 200
    body = json.dumps(json.loads(requests[0].content)).lower()
    assert "legal uci moves" in body and "fen:" in body
    assert ("pgn:" in body) == (level != "minimal")
    assert ("pieces (square=piece)" in body) == (level == "structured_position")
    assert ("castling rights:" in body) == (level == "structured_position")
    assert "server-secret" not in body
    for forbidden in ("evaluation", "suggested move", "best move", "principal variation", "stockfish"):
        assert forbidden not in body


def test_live_context_cannot_gain_analysis_fields():
    position = ModelPosition("fen", "white", ("e2e4",))
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        position.evaluation = "+3.2"
    with TestClient(create_app(GameStore(clock=Clock()), providers={})) as client:
        for field in ("evaluation", "candidate_moves", "principal_variation", "tablebase", "opening_advice"):
            assert client.post("/games", json={field: "secret hint"}).status_code == 422


@pytest.mark.parametrize("adapter_type,wrap", [
    (OpenAIAdapter, lambda move: {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": move}]}]}),
    (AnthropicAdapter, lambda move: {"content": [{"type": "text", "text": move}]}),
    (GeminiAdapter, lambda move: {"candidates": [{"content": {"parts": [{"text": move}]}}]}),
    (OpenRouterAdapter, lambda move: {"choices": [{"message": {"content": move}}]}),
])
def test_retry_http_payload_has_only_live_context(adapter_type, wrap):
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=wrap("e2e4" if len(requests) == 1 else "e7e5"))

    adapter = adapter_type("secret-key", "server-model", httpx.MockTransport(respond))
    with TestClient(create_app(GameStore(Clock()), {"openai": ProviderBinding("server-model", adapter)})) as client:
        game_id = client.post("/games", json={"model_provider": "openai", "model_color": "black", "context_level": "structured_position"}).json()["game_id"]
        client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"})
        state = client.post(f"/games/{game_id}/model-turn").json()
        assert state["illegal_model_move_count"] == 1
    assert len(requests) == 2
    first, retry = (json.dumps(request).lower() for request in requests)
    assert "previous proposed move" not in first
    assert "previous proposed move" in retry
    for body in (first, retry):
        assert "fen:" in body and "legal uci moves" in body
        for forbidden in ("stockfish", "evaluation", "tablebase", "opening advice", "principal variation", "best move"):
            assert forbidden not in body
