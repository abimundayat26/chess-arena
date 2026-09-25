"""In-memory, authoritative chess state and game operations."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from math import ceil, isfinite
from threading import RLock
from time import monotonic
from typing import Callable
from uuid import uuid4

import chess
import chess.pgn

from backend.providers import ModelPosition
from backend.storage import LocalStorage


class GameNotFound(Exception):
    pass


class GameCorrupt(Exception):
    pass


class GameOver(Exception):
    pass


class IllegalMove(Exception):
    pass


class ModelTurnConflict(Exception):
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
MAX_ILLEGAL_ATTEMPTS = 5


def thinking_budget(remaining_seconds: float) -> float:
    """Maximum provider time for this turn, capped by the authoritative clock."""
    if remaining_seconds >= 600:
        tier = 15
    elif remaining_seconds >= 300:
        tier = 10
    elif remaining_seconds >= 120:
        tier = 6
    elif remaining_seconds >= 30:
        tier = 3
    else:
        tier = 1
    return min(remaining_seconds, tier)


@dataclass
class Game:
    id: str = field(default_factory=lambda: str(uuid4()))
    board: chess.Board = field(default_factory=chess.Board)
    status: str = "playing"
    result: str = "*"
    termination_reason: str | None = None
    time_control: str = "10+5"
    model_provider: str | None = None
    model_color: str | None = None
    model_id: str | None = None
    created_date: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y.%m.%d"))
    context_level: str = "minimal"
    illegal_model_move_count: int = 0
    clock_override: str | None = field(default=None, repr=False)
    clock: Callable[[], float] = field(default=monotonic, repr=False)
    on_change: Callable[["Game"], None] | None = field(default=None, repr=False)
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
        return {
            "game_id": self.id,
            "fen": self.board.fen(),
            "pgn": self.pgn(),
            "side_to_move": "white" if self.board.turn == chess.WHITE else "black",
            "legal_moves": [move.uci() for move in self.board.legal_moves] if self.status == "playing" else [],
            "game_status": self.status,
            "result": self.result,
            "termination_reason": self.termination_reason,
            "time_control": self.time_control,
            "model_provider": self.model_provider,
            "model_color": self.model_color,
            "context_level": self.context_level,
            "illegal_model_move_count": self.illegal_model_move_count,
            "white_clock_ms": ceil(self.white_seconds * 1000),
            "black_clock_ms": ceil(self.black_seconds * 1000),
            "active_clock": (self.clock_override or ("white" if self.board.turn == chess.WHITE else "black")) if self.status == "playing" else None,
        }

    def pgn(self) -> str:
        pgn_game = chess.pgn.Game.from_board(self.board)
        pgn_game.headers["Result"] = self.result
        return pgn_game.accept(chess.pgn.StringExporter(
            headers="FEN" in pgn_game.headers, variations=False, comments=False
        ))

    def export_pgn(self) -> str:
        self._charge_time()
        self._require_exportable()
        record = chess.pgn.Game.from_board(self.board)
        model_name = self.model_id or ("Demo model" if self.model_provider is None else self.model_provider)
        record.headers.update({
            "Event": "Multi-Model Chess Arena", "Site": "Chess Arena",
            "Date": self.created_date, "Round": "?",
            "White": model_name if self.model_color == "white" else "Human",
            "Black": model_name if self.model_color == "black" or self.model_provider is None else "Human",
            "Result": self.result,
            "TimeControl": "+".join(str(value) for value in TIME_CONTROLS[self.time_control]),
            "Termination": self.termination_reason or "?",
            "IllegalModelMoves": str(self.illegal_model_move_count),
        })
        if self.model_provider:
            record.headers["AIProvider"] = self.model_provider
            record.headers["AIModel"] = model_name
        return record.accept(chess.pgn.StringExporter(headers=True, variations=False, comments=False)) + "\n"

    def _require_exportable(self) -> None:
        if self.status != "game-over":
            raise GameOver("Game is still active")

    def submit_move(self, uci: str, *, charge_time: bool = True) -> None:
        if charge_time:
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
        self._changed()

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
        self._changed()

    def offer_draw(self, accepted: bool) -> None:
        self._charge_time()
        self._require_playing()
        if accepted:
            self._finish("1/2-1/2", "draw_agreement")
            self._changed()

    def _changed(self) -> None:
        if self.on_change is not None:
            self.on_change(self)

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
        white = self.clock_override == "white" if self.clock_override else self.board.turn == chess.WHITE
        remaining = (self.white_seconds if white else self.black_seconds) - elapsed
        if white:
            self.white_seconds = max(0.0, remaining)
        else:
            self.black_seconds = max(0.0, remaining)
        if remaining <= 0:
            winner = not white
            result = (
                "1/2-1/2" if self.board.has_insufficient_material(winner)
                else "1-0" if winner == chess.WHITE else "0-1"
            )
            self._finish(result, "timeout")
        self._changed()


class GameStore:
    def __init__(self, clock: Callable[[], float] = monotonic, path: str | None = None,
                 wall_clock: Callable[[], float] | None = None) -> None:
        self._games: dict[str, Game] = {}
        self._corrupt_games: set[str] = set()
        self._lock = RLock()
        self._clock = clock
        self._model_calls: dict[str, tuple[object, float, float, int]] = {}
        self._draw_calls: dict[str, tuple[object, float, float]] = {}
        self._storage = None
        if path is not None:
            self._storage = LocalStorage(path, wall_clock) if wall_clock is not None else LocalStorage(path)
        if self._storage is not None:
            self._restore_games()

    def _save_game(self, game: Game) -> None:
        if self._storage is None:
            return
        self._storage.save(game.id, {
            "root_fen": game.board.root().fen(),
            "moves": [move.uci() for move in game.board.move_stack],
            "status": game.status, "result": game.result,
            "termination_reason": game.termination_reason,
            "time_control": game.time_control,
            "model_provider": game.model_provider, "model_color": game.model_color,
            "model_id": game.model_id, "created_date": game.created_date,
            "context_level": game.context_level,
            "illegal_model_move_count": game.illegal_model_move_count,
            "white_seconds": game.white_seconds, "black_seconds": game.black_seconds,
            "clock_override": game.clock_override,
        })

    def _restore_games(self) -> None:
        assert self._storage is not None
        for game_id, raw_payload, saved_wall in self._storage.load_all():
            try:
                payload = json.loads(raw_payload)
                self._restore_game(game_id, payload, saved_wall)
            except (ValueError, KeyError, TypeError, IndexError):
                self._corrupt_games.add(game_id)

    def _restore_game(self, game_id: str, payload: dict, saved_wall: float) -> None:
        assert self._storage is not None
        status = payload["status"]
        result = payload["result"]
        reason = payload["termination_reason"]
        if status == "playing":
            if result != "*" or reason is not None:
                raise ValueError("Invalid saved game result")
        elif status == "game-over":
            if result not in ("1-0", "0-1", "1/2-1/2") or not isinstance(reason, str) or not reason:
                raise ValueError("Invalid saved game result")
        else:
            raise ValueError("Invalid saved game status")
        count = payload["illegal_model_move_count"]
        if type(count) is not int or count < 0:
            raise ValueError("Invalid saved illegal-move count")
        for color in ("white", "black"):
            seconds = payload[f"{color}_seconds"]
            if type(seconds) not in (int, float) or not isfinite(seconds) or seconds < 0:
                raise ValueError("Invalid saved clock")
        board = chess.Board(payload["root_fen"])
        for uci in payload["moves"]:
            board.push_uci(uci)
        game = Game(id=game_id, board=board, time_control=payload["time_control"],
                    model_provider=payload["model_provider"], model_color=payload["model_color"],
                    model_id=payload.get("model_id"), created_date=payload.get("created_date", "????.??.??"),
                    context_level=payload["context_level"], clock=self._clock,
                    illegal_model_move_count=payload["illegal_model_move_count"])
        game.status = payload["status"]
        game.result = payload["result"]
        game.termination_reason = payload["termination_reason"]
        game.white_seconds = payload["white_seconds"]
        game.black_seconds = payload["black_seconds"]
        game.clock_override = payload["clock_override"]
        game.last_tick = self._clock()
        if game.status == "playing":
            downtime = max(0.0, self._storage.wall_clock() - saved_wall)
            game.last_tick -= downtime
            game._charge_time()
            game.clock_override = None
            game.last_tick = self._clock()
        self._games[game_id] = game
        game.on_change = self._save_game
        self._save_game(game)

    def create(
        self, time_control: str = "10+5", model_provider: str | None = None,
        model_color: str | None = None, context_level: str = "minimal", model_id: str | None = None,
    ) -> dict:
        with self._lock:
            game = Game(
                time_control=time_control, clock=self._clock,
                model_provider=model_provider, model_color=model_color,
                context_level=context_level, model_id=model_id,
            )
            self._games[game.id] = game
            game.on_change = self._save_game
            return game.snapshot()

    def get(self, game_id: str) -> dict:
        with self._lock:
            return self._find(game_id).snapshot()

    def export_pgn(self, game_id: str) -> str:
        with self._lock:
            return self._find(game_id).export_pgn()

    def move(self, game_id: str, uci: str) -> dict:
        with self._lock:
            game = self._find(game_id)
            game._charge_time()
            game._require_playing()
            if game_id in self._draw_calls:
                raise ModelTurnConflict("Draw decision already in progress")
            if game.model_color == ("white" if game.board.turn else "black"):
                raise ModelTurnConflict("Model turn must use the model-turn endpoint")
            game.submit_move(uci)
            return game.snapshot()

    def begin_model_turn(self, game_id: str) -> tuple[str, ModelPosition, float, object]:
        with self._lock:
            game = self._find(game_id)
            game._charge_time()
            game._require_playing()
            color = "white" if game.board.turn else "black"
            if game.model_provider is None or game.model_color != color:
                raise ModelTurnConflict("Not the model's turn")
            if game_id in self._model_calls or game_id in self._draw_calls:
                raise ModelTurnConflict("Model turn already in progress")
            remaining = game.white_seconds if game.board.turn else game.black_seconds
            budget = thinking_budget(remaining)
            token = object()
            self._model_calls[game_id] = (token, game.last_tick, budget, game.illegal_model_move_count)
            game._changed()
            extra = {}
            if game.context_level != "minimal":
                extra["pgn"] = game.pgn()
                remaining = game.white_seconds if game.board.turn else game.black_seconds
                extra["time_remaining_ms"] = ceil(remaining * 1000)
            if game.context_level == "structured_position":
                extra["pieces"] = tuple(
                    (chess.square_name(square), piece.symbol())
                    for square, piece in sorted(game.board.piece_map().items())
                )
                extra["material_counts"] = tuple(
                    (name, len(game.board.pieces(kind, chess.WHITE)), len(game.board.pieces(kind, chess.BLACK)))
                    for name, kind in (
                        ("pawn", chess.PAWN), ("knight", chess.KNIGHT),
                        ("bishop", chess.BISHOP), ("rook", chess.ROOK), ("queen", chess.QUEEN),
                    )
                )
                extra["castling_rights"] = game.board.castling_xfen()
                extra["fullmove_number"] = game.board.fullmove_number
            position = ModelPosition(
                game.board.fen(), color, tuple(move.uci() for move in game.board.legal_moves), **extra
            )
            return game.model_provider, position, budget, token

    def finish_model_turn(self, game_id: str, uci: str | None, token: object) -> dict:
        with self._lock:
            call = self._model_calls.get(game_id)
            if call is None or call[0] is not token:
                raise ModelTurnConflict("Game changed during model turn")
            try:
                game = self._find(game_id)
                game._charge_time()
                if game.status == "game-over" and game.termination_reason == "timeout":
                    return game.snapshot()
                if game.status != "playing" or game.model_color != ("white" if game.board.turn else "black"):
                    raise ModelTurnConflict("Game changed during model turn")
                if game.last_tick - call[1] >= call[2]:
                    raise IllegalMove("Model thinking budget expired")
                if not isinstance(uci, str):
                    raise IllegalMove("Model provider failed")
                try:
                    game.submit_move(uci, charge_time=False)
                except IllegalMove:
                    game.illegal_model_move_count += 1
                    game._changed()
                    if game.illegal_model_move_count - call[3] >= MAX_ILLEGAL_ATTEMPTS:
                        game._finish("0-1" if game.model_color == "white" else "1-0", "model_forfeit")
                        game._changed()
                        return game.snapshot()
                    raise
                return game.snapshot()
            finally:
                self._model_calls.pop(game_id, None)

    def model_attempt(self, game_id: str, uci: str, token: object) -> dict | None:
        """Return a final state, or None when another invalid attempt is allowed."""
        with self._lock:
            call = self._model_calls.get(game_id)
            if call is None or call[0] is not token:
                raise ModelTurnConflict("Game changed during model turn")
            game = self._find(game_id)
            game._charge_time()
            if game.status == "game-over" and game.termination_reason == "timeout":
                self._model_calls.pop(game_id, None)
                return game.snapshot()
            if game.status != "playing":
                self._model_calls.pop(game_id, None)
                raise ModelTurnConflict("Game changed during model turn")
            if game.last_tick - call[1] >= call[2]:
                self._model_calls.pop(game_id, None)
                raise IllegalMove("Model thinking budget expired")
            try:
                move = chess.Move.from_uci(uci)
                valid = move in game.board.legal_moves
            except ValueError:
                valid = False
            if valid:
                return self.finish_model_turn(game_id, uci, token)
            game.illegal_model_move_count += 1
            game._changed()
            if game.illegal_model_move_count - call[3] >= MAX_ILLEGAL_ATTEMPTS:
                game._finish("0-1" if game.model_color == "white" else "1-0", "model_forfeit")
                game._changed()
                self._model_calls.pop(game_id, None)
                return game.snapshot()
            return None

    def remaining_model_budget(self, game_id: str, token: object) -> float:
        with self._lock:
            call = self._model_calls.get(game_id)
            if call is None or call[0] is not token:
                raise ModelTurnConflict("Game changed during model turn")
            game = self._find(game_id)
            game._charge_time()
            if game.status == "game-over" and game.termination_reason != "timeout":
                raise ModelTurnConflict("Game changed during model turn")
            return max(0.0, min(call[2] - (game.last_tick - call[1]),
                                game.white_seconds if game.board.turn else game.black_seconds))

    def abort_model_turn(self, game_id: str, token: object) -> None:
        with self._lock:
            call = self._model_calls.get(game_id)
            if call is not None and call[0] is token:
                self._find(game_id)._charge_time()
                self._model_calls.pop(game_id, None)

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

    def begin_draw_decision(self, game_id: str) -> tuple[str, ModelPosition, float, object]:
        with self._lock:
            game = self._find(game_id)
            game._charge_time()
            game._require_playing()
            if game.model_provider is None or game.model_color is None:
                raise ModelTurnConflict("Game has no bound model")
            if game_id in self._model_calls or game_id in self._draw_calls:
                raise ModelTurnConflict("Provider action already in progress")
            game.clock_override = game.model_color
            game.last_tick = game.clock()
            game._changed()
            remaining = game.white_seconds if game.model_color == "white" else game.black_seconds
            budget = thinking_budget(remaining)
            token = object()
            self._draw_calls[game_id] = (token, game.last_tick, budget)
            extra = {}
            if game.context_level != "minimal":
                extra["pgn"] = game.pgn()
                extra["time_remaining_ms"] = ceil(remaining * 1000)
            if game.context_level == "structured_position":
                extra["pieces"] = tuple((chess.square_name(square), piece.symbol()) for square, piece in sorted(game.board.piece_map().items()))
                extra["material_counts"] = tuple((name, len(game.board.pieces(kind, chess.WHITE)), len(game.board.pieces(kind, chess.BLACK))) for name, kind in (("pawn", chess.PAWN), ("knight", chess.KNIGHT), ("bishop", chess.BISHOP), ("rook", chess.ROOK), ("queen", chess.QUEEN)))
                extra["castling_rights"] = game.board.castling_xfen()
                extra["fullmove_number"] = game.board.fullmove_number
            position = ModelPosition(game.board.fen(), "white" if game.board.turn else "black", tuple(move.uci() for move in game.board.legal_moves), draw_offer=True, model_color=game.model_color, **extra)
            return game.model_provider, position, budget, token

    def finish_draw_decision(self, game_id: str, accepted: bool | None, token: object) -> dict:
        with self._lock:
            call = self._draw_calls.get(game_id)
            if call is None or call[0] is not token:
                raise ModelTurnConflict("Game changed during draw decision")
            game = self._find(game_id)
            try:
                game._charge_time()
                if game.status == "game-over" and game.termination_reason == "timeout":
                    return game.snapshot()
                if game.status != "playing":
                    raise ModelTurnConflict("Game changed during draw decision")
                if game.last_tick - call[1] >= call[2] or accepted is None:
                    raise IllegalMove("Draw decision failed")
                if accepted:
                    game._finish("1/2-1/2", "draw_agreement")
                game.clock_override = None
                game.last_tick = game.clock()
                game._changed()
                return game.snapshot()
            finally:
                game.clock_override = None
                game.last_tick = game.clock()
                game._changed()
                self._draw_calls.pop(game_id, None)

    def abort_draw_decision(self, game_id: str, token: object) -> None:
        with self._lock:
            call = self._draw_calls.get(game_id)
            if call is not None and call[0] is token:
                game = self._find(game_id)
                game._charge_time()
                game.clock_override = None
                game.last_tick = game.clock()
                game._changed()
                self._draw_calls.pop(game_id, None)

    def _find(self, game_id: str) -> Game:
        if game_id in self._corrupt_games:
            raise GameCorrupt("Stored game is unavailable")
        try:
            return self._games[game_id]
        except KeyError as exc:
            raise GameNotFound("Game not found") from exc
