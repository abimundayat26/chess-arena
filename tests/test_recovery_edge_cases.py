"""Model play and recovery edge cases."""

import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.game import GameStore
from backend.providers import (
    AnthropicAdapter, GeminiAdapter, OpenAIAdapter, OpenRouterAdapter,
    ProviderBinding,
)


class Clock:
    now = 100.0

    def __call__(self):
        return self.now


class DrawModel:
    calls = 0

    async def choose_draw(self, position):
        self.calls += 1
        return False

    async def choose_move(self, position):
        raise AssertionError("A draw offer must not request a move")


def test_bound_draw_rejects_explicit_null_without_calling_provider():
    model = DrawModel()
    with TestClient(create_app(GameStore(Clock()), {
        "openai": ProviderBinding("server-model", model),
    })) as client:
        game_id = client.post("/games", json={
            "model_provider": "openai", "model_color": "black",
        }).json()["game_id"]
        response = client.post(f"/games/{game_id}/draw-offer", json={"accepted": None})
        assert response.status_code == 422
        assert model.calls == 0
        state = client.get(f"/games/{game_id}").json()
        assert state["game_status"] == "playing"
        assert state["white_clock_ms"] == state["black_clock_ms"] == 600000


@pytest.mark.parametrize("bad_clock", ["invalid", -1, float("nan")])
def test_corrupt_completed_clock_fails_safely_after_restart(tmp_path, bad_clock):
    monotonic, wall = Clock(), Clock()
    path = str(tmp_path / "arena.sqlite3")
    store = GameStore(monotonic, path, wall)
    game_id = store.create("3+0")["game_id"]
    store.resign(game_id, "white")
    connection = sqlite3.connect(path)
    payload = json.loads(connection.execute(
        "SELECT payload FROM games WHERE id = ?", (game_id,)
    ).fetchone()[0])
    payload["white_seconds"] = bad_clock
    connection.execute("UPDATE games SET payload = ? WHERE id = ?", (json.dumps(payload), game_id))
    connection.commit()
    connection.close()
    with TestClient(create_app(GameStore(monotonic, path, wall), providers={})) as client:
        response = client.get(f"/games/{game_id}")
        assert response.status_code == 503
        assert response.json() == {"detail": "Stored game is unavailable"}


@pytest.mark.parametrize("field,value", [
    ("status", "unknown"),
    ("result", "*"),
    ("illegal_model_move_count", -1),
])
def test_corrupt_completed_metadata_fails_safely_after_restart(tmp_path, field, value):
    monotonic, wall = Clock(), Clock()
    path = str(tmp_path / "arena.sqlite3")
    store = GameStore(monotonic, path, wall)
    game_id = store.create("3+0")["game_id"]
    store.resign(game_id, "white")
    connection = sqlite3.connect(path)
    payload = json.loads(connection.execute(
        "SELECT payload FROM games WHERE id = ?", (game_id,)
    ).fetchone()[0])
    payload[field] = value
    connection.execute("UPDATE games SET payload = ? WHERE id = ?", (json.dumps(payload), game_id))
    connection.commit()
    connection.close()
    with TestClient(create_app(GameStore(monotonic, path, wall), providers={})) as client:
        response = client.get(f"/games/{game_id}")
        assert response.status_code == 503


def test_restart_abandons_model_turn_and_charges_downtime(tmp_path):
    monotonic, wall = Clock(), Clock()
    path = str(tmp_path / "arena.sqlite3")
    first = GameStore(monotonic, path, wall)
    game_id = first.create("3+2", "openai", "black")["game_id"]
    first.move(game_id, "e2e4")
    _, position, _, token = first.begin_model_turn(game_id)
    assert first.model_attempt(game_id, "e2e4", token) is None
    assert position.side_to_move == "black"
    wall.now += 7
    recovered = GameStore(monotonic, path, wall)
    state = recovered.get(game_id)
    assert state["pgn"] == "1. e4 *"
    assert state["black_clock_ms"] == 173000
    assert state["illegal_model_move_count"] == 1
    assert state["active_clock"] == "black"
    assert recovered.begin_model_turn(game_id)[0] == "openai"


@pytest.mark.parametrize("adapter_type,wrap", [
    (OpenAIAdapter, lambda text: {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}),
    (AnthropicAdapter, lambda text: {"content": [{"type": "text", "text": text}]}),
    (GeminiAdapter, lambda text: {"candidates": [{"content": {"parts": [{"text": text}]}}]}),
    (OpenRouterAdapter, lambda text: {"choices": [{"message": {"content": text}}]}),
])
def test_intercepted_draw_failure_keeps_live_context_and_no_count(adapter_type, wrap):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=wrap("ACCEPT with explanation"))

    adapter = adapter_type("server-secret", "server-model", httpx.MockTransport(respond))
    with TestClient(create_app(GameStore(Clock()), {
        "openai": ProviderBinding("server-model", adapter),
    })) as client:
        game_id = client.post("/games", json={
            "model_provider": "openai", "model_color": "black", "context_level": "minimal",
        }).json()["game_id"]
        response = client.post(f"/games/{game_id}/draw-offer", json={})
        assert response.status_code == 502
        assert response.json() == {"detail": "Model draw decision failed"}
        state = client.get(f"/games/{game_id}").json()
        assert state["pgn"] == "*"
        assert state["illegal_model_move_count"] == 0
        assert state["active_clock"] == "white"
    assert len(requests) == 1
    body = requests[0].content.decode().lower()
    assert "your color: black" in body
    assert "side to move: white" in body
    assert "pgn:" not in body
    assert "server-secret" not in body
    for forbidden in ("stockfish", "evaluation", "tablebase", "principal variation", "opening advice"):
        assert forbidden not in body
