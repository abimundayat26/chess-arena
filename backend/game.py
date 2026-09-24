"""In-memory, authoritative chess state and game operations."""

from dataclasses import dataclass, field
from math import ceil
from threading import RLock
from time import monotonic
from typing import Callable
from uuid import uuid4

import chess
import chess.pgn


class GameNotFound(Exception):
    pass


class GameOver(Exception):
    pass


class IllegalMove(Exception):
    pass


TIME_CONTROLS = {
    "3+0": (180, 0),
    "3+2": (180, 2),
    "5+0": (300, 0),
    "5+3": (300, 3),
    "10+0": (600, 0),
    "10+5": (600, 5),
    "15+10": (900, 10),
    "20+0": (1200, 0),
}


@dataclass
class Game:
    id: str = field(default_factory=lambda: str(uuid4()))
    board: chess.Board = field(default_factory=chess.Board)
    status: str = "playing"
    result: str = "*"
    termination_reason: str | None = None
    time_control: str = "10+5"
    clock: Callable[[], float] = field(default=monotonic, repr=False)
    white_seconds: float = field(init=False)
    black_seconds: float = field(init=False)
    last_tick: float = field(init=False)

    def __post_init__(self) -> None:
        initial, _ = TIME_CONTROLS[self.time_control]
        self.white_seconds = self.black_seconds = float(initial)
        self.last_tick = self.clock()
        if self.status == "playing":
            self._finish_board_outcome()

    def snapshot(self) -> dict:
        self._charge_time()
        pgn_game = chess.pgn.Game.from_board(self.board)
        pgn_game.headers["Result"] = self.result
        return {
            "game_id": self.id,
            "fen": self.board.fen(),
            "pgn": pgn_game.accept(
                chess.pgn.StringExporter(
                    headers="FEN" in pgn_game.headers, variations=False, comments=False
                )
            ),
            "side_to_move": "white" if self.board.turn == chess.WHITE else "black",
            "legal_moves": [move.uci() for move in self.board.legal_moves] if self.status == "playing" else [],
            "game_status": self.status,
            "result": self.result,
            "termination_reason": self.termination_reason,
            "time_control": self.time_control,
            "white_clock_ms": ceil(self.white_seconds * 1000),
            "black_clock_ms": ceil(self.black_seconds * 1000),
            "active_clock": (
                "white" if self.board.turn == chess.WHITE else "black"
            ) if self.status == "playing" else None,
        }

    def submit_move(self, uci: str) -> None:
        self._charge_time()
        self._require_playing()
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            raise IllegalMove("Invalid UCI move") from exc
        if move not in self.board.legal_moves:
            raise IllegalMove("Illegal move")
        mover = self.board.turn
        self.board.push(move)
        increment = TIME_CONTROLS[self.time_control][1]
        if mover == chess.WHITE:
            self.white_seconds += increment
        else:
            self.black_seconds += increment
        self._finish_board_outcome()

    def _finish_board_outcome(self) -> None:
        outcome = self.board.outcome(claim_draw=False)
        if outcome is not None:
            reasons = {
                chess.Termination.CHECKMATE: "checkmate",
                chess.Termination.STALEMATE: "stalemate",
                chess.Termination.INSUFFICIENT_MATERIAL: "insufficient_material",
                chess.Termination.THREEFOLD_REPETITION: "repetition",
                chess.Termination.FIVEFOLD_REPETITION: "repetition",
                chess.Termination.FIFTY_MOVES: "fifty_move_rule",
                chess.Termination.SEVENTYFIVE_MOVES: "fifty_move_rule",
                chess.Termination.VARIANT_WIN: "variant_win",
                chess.Termination.VARIANT_LOSS: "variant_loss",
                chess.Termination.VARIANT_DRAW: "variant_draw",
            }
            self._finish(outcome.result(), reasons[outcome.termination])
        elif self.board.is_repetition(3):
            self._finish("1/2-1/2", "repetition")
        elif self.board.halfmove_clock >= 100:
            self._finish("1/2-1/2", "fifty_move_rule")

    def resign(self, color: str) -> None:
        self._charge_time()
        self._require_playing()
        self._finish("0-1" if color == "white" else "1-0", "resignation")

    def offer_draw(self, accepted: bool) -> None:
        self._charge_time()
        self._require_playing()
        if accepted:
            self._finish("1/2-1/2", "draw_agreement")

    def _require_playing(self) -> None:
        if self.status != "playing":
            raise GameOver("Game is over")

    def _finish(self, result: str, reason: str) -> None:
        self.status = "game-over"
        self.result = result
        self.termination_reason = reason

    def _charge_time(self) -> None:
        if self.status != "playing":
            return
        now = self.clock()
        elapsed = max(0.0, now - self.last_tick)
        self.last_tick = now
        white = self.board.turn == chess.WHITE
        remaining = (self.white_seconds if white else self.black_seconds) - elapsed
        if white:
            self.white_seconds = max(0.0, remaining)
        else:
            self.black_seconds = max(0.0, remaining)
        if remaining <= 0:
            winner = not self.board.turn
            result = (
                "1/2-1/2" if self.board.has_insufficient_material(winner)
                else "1-0" if winner == chess.WHITE else "0-1"
            )
            self._finish(result, "timeout")


class GameStore:
    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        self._games: dict[str, Game] = {}
        self._lock = RLock()
        self._clock = clock

    def create(self, time_control: str = "10+5") -> dict:
        with self._lock:
            game = Game(time_control=time_control, clock=self._clock)
            self._games[game.id] = game
            return game.snapshot()

    def get(self, game_id: str) -> dict:
        with self._lock:
            return self._find(game_id).snapshot()

    def move(self, game_id: str, uci: str) -> dict:
        with self._lock:
            game = self._find(game_id)
            game.submit_move(uci)
            return game.snapshot()

    def resign(self, game_id: str, color: str) -> dict:
        with self._lock:
            game = self._find(game_id)
            game.resign(color)
            return game.snapshot()

    def offer_draw(self, game_id: str, accepted: bool) -> dict:
        with self._lock:
            game = self._find(game_id)
            game.offer_draw(accepted)
            return game.snapshot()

    def _find(self, game_id: str) -> Game:
        try:
            return self._games[game_id]
        except KeyError as exc:
            raise GameNotFound("Game not found") from exc
