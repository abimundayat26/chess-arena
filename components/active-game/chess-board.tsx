"use client"

import { useMemo, useState } from "react"
import type { Move, PieceSymbol, Square } from "chess.js"

import type { ChessGame } from "@/hooks/use-chess-game"
import type { PlayerColor } from "@/lib/chess/types"
import { cn } from "@/lib/utils"

import { ChessPieceIcon } from "./chess-piece"
import { PromotionDialog } from "./promotion-dialog"

const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"]
const RANKS = [8, 7, 6, 5, 4, 3, 2, 1]

interface ChessBoardProps {
  game: ChessGame
  orientation: PlayerColor
  disabled: boolean
  onMove: (from: Square, to: Square, promotion?: PieceSymbol) => void
}

export function ChessBoard({
  game,
  orientation,
  disabled,
  onMove,
}: ChessBoardProps) {
  const [selected, setSelected] = useState<Square | null>(null)
  const [pendingPromotion, setPendingPromotion] = useState<{
    from: Square
    to: Square
    color: "w" | "b"
  } | null>(null)

  const files = orientation === "white" ? FILES : [...FILES].reverse()
  const ranks = orientation === "white" ? RANKS : [...RANKS].reverse()

  const pieceBySquare = useMemo(() => {
    const map = new Map<Square, { type: PieceSymbol; color: "w" | "b" }>()
    for (const piece of game.board) {
      map.set(piece.square, { type: piece.type, color: piece.color })
    }
    return map
  }, [game.board])

  const legalMoves: Move[] = useMemo(() => {
    if (!selected || disabled) return []
    return game.legalMovesFrom(selected)
  }, [selected, game, disabled])

  const legalTargets = useMemo(() => {
    const targets = new Map<Square, Move>()
    for (const move of legalMoves) {
      targets.set(move.to, move)
    }
    return targets
  }, [legalMoves])

  function clearSelection() {
    setSelected(null)
  }

  function attemptMove(from: Square, to: Square) {
    const move = legalTargets.get(to)
    if (!move) return

    if (move.promotion) {
      setPendingPromotion({ from, to, color: move.color })
      clearSelection()
      return
    }

    clearSelection()
    onMove(from, to)
  }

  function handleSquareClick(square: Square) {
    if (disabled || pendingPromotion) return

    const piece = pieceBySquare.get(square)

    if (selected) {
      if (square === selected) {
        clearSelection()
        return
      }
      if (legalTargets.has(square)) {
        attemptMove(selected, square)
        return
      }
      if (piece && piece.color === (game.turn === "white" ? "w" : "b")) {
        setSelected(square)
        return
      }
      clearSelection()
      return
    }

    if (piece && piece.color === (game.turn === "white" ? "w" : "b")) {
      setSelected(square)
    }
  }

  function handleDragStart(square: Square) {
    if (disabled || pendingPromotion) return
    const piece = pieceBySquare.get(square)
    if (piece && piece.color === (game.turn === "white" ? "w" : "b")) {
      setSelected(square)
    }
  }

  function handleDrop(square: Square) {
    if (disabled || pendingPromotion || !selected) return
    if (legalTargets.has(square)) {
      attemptMove(selected, square)
    } else {
      clearSelection()
    }
  }

  function handlePromotionSelect(piece: PieceSymbol) {
    if (!pendingPromotion) return
    onMove(pendingPromotion.from, pendingPromotion.to, piece)
    setPendingPromotion(null)
  }

  return (
    <div className="relative mx-auto w-full max-w-[560px]">
      <div className="rounded-md border-[6px] border-board-border bg-board-border p-1 shadow-sm">
        <div className="grid grid-cols-8 overflow-hidden rounded-[2px]">
          {ranks.map((rank) =>
            files.map((file) => {
              const square = `${file}${rank}` as Square
              const piece = pieceBySquare.get(square)
              const isDark =
                (FILES.indexOf(file) + RANKS.indexOf(rank)) % 2 === 1
              const isSelected = selected === square
              const isLastMove =
                game.lastMove &&
                (game.lastMove.from === square || game.lastMove.to === square)
              const isCheck = game.checkSquare === square

              return (
                <button
                  key={square}
                  type="button"
                  onClick={() => handleSquareClick(square)}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault()
                    handleDrop(square)
                  }}
                  className={cn(
                    "relative flex aspect-square items-center justify-center select-none",
                    isDark ? "bg-board-dark" : "bg-board-light"
                  )}
                  aria-label={`${square}${piece ? ` ${piece.color === "w" ? "white" : "black"} ${piece.type}` : ""}`}
                >
                  {isLastMove && (
                    <span
                      className="absolute inset-0 bg-board-last-move"
                      aria-hidden
                    />
                  )}
                  {isCheck && (
                    <span
                      className="absolute inset-0 rounded-[2px] bg-board-check"
                      aria-hidden
                    />
                  )}
                  {isSelected && (
                    <span
                      className="absolute inset-0 ring-2 ring-board-selected ring-inset"
                      aria-hidden
                    />
                  )}

                  {piece && (
                    <div
                      draggable={!disabled}
                      onDragStart={() => handleDragStart(square)}
                      className={cn(
                        "relative z-10 flex size-[86%] items-center justify-center",
                        !disabled && "cursor-grab active:cursor-grabbing"
                      )}
                    >
                      <ChessPieceIcon
                        type={piece.type}
                        color={piece.color}
                        className="size-full drop-shadow-sm"
                      />
                    </div>
                  )}

                  {file === files[0] && (
                    <span className="absolute top-0.5 left-1 text-[10px] font-medium text-foreground/50">
                      {rank}
                    </span>
                  )}
                  {rank === ranks[ranks.length - 1] && (
                    <span className="absolute right-1 bottom-0.5 text-[10px] font-medium text-foreground/50">
                      {file}
                    </span>
                  )}
                </button>
              )
            })
          )}
        </div>
      </div>

      {pendingPromotion && (
        <PromotionDialog
          open
          color={pendingPromotion.color}
          onSelect={handlePromotionSelect}
        />
      )}
    </div>
  )
}
