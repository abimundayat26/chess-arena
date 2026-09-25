"use client"

import { useState } from "react"

import { AppShell } from "@/components/app-shell"
import { GameSetup } from "@/components/game-setup/game-setup"
import { ActiveGame } from "@/components/active-game/active-game"
import { GameOver } from "@/components/game-over/game-over"
import { gameApi, type ServerGame } from "@/lib/chess/api"
import { mockAccuracy } from "@/lib/chess/mock-data"
import type {
  AppScreen,
  CompletedGame,
  GameOverInfo,
  MatchConfig,
  PlayerColor,
} from "@/lib/chess/types"

function resolveHumanColor(
  preference: MatchConfig["colorPreference"]
): PlayerColor {
  return preference === "random"
    ? Math.random() < 0.5
      ? "white"
      : "black"
    : preference
}

export default function Home() {
  const [screen, setScreen] = useState<AppScreen>("setup")
  const [config, setConfig] = useState<MatchConfig | null>(null)
  const [humanColor, setHumanColor] = useState<PlayerColor>("white")
  const [initialState, setInitialState] = useState<ServerGame | null>(null)
  const [completedGame, setCompletedGame] = useState<CompletedGame | null>(null)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)

  async function handleStart(matchConfig: MatchConfig) {
    if (starting) return
    setStarting(true)
    setStartError(null)
    try {
      const color = resolveHumanColor(matchConfig.colorPreference)
      const modelColor = color === "white" ? "black" : "white"
      const contextLevel = matchConfig.difficulty === "casual" ? "minimal" : matchConfig.difficulty === "strong" ? "structured_position" : "game_context"
      const created = await gameApi.create(matchConfig.timeControl.id, matchConfig.model.backendProvider, modelColor, contextLevel)
      const current = await gameApi.get(created.game_id)
      setConfig(matchConfig)
      setHumanColor(color)
      setCompletedGame(null)
      setInitialState(current)
      setScreen("playing")
    } catch (cause) {
      setStartError(matchConfig.model.backendProvider ? "Could not start this model game. Check the provider configuration and try again." : cause instanceof Error ? cause.message : "Could not start the game")
    } finally {
      setStarting(false)
    }
  }

  function handleGameOver(
    info: GameOverInfo,
    snapshot: {
      gameId: string
      pgn: string
      san: string[]
      fen: string
      illegalModelMoves: number
    }
  ) {
    if (!config) return
    const { humanAccuracy, modelAccuracy } = mockAccuracy()
    setCompletedGame({
      gameId: snapshot.gameId,
      config,
      gameOver: info,
      pgn: snapshot.pgn,
      san: snapshot.san,
      fen: snapshot.fen,
      extras: {
        humanColor,
        humanClockLabel: "",
        modelClockLabel: "",
        illegalModelMoves: snapshot.illegalModelMoves,
        humanAccuracy,
        modelAccuracy,
      },
    })
    setScreen("game-over")
  }

  function handleNewSetup() {
    setConfig(null)
    setCompletedGame(null)
    setInitialState(null)
    setScreen("setup")
  }

  return (
    <AppShell>
      {screen === "setup" && (
        <>
          <GameSetup onStart={handleStart} starting={starting} />
          {startError && (
            <p role="alert" className="mt-4 text-center text-sm text-accent">
              {startError}
            </p>
          )}
        </>
      )}
      {screen === "playing" && config && initialState && (
        <ActiveGame
          key={initialState.game_id}
          initialState={initialState}
          config={config}
          humanColor={humanColor}
          onGameOver={handleGameOver}
          onNewSetup={handleNewSetup}
        />
      )}
      {screen === "game-over" && completedGame && (
        <GameOver
          game={completedGame}
          starting={starting}
          startError={startError}
          onRematch={() => {
            if (config) void handleStart(config)
          }}
          onNewSetup={handleNewSetup}
        />
      )}
    </AppShell>
  )
}
