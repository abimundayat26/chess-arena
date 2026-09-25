import json
import sqlite3

from fastapi.testclient import TestClient
import httpx

from backend.app import create_app
from backend.game import GameStore
from backend.providers import ADAPTERS, OpenAIAdapter


ORIGIN = "https://chess.example.test"
KEY = "sk-fake-test-credential-only"


def public_app(monkeypatch, store):
    monkeypatch.setenv("CHESS_PUBLIC_MODE", "1")
    monkeypatch.setenv("CHESS_PUBLIC_ORIGIN", ORIGIN)
    monkeypatch.setenv("CHESS_OPENAI_MODEL", "approved-test-model")
    monkeypatch.setenv("CHESS_GEMINI_MODEL", "approved-gemini-model")
    seen = []

    def intercept(request):
        seen.append(request)
        return httpx.Response(200, json={"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "e7e5"}]}]})

    transport = httpx.MockTransport(intercept)
    monkeypatch.setitem(ADAPTERS, "openai", lambda key, model: OpenAIAdapter(key, model, transport))
    return create_app(store), seen


def test_byok_ownership_transport_and_restart(tmp_path, monkeypatch):
    path = str(tmp_path / "games.db")
    app, seen = public_app(monkeypatch, GameStore(path=path))
    with TestClient(app, base_url=ORIGIN) as owner, TestClient(app, base_url=ORIGIN) as stranger:
        assert owner.get("/providers").json() == [
            {"provider": "gemini", "model": "approved-gemini-model", "byok": True},
            {"provider": "openai", "model": "approved-test-model", "byok": True},
        ]
        credential = owner.post("/credentials", json={"provider": "openai", "api_key": KEY}, headers={"Origin": ORIGIN})
        assert credential.status_code == 204
        assert KEY not in str(credential.headers)
        assert "httponly" in credential.headers["set-cookie"].lower()
        assert "secure" in credential.headers["set-cookie"].lower()
        assert "samesite=strict" in credential.headers["set-cookie"].lower()
        created = owner.post("/games", json={"model_provider": "openai", "model_color": "black"}, headers={"Origin": ORIGIN})
        assert created.status_code == 201, created.text
        game_id = created.json()["game_id"]
        assert stranger.get(f"/games/{game_id}").status_code == 404
        assert owner.get("/games/no-such-game").status_code == 404
        assert stranger.post(f"/games/{game_id}/model-turn", headers={"Origin": ORIGIN}).status_code == 404
        assert owner.post("/games", json={"model_provider": "gemini", "model_color": "black"}, headers={"Origin": ORIGIN}).status_code == 503
        assert owner.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}, headers={"Origin": ORIGIN}).status_code == 200
        result = owner.post(f"/games/{game_id}/model-turn", headers={"Origin": ORIGIN})
        assert result.status_code == 200, result.text
        assert len(seen) == 1
        assert seen[0].headers["Authorization"] == f"Bearer {KEY}"
        assert KEY not in seen[0].content.decode()
        assert KEY not in json.dumps(result.json())
        assert owner.post(f"/games/{game_id}/resign", json={"color": "white"}, headers={"Origin": ORIGIN}).status_code == 200
        assert stranger.get(f"/games/{game_id}/pgn").status_code == 404
        assert stranger.get(f"/games/{game_id}/metrics").status_code == 404
        assert stranger.post(f"/games/{game_id}/analysis", headers={"Origin": ORIGIN}).status_code == 404
        assert KEY not in owner.get(f"/games/{game_id}/pgn").text
        cookies = owner.cookies
    with sqlite3.connect(path) as connection:
        payload = connection.execute("SELECT payload FROM games WHERE id=?", (game_id,)).fetchone()[0]
    assert KEY not in payload
    assert "owner_hash" in payload
    restarted, _ = public_app(monkeypatch, GameStore(path=path))
    with TestClient(restarted, base_url=ORIGIN, cookies=cookies) as restored:
        assert restored.get(f"/games/{game_id}").status_code == 200
        assert restored.get(f"/games/{game_id}/metrics").status_code == 200


def test_public_limits_and_generic_credential_validation(tmp_path, monkeypatch):
    app, _ = public_app(monkeypatch, GameStore(path=str(tmp_path / "games.db")))
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.post("/credentials", json={"provider": "openai", "api_key": KEY}, headers={"Origin": "https://evil.test"}).status_code == 403
        invalid = client.post("/credentials", json={"provider": "openai", "api_key": KEY, "extra": "secret"}, headers={"Origin": ORIGIN})
        assert invalid.status_code == 422
        assert KEY not in invalid.text
        typed = client.post("/games", json={"time_control": KEY}, headers={"Origin": ORIGIN})
        assert typed.status_code == 422
        assert KEY not in typed.text
        assert client.post("/credentials", content="x" * 8193, headers={"Origin": ORIGIN}).status_code == 413
        for _ in range(4):
            assert client.post("/games", headers={"Origin": ORIGIN}).status_code == 201
        assert client.post("/games", headers={"Origin": ORIGIN}).status_code == 429


def test_missing_key_after_restart_and_provider_cap(tmp_path, monkeypatch):
    path = str(tmp_path / "games.db")
    store = GameStore(path=path)
    app, seen = public_app(monkeypatch, store)
    with TestClient(app, base_url=ORIGIN) as client:
        client.post("/credentials", json={"provider": "openai", "api_key": KEY}, headers={"Origin": ORIGIN})
        game_id = client.post("/games", json={"model_provider": "openai", "model_color": "black"}, headers={"Origin": ORIGIN}).json()["game_id"]
        client.post(f"/games/{game_id}/moves", json={"uci": "e2e4"}, headers={"Origin": ORIGIN})
        cookies = client.cookies
    restarted_store = GameStore(path=path)
    restarted, restarted_seen = public_app(monkeypatch, restarted_store)
    with TestClient(restarted, base_url=ORIGIN, cookies=cookies) as client:
        assert client.post(f"/games/{game_id}/model-turn", headers={"Origin": ORIGIN}).status_code == 503
        assert restarted_seen == []
        client.post("/credentials", json={"provider": "openai", "api_key": KEY}, headers={"Origin": ORIGIN})
        game = restarted_store._games[game_id]
        game.provider_attempt_count = 200
        game._changed()
        assert client.post(f"/games/{game_id}/model-turn", headers={"Origin": ORIGIN}).status_code == 429
        assert restarted_seen == []
