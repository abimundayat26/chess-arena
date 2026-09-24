import chess
from fastapi.testclient import TestClient
import pytest

from backend.app import create_app
from backend.game import Game, GameStore, IllegalMove


@pytest.fixture
def client():
    with TestClient(create_app(GameStore(clock=lambda: 0.0))) as test_client:
        yield test_client


def new_game(client):
    response = client.post("/games")
    assert response.status_code == 201
    return response.json()


def move(client, game_id, uci):
    return client.post(f"/games/{game_id}/moves", json={"uci": uci})


def test_game_creation_and_get(client):
    game = new_game(client)
    assert game["fen"] == chess.STARTING_FEN
    assert game["pgn"] == "*"
    assert game["game_status"] == "playing"
    assert game["result"] == "*"
    assert game["termination_reason"] is None
    assert game["side_to_move"] == "white"
    assert "e2e4" in game["legal_moves"]
    assert client.get(f"/games/{game['game_id']}").json() == game


def test_legal_move_updates_fen_and_pgn(client):
    game_id = new_game(client)["game_id"]
    response = move(client, game_id, "e2e4")
    assert response.status_code == 200
    state = response.json()
    assert state["fen"] == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    assert state["pgn"] == "1. e4 *"
    assert state["side_to_move"] == "black"
    assert "e7e5" in state["legal_moves"]
    assert client.get(f"/games/{game_id}").json() == state


@pytest.mark.parametrize("uci", ["e2e5", "bad", "e7e5", "e2e4q"])
def test_illegal_move_does_not_change_game(client, uci):
    game = new_game(client)
    response = move(client, game["game_id"], uci)
    assert response.status_code == 400
    assert client.get(f"/games/{game['game_id']}").json() == game


def test_checkmate_ends_game(client):
    game_id = new_game(client)["game_id"]
    for uci in ["f2f3", "e7e5", "g2g4", "d8h4"]:
        response = move(client, game_id, uci)
        assert response.status_code == 200
    state = response.json()
    assert state["game_status"] == "game-over"
    assert state["result"] == "0-1"
    assert state["termination_reason"] == "checkmate"
    assert state["pgn"] == "1. f3 e5 2. g4 Qh4# 0-1"
    assert state["legal_moves"] == []
    assert move(client, game_id, "e2e4").status_code == 409


def test_stalemate_ends_game():
    game = Game(board=chess.Board("k7/8/1QK5/8/8/8/8/8 w - - 0 1"))
    game.submit_move("b6c7")
    state = game.snapshot()
    assert state["game_status"] == "game-over"
    assert state["result"] == "1/2-1/2"
    assert state["termination_reason"] == "stalemate"


def test_insufficient_material_ends_game():
    game = Game(board=chess.Board("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1"))
    # A legal king capture leaves only the kings.
    game.submit_move("e1e2")
    assert game.snapshot()["termination_reason"] == "insufficient_material"


def test_promotion_requires_piece_and_updates_pgn():
    game = Game(board=chess.Board("4k3/P7/8/8/8/8/8/4K3 w - - 0 1"))
    with pytest.raises(IllegalMove):
        game.submit_move("a7a8")
    game.submit_move("a7a8q")
    assert "a8=Q+" in game.snapshot()["pgn"]


def test_resignation_and_rejecting_later_moves(client):
    game_id = new_game(client)["game_id"]
    response = client.post(f"/games/{game_id}/resign", json={"color": "white"})
    assert response.status_code == 200
    state = response.json()
    assert state["game_status"] == "game-over"
    assert state["result"] == "0-1"
    assert state["termination_reason"] == "resignation"
    assert move(client, game_id, "e2e4").status_code == 409


def test_draw_offer_decline_then_accept(client):
    game_id = new_game(client)["game_id"]
    declined = client.post(f"/games/{game_id}/draw-offer", json={"accepted": False})
    assert declined.status_code == 200
    assert declined.json()["game_status"] == "playing"
    accepted = client.post(f"/games/{game_id}/draw-offer", json={"accepted": True})
    assert accepted.status_code == 200
    state = accepted.json()
    assert state["game_status"] == "game-over"
    assert state["result"] == "1/2-1/2"
    assert state["termination_reason"] == "draw_agreement"
    assert move(client, game_id, "e2e4").status_code == 409


def test_unknown_game_returns_404(client):
    assert client.get("/games/missing").status_code == 404
    assert move(client, "missing", "e2e4").status_code == 404
