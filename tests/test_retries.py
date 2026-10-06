"""Adversarial retry and clock behavior with a fake provider."""

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.game import GameStore
from backend.providers import ProviderBinding


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


class SequenceModel:
    def __init__(self, clock, responses):
        self.clock, self.responses, self.positions = clock, iter(responses), []

    async def choose_move(self, position):
        self.positions.append(position)
        delay, move = next(self.responses)
        self.clock.now += delay
        return move


def setup(responses):
    clock = Clock()
    model = SequenceModel(clock, responses)
    client = TestClient(create_app(GameStore(clock), {"openai": ProviderBinding("fake", model)}))
    game_id = client.post("/games", json={"time_control": "3+0", "model_provider": "openai", "model_color": "black"}).json()["game_id"]
    assert client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).status_code == 200
    return client, game_id, model


def test_retries_charge_clock_and_award_only_legal_increment():
    client, game_id, model = setup([(0.5, "bad"), (0.5, "e2e4"), (0.5, "e7e5")])
    with client:
        result = client.post(f"/games/{game_id}/model-turn")
        assert result.status_code == 200
        state = result.json()
        assert state["illegal_model_move_count"] == 2
        assert state["black_clock_ms"] == 178500
        assert state["pgn"] == "1. e4 e5 *"
        assert model.positions[1].previous_illegal_move == "bad"
        assert model.positions[2].previous_illegal_move == "e2e4"


def test_fifth_invalid_forfeits_without_move_or_increment():
    client, game_id, model = setup([(0.5, "bad")] * 5)
    with client:
        state = client.post(f"/games/{game_id}/model-turn").json()
        assert len(model.positions) == 5
        assert state["game_status"] == "game-over"
        assert state["termination_reason"] == "model_forfeit"
        assert state["black_clock_ms"] == 177500
        assert state["pgn"] == "1. e4 1-0"
        assert client.post(f"/games/{game_id}/model-turn").status_code == 409


def test_retry_budget_does_not_reset():
    client, game_id, model = setup([(5, "bad"), (1, "e7e5")])
    with client:
        result = client.post(f"/games/{game_id}/model-turn")
        assert result.status_code == 502
        state = client.get(f"/games/{game_id}").json()
        assert state["illegal_model_move_count"] == 1
        assert state["black_clock_ms"] == 174000
        assert state["pgn"] == "1. e4 *"
