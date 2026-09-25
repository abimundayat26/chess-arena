from fastapi.testclient import TestClient

from backend.app import create_app
from backend.game import GameStore, IllegalMove
from backend.providers import ProviderBinding
from backend.providers import ProviderError


class Clock:
    value = 0.0

    def __call__(self):
        return self.value


class RetryProvider:
    def __init__(self):
        self.calls = 0

    async def choose_move(self, position):
        self.calls += 1
        return "bad" if self.calls == 1 else "e7e5"

    async def choose_draw(self, position):
        raise AssertionError


def test_move_clock_samples_and_restart(tmp_path):
    clock = Clock()
    path = str(tmp_path / "games.db")
    store = GameStore(clock=clock, wall_clock=clock, path=path)
    game_id = store.create("3+2")["game_id"]
    clock.value = 3
    store.move(game_id, "e2e4")
    clock.value = 8
    store.move(game_id, "e7e5")
    clock.value = 12
    store.move(game_id, "g1f3")
    store.resign(game_id, "black")
    metrics = store.metrics(game_id)
    assert metrics["white_move_times_ms"] == [3000, 4000]
    assert metrics["black_move_times_ms"] == [5000]
    assert metrics["average_model_move_time_ms"] is None
    assert metrics["provider_attempt_count"] == 0
    assert GameStore(clock=clock, wall_clock=clock, path=path).metrics(game_id) == metrics


def test_provider_attempts_retries_and_terminal_metrics(tmp_path):
    store = GameStore(path=str(tmp_path / "games.db"))
    provider = RetryProvider()
    with TestClient(create_app(store, {"openai": ProviderBinding("fake", provider)})) as client:
        game_id = client.post("/games", json={"model_provider": "openai", "model_color": "black"}).json()["game_id"]
        assert client.get(f"/games/{game_id}/metrics").status_code == 409
        client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"})
        assert client.post(f"/games/{game_id}/model-turn").status_code == 200
        client.post(f"/games/{game_id}/resign", json={"color": "white"})
        metrics = client.get(f"/games/{game_id}/metrics").json()
    assert metrics["provider_attempt_count"] == 2
    assert metrics["retry_count"] == 1
    assert metrics["provider_failure_count"] == 0
    assert metrics["illegal_model_move_count"] == 1
    assert len(metrics["black_move_times_ms"]) == 1
    assert metrics["average_model_move_time_ms"] == metrics["median_model_move_time_ms"]
    assert GameStore(path=str(tmp_path / "games.db")).metrics(game_id) == metrics


def test_move_sample_includes_rejected_move_and_restart_downtime(tmp_path):
    clock = Clock()
    path = str(tmp_path / "games.db")
    store = GameStore(clock=clock, wall_clock=clock, path=path)
    game_id = store.create("3+2")["game_id"]
    clock.value = 1
    store.move(game_id, "e2e4")
    clock.value = 2
    store.move(game_id, "e7e5")
    clock.value = 4
    try:
        store.move(game_id, "e4e6")
    except IllegalMove:
        pass
    else:
        raise AssertionError("illegal move accepted")
    clock.value = 6
    restored = GameStore(clock=clock, wall_clock=clock, path=path)
    clock.value = 7
    restored.move(game_id, "g1f3")
    restored.resign(game_id, "black")
    assert restored.metrics(game_id)["white_move_times_ms"] == [1000, 5000]


def test_provider_failure_after_invalid_retry_is_counted_once(tmp_path):
    class FailingRetryProvider:
        def __init__(self):
            self.calls = 0

        async def choose_move(self, position):
            self.calls += 1
            if self.calls == 1:
                return "bad"
            raise ProviderError("fake failure")

        async def choose_draw(self, position):
            raise AssertionError

    path = str(tmp_path / "games.db")
    store = GameStore(path=path)
    with TestClient(create_app(store, {"openai": ProviderBinding("fake", FailingRetryProvider())})) as client:
        game_id = client.post("/games", json={"model_provider": "openai", "model_color": "black"}).json()["game_id"]
        assert client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}).status_code == 200
        assert client.post(f"/games/{game_id}/model-turn").status_code == 502
        assert client.post(f"/games/{game_id}/resign", json={"color": "white"}).status_code == 200
        metrics = client.get(f"/games/{game_id}/metrics").json()
    assert (metrics["provider_attempt_count"], metrics["retry_count"], metrics["provider_failure_count"]) == (2, 1, 1)
    assert metrics["illegal_model_move_count"] == 1
    assert GameStore(path=path).metrics(game_id) == metrics
