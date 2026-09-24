"""HTTP API for the Phase 2 chess backend."""

from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.game import GameNotFound, GameOver, GameStore, IllegalMove


class CreateGameRequest(BaseModel):
    time_control: Literal["3+0", "3+2", "5+0", "5+3", "10+0", "10+5", "15+10", "20+0"] = "10+5"


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
    white_clock_ms: int
    black_clock_ms: int
    active_clock: Literal["white", "black"] | None


def create_app(store: GameStore | None = None) -> FastAPI:
    app = FastAPI(title="Multi-Model Chess Arena")
    games = store if store is not None else GameStore()

    @app.post("/games", status_code=201, response_model=GameState)
    async def create_game(request: CreateGameRequest | None = None):
        return games.create(request.time_control if request else "10+5")

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
