"""Deterministic contract tests for authoritative clocks."""

import chess
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.game import Game, GameStore


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def timed_client():
    clock = Clock()
    with TestClient(create_app(GameStore(clock=clock))) as client:
        yield client, clock


@pytest.mark.parametrize("preset,initial,increment", [
    ("3+0", 180, 0), ("3+2", 180, 2), ("5+0", 300, 0),
    ("5+3", 300, 3), ("10+0", 600, 0), ("10+5", 600, 5),
    ("15+10", 900, 10), ("20+0", 1200, 0),
])
def test_presets_and_increments(timed_client, preset, initial, increment):
    client, clock = timed_client
    created = client.post("/games", json={"time_control": preset}).json()
    game_id = created["game_id"]
    assert created["time_control"] == preset
    assert created["white_clock_ms"] == created["black_clock_ms"] == initial * 1000
    assert created["active_clock"] == "white"
    clock.advance(1.25)
    moved = client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).json()
    assert moved["white_clock_ms"] == (initial - 1.25 + increment) * 1000
    assert moved["black_clock_ms"] == initial * 1000
    assert moved["active_clock"] == "black"
    clock.advance(2.5)
    fetched = client.get(f"/games/{game_id}").json()
    assert fetched["black_clock_ms"] == (initial - 2.5) * 1000
    assert fetched["white_clock_ms"] == moved["white_clock_ms"]
    assert client.post(f"/games/{game_id}/moves", json={"uci": "e7e5"}).json()["black_clock_ms"] == (initial - 2.5 + increment) * 1000


def test_rejected_moves_charge_active_side_and_no_increment(timed_client):
    client, clock = timed_client
    game_id = client.post("/games", json={"time_control": "3+2"}).json()["game_id"]
    clock.advance(2)
    assert client.post(f"/games/{game_id}/moves", json={"uci": "e2e5"}).status_code == 400
    state = client.get(f"/games/{game_id}").json()
    assert state["white_clock_ms"] == 178000
    assert state["fen"] == chess.STARTING_FEN
    clock.advance(3)
    state = client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).json()
    assert state["white_clock_ms"] == 177000
    clock.advance(4)
    assert client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).status_code == 400
    assert client.get(f"/games/{game_id}").json()["black_clock_ms"] == 176000


@pytest.mark.parametrize("loser,expected", [("white", "0-1"), ("black", "1-0")])
def test_timeout_freezes_state_and_rejects_actions(timed_client, loser, expected):
    client, clock = timed_client
    game_id = client.post("/games", json={"time_control": "3+0"}).json()["game_id"]
    if loser == "black":
        client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"})
    clock.advance(180)
    final = client.get(f"/games/{game_id}").json()
    assert final["game_status"] == "game-over"
    assert final["result"] == expected
    assert final["termination_reason"] == "timeout"
    assert final["active_clock"] is None
    assert final[f"{loser}_clock_ms"] == 0
    assert final["legal_moves"] == []
    for path, body in [("moves", {"uci": "e2e4"}), ("resign", {"color": loser}), ("draw-offer", {"accepted": True}), ("draw-offer", {"accepted": False})]:
        assert client.post(f"/games/{game_id}/{path}", json=body).status_code == 409
    clock.advance(100)
    assert client.get(f"/games/{game_id}").json() == final


def test_timeout_during_action_wins_over_action(timed_client):
    client, clock = timed_client
    game_id = client.post("/games", json={"time_control": "3+2"}).json()["game_id"]
    clock.advance(180.01)
    assert client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).status_code == 409
    final = client.get(f"/games/{game_id}").json()
    assert final["termination_reason"] == "timeout"
    assert final["fen"] == chess.STARTING_FEN
    assert final["white_clock_ms"] == 0


def test_timeout_is_draw_when_opponent_cannot_mate():
    clock = Clock()
    game = Game(board=chess.Board("4k3/8/8/8/8/8/8/4K2R w - - 0 1"), time_control="3+0", clock=clock)
    clock.advance(180)
    state = game.snapshot()
    assert state["termination_reason"] == "timeout"
    assert state["result"] == "1/2-1/2"


def test_invalid_preset_is_rejected(timed_client):
    client, _ = timed_client
    assert client.post("/games", json={"time_control": "30+0"}).status_code == 422


@pytest.mark.parametrize("invalid", ["0+0", "3+1", "20+5", "30+0", "3+0 ", None, 3])
def test_only_supported_presets_are_accepted(timed_client, invalid):
    client, _ = timed_client
    assert client.post("/games", json={"time_control": invalid}).status_code == 422


def test_default_preset_and_elapsed_time_on_both_sides(timed_client):
    client, clock = timed_client
    created = client.post("/games").json()
    game_id = created["game_id"]
    assert created["time_control"] == "10+5"
    clock.advance(0.125)
    assert client.get(f"/games/{game_id}").json()["white_clock_ms"] == 599875
    clock.advance(0.875)
    first = client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).json()
    assert (first["white_clock_ms"], first["black_clock_ms"]) == (604000, 600000)
    clock.advance(2)
    assert client.post(f"/games/{game_id}/draw-offer", json={"accepted": False}).json()["black_clock_ms"] == 598000
    clock.advance(3)
    second = client.post(f"/games/{game_id}/moves", json={"uci": "e7e5"}).json()
    assert (second["white_clock_ms"], second["black_clock_ms"]) == (604000, 600000)
    clock.advance(7)
    assert client.get(f"/games/{game_id}").json()["white_clock_ms"] == 597000


def test_repeated_bad_moves_and_declined_draw_consume_time_without_increment(timed_client):
    client, clock = timed_client
    game_id = client.post("/games", json={"time_control": "3+2"}).json()["game_id"]
    for uci in ("bad", "e2e5", "e7e5"):
        clock.advance(1)
        assert client.post(f"/games/{game_id}/moves", json={"uci": uci}).status_code == 400
    clock.advance(1)
    declined = client.post(f"/games/{game_id}/draw-offer", json={"accepted": False}).json()
    assert declined["white_clock_ms"] == 176000
    assert declined["black_clock_ms"] == 180000
    clock.advance(1)
    moved = client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).json()
    assert moved["white_clock_ms"] == 177000
    assert moved["active_clock"] == "black"


@pytest.mark.parametrize("action,payload", [
    ("moves", {"uci": "e2e4"}),
    ("moves", {"uci": "bad"}),
    ("resign", {"color": "white"}),
    ("draw-offer", {"accepted": True}),
    ("draw-offer", {"accepted": False}),
])
def test_action_at_exact_timeout_is_rejected_and_freezes_clock(timed_client, action, payload):
    client, clock = timed_client
    game_id = client.post("/games", json={"time_control": "3+0"}).json()["game_id"]
    clock.advance(180)
    assert client.post(f"/games/{game_id}/{action}", json=payload).status_code == 409
    final = client.get(f"/games/{game_id}").json()
    assert (final["result"], final["termination_reason"]) == ("0-1", "timeout")
    assert final["white_clock_ms"] == 0
    assert final["fen"] == chess.STARTING_FEN
    clock.advance(100)
    assert client.get(f"/games/{game_id}").json() == final


@pytest.mark.parametrize("fen,expected", [
    ("4k3/8/8/8/8/8/8/4K2R w - - 0 1", "1/2-1/2"),
    ("4k3/8/8/8/8/8/8/4K1BN w - - 0 1", "1/2-1/2"),
    ("4k3/8/8/8/8/8/8/4K2R b - - 0 1", "1-0"),
    ("4k3/8/8/8/8/8/8/4KBN1 b - - 0 1", "1-0"),
])
def test_timeout_result_uses_winners_mating_material(fen, expected):
    clock = Clock()
    game = Game(board=chess.Board(fen), time_control="3+0", clock=clock)
    clock.advance(180)
    state = game.snapshot()
    assert state["termination_reason"] == "timeout"
    assert state["result"] == expected


@pytest.mark.parametrize("action,payload,reason", [
    ("resign", {"color": "white"}, "resignation"),
    ("draw-offer", {"accepted": True}, "draw_agreement"),
])
def test_other_terminal_actions_charge_then_stop_clocks(timed_client, action, payload, reason):
    client, clock = timed_client
    game_id = client.post("/games", json={"time_control": "3+2"}).json()["game_id"]
    clock.advance(2.5)
    final = client.post(f"/games/{game_id}/{action}", json=payload).json()
    assert final["termination_reason"] == reason
    assert final["white_clock_ms"] == 177500
    assert final["active_clock"] is None
    clock.advance(200)
    assert client.get(f"/games/{game_id}").json() == final
