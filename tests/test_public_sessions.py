"""Adversarial public-session tests using fake credentials only."""

import asyncio
from threading import Event

from fastapi.testclient import TestClient
import httpx

from backend.app import create_app
from backend.game import GameStore
from backend.providers import ADAPTERS, OpenAIAdapter


ORIGIN = "https://chess.example.test"
FIXED_TOKEN = "a" * 43
FAKE_KEY = "sk-fake-review-only-key"


def app_with_public_models(monkeypatch, store):
    monkeypatch.setenv("CHESS_PUBLIC_MODE", "1")
    monkeypatch.setenv("CHESS_PUBLIC_ORIGIN", ORIGIN)
    monkeypatch.setenv("CHESS_OPENAI_MODEL", "approved-test-model")
    return create_app(store)


def test_caller_chosen_cookie_is_replaced_before_credential_and_game_creation(monkeypatch, tmp_path):
    app = app_with_public_models(monkeypatch, GameStore(path=str(tmp_path / "games.db")))
    with TestClient(app, base_url=ORIGIN) as owner, TestClient(app, base_url=ORIGIN) as holder:
        owner.cookies.set("chess_session", FIXED_TOKEN, domain="chess.example.test", path="/")
        credential = owner.post("/credentials", json={
            "provider": "openai", "api_key": FAKE_KEY,
        }, headers={"Origin": ORIGIN})
        assert credential.status_code == 204
        assert owner.cookies.get("chess_session") != FIXED_TOKEN
        created = owner.post("/games", json={
            "model_provider": "openai", "model_color": "black",
        }, headers={"Origin": ORIGIN})
        assert created.status_code == 201
        game_id = created.json()["game_id"]
        holder.cookies.set("chess_session", FIXED_TOKEN, domain="chess.example.test", path="/")
        assert holder.get(f"/games/{game_id}").status_code == 404


def test_caller_chosen_cookie_is_replaced_for_demo_game(monkeypatch, tmp_path):
    app = app_with_public_models(monkeypatch, GameStore(path=str(tmp_path / "games.db")))
    with TestClient(app, base_url=ORIGIN) as owner, TestClient(app, base_url=ORIGIN) as holder:
        owner.cookies.set("chess_session", FIXED_TOKEN, domain="chess.example.test", path="/")
        created = owner.post("/games", headers={"Origin": ORIGIN})
        assert created.status_code == 201
        assert owner.cookies.get("chess_session") != FIXED_TOKEN
        holder.cookies.set("chess_session", FIXED_TOKEN, domain="chess.example.test", path="/")
        assert holder.get(f"/games/{created.json()['game_id']}").status_code == 404


def test_server_issued_session_can_create_games_after_restart(monkeypatch, tmp_path):
    path = str(tmp_path / "games.db")
    first = app_with_public_models(monkeypatch, GameStore(path=path))
    with TestClient(first, base_url=ORIGIN) as client:
        game_id = client.post("/games", headers={"Origin": ORIGIN}).json()["game_id"]
        cookies = client.cookies
    restarted = app_with_public_models(monkeypatch, GameStore(path=path))
    with TestClient(restarted, base_url=ORIGIN, cookies=cookies) as client:
        assert client.get(f"/games/{game_id}").status_code == 200
        second = client.post("/games", headers={"Origin": ORIGIN})
        assert second.status_code == 201
        assert "set-cookie" not in second.headers
        assert client.get(f"/games/{second.json()['game_id']}").status_code == 200


def test_provider_cap_blocks_retry_before_another_upstream_request(monkeypatch, tmp_path):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={
            "status": "completed", "output": [{"type": "message", "content": [
                {"type": "output_text", "text": "e2e4"},
            ]}],
        })

    monkeypatch.setitem(ADAPTERS, "openai", lambda key, model: OpenAIAdapter(
        key, model, httpx.MockTransport(respond)
    ))
    store = GameStore(path=str(tmp_path / "games.db"))
    app = app_with_public_models(monkeypatch, store)
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.post("/credentials", json={
            "provider": "openai", "api_key": FAKE_KEY,
        }, headers={"Origin": ORIGIN}).status_code == 204
        game_id = client.post("/games", json={
            "model_provider": "openai", "model_color": "black",
        }, headers={"Origin": ORIGIN}).json()["game_id"]
        client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}, headers={"Origin": ORIGIN})
        game = store._games[game_id]
        game.provider_attempt_count = 199
        game._changed()
        response = client.post(f"/games/{game_id}/model-turn", headers={"Origin": ORIGIN})
        assert response.status_code == 429
        assert len(requests) == 1
        assert requests[0].headers["authorization"] == f"Bearer {FAKE_KEY}"
        assert FAKE_KEY not in requests[0].content.decode()
        state = client.get(f"/games/{game_id}").json()
        assert state["illegal_model_move_count"] == 1
        assert state["pgn"] == "1. e4 *"
        assert store.provider_attempts(game_id) == 200


def test_public_analysis_rejects_parallel_engine_work(monkeypatch, tmp_path):
    asyncio.run(_public_analysis_rejects_parallel_engine_work(monkeypatch, tmp_path))


async def _public_analysis_rejects_parallel_engine_work(monkeypatch, tmp_path):
    entered = Event()
    release = Event()
    calls = []

    def fake_analysis(board, executable):
        calls.append(executable)
        entered.set()
        release.wait(timeout=3)
        return {"status": "complete", "moves": [], "white_accuracy": None, "black_accuracy": None}

    monkeypatch.setattr("backend.app.run_analysis", fake_analysis)
    app = app_with_public_models(monkeypatch, GameStore(path=str(tmp_path / "games.db")))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as client:
        ids = []
        for _ in range(2):
            game_id = (await client.post("/games", headers={"Origin": ORIGIN})).json()["game_id"]
            await client.post(f"/games/{game_id}/resign", json={"color": "white"}, headers={"Origin": ORIGIN})
            ids.append(game_id)
        first = asyncio.create_task(client.post(f"/games/{ids[0]}/analysis", headers={"Origin": ORIGIN}))
        try:
            assert await asyncio.to_thread(entered.wait, 1)
            second = await asyncio.wait_for(client.post(
                f"/games/{ids[1]}/analysis", headers={"Origin": ORIGIN}
            ), 1)
            assert second.status_code == 429
            assert len(calls) == 1
        finally:
            release.set()
        assert (await first).status_code == 200
