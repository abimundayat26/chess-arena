import type { PieceSymbol } from "chess.js"

interface ChessPieceIconProps {
  type: PieceSymbol
  color: "w" | "b"
  className?: string
}

const PIECES: Record<PieceSymbol, string> = {
  p: "♟",
  n: "♞",
  b: "♝",
  r: "♜",
  q: "♛",
  k: "♚",
}

export function ChessPieceIcon({ type, color, className }: ChessPieceIconProps) {
  return (
    <svg viewBox="0 0 45 45" className={className} aria-hidden focusable="false">
      <text
        x="22.5"
        y="23"
        dominantBaseline="central"
        textAnchor="middle"
        fontFamily='"DejaVu Sans", "Segoe UI Symbol", "Apple Symbols", sans-serif'
        fontSize="39"
        fill={color === "w" ? "oklch(0.97 0.012 75)" : "oklch(0.22 0.02 50)"}
        stroke={color === "w" ? "oklch(0.32 0.02 50)" : "oklch(0.15 0.012 50)"}
        strokeWidth="0.6"
        paintOrder="stroke"
      >
        {PIECES[type]}
      </text>
    </svg>
  )
}
