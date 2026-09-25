"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import type { PieceSymbol, Square } from "chess.js"
import { toast } from "sonner"

import { useChessGame } from "@/hooks/use-chess-game"
import { gameApi, type ServerGame } from "@/lib/chess/api"
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
      gameId: string
      pgn: string
      san: string[]
      fen: string
      illegalModelMoves: number
    }
  ) => void
  onNewSetup: () => void
}

function formatClock(totalMs: number): string {
  const s = Math.max(0, Math.ceil(totalMs / 1000))
  return `${Math.floor(s / 60)
    .toString()
    .padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`
}

export function ActiveGame({
  initialState,
  config,
  humanColor,
  onGameOver,
  onNewSetup,
}: ActiveGameProps) {
  const [state, setState] = useState(initialState)
  const game = useChessGame(state)
  const [receivedAt, setReceivedAt] = useState(() => performance.now())
  const [now, setNow] = useState(() => performance.now())
  const applyState = useCallback((next: ServerGame) => {
    const received = performance.now()
    setReceivedAt(received)
    setNow(received)
    setState(next)
  }, [])
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [syncFailed, setSyncFailed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const hasReportedRef = useRef(false)

  const refresh = useCallback(async () => {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    try {
      applyState(await gameApi.get(state.game_id))
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
  }, [state.game_id, applyState])

  const runAction = useCallback(
    async (action: () => Promise<ServerGame>, genericError?: string): Promise<boolean> => {
      if (busyRef.current || syncFailed || state.game_status === "game-over")
        return false
      busyRef.current = true
      setBusy(true)
      setError(null)
      try {
        applyState(await action())
        return true
      } catch (cause) {
        const message = genericError ?? (cause instanceof Error ? cause.message : "Game request failed")
        // A response can be lost after the server commits the action. Always fetch its current state.
        try {
          applyState(await gameApi.get(state.game_id))
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
    [state.game_id, state.game_status, syncFailed, applyState]
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
        if (state.model_provider) {
          void runAction(() => gameApi.modelTurn(state.game_id), "Model turn failed. Retry to continue.")
        } else {
          const moves = state.legal_moves
          const uci = moves[Math.floor(Math.random() * moves.length)]
          if (uci) void runAction(() => gameApi.move(state.game_id, uci))
        }
      },
      state.model_provider ? 0 : 900 + Math.random() * 700
    )
    return () => window.clearTimeout(timeout)
  }, [state, humanColor, busy, syncFailed, error, runAction])

  useEffect(() => {
    if (state.game_status !== "playing") return
    const interval = window.setInterval(() => setNow(performance.now()), 200)
    return () => window.clearInterval(interval)
  }, [state.game_status])

  useEffect(() => {
    if (state.game_status !== "playing" || syncFailed) return
    const interval = window.setInterval(async () => {
      if (busyRef.current) return
      busyRef.current = true
      try {
        applyState(await gameApi.get(state.game_id))
      } catch {
        // Keep the last server snapshot visible; the next poll can recover it.
      } finally {
        busyRef.current = false
      }
    }, 2000)
    return () => window.clearInterval(interval)
  }, [state.game_id, state.game_status, syncFailed, applyState])

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
        gameId: state.game_id,
        pgn: state.pgn,
        san: game.sanHistory,
        fen: state.fen,
        illegalModelMoves: state.illegal_model_move_count,
      }
    )
  }, [state, game.sanHistory, onGameOver])

  async function offerDraw(accepted?: boolean) {
    const succeeded = state.model_provider
      ? await runAction(() => gameApi.modelDraw(state.game_id), "Draw decision failed. You can try again.")
      : await runAction(() => gameApi.offerDraw(state.game_id, Boolean(accepted)))
    if (succeeded) toast(state.model_provider ? "Draw decision received" : accepted ? "Draw accepted" : "Draw declined")
  }

  const modelColor: PlayerColor = humanColor === "white" ? "black" : "white"
  const projectedMs = (color: PlayerColor) =>
    Math.max(0, (color === "white" ? state.white_clock_ms : state.black_clock_ms) -
      (state.active_clock === color ? now - receivedAt : 0))
  const isThinking =
    state.game_status === "playing" &&
    state.side_to_move === modelColor &&
    !syncFailed && !error
  const boardDisabled =
    busy || syncFailed || game.isGameOver || game.turn !== humanColor

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
      <div className="flex flex-col gap-3">
        <PlayerIdentity
          variant="model"
          name={config.model.name}
          subtitle={config.model.provider}
          clockLabel={formatClock(projectedMs(modelColor))}
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
          clockLabel={formatClock(projectedMs(humanColor))}
          isActiveTurn={game.turn === humanColor && !game.isGameOver}
        />
      </div>
      <div className="flex flex-col gap-3">
        <MoveList sanHistory={game.sanHistory} />
        {busy && (
          <p role="status" className="text-sm text-muted-foreground">
            {state.model_provider && isThinking ? "Model thinking…" : "Updating game…"}
          </p>
        )}
        {error && (
          <div role="alert" className="text-sm text-accent">
            {error}
          </div>
        )}
        {syncFailed && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void refresh()}>
              Retry sync
            </Button>
            <Button variant="outline" onClick={onNewSetup}>
              New setup
            </Button>
          </div>
        )}
        {!syncFailed && error && state.side_to_move === modelColor && (
          <Button variant="outline" onClick={() => setError(null)}>
            {state.model_provider ? "Retry model turn" : "Continue game"}
          </Button>
        )}
        <GameControls
          disabled={busy || syncFailed || game.isGameOver}
          opponentName={config.model.name}
          onResign={() =>
            void runAction(() => gameApi.resign(state.game_id, humanColor))
          }
          onOfferDraw={offerDraw}
          realModel={Boolean(state.model_provider)}
        />
      </div>
    </div>
  )
}
