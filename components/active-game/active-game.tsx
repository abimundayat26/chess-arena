"use client"

import { useEffect, useRef, useState } from "react"

import { useChessGame } from "@/hooks/use-chess-game"
import { mockIllegalModelMoves } from "@/lib/chess/mock-data"
import type { GameOverInfo, MatchConfig, PlayerColor } from "@/lib/chess/types"

import { ChessBoard } from "./chess-board"
import { GameControls } from "./game-controls"
import { MoveList } from "./move-list"
import { PlayerIdentity } from "./player-identity"

interface ActiveGameProps {
  config: MatchConfig
  humanColor: PlayerColor
  onGameOver: (
    info: GameOverInfo,
    snapshot: { pgn: string; san: string[]; fen: string; illegalModelMoves: number },
  ) => void
}

function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m.toString().padStart(2, "0")}:${r.toString().padStart(2, "0")}`
}

export function ActiveGame({ config, humanColor, onGameOver }: ActiveGameProps) {
  const game = useChessGame()
  const { turn, moveCount, isGameOver, gameOverInfo, pgn, sanHistory, fen, makeRandomMove } =
    game

  const initialSeconds = config.timeControl.initialMinutes * 60
  const [humanSeconds, setHumanSeconds] = useState(initialSeconds)
  const [modelSeconds, setModelSeconds] = useState(initialSeconds)
  const [isThinking, setIsThinking] = useState(false)
  const [illegalModelMoves] = useState(() => mockIllegalModelMoves())

  const scheduledForCountRef = useRef<number | null>(null)
  const hasReportedRef = useRef(false)

  // Mocked AI turn: pick a random legal move after a short "thinking" delay.
  useEffect(() => {
    if (isGameOver) return
    if (turn === humanColor) return
    if (scheduledForCountRef.current === moveCount) return
    scheduledForCountRef.current = moveCount
    setIsThinking(true)
    const timeout = window.setTimeout(
      () => {
        makeRandomMove()
        setIsThinking(false)
      },
      900 + Math.random() * 700,
    )
    return () => window.clearTimeout(timeout)
  }, [turn, moveCount, isGameOver, humanColor, makeRandomMove])

  // Simulated clock: ticks down for whichever side is on the move.
  useEffect(() => {
    if (isGameOver) return
    const interval = window.setInterval(() => {
      if (turn === humanColor) {
        setHumanSeconds((s) => Math.max(0, s - 1))
      } else {
        setModelSeconds((s) => Math.max(0, s - 1))
      }
    }, 1000)
    return () => window.clearInterval(interval)
  }, [turn, humanColor, isGameOver])

  useEffect(() => {
    if (isGameOver && gameOverInfo && !hasReportedRef.current) {
      hasReportedRef.current = true
      onGameOver(gameOverInfo, { pgn, san: sanHistory, fen, illegalModelMoves })
    }
  }, [isGameOver, gameOverInfo, onGameOver, pgn, sanHistory, fen, illegalModelMoves])

  function handleResign() {
    if (hasReportedRef.current) return
    hasReportedRef.current = true
    onGameOver(
      {
        result: humanColor === "white" ? "0-1" : "1-0",
        terminationReason: "resignation",
        winner: humanColor === "white" ? "black" : "white",
      },
      { pgn, san: sanHistory, fen, illegalModelMoves },
    )
  }

  function handleDrawAccepted() {
    if (hasReportedRef.current) return
    hasReportedRef.current = true
    onGameOver(
      { result: "1/2-1/2", terminationReason: "draw_agreement", winner: "draw" },
      { pgn, san: sanHistory, fen, illegalModelMoves },
    )
  }

  const modelColor: PlayerColor = humanColor === "white" ? "black" : "white"
  const boardDisabled = isGameOver || isThinking || turn !== humanColor

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
      <div className="flex flex-col gap-3">
        <PlayerIdentity
          variant="model"
          name={config.model.name}
          subtitle={config.model.provider}
          clockLabel={formatClock(modelSeconds)}
          isActiveTurn={turn === modelColor && !isGameOver}
          isThinking={isThinking}
        />

        <ChessBoard
          game={game}
          orientation={humanColor}
          disabled={boardDisabled}
          onMoveMade={() => {}}
        />

        <PlayerIdentity
          variant="human"
          name="You"
          clockLabel={formatClock(humanSeconds)}
          isActiveTurn={turn === humanColor && !isGameOver}
        />
      </div>

      <div className="flex flex-col gap-3">
        <MoveList sanHistory={sanHistory} />
        <GameControls
          disabled={isGameOver}
          opponentName={config.model.name}
          onResign={handleResign}
          onDrawAccepted={handleDrawAccepted}
        />
      </div>
    </div>
  )
}
