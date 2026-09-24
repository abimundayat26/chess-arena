"use client"

import { useCallback, useMemo, useRef, useState } from "react"
import { Chess, type Square, type PieceSymbol, type Move } from "chess.js"

import type { GameOverInfo, PlayerColor, TerminationReason } from "@/lib/chess/types"

export interface BoardSquare {
  square: Square
  type: PieceSymbol
  color: "w" | "b"
}

function computeGameOver(game: Chess): GameOverInfo | null {
  if (!game.isGameOver()) return null

  let terminationReason: TerminationReason = "checkmate"
  let winner: PlayerColor | "draw" = "draw"

  if (game.isCheckmate()) {
    terminationReason = "checkmate"
    winner = game.turn() === "w" ? "black" : "white"
  } else if (game.isStalemate()) {
    terminationReason = "stalemate"
  } else if (game.isInsufficientMaterial()) {
    terminationReason = "insufficient_material"
  } else if (game.isThreefoldRepetition()) {
    terminationReason = "repetition"
  } else if (game.isDrawByFiftyMoves()) {
    terminationReason = "fifty_move_rule"
  }

  return {
    result: winner === "white" ? "1-0" : winner === "black" ? "0-1" : "1/2-1/2",
    terminationReason,
    winner,
  }
}

export function useChessGame() {
  const gameRef = useRef(new Chess())
  const [, setVersion] = useState(0)
  const bump = useCallback(() => setVersion((v) => v + 1), [])

  const [lastMove, setLastMove] = useState<{ from: Square; to: Square } | null>(null)
  const [checkSquare, setCheckSquare] = useState<Square | null>(null)

  const findKingSquare = useCallback((color: "w" | "b"): Square | null => {
    const board = gameRef.current.board()
    for (const row of board) {
      for (const cell of row) {
        if (cell && cell.type === "k" && cell.color === color) {
          return cell.square
        }
      }
    }
    return null
  }, [])

  const syncCheckSquare = useCallback(() => {
    const game = gameRef.current
    if (game.isCheck()) {
      setCheckSquare(findKingSquare(game.turn()))
    } else {
      setCheckSquare(null)
    }
  }, [findKingSquare])

  const board = useMemo<BoardSquare[]>(() => {
    const squares: BoardSquare[] = []
    for (const row of gameRef.current.board()) {
      for (const cell of row) {
        if (cell) {
          squares.push({ square: cell.square, type: cell.type, color: cell.color })
        }
      }
    }
    return squares
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameRef.current.fen()])

  const legalMovesFrom = useCallback((square: Square): Move[] => {
    return gameRef.current.moves({ square, verbose: true }) as Move[]
  }, [])

  const makeMove = useCallback(
    (from: Square, to: Square, promotion?: string): Move | null => {
      try {
        const move = gameRef.current.move({ from, to, promotion })
        setLastMove({ from, to })
        syncCheckSquare()
        bump()
        return move
      } catch {
        return null
      }
    },
    [bump, syncCheckSquare],
  )

  const makeRandomMove = useCallback((): Move | null => {
    const game = gameRef.current
    const moves = game.moves({ verbose: true }) as Move[]
    if (moves.length === 0) return null
    const choice = moves[Math.floor(Math.random() * moves.length)]
    const move = game.move({ from: choice.from, to: choice.to, promotion: choice.promotion })
    setLastMove({ from: choice.from, to: choice.to })
    syncCheckSquare()
    bump()
    return move
  }, [bump, syncCheckSquare])

  const reset = useCallback(() => {
    gameRef.current = new Chess()
    setLastMove(null)
    setCheckSquare(null)
    bump()
  }, [bump])

  const resignOrEndByAgreement = useCallback(() => {
    bump()
  }, [bump])

  const turn: PlayerColor = gameRef.current.turn() === "w" ? "white" : "black"
  const fen = gameRef.current.fen()
  const isGameOver = gameRef.current.isGameOver()
  const gameOverInfo = computeGameOver(gameRef.current)
  const sanHistory = gameRef.current.history()
  const pgn = gameRef.current.pgn()
  const moveCount = sanHistory.length

  return {
    board,
    turn,
    fen,
    isGameOver,
    gameOverInfo,
    lastMove,
    checkSquare,
    sanHistory,
    pgn,
    moveCount,
    legalMovesFrom,
    makeMove,
    makeRandomMove,
    reset,
    resignOrEndByAgreement,
    getGame: () => gameRef.current,
  }
}

export type ChessGame = ReturnType<typeof useChessGame>
