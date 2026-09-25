"""HTTP API for authoritative chess, clocks, and one model turn."""

import asyncio
from dataclasses import replace
from hashlib import sha256
import os
import secrets
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from backend.game import GameCorrupt, GameNotFound, GameOver, GameStore, IllegalMove, ModelTurnConflict
from backend.providers import ADAPTERS, ProviderBinding, configured_providers
from backend.analysis import run_analysis, unavailable


class CreateGameRequest(BaseModel):
    # Inspect unknown fields in the endpoint so rejection never echoes a supplied key.
    model_config = ConfigDict(extra="allow")

    time_control: Literal["3+0", "3+2", "5+0", "5+3", "10+0", "10+5", "15+10", "20+0"] = "10+5"
    model_provider: Literal["openai", "anthropic", "gemini", "openrouter"] | None = None
    model_color: Literal["white", "black"] | None = None
    context_level: Literal["minimal", "game_context", "structured_position"] = "minimal"


class MoveRequest(BaseModel):
    uci: str


class ResignRequest(BaseModel):
    color: Literal["white", "black"]


class DrawOfferRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    accepted: bool | None = None


class GameState(BaseModel):
    game_id: str
    fen: str
    pgn: str
    side_to_move: Literal["white", "black"]
    legal_moves: list[str]
    game_status: Literal["playing", "game-over"]
    result: str
    termination_reason: str | None
    time_control: str
    model_provider: str | None
    model_color: Literal["white", "black"] | None
    context_level: Literal["minimal", "game_context", "structured_position"]
    illegal_model_move_count: int
    white_clock_ms: int
    black_clock_ms: int
    active_clock: Literal["white", "black"] | None


def create_app(
    store: GameStore | None = None,
    providers: dict[str, ProviderBinding] | None = None,
) -> FastAPI:
    app = FastAPI(title="Multi-Model Chess Arena")
    games = store if store is not None else GameStore(path=os.environ.get("CHESS_DB_PATH", ".data/chess-arena.sqlite3"))
    public_mode = os.environ.get("CHESS_PUBLIC_MODE") == "1"
    available = providers if providers is not None else ({} if public_mode else configured_providers())
    catalog = ({name: os.environ.get(f"CHESS_{name.upper()}_MODEL") for name in ADAPTERS}
               if public_mode and providers is None else {name: binding.model_id for name, binding in available.items()})
    catalog = {name: model for name, model in catalog.items() if model}
    credentials: dict[str, dict[str, str]] = {}
    public_origin = os.environ.get("CHESS_PUBLIC_ORIGIN", "")
    analysis_locks: dict[str, asyncio.Lock] = {}

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        if public_mode:
            return JSONResponse({"detail": "Invalid request"}, status_code=422)
        return await request_validation_exception_handler(request, exc)

    def session_hash(request: Request) -> str | None:
        token = request.cookies.get("chess_session")
        return sha256(token.encode()).hexdigest() if token and len(token) == 43 else None

    def set_session_cookie(response: Response, token: str) -> None:
        response.set_cookie("chess_session", token, httponly=True, secure=True,
                            samesite="strict", path="/", max_age=None)

    def require_owner(game_id: str, request: Request) -> None:
        if public_mode:
            owner = session_hash(request)
            if not owner or len(game_id) > 64:
                raise HTTPException(status_code=404, detail="Game not found")
            try:
                stored_owner = games.owner_hash(game_id)
            except (GameNotFound, GameCorrupt):
                raise HTTPException(status_code=404, detail="Game not found") from None
            if stored_owner != owner:
                raise HTTPException(status_code=404, detail="Game not found")

    def require_binding(provider_name: str, request: Request) -> ProviderBinding:
        if not public_mode:
            return available[provider_name]
        key = credentials.get(session_hash(request) or "", {}).get(provider_name)
        if not key or provider_name not in catalog:
            raise HTTPException(status_code=503, detail="Provider credential is required")
        return ProviderBinding(catalog[provider_name], ADAPTERS[provider_name](key, catalog[provider_name]))

    @app.middleware("http")
    async def public_limits(request: Request, call_next):
        if public_mode:
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                origin = request.headers.get("origin")
                if origin and (not public_origin or origin != public_origin):
                    return JSONResponse({"detail": "Forbidden"}, status_code=403)
            size = request.headers.get("content-length")
            if size and (not size.isdigit() or int(size) > 8192):
                return JSONResponse({"detail": "Request too large"}, status_code=413)
            if len(await request.body()) > 8192:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
        return await call_next(request)

    @app.get("/providers")
    async def list_providers():
        return [{"provider": name, "model": model, **({"byok": True} if public_mode else {})}
                for name, model in sorted(catalog.items())]

    @app.post("/credentials", status_code=204)
    async def register_credential(request: Request, response: Response):
        if not public_mode:
            raise HTTPException(status_code=404, detail="Not found")
        try:
            body = await request.json()
        except ValueError:
            body = None
        if (not isinstance(body, dict) or set(body) != {"provider", "api_key"} or
                not isinstance(body.get("provider"), str) or body["provider"] not in catalog or
                not isinstance(body.get("api_key"), str) or
                not 8 <= len(body["api_key"]) <= 512 or any(ord(ch) < 32 for ch in body["api_key"])):
            raise HTTPException(status_code=422, detail="Invalid credential request")
        token = request.cookies.get("chess_session")
        if session_hash(request) is None:
            token = secrets.token_urlsafe(32)
            set_session_cookie(response, token)
        credentials.setdefault(sha256(token.encode()).hexdigest(), {})[body["provider"]] = body["api_key"]
        response.headers["Cache-Control"] = "no-store"

    @app.exception_handler(GameCorrupt)
    async def corrupt_game_handler(_request, _exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"detail": "Stored game is unavailable"})

    @app.post("/games", status_code=201, response_model=GameState)
    async def create_game(http_request: Request, response: Response, request: CreateGameRequest | None = None):
        owner = session_hash(http_request) if public_mode else None
        if public_mode and owner is None:
            token = secrets.token_urlsafe(32)
            owner = sha256(token.encode()).hexdigest()
            set_session_cookie(response, token)
        if public_mode and games.active_games_for_owner(owner) >= 4:
            raise HTTPException(status_code=429, detail="Active game limit reached")
        if request is None:
            return games.create(owner_hash=owner)
        if request.model_extra:
            raise HTTPException(status_code=422, detail="Unsupported game creation field")
        if (request.model_provider is None) != (request.model_color is None):
            raise HTTPException(status_code=422, detail="Model provider and color must be supplied together")
        if request.model_provider and request.model_provider not in catalog:
            raise HTTPException(status_code=503, detail="Model provider is not configured")
        if request.model_provider and public_mode:
            require_binding(request.model_provider, http_request)
        model_id = catalog[request.model_provider] if request.model_provider else None
        return games.create(request.time_control, request.model_provider, request.model_color, request.context_level, model_id, owner)

    @app.get("/games/{game_id}/pgn")
    async def export_pgn(game_id: str, request: Request):
        require_owner(game_id, request)
        try:
            pgn = games.export_pgn(game_id)
        except GameNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GameOver as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return Response(pgn, media_type="application/x-chess-pgn; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="chess-arena-{game_id}.pgn"',
                                 "Cache-Control": "no-store"})

    @app.post("/games/{game_id}/analysis")
    async def analyze_game(game_id: str, request: Request):
        require_owner(game_id, request)
        async with analysis_locks.setdefault(game_id, asyncio.Lock()):
            try:
                board, cached = games.analysis_input(game_id)
            except GameNotFound as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except GameOver as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            if board is None:
                return cached
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(run_analysis, board, os.environ.get("CHESS_STOCKFISH_PATH", "stockfish")),
                    timeout=30.0,
                )
            except Exception:
                result = unavailable("engine_failed")
            return games.save_analysis(game_id, result)

    @app.get("/games/{game_id}/metrics")
    async def game_metrics(game_id: str, request: Request):
        require_owner(game_id, request)
        try:
            return games.metrics(game_id)
        except GameNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GameOver as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/games/{game_id}/model-turn", response_model=GameState)
    async def model_turn(game_id: str, request: Request):
        require_owner(game_id, request)
        if public_mode and games.provider_attempts(game_id) >= 200:
            raise HTTPException(status_code=429, detail="Provider attempt limit reached")
        try:
            provider_name, position, budget, token = games.begin_model_turn(game_id)
        except GameNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (GameOver, ModelTurnConflict) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        try:
            binding = require_binding(provider_name, request)
        except HTTPException:
            games.abort_model_turn(game_id, token)
            raise
        failure_recorded = False
        try:
            attempt_index = 0
            while True:
                remaining = games.remaining_model_budget(game_id, token)
                if remaining <= 0:
                    return games.finish_model_turn(game_id, None, token)
                if public_mode and games.provider_attempts(game_id) >= 200:
                    games.abort_model_turn(game_id, token)
                    raise HTTPException(status_code=429, detail="Provider attempt limit reached")
                games.record_provider_attempt(game_id, token, retry=attempt_index > 0)
                attempt_index += 1
                provider_task = asyncio.create_task(binding.adapter.choose_move(position))
                try:
                    done, pending = await asyncio.wait({provider_task}, timeout=remaining)
                    if pending:
                        provider_task.cancel()
                        provider_task.add_done_callback(
                            lambda task: task.exception() if not task.cancelled() else None
                        )
                        await asyncio.sleep(0)
                        return games.finish_model_turn(game_id, None, token)
                    try:
                        uci = provider_task.result()
                    except (Exception, asyncio.CancelledError):
                        games.record_provider_failure(game_id)
                        failure_recorded = True
                        return games.finish_model_turn(game_id, None, token)
                except asyncio.CancelledError:
                    provider_task.cancel()
                    raise
                if not isinstance(uci, str):
                    games.record_provider_failure(game_id)
                    failure_recorded = True
                    return games.finish_model_turn(game_id, None, token)
                result = games.model_attempt(game_id, uci, token)
                if result is not None:
                    return result
                position = replace(position, previous_illegal_move=uci[:32])
        except asyncio.CancelledError:
            games.abort_model_turn(game_id, token)
            raise
        except ModelTurnConflict as exc:
            games.abort_model_turn(game_id, token)
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except IllegalMove:
            if not failure_recorded:
                games.record_provider_failure(game_id)
            raise HTTPException(status_code=502, detail="Model turn failed") from None

    @app.get("/games/{game_id}", response_model=GameState)
    async def get_game(game_id: str, request: Request):
        require_owner(game_id, request)
        try:
            return games.get(game_id)
        except GameNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/games/{game_id}/moves", response_model=GameState)
    async def submit_move(game_id: str, request: MoveRequest, http_request: Request):
        require_owner(game_id, http_request)
        try:
            return games.move(game_id, request.uci)
        except GameNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GameOver as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except IllegalMove as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ModelTurnConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/games/{game_id}/resign", response_model=GameState)
    async def resign(game_id: str, request: ResignRequest, http_request: Request):
        require_owner(game_id, http_request)
        try:
            return games.resign(game_id, request.color)
        except GameNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GameOver as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/games/{game_id}/draw-offer", response_model=GameState)
    async def offer_draw(game_id: str, request: DrawOfferRequest, http_request: Request):
        require_owner(game_id, http_request)
        try:
            current = games.get(game_id)
            if current["game_status"] == "game-over":
                raise HTTPException(status_code=409, detail="Game is over")
            if current["model_provider"] is None:
                if request.accepted is None or request.model_extra:
                    raise HTTPException(status_code=422, detail="Unbound draw offer requires accepted")
                return games.offer_draw(game_id, request.accepted)
            if "accepted" in request.model_fields_set or request.model_extra:
                raise HTTPException(status_code=422, detail="Bound draw decision accepts no client decision")
            if public_mode and games.provider_attempts(game_id) >= 200:
                raise HTTPException(status_code=429, detail="Provider attempt limit reached")
            provider_name, position, budget, token = games.begin_draw_decision(game_id)
        except GameNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (GameOver, ModelTurnConflict) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        try:
            binding = require_binding(provider_name, http_request)
        except HTTPException:
            games.abort_draw_decision(game_id, token)
            raise
        games.record_provider_attempt(game_id, token)
        provider_task = asyncio.create_task(binding.adapter.choose_draw(position))
        try:
            done, pending = await asyncio.wait({provider_task}, timeout=budget)
            if pending:
                provider_task.cancel()
                provider_task.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
                await asyncio.sleep(0)
                decision = None
            else:
                try:
                    answer = provider_task.result()
                    decision = answer if type(answer) is bool else None
                except (Exception, asyncio.CancelledError):
                    decision = None
        except asyncio.CancelledError:
            provider_task.cancel()
            games.abort_draw_decision(game_id, token)
            raise
        try:
            if decision is None:
                games.record_provider_failure(game_id)
            return games.finish_draw_decision(game_id, decision, token)
        except ModelTurnConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except IllegalMove:
            if decision is not None:
                games.record_provider_failure(game_id)
            raise HTTPException(status_code=502, detail="Model draw decision failed") from None

    return app


app = create_app()
