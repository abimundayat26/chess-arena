"""Adaptive deadlines and clock accounting without live provider calls."""

import asyncio
from time import monotonic

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.game import GameStore, ModelTurnConflict, thinking_budget
from backend.providers import ProviderBinding


class Clock:
    now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeModel:
    def __init__(self, clock, delay=0, result="e7e5"):
        self.clock, self.delay, self.result = clock, delay, result
        self.calls = 0

    async def choose_move(self, position):
        self.calls += 1
        self.clock.advance(self.delay)
        return self.result


def bound(client):
    game_id = client.post("/games", json={"time_control": "3+2", "model_provider": "openai", "model_color": "black"}).json()["game_id"]
    assert client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).status_code == 200
    return game_id


@pytest.mark.parametrize("remaining,expected", [
    (600, 15), (599.999, 10), (300, 10), (299.999, 6),
    (120, 6), (119.999, 3), (30, 3), (29.999, 1),
    (1, 1), (0.25, 0.25),
])
def test_budget_boundaries(remaining, expected):
    assert thinking_budget(remaining) == expected


@pytest.mark.parametrize("delay,expected_status,remaining", [
    (5.999, 200, 176001),
    (6, 502, 174000),
    (7, 502, 173000),
    (180, 200, 0),
])
def test_provider_latency_and_budget_priority(delay, expected_status, remaining):
    clock = Clock()
    model = FakeModel(clock, delay)
    with TestClient(create_app(GameStore(clock), {"openai": ProviderBinding("server-model", model)})) as client:
        game_id = bound(client)
        response = client.post(f"/games/{game_id}/model-turn")
        assert response.status_code == expected_status
        state = client.get(f"/games/{game_id}").json()
        assert state["black_clock_ms"] == remaining
        assert state["pgn"] == ("1. e4 e5 *" if expected_status == 200 and delay < 180 else
                                "1. e4 1-0" if delay == 180 else "1. e4 *")
        assert model.calls == 1
        if delay == 180:
            assert state["termination_reason"] == "timeout"


def test_stale_token_cannot_finish_or_release_newer_call():
    clock = Clock()
    store = GameStore(clock)
    game_id = store.create("3+2", "openai", "black")["game_id"]
    store.move(game_id, "e2e4")
    _, _, _, old = store.begin_model_turn(game_id)
    store.abort_model_turn(game_id, old)
    _, _, _, current = store.begin_model_turn(game_id)
    with pytest.raises(ModelTurnConflict):
        store.finish_model_turn(game_id, "e7e5", old)
    store.abort_model_turn(game_id, old)
    with pytest.raises(ModelTurnConflict):
        store.begin_model_turn(game_id)
    assert store.finish_model_turn(game_id, "e7e5", current)["pgn"] == "1. e4 e5 *"


def test_illegal_move_after_latency_has_no_increment():
    clock = Clock()
    model = FakeModel(clock, 2, "e2e4")
    with TestClient(create_app(GameStore(clock), {"openai": ProviderBinding("server-model", model)})) as client:
        game_id = bound(client)
        assert client.post(f"/games/{game_id}/model-turn").status_code == 502
        state = client.get(f"/games/{game_id}").json()
        assert state["black_clock_ms"] == 178000
        assert state["pgn"] == "1. e4 *"


def test_async_provider_budget_cancels_and_charges_clock():
    asyncio.run(_async_provider_budget_cancels_and_charges_clock())


async def _async_provider_budget_cancels_and_charges_clock():
    class WallClock:
        start = monotonic()
        offset = 0.0

        def __call__(self):
            return monotonic() - self.start + self.offset

    clock = WallClock()
    cancelled = asyncio.Event()

    class WaitingModel:
        async def choose_move(self, position):
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.set()
                raise

    app = create_app(GameStore(clock), {"openai": ProviderBinding("server-model", WaitingModel())})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        game_id = (await client.post("/games", json={"time_control": "3+2", "model_provider": "openai", "model_color": "black"})).json()["game_id"]
        await client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"})
        clock.offset += 151
        response = await client.post(f"/games/{game_id}/model-turn")
        assert response.status_code == 502
        assert response.json() == {"detail": "Model turn failed"}
        assert cancelled.is_set()
        state = (await client.get(f"/games/{game_id}")).json()
        assert 27000 <= state["black_clock_ms"] <= 28000
        assert state["pgn"] == "1. e4 *"


def test_request_cancellation_releases_guard_and_charges_elapsed_time():
    asyncio.run(_request_cancellation_releases_guard_and_charges_elapsed_time())


async def _request_cancellation_releases_guard_and_charges_elapsed_time():
    clock = Clock()
    started = asyncio.Event()
    started_again = asyncio.Event()

    class WaitingModel:
        calls = 0

        async def choose_move(self, position):
            self.calls += 1
            started.set()
            if self.calls == 2:
                started_again.set()
            await asyncio.Event().wait()

    app = create_app(GameStore(clock), {"openai": ProviderBinding("server-model", WaitingModel())})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        game_id = (await client.post("/games", json={"model_provider": "openai", "model_color": "black"})).json()["game_id"]
        await client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"})
        pending = asyncio.create_task(client.post(f"/games/{game_id}/model-turn"))
        await asyncio.wait_for(started.wait(), 1)
        assert (await client.post(f"/games/{game_id}/model-turn")).status_code == 409
        clock.advance(2)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        state = (await client.get(f"/games/{game_id}")).json()
        assert state["black_clock_ms"] == 598000
        assert state["pgn"] == "1. e4 *"
        # The aborted call's token cannot leave the game permanently busy.
        retry = asyncio.create_task(client.post(f"/games/{game_id}/model-turn"))
        await asyncio.wait_for(started_again.wait(), 1)
        retry.cancel()
        with pytest.raises(asyncio.CancelledError):
            await retry
