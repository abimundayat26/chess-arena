from fastapi.testclient import TestClient
from dataclasses import fields
import chess.engine

from backend import analysis
from backend.app import create_app
from backend.game import GameStore
from backend.providers import ProviderBinding


class RecordingProvider:
    def __init__(self):
        self.positions = []

    async def choose_move(self, position):
        self.positions.append(position)
        return "e7e5"

    async def choose_draw(self, position):
        self.positions.append(position)
        return False


def test_engine_never_called_during_live_game_or_provider_request(monkeypatch):
    calls = []
    monkeypatch.setattr("backend.app.run_analysis", lambda *args: calls.append(args))
    adapter = RecordingProvider()
    store = GameStore()
    with TestClient(create_app(store, {"openai": ProviderBinding("test-model", adapter)})) as client:
        game_id = client.post("/games", json={"model_provider": "openai", "model_color": "black", "context_level": "structured_position"}).json()["game_id"]
        assert client.post(f"/games/{game_id}/analysis").status_code == 409
        assert client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).status_code == 200
        assert client.post(f"/games/{game_id}/model-turn").status_code == 200
        assert calls == []
        assert len(adapter.positions) == 1
        assert not any("evaluation" in field.name or "analysis" in field.name for field in fields(adapter.positions[0]))


def test_missing_engine_unavailable_and_complete_cache_after_restart(tmp_path, monkeypatch):
    path = str(tmp_path / "game.db")
    store = GameStore(path=path)
    game_id = store.create()["game_id"]
    store.move(game_id, "e2e4")
    store.resign(game_id, "black")
    monkeypatch.setenv("CHESS_STOCKFISH_PATH", "/no/such/stockfish")
    with TestClient(create_app(store, {})) as client:
        assert client.post(f"/games/{game_id}/analysis").json() == {"status": "unavailable", "reason": "engine_unavailable"}
    expected = {"status": "complete", "moves": [], "white_accuracy": None, "black_accuracy": None}
    monkeypatch.setattr("backend.app.run_analysis", lambda board, path: expected)
    with TestClient(create_app(store, {})) as client:
        assert client.post(f"/games/{game_id}/analysis").json() == expected
    monkeypatch.setattr("backend.app.run_analysis", lambda *args: (_ for _ in ()).throw(AssertionError("cached")))
    with TestClient(create_app(GameStore(path=path), {})) as client:
        assert client.post(f"/games/{game_id}/analysis").json() == expected


def test_classification_and_accuracy_use_evaluations(monkeypatch):
    class FakeEngine:
        def __init__(self):
            self.scores = iter([0, -20, 10])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def analyse(self, board, limit):
            return {"score": chess.engine.PovScore(chess.engine.Cp(next(self.scores)), chess.WHITE)}

    import chess
    monkeypatch.setattr(analysis.chess.engine.SimpleEngine, "popen_uci", lambda *args, **kwargs: FakeEngine())
    board = chess.Board()
    board.push_uci("e2e4")
    board.push_uci("e7e5")
    result = analysis.run_analysis(board, "fake")
    assert result["status"] == "complete"
    assert [row["classification"] for row in result["moves"]] == ["good", "good"]
    assert [row["centipawn_loss"] for row in result["moves"]] == [20, 30]
    assert result["white_accuracy"] == 96.0
    assert result["black_accuracy"] == 94.0


def test_engine_failure_after_start_is_not_reported_as_missing(monkeypatch):
    class FailingEngine:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def analyse(self, board, limit):
            raise chess.engine.EngineError("analysis failed")

    import chess
    monkeypatch.setattr(analysis.chess.engine.SimpleEngine, "popen_uci", lambda *args, **kwargs: FailingEngine())
    assert analysis.run_analysis(chess.Board(), "fake") == {"status": "unavailable", "reason": "engine_failed"}


def test_too_long_game_skips_engine_process(monkeypatch):
    import chess
    board = chess.Board()
    for _ in range(41):
        for uci in ("g1f3", "g8f6", "f3g1", "f6g8"):
            board.push_uci(uci)
    monkeypatch.setattr(analysis.chess.engine.SimpleEngine, "popen_uci", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("started")))
    assert analysis.run_analysis(board, "fake") == {"status": "unavailable", "reason": "game_too_long"}
