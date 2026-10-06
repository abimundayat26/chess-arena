"""Durable authoritative state and restart clock recovery."""

import sqlite3

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.game import GameStore


class Clock:
    now = 100.0

    def __call__(self):
        return self.now


def test_restart_restores_moves_config_count_and_clocks(tmp_path):
    monotonic, wall = Clock(), Clock()
    path = str(tmp_path / "games.sqlite3")
    first = GameStore(monotonic, path, wall)
    game_id = first.create("3+2", "openai", "black", "structured_position")["game_id"]
    monotonic.now += 4
    wall.now += 4
    first.move(game_id, "e2e4")
    _, _, _, token = first.begin_model_turn(game_id)
    assert first.model_attempt(game_id, "e2e4", token) is None
    first.abort_model_turn(game_id, token)
    original = first.get(game_id)
    wall.now += 7
    second = GameStore(monotonic, path, wall)
    restored = second.get(game_id)
    assert restored["pgn"] == original["pgn"]
    assert restored["fen"] == original["fen"]
    assert restored["context_level"] == "structured_position"
    assert restored["model_provider"] == "openai"
    assert restored["illegal_model_move_count"] == 1
    assert restored["white_clock_ms"] == original["white_clock_ms"]
    assert restored["black_clock_ms"] == original["black_clock_ms"] - 7000
    assert second.begin_model_turn(game_id)[0] == "openai"


def test_restart_timeout_and_frozen_completed_clock(tmp_path):
    monotonic, wall = Clock(), Clock()
    path = str(tmp_path / "games.sqlite3")
    first = GameStore(monotonic, path, wall)
    game_id = first.create("3+0")["game_id"]
    wall.now += 181
    second = GameStore(monotonic, path, wall)
    timed_out = second.get(game_id)
    assert timed_out["termination_reason"] == "timeout"
    assert timed_out["result"] == "0-1"
    assert timed_out["white_clock_ms"] == 0
    wall.now += 200
    third = GameStore(monotonic, path, wall)
    assert third.get(game_id) == timed_out


def test_pending_draw_is_abandoned_and_model_clock_charged(tmp_path):
    monotonic, wall = Clock(), Clock()
    path = str(tmp_path / "games.sqlite3")
    first = GameStore(monotonic, path, wall)
    game_id = first.create("3+0", "openai", "black")["game_id"]
    first.begin_draw_decision(game_id)
    wall.now += 9
    second = GameStore(monotonic, path, wall)
    state = second.get(game_id)
    assert state["active_clock"] == "white"
    assert state["white_clock_ms"] == 180000
    assert state["black_clock_ms"] == 171000
    assert state["game_status"] == "playing"
    assert second.begin_draw_decision(game_id)[0] == "openai"


def test_backwards_wall_clock_adds_no_time(tmp_path):
    monotonic, wall = Clock(), Clock()
    path = str(tmp_path / "games.sqlite3")
    game_id = GameStore(monotonic, path, wall).create("3+0")["game_id"]
    wall.now -= 100
    assert GameStore(monotonic, path, wall).get(game_id)["white_clock_ms"] == 180000


def test_corrupt_record_is_not_replaced(tmp_path):
    monotonic, wall = Clock(), Clock()
    path = str(tmp_path / "games.sqlite3")
    game_id = GameStore(monotonic, path, wall).create()["game_id"]
    connection = sqlite3.connect(path)
    connection.execute("UPDATE games SET payload = ? WHERE id = ?", ("not-json", game_id))
    connection.commit()
    connection.close()
    with TestClient(create_app(GameStore(monotonic, path, wall), providers={})) as client:
        response = client.get(f"/games/{game_id}")
        assert response.status_code == 503
        assert response.json() == {"detail": "Stored game is unavailable"}
