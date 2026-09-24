"""HTTP API for authoritative chess, clocks, and one model turn."""

import asyncio
from dataclasses import replace
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

from backend.game import GameNotFound, GameOver, GameStore, IllegalMove, ModelTurnConflict
from backend.providers import ProviderBinding, configured_providers


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
    accepted: bool


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
    games = store if store is not None else GameStore()
    available = providers if providers is not None else configured_providers()

    @app.post("/games", status_code=201, response_model=GameState)
    async def create_game(request: CreateGameRequest | None = None):
        if request is None:
            return games.create()
        if request.model_extra:
            raise HTTPException(status_code=422, detail="Unsupported game creation field")
        if (request.model_provider is None) != (request.model_color is None):
            raise HTTPException(status_code=422, detail="Model provider and color must be supplied together")
        if request.model_provider and request.model_provider not in available:
            raise HTTPException(status_code=503, detail="Model provider is not configured")
        return games.create(request.time_control, request.model_provider, request.model_color, request.context_level)

    @app.post("/games/{game_id}/model-turn", response_model=GameState)
    async def model_turn(game_id: str):
        try:
            provider_name, position, budget, token = games.begin_model_turn(game_id)
        except GameNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (GameOver, ModelTurnConflict) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        try:
            while True:
                remaining = games.remaining_model_budget(game_id, token)
                if remaining <= 0:
                    return games.finish_model_turn(game_id, None, token)
                provider_task = asyncio.create_task(available[provider_name].adapter.choose_move(position))
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
                        return games.finish_model_turn(game_id, None, token)
                except asyncio.CancelledError:
                    provider_task.cancel()
                    raise
                if not isinstance(uci, str):
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
            raise HTTPException(status_code=502, detail="Model turn failed") from None

    @app.get("/games/{game_id}", response_model=GameState)
    async def get_game(game_id: str):
        try:
            return games.get(game_id)
        except GameNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/games/{game_id}/moves", response_model=GameState)
    async def submit_move(game_id: str, request: MoveRequest):
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
    async def resign(game_id: str, request: ResignRequest):
        try:
            return games.resign(game_id, request.color)
        except GameNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GameOver as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/games/{game_id}/draw-offer", response_model=GameState)
    async def offer_draw(game_id: str, request: DrawOfferRequest):
        try:
            return games.offer_draw(game_id, request.accepted)
        except GameNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GameOver as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


app = create_app()
