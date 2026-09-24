"use client"

import { useState } from "react"

import { AppShell } from "@/components/app-shell"
import { GameSetup } from "@/components/game-setup/game-setup"
import { ActiveGame } from "@/components/active-game/active-game"
import { GameOver } from "@/components/game-over/game-over"
import { mockAccuracy } from "@/lib/chess/mock-data"
import type {
  AppScreen,
  CompletedGame,
  GameOverInfo,
  MatchConfig,
  PlayerColor,
} from "@/lib/chess/types"

function resolveHumanColor(preference: MatchConfig["colorPreference"]): PlayerColor {
  if (preference === "random") {
    return Math.random() < 0.5 ? "white" : "black"
  }
  return preference
}

export default function Home() {
  const [screen, setScreen] = useState<AppScreen>("setup")
  const [config, setConfig] = useState<MatchConfig | null>(null)
  const [humanColor, setHumanColor] = useState<PlayerColor>("white")
  const [completedGame, setCompletedGame] = useState<CompletedGame | null>(null)
  const [gameId, setGameId] = useState(0)

  function handleStart(matchConfig: MatchConfig) {
    setConfig(matchConfig)
    setHumanColor(resolveHumanColor(matchConfig.colorPreference))
    setCompletedGame(null)
    setGameId((id) => id + 1)
    setScreen("playing")
  }

  function handleGameOver(
    info: GameOverInfo,
    snapshot: { pgn: string; san: string[]; fen: string; illegalModelMoves: number },
  ) {
    if (!config) return
    const { humanAccuracy, modelAccuracy } = mockAccuracy()
    setCompletedGame({
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

  function handleRematch() {
    if (!config) return
    setHumanColor(resolveHumanColor(config.colorPreference))
    setCompletedGame(null)
    setGameId((id) => id + 1)
    setScreen("playing")
  }

  function handleNewSetup() {
    setConfig(null)
    setCompletedGame(null)
    setScreen("setup")
  }

  return (
    <AppShell>
      {screen === "setup" && <GameSetup onStart={handleStart} />}

      {screen === "playing" && config && (
        <ActiveGame
          key={gameId}
          config={config}
          humanColor={humanColor}
          onGameOver={handleGameOver}
        />
      )}

      {screen === "game-over" && completedGame && (
        <GameOver
          game={completedGame}
          onRematch={handleRematch}
          onNewSetup={handleNewSetup}
        />
      )}
    </AppShell>
  )
}
