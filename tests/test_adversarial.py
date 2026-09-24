"""Adversarial checks of the authoritative game state and HTTP contract."""

from io import StringIO

import chess
import chess.pgn
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.game import Game, GameOver


@pytest.fixture
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def create_game(client):
    response = client.post("/games")
    assert response.status_code == 201
    return response.json()


def play(client, game_id, uci):
    return client.post(f"/games/{game_id}/moves", json={"uci": uci})


def assert_pgn_matches_state(state):
    parsed = chess.pgn.read_game(StringIO(state["pgn"]))
    assert parsed is not None
    assert parsed.errors == []
    assert parsed.headers["Result"] == state["result"]
    board = parsed.end().board()
    assert board.fen() == state["fen"]
    assert state["legal_moves"] == (
        [move.uci() for move in board.legal_moves] if state["game_status"] == "playing" else []
    )


@pytest.mark.parametrize(
    "uci",
    ["", "e2", "e2e4x", "e2e4qq", "i2e4", "e0e4", "E2E4", "e2 e4", "0000", "e2e2"],
)
def test_malformed_uci_is_rejected_without_mutation(client, uci):
    initial = create_game(client)
    response = play(client, initial["game_id"], uci)
    assert response.status_code == 400
    assert client.get(f"/games/{initial['game_id']}").json() == initial


@pytest.mark.parametrize("uci", ["e2e5", "e1e2", "f1b5", "e7e5", "g8f6", "a2a1q"])
def test_legal_looking_but_illegal_or_wrong_side_moves_do_not_mutate(client, uci):
    initial = create_game(client)
    assert play(client, initial["game_id"], uci).status_code == 400
    assert client.get(f"/games/{initial['game_id']}").json() == initial


@pytest.mark.parametrize(
    "path,payload",
    [
        ("moves", {}),
        ("moves", {"uci": None}),
        ("moves", {"uci": 1234}),
        ("moves", {"uci": ["e2e4"]}),
        ("resign", {}),
        ("resign", {"color": "green"}),
        ("draw-offer", {}),
        ("draw-offer", {"accepted": "maybe"}),
    ],
)
def test_invalid_payload_is_rejected_without_mutation(client, path, payload):
    initial = create_game(client)
    response = client.post(f"/games/{initial['game_id']}/{path}", json=payload)
    assert response.status_code == 422
    assert client.get(f"/games/{initial['game_id']}").json() == initial


def test_malformed_json_is_rejected_without_mutation(client):
    initial = create_game(client)
    response = client.post(
        f"/games/{initial['game_id']}/moves",
        content=b'{"uci":',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert client.get(f"/games/{initial['game_id']}").json() == initial


@pytest.mark.parametrize("game_id", ["missing", "not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_unknown_or_malformed_game_ids_return_404(client, game_id):
    assert client.get(f"/games/{game_id}").status_code == 404
    assert play(client, game_id, "e2e4").status_code == 404
    assert client.post(f"/games/{game_id}/resign", json={"color": "white"}).status_code == 404
    assert client.post(f"/games/{game_id}/draw-offer", json={"accepted": True}).status_code == 404


@pytest.mark.parametrize("ending", ["resign", "draw-offer", "checkmate"])
def test_terminal_game_rejects_repeated_actions_without_mutation(client, ending):
    state = create_game(client)
    game_id = state["game_id"]
    if ending == "checkmate":
        for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
            response = play(client, game_id, uci)
            assert response.status_code == 200
        state = response.json()
    elif ending == "resign":
        state = client.post(f"/games/{game_id}/resign", json={"color": "black"}).json()
        assert state["result"] == "1-0"
    else:
        state = client.post(f"/games/{game_id}/draw-offer", json={"accepted": True}).json()
    assert state["game_status"] == "game-over"
    assert state["legal_moves"] == []
    assert_pgn_matches_state(state)
    assert play(client, game_id, "e2e4").status_code == 409
    assert client.post(f"/games/{game_id}/resign", json={"color": "white"}).status_code == 409
    assert client.post(f"/games/{game_id}/draw-offer", json={"accepted": True}).status_code == 409
    assert client.post(f"/games/{game_id}/draw-offer", json={"accepted": False}).status_code == 409
    assert client.get(f"/games/{game_id}").json() == state


def test_repeated_declined_draw_offer_is_idempotent(client):
    state = create_game(client)
    url = f"/games/{state['game_id']}/draw-offer"
    for _ in range(2):
        response = client.post(url, json={"accepted": False})
        assert response.status_code == 200
        assert response.json() == state


def test_castling_and_en_passant_keep_pgn_fen_and_legal_moves_consistent(client):
    game_id = create_game(client)["game_id"]
    for uci in ("e2e4", "a7a6", "e4e5", "d7d5", "e5d6"):
        response = play(client, game_id, uci)
        assert response.status_code == 200
        assert_pgn_matches_state(response.json())

    other_game_id = create_game(client)["game_id"]
    for uci in ("e2e4", "e7e5", "g1f3", "b8c6", "f1e2", "g8f6", "e1g1"):
        response = play(client, other_game_id, uci)
        assert response.status_code == 200
        assert_pgn_matches_state(response.json())


def test_games_have_isolated_state(client):
    first = create_game(client)
    second = create_game(client)
    assert first["game_id"] != second["game_id"]
    assert play(client, first["game_id"], "e2e4").status_code == 200
    assert client.get(f"/games/{second['game_id']}").json() == second


def test_repetition_ends_game_and_preserves_pgn_fen(client):
    game_id = create_game(client)["game_id"]
    for index, uci in enumerate(("g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1", "f6g8")):
        response = play(client, game_id, uci)
        assert response.status_code == 200
        assert response.json()["game_status"] == ("game-over" if index == 7 else "playing")
    state = response.json()
    assert state["game_status"] == "game-over"
    assert state["result"] == "1/2-1/2"
    assert state["termination_reason"] == "repetition"
    assert_pgn_matches_state(state)


def test_fifty_move_rule_ends_game():
    game = Game(board=chess.Board("7k/8/8/8/8/8/8/KR6 w - - 98 50"))
    game.submit_move("b1b2")
    assert game.snapshot()["game_status"] == "playing"
    game.submit_move("h8h7")
    state = game.snapshot()
    assert state["game_status"] == "game-over"
    assert state["result"] == "1/2-1/2"
    assert state["termination_reason"] == "fifty_move_rule"


def test_pgn_preserves_nonstandard_starting_position():
    game = Game(board=chess.Board("4k3/8/8/8/8/8/8/4K2R w - - 0 1"))
    game.submit_move("h1h2")
    assert_pgn_matches_state(game.snapshot())


def test_terminal_initial_position_cannot_be_changed():
    game = Game(board=chess.Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1"))
    state = game.snapshot()
    assert state["game_status"] == "game-over"
    assert state["result"] == "1-0"
    assert state["termination_reason"] == "checkmate"
    with pytest.raises(GameOver):
        game.resign("black")
    assert game.snapshot() == state
