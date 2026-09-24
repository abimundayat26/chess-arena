import type { PieceSymbol } from "chess.js"

interface ChessPieceIconProps {
  type: PieceSymbol
  color: "w" | "b"
  className?: string
}

const FILL = {
  w: "oklch(0.97 0.012 75)",
  b: "oklch(0.28 0.02 50)",
}

const STROKE = {
  w: "oklch(0.32 0.02 50)",
  b: "oklch(0.15 0.012 50)",
}

function Base({ fill, stroke }: { fill: string; stroke: string }) {
  return (
    <rect
      x="9"
      y="37"
      width="27"
      height="4.5"
      rx="1.5"
      fill={fill}
      stroke={stroke}
      strokeWidth="1.4"
    />
  )
}

function Body({
  fill,
  stroke,
  d,
}: {
  fill: string
  stroke: string
  d: string
}) {
  return <path d={d} fill={fill} stroke={stroke} strokeWidth="1.4" strokeLinejoin="round" />
}

export function ChessPieceIcon({ type, color, className }: ChessPieceIconProps) {
  const fill = FILL[color]
  const stroke = STROKE[color]
  const common = { fill, stroke }

  return (
    <svg viewBox="0 0 45 45" className={className} aria-hidden focusable="false">
      {type === "p" && (
        <>
          <circle cx="22.5" cy="14" r="5.2" {...common} strokeWidth="1.4" />
          <Body {...common} d="M17 21 C17 26, 15.5 30, 14.5 34.5 L30.5 34.5 C29.5 30, 28 26, 28 21 Z" />
          <Base fill={fill} stroke={stroke} />
        </>
      )}

      {type === "r" && (
        <>
          <path
            d="M13 12 H17 V16 H20 V12 H25 V16 H28 V12 H32 V20 H13 Z"
            {...common}
            strokeWidth="1.4"
            strokeLinejoin="round"
          />
          <Body {...common} d="M14.5 20 L30.5 20 L29 34.5 L16 34.5 Z" />
          <Base fill={fill} stroke={stroke} />
        </>
      )}

      {type === "n" && (
        <>
          <Body
            {...common}
            d="M29.5 34.5 C29 29 27.5 25.5 24 23.5 C27 21 27.5 17.5 24.5 14.5 C22.5 12.5 19.5 12 17.5 13.5 C16.2 14.5 16.6 16.2 17.8 16.6 C16.3 17 15 18.4 15.5 20 C13.8 20.6 12.6 22.4 13.2 24.3 C11.8 25.6 11.6 27.6 12.6 29 C12.1 30.8 12.6 32.8 14 34.5 Z"
          />
          <circle cx="21.3" cy="17.6" r="0.9" fill={stroke} />
          <Base fill={fill} stroke={stroke} />
        </>
      )}

      {type === "b" && (
        <>
          <circle cx="22.5" cy="9.5" r="2.3" {...common} strokeWidth="1.3" />
          <Body
            {...common}
            d="M22.5 13 C26 16, 27.5 19.5, 25.5 23 C28 25.5, 29 29.5, 29.5 34.5 L15.5 34.5 C16 29.5, 17 25.5, 19.5 23 C17.5 19.5, 19 16, 22.5 13 Z"
          />
          <path
            d="M17.5 22 L27.5 22"
            stroke={stroke}
            strokeWidth="1.4"
            strokeLinecap="round"
          />
          <Base fill={fill} stroke={stroke} />
        </>
      )}

      {type === "q" && (
        <>
          {[13, 18.5, 22.5, 26.5, 32].map((cx, i) => (
            <circle
              key={cx}
              cx={cx}
              cy={i % 2 === 0 ? 12.5 : 10}
              r="2.1"
              {...common}
              strokeWidth="1.2"
            />
          ))}
          <path d="M13 14 L32 14 L29.5 22 L15.5 22 Z" {...common} strokeWidth="1.4" strokeLinejoin="round" />
          <Body {...common} d="M16 22 C15 27, 15 31, 14.5 34.5 L30.5 34.5 C30 31, 30 27, 29 22 Z" />
          <Base fill={fill} stroke={stroke} />
        </>
      )}

      {type === "k" && (
        <>
          <path d="M22.5 6 V12" stroke={stroke} strokeWidth="1.8" strokeLinecap="round" />
          <path d="M19.5 9 H25.5" stroke={stroke} strokeWidth="1.8" strokeLinecap="round" />
          <path
            d="M22.5 12 C27 15, 29 18.5, 27.5 22 C29.5 23, 30.5 24.5, 30 26.5 C29.7 25 28.5 24 27 23.7 C28.5 27 29.3 30.8, 29.7 34.5 L15.3 34.5 C15.7 30.8, 16.5 27, 18 23.7 C16.5 24 15.3 25 15 26.5 C14.5 24.5, 15.5 23, 17.5 22 C16 18.5, 18 15, 22.5 12 Z"
            {...common}
            strokeWidth="1.4"
            strokeLinejoin="round"
          />
          <path
            d="M16.5 25 C19.5 26.5, 25.5 26.5, 28.5 25"
            fill="none"
            stroke={stroke}
            strokeWidth="1.2"
          />
          <Base fill={fill} stroke={stroke} />
        </>
      )}
    </svg>
  )
}
