"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import type { PieceSymbol, Square } from "chess.js"
import { toast } from "sonner"

import { useChessGame } from "@/hooks/use-chess-game"
import { gameApi, type ServerGame } from "@/lib/chess/api"
import { mockIllegalModelMoves } from "@/lib/chess/mock-data"
import type {
  GameOverInfo,
  MatchConfig,
  PlayerColor,
  TerminationReason,
} from "@/lib/chess/types"
import { Button } from "@/components/ui/button"

import { ChessBoard } from "./chess-board"
import { GameControls } from "./game-controls"
import { MoveList } from "./move-list"
import { PlayerIdentity } from "./player-identity"

interface ActiveGameProps {
  initialState: ServerGame
  config: MatchConfig
  humanColor: PlayerColor
  onGameOver: (
    info: GameOverInfo,
    snapshot: {
      pgn: string
      san: string[]
      fen: string
      illegalModelMoves: number
    }
  ) => void
}

function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds))
  return `${Math.floor(s / 60)
    .toString()
    .padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`
}

export function ActiveGame({
  initialState,
  config,
  humanColor,
  onGameOver,
}: ActiveGameProps) {
  const [state, setState] = useState(initialState)
  const game = useChessGame(state)
  const [humanSeconds, setHumanSeconds] = useState(
    config.timeControl.initialMinutes * 60
  )
  const [modelSeconds, setModelSeconds] = useState(
    config.timeControl.initialMinutes * 60
  )
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [syncFailed, setSyncFailed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [illegalModelMoves] = useState(() => mockIllegalModelMoves())
  const hasReportedRef = useRef(false)

  const refresh = useCallback(async () => {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    try {
      setState(await gameApi.get(state.game_id))
      setError(null)
      setSyncFailed(false)
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not refresh the game"
      )
      setSyncFailed(true)
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }, [state.game_id])

  const runAction = useCallback(
    async (action: () => Promise<ServerGame>): Promise<boolean> => {
      if (busyRef.current || syncFailed || state.game_status === "game-over")
        return false
      busyRef.current = true
      setBusy(true)
      setError(null)
      try {
        setState(await action())
        return true
      } catch (cause) {
        const message =
          cause instanceof Error ? cause.message : "Game request failed"
        // A response can be lost after the server commits the action. Always fetch its current state.
        try {
          setState(await gameApi.get(state.game_id))
          setError(message)
        } catch {
          setError(
            `${message} Could not refresh the game. Retry sync to continue.`
          )
          setSyncFailed(true)
        }
        return false
      } finally {
        busyRef.current = false
        setBusy(false)
      }
    },
    [state.game_id, state.game_status, syncFailed]
  )

  const submitMove = useCallback(
    (from: Square, to: Square, promotion?: PieceSymbol) => {
      const uci = `${from}${to}${promotion ?? ""}`
      if (!state.legal_moves.includes(uci)) {
        setError("That move is no longer legal. Refreshing the position.")
        void refresh()
        return
      }
      void runAction(() => gameApi.move(state.game_id, uci))
    },
    [state.game_id, state.legal_moves, refresh, runAction]
  )

  useEffect(() => {
    if (
      state.game_status !== "playing" ||
      state.side_to_move === humanColor ||
      busy ||
      syncFailed ||
      error
    )
      return
    const timeout = window.setTimeout(
      () => {
        const moves = state.legal_moves
        const uci = moves[Math.floor(Math.random() * moves.length)]
        if (uci) void runAction(() => gameApi.move(state.game_id, uci))
      },
      900 + Math.random() * 700
    )
    return () => window.clearTimeout(timeout)
  }, [state, humanColor, busy, syncFailed, error, runAction])

  useEffect(() => {
    if (state.game_status !== "playing" || busy || syncFailed) return
    const interval = window.setInterval(() => {
      if (state.side_to_move === humanColor)
        setHumanSeconds((s) => Math.max(0, s - 1))
      else setModelSeconds((s) => Math.max(0, s - 1))
    }, 1000)
    return () => window.clearInterval(interval)
  }, [state.side_to_move, state.game_status, humanColor, busy, syncFailed])

  useEffect(() => {
    if (state.game_status !== "game-over" || hasReportedRef.current) return
    hasReportedRef.current = true
    const result = state.result
    const winner =
      result === "1-0" ? "white" : result === "0-1" ? "black" : "draw"
    if (result === "*") return
    onGameOver(
      {
        result,
        winner,
        terminationReason: (state.termination_reason ??
          "variant_draw") as TerminationReason,
      },
      {
        pgn: state.pgn,
        san: game.sanHistory,
        fen: state.fen,
        illegalModelMoves,
      }
    )
  }, [state, game.sanHistory, illegalModelMoves, onGameOver])

  async function offerDraw(accepted: boolean) {
    const succeeded = await runAction(() =>
      gameApi.offerDraw(state.game_id, accepted)
    )
    if (succeeded) toast(accepted ? "Draw accepted" : "Draw declined")
  }

  const modelColor: PlayerColor = humanColor === "white" ? "black" : "white"
  const isThinking =
    state.game_status === "playing" &&
    state.side_to_move === modelColor &&
    !syncFailed
  const boardDisabled =
    busy || syncFailed || game.isGameOver || game.turn !== humanColor

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
      <div className="flex flex-col gap-3">
        <PlayerIdentity
          variant="model"
          name={config.model.name}
          subtitle={config.model.provider}
          clockLabel={formatClock(modelSeconds)}
          isActiveTurn={game.turn === modelColor && !game.isGameOver}
          isThinking={isThinking}
        />
        <ChessBoard
          key={game.fen}
          game={game}
          orientation={humanColor}
          disabled={boardDisabled}
          onMove={submitMove}
        />
        <PlayerIdentity
          variant="human"
          name="You"
          clockLabel={formatClock(humanSeconds)}
          isActiveTurn={game.turn === humanColor && !game.isGameOver}
        />
      </div>
      <div className="flex flex-col gap-3">
        <MoveList sanHistory={game.sanHistory} />
        {busy && (
          <p role="status" className="text-sm text-muted-foreground">
            Updating game…
          </p>
        )}
        {error && (
          <div role="alert" className="text-sm text-accent">
            {error}
          </div>
        )}
        {syncFailed && (
          <Button variant="outline" onClick={() => void refresh()}>
            Retry sync
          </Button>
        )}
        {!syncFailed && error && state.side_to_move === modelColor && (
          <Button variant="outline" onClick={() => setError(null)}>
            Continue game
          </Button>
        )}
        <GameControls
          disabled={busy || syncFailed || game.isGameOver}
          opponentName={config.model.name}
          onResign={() =>
            void runAction(() => gameApi.resign(state.game_id, humanColor))
          }
          onOfferDraw={offerDraw}
        />
      </div>
    </div>
  )
}
