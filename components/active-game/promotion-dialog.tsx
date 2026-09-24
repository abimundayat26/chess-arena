"use client"

import type { PieceSymbol } from "chess.js"

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

import { ChessPieceIcon } from "./chess-piece"

const PROMOTION_PIECES: { type: PieceSymbol; label: string }[] = [
  { type: "q", label: "Queen" },
  { type: "r", label: "Rook" },
  { type: "b", label: "Bishop" },
  { type: "n", label: "Knight" },
]

interface PromotionDialogProps {
  open: boolean
  color: "w" | "b"
  onSelect: (piece: PieceSymbol) => void
}

export function PromotionDialog({ open, color, onSelect }: PromotionDialogProps) {
  return (
    <Dialog open={open}>
      <DialogContent className="max-w-xs" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle className="font-heading text-base">Promote pawn</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-4 gap-2">
          {PROMOTION_PIECES.map((piece) => (
            <button
              key={piece.type}
              type="button"
              onClick={() => onSelect(piece.type)}
              className="flex flex-col items-center gap-1.5 rounded-sm border border-border bg-card p-2.5 transition-colors hover:border-primary hover:bg-primary/10"
            >
              <ChessPieceIcon type={piece.type} color={color} className="size-8" />
              <span className="text-xs text-muted-foreground">{piece.label}</span>
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
