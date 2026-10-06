"""Bound draw decisions and clock/concurrency edge cases."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.game import GameStore
from backend.providers import ProviderBinding


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


class DrawModel:
    def __init__(self, clock, answer, delay=0):
        self.clock, self.answer, self.delay = clock, answer, delay
        self.positions = []

    async def choose_draw(self, position):
        self.positions.append(position)
        self.clock.now += self.delay
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer

    async def choose_move(self, position):
        return "e7e5"


def setup(answer, delay=0):
    clock = Clock()
    model = DrawModel(clock, answer, delay)
    client = TestClient(create_app(GameStore(clock), {"openai": ProviderBinding("fake", model)}))
    game_id = client.post("/games", json={"model_provider": "openai", "model_color": "black", "time_control": "3+0"}).json()["game_id"]
    return client, game_id, model, clock


@pytest.mark.parametrize("answer,reason", [(True, "draw_agreement"), (False, None)])
def test_bound_draw_decision_on_human_turn(answer, reason):
    client, game_id, model, clock = setup(answer, 2)
    with client:
        result = client.post(f"/games/{game_id}/draw-offer", json={})
        assert result.status_code == 200
        state = result.json()
        assert state["termination_reason"] == reason
        assert state["black_clock_ms"] == 178000
        assert state["white_clock_ms"] == 180000
        assert state["illegal_model_move_count"] == 0
        assert model.positions[0].draw_offer is True
        assert model.positions[0].model_color == "black"
        if not answer:
            assert state["active_clock"] == "white"
            clock.now += 1
            resumed = client.get(f"/games/{game_id}").json()
            assert resumed["white_clock_ms"] == 179000
            assert resumed["black_clock_ms"] == 178000


def test_draw_budget_failure_and_clock_timeout_priority():
    for delay, status, reason in [(6, 502, None), (180, 200, "timeout")]:
        client, game_id, _, _ = setup(False, delay)
        with client:
            result = client.post(f"/games/{game_id}/draw-offer", json={})
            assert result.status_code == status
            state = client.get(f"/games/{game_id}").json()
            assert state["termination_reason"] == reason
            assert state["black_clock_ms"] == 180000 - min(delay, 180) * 1000
            assert state["pgn"] == ("*" if reason is None else "1-0")


def test_bad_draw_decision_is_generic_and_unbound_draw_survives():
    client, game_id, _, _ = setup(RuntimeError("secret-provider-error"), 1)
    with client:
        assert client.post(f"/games/{game_id}/draw-offer", json={"accepted": True}).status_code == 422
        failure = client.post(f"/games/{game_id}/draw-offer", json={})
        assert failure.status_code == 502
        assert "secret-provider-error" not in failure.text
        assert client.get(f"/games/{game_id}").json()["black_clock_ms"] == 179000
        unbound = client.post("/games").json()["game_id"]
        assert client.post(f"/games/{unbound}/draw-offer", json={"accepted": True}).json()["termination_reason"] == "draw_agreement"


def test_pending_draw_blocks_moves_and_stale_answer_after_resignation():
    asyncio.run(_pending_draw_blocks_moves())


async def _pending_draw_blocks_moves():
    clock = Clock()
    started = asyncio.Event()
    release = asyncio.Event()

    class WaitingModel:
        async def choose_draw(self, position):
            started.set()
            await release.wait()
            return True

        async def choose_move(self, position):
            return "e7e5"

    app = create_app(GameStore(clock), {"openai": ProviderBinding("fake", WaitingModel())})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        game_id = (await client.post("/games", json={"model_provider": "openai", "model_color": "black"})).json()["game_id"]
        pending = asyncio.create_task(client.post(f"/games/{game_id}/draw-offer", json={}))
        await asyncio.wait_for(started.wait(), 1)
        assert (await client.post(f"/games/{game_id}/draw-offer", json={})).status_code == 409
        assert (await client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"})).status_code == 409
        assert (await client.post(f"/games/{game_id}/model-turn")).status_code == 409
        terminal = (await client.post(f"/games/{game_id}/resign", json={"color": "white"})).json()
        release.set()
        assert (await pending).status_code == 409
        state = (await client.get(f"/games/{game_id}")).json()
        assert state["result"] == terminal["result"]
        assert state["termination_reason"] == "resignation"
