"""Terminal-only engine analysis. Never import this module from live game/provider paths."""

import chess
import chess.engine
from time import monotonic

MAX_PLIES = 160
POSITION_SECONDS = 0.05
TOTAL_SECONDS = 30.0


def unavailable(reason: str) -> dict:
    return {"status": "unavailable", "reason": reason}


def run_analysis(board: chess.Board, executable: str) -> dict:
    if len(board.move_stack) > MAX_PLIES:
        return unavailable("game_too_long")
    moves = list(board.move_stack)
    replay = board.root()
    deadline = monotonic() + TOTAL_SECONDS
    try:
        with chess.engine.SimpleEngine.popen_uci(executable, timeout=1.0) as engine:
            def evaluate() -> int:
                if monotonic() >= deadline:
                    raise TimeoutError
                score = engine.analyse(replay, chess.engine.Limit(time=POSITION_SECONDS))["score"]
                value = score.white().score(mate_score=10000)
                if value is None:
                    raise ValueError("No engine score")
                return value

            before = evaluate()
            rows = []
            accuracy = {"white": [], "black": []}
            for ply, move in enumerate(moves, 1):
                color = "white" if replay.turn else "black"
                san = replay.san(move)
                replay.push(move)
                after = evaluate()
                loss = max(0, (before - after) * (1 if color == "white" else -1))
                category = ("best" if loss <= 15 else "good" if loss <= 50 else
                            "inaccuracy" if loss <= 100 else "mistake" if loss <= 250 else "blunder")
                accuracy[color].append(max(0, 100 - loss / 5))
                rows.append({"ply": ply, "san": san, "uci": move.uci(), "mover": color,
                             "evaluation_cp": after, "centipawn_loss": loss, "classification": category})
                before = after
            return {"status": "complete", "moves": rows,
                    "white_accuracy": round(sum(accuracy["white"]) / len(accuracy["white"]), 1) if accuracy["white"] else None,
                    "black_accuracy": round(sum(accuracy["black"]) / len(accuracy["black"]), 1) if accuracy["black"] else None}
    except (OSError, chess.engine.EngineError, chess.engine.EngineTerminatedError):
        return unavailable("engine_unavailable")
    except (TimeoutError, KeyError, TypeError, ValueError, chess.engine.EngineError):
        return unavailable("engine_failed")
