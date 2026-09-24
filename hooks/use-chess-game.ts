"use client"

import { useMemo } from "react"
import { Chess, type Square, type PieceSymbol, type Move } from "chess.js"

import type { ServerGame } from "@/lib/chess/api"

export interface BoardSquare {
  square: Square
  type: PieceSymbol
  color: "w" | "b"
}

// The server snapshot owns game state. chess.js supplies fast board feedback only.
export function useChessGame(snapshot: ServerGame) {
  return useMemo(() => {
    const boardGame = new Chess(snapshot.fen)
    const historyGame = new Chess()
    historyGame.loadPgn(snapshot.pgn)
    const moves = historyGame.history({ verbose: true }) as Move[]
    const last = moves.at(-1)
    const board: BoardSquare[] = boardGame
      .board()
      .flat()
      .filter((piece): piece is NonNullable<typeof piece> => piece !== null)
      .map((piece) => ({
        square: piece.square,
        type: piece.type,
        color: piece.color,
      }))
    const checkedKing = boardGame.isCheck()
      ? (board.find(
          (piece) => piece.type === "k" && piece.color === boardGame.turn()
        )?.square ?? null)
      : null
    const legal = new Set(snapshot.legal_moves)

    return {
      board,
      turn: snapshot.side_to_move,
      fen: snapshot.fen,
      pgn: snapshot.pgn,
      isGameOver: snapshot.game_status === "game-over",
      lastMove: last ? { from: last.from, to: last.to } : null,
      checkSquare: checkedKing,
      sanHistory: moves.map((move) => move.san),
      moveCount: moves.length,
      legalMovesFrom: (square: Square): Move[] =>
        (boardGame.moves({ square, verbose: true }) as Move[]).filter((move) =>
          legal.has(`${move.from}${move.to}${move.promotion ?? ""}`)
        ),
    }
  }, [snapshot])
}

export type ChessGame = ReturnType<typeof useChessGame>
