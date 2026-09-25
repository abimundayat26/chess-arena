import io

import chess.pgn
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.game import GameStore
from backend.providers import ProviderBinding


class UnusedProvider:
    async def choose_move(self, position):
        raise AssertionError("provider must not be called")

    async def choose_draw(self, position):
        raise AssertionError("provider must not be called")


def test_completed_pgn_headers_and_restart(tmp_path):
    path = str(tmp_path / "games.sqlite3")
    providers = {"openai": ProviderBinding('Model "A"', UnusedProvider())}
    store = GameStore(path=path)
    with TestClient(create_app(store, providers)) as client:
        created = client.post("/games", json={"time_control": "3+2", "model_provider": "openai", "model_color": "black"}).json()
        game_id = created["game_id"]
        assert client.get(f"/games/{game_id}/pgn").status_code == 409
        assert client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).status_code == 200
        assert client.post(f"/games/{game_id}/resign", json={"color": "black"}).status_code == 200
        response = client.get(f"/games/{game_id}/pgn")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-chess-pgn")
        first = response.text
    restored = GameStore(path=path)
    replay = chess.pgn.read_game(io.StringIO(restored.export_pgn(game_id)))
    assert replay is not None
    assert not replay.errors
    assert replay.headers["White"] == "Human"
    assert replay.headers["Black"] == 'Model "A"'
    assert replay.headers["AIModel"] == 'Model "A"'
    assert replay.headers["TimeControl"] == "180+2"
    assert replay.headers["Result"] == "1-0"
    assert replay.headers["Termination"] == "resignation"
    assert replay.end().board().fullmove_number == 1
    assert first == restored.export_pgn(game_id)


def test_draw_and_promotion_export():
    store = GameStore()
    game_id = store.create()["game_id"]
    for move in ("a2a4", "h7h5", "a4a5", "h5h4", "a5a6", "h4h3", "a6b7", "h3g2", "b7a8q"):
        store.move(game_id, move)
    store.offer_draw(game_id, True)
    replay = chess.pgn.read_game(io.StringIO(store.export_pgn(game_id)))
    assert replay.headers["Result"] == "1/2-1/2"
    assert "=Q" in store.export_pgn(game_id)
    assert replay.end().board().fen() == store.get(game_id)["fen"]
