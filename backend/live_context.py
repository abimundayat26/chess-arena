"""Allowlisted live-game context and prompt; analysis must not enter this path."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelPosition:
    fen: str
    side_to_move: str
    legal_moves: tuple[str, ...]
    pgn: str | None = None
    time_remaining_ms: int | None = None
    pieces: tuple[tuple[str, str], ...] | None = None
    material_counts: tuple[tuple[str, int, int], ...] | None = None
    castling_rights: str | None = None
    fullmove_number: int | None = None
    previous_illegal_move: str | None = None
    draw_offer: bool = False
    model_color: str | None = None



def _prompt(position: ModelPosition) -> str:
    prompt = (
        ("Decide whether to accept the human's draw offer. Reply with exactly ACCEPT or DECLINE, no prose.\n"
         if position.draw_offer else "Choose one legal chess move. Reply with only its UCI notation, no prose.\n") +
        f"FEN: {position.fen}\n"
        f"Side to move: {position.side_to_move}\n"
        f"Legal UCI moves: {', '.join(position.legal_moves)}"
    )
    if position.draw_offer:
        prompt += f"\nYour color: {position.model_color}"
    if position.pgn is not None:
        prompt += f"\nPGN: {position.pgn}\nTime remaining (ms): {position.time_remaining_ms}"
    if position.pieces is not None:
        prompt += "\nPieces (square=piece): " + ", ".join(
            f"{square}={piece}" for square, piece in position.pieces
        )
        prompt += "\nMaterial counts (piece: white, black): " + ", ".join(
            f"{name}: {white}, {black}" for name, white, black in position.material_counts or ()
        )
        prompt += f"\nCastling rights: {position.castling_rights}"
        prompt += f"\nFull move number: {position.fullmove_number}"
    if position.previous_illegal_move is not None:
        prompt += f"\nThe previous proposed move {position.previous_illegal_move!r} was illegal. Choose exactly one move from the listed legal UCI moves."
    return prompt
