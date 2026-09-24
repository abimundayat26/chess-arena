"""Adversarial context and deadline checks without provider network calls."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.game import GameStore, thinking_budget
from backend.providers import ProviderBinding


class Clock:
    now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def create_bound(client, level="minimal", control="3+2"):
    response = client.post("/games", json={
        "time_control": control, "model_provider": "openai",
        "model_color": "black", "context_level": level,
    })
    assert response.status_code == 201
    game_id = response.json()["game_id"]
    assert client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).status_code == 200
    return game_id


@pytest.mark.parametrize("remaining,budget", [
    (600, 15), (599.999, 10), (300, 10), (299.999, 6),
    (120, 6), (119.999, 3), (30, 3), (29.999, 1), (0.25, 0.25),
])
def test_actual_model_turn_uses_boundary_budget(remaining, budget):
    clock = Clock()
    store = GameStore(clock)
    game_id = store.create("10+0", "openai", "black")["game_id"]
    store.move(game_id, "e2e4")
    clock.advance(600 - remaining)
    _, position, actual, token = store.begin_model_turn(game_id)
    assert actual == pytest.approx(budget)
    assert position.time_remaining_ms is None
    store.abort_model_turn(game_id, token)


@pytest.mark.parametrize("level", ["minimal", "game_context", "structured_position"])
def test_context_is_immutable_and_uses_authoritative_remaining_time(level):
    clock = Clock()
    positions = []

    class Model:
        async def choose_move(self, position):
            positions.append(position)
            return "e7e5"

    with TestClient(create_app(GameStore(clock), {"openai": ProviderBinding("server-model", Model())})) as client:
        game_id = create_bound(client, level)
        clock.advance(4.25)
        before = client.get(f"/games/{game_id}").json()
        assert client.post(f"/games/{game_id}/model-turn").status_code == 200
    position = positions[0]
    assert position.fen == before["fen"]
    assert position.legal_moves == tuple(before["legal_moves"])
    assert position.side_to_move == "black"
    if level == "minimal":
        assert position.pgn is position.time_remaining_ms is None
        assert position.pieces is position.material_counts is None
        assert position.castling_rights is position.fullmove_number is None
    else:
        assert position.pgn == before["pgn"]
        assert position.time_remaining_ms == before["black_clock_ms"]
    if level == "structured_position":
        assert dict(position.pieces)["e4"] == "P"
        assert ("pawn", 8, 8) in position.material_counts
        assert position.castling_rights == "KQkq"
        assert position.fullmove_number == 1


def test_provider_cannot_turn_budget_cancellation_into_a_move():
    asyncio.run(_provider_cannot_turn_budget_cancellation_into_a_move())


async def _provider_cannot_turn_budget_cancellation_into_a_move():
    clock = Clock()
    cancelled = asyncio.Event()

    class CancellationSuppressingModel:
        calls = 0

        async def choose_move(self, position):
            self.calls += 1
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                return "e7e5"

    model = CancellationSuppressingModel()
    app = create_app(GameStore(clock), {"openai": ProviderBinding("server-model", model)})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        game_id = (await client.post("/games", json={
            "model_provider": "openai", "model_color": "black", "time_control": "3+2",
        })).json()["game_id"]
        await client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"})
        clock.advance(179.98)
        response = await client.post(f"/games/{game_id}/model-turn")
        assert cancelled.is_set()
        assert response.status_code == 502
        assert response.json() == {"detail": "Model turn failed"}
        state = (await client.get(f"/games/{game_id}")).json()
        assert state["pgn"] == "1. e4 *"
        assert state["black_clock_ms"] == pytest.approx(20, abs=1)
        assert model.calls == 1


def test_timeout_during_late_provider_result_takes_priority():
    clock = Clock()

    class SlowModel:
        async def choose_move(self, position):
            clock.advance(180)
            return "e7e5"

    with TestClient(create_app(GameStore(clock), {"openai": ProviderBinding("server-model", SlowModel())})) as client:
        game_id = create_bound(client)
        response = client.post(f"/games/{game_id}/model-turn")
        assert response.status_code == 200
        state = response.json()
        assert state["termination_reason"] == "timeout"
        assert state["pgn"] == "1. e4 1-0"
        assert client.post(f"/games/{game_id}/model-turn").status_code == 409
