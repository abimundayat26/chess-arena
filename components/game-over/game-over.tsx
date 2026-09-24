"use client"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { GameResult } from "@/components/game-over/game-result"
import { GameSummary } from "@/components/game-over/game-summary"
import { AccuracyBar } from "@/components/game-over/accuracy-bar"
import type { CompletedGame } from "@/lib/chess/types"
import { RotateCcwIcon, SettingsIcon } from "lucide-react"

interface GameOverProps {
  game: CompletedGame
  onRematch: () => void
  onNewSetup: () => void
}

export function GameOver({ game, onRematch, onNewSetup }: GameOverProps) {
  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center p-4">
      <Card className="w-full max-w-lg border-border/60">
        <CardContent className="flex flex-col gap-6 pt-2">
          <GameResult game={game} />
          <GameSummary game={game} />
          <AccuracyBar game={game} />

          <div className="flex flex-col gap-2 sm:flex-row">
            <Button className="flex-1" onClick={onRematch}>
              <RotateCcwIcon data-icon="inline-start" />
              Rematch
            </Button>
            <Button variant="outline" className="flex-1" onClick={onNewSetup}>
              <SettingsIcon data-icon="inline-start" />
              New setup
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
