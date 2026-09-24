"""In-memory, authoritative chess state and game operations."""

from dataclasses import dataclass, field
from threading import RLock
from uuid import uuid4

import chess
import chess.pgn


class GameNotFound(Exception):
    pass


class GameOver(Exception):
    pass


class IllegalMove(Exception):
    pass


@dataclass
class Game:
    id: str = field(default_factory=lambda: str(uuid4()))
    board: chess.Board = field(default_factory=chess.Board)
    status: str = "playing"
    result: str = "*"
    termination_reason: str | None = None

    def snapshot(self) -> dict:
        pgn_game = chess.pgn.Game.from_board(self.board)
        pgn_game.headers["Result"] = self.result
        return {
            "game_id": self.id,
            "fen": self.board.fen(),
            "pgn": pgn_game.accept(chess.pgn.StringExporter(headers=False, variations=False, comments=False)),
            "side_to_move": "white" if self.board.turn == chess.WHITE else "black",
            "legal_moves": [move.uci() for move in self.board.legal_moves] if self.status == "playing" else [],
            "game_status": self.status,
            "result": self.result,
            "termination_reason": self.termination_reason,
        }

    def submit_move(self, uci: str) -> None:
        self._require_playing()
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            raise IllegalMove("Invalid UCI move") from exc
        if move not in self.board.legal_moves:
            raise IllegalMove("Illegal move")
        self.board.push(move)
        outcome = self.board.outcome(claim_draw=True)
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

    def resign(self, color: str) -> None:
        self._require_playing()
        self._finish("0-1" if color == "white" else "1-0", "resignation")

    def offer_draw(self, accepted: bool) -> None:
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


class GameStore:
    def __init__(self) -> None:
        self._games: dict[str, Game] = {}
        self._lock = RLock()

    def create(self) -> dict:
        with self._lock:
            game = Game()
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
