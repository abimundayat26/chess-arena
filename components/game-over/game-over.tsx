"use client"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { GameResult } from "@/components/game-over/game-result"
import { GameSummary } from "@/components/game-over/game-summary"
import { AccuracyBar } from "@/components/game-over/accuracy-bar"
import { MoveReview } from "@/components/game-over/move-review"
import { PostGameExplanation } from "@/components/game-over/post-game-explanation"
import type { CompletedGame } from "@/lib/chess/types"
import { DownloadIcon, RotateCcwIcon, SettingsIcon } from "lucide-react"

interface GameOverProps {
  game: CompletedGame
  onRematch: () => void
  onNewSetup: () => void
}

function downloadPgn(pgn: string) {
  const blob = new Blob([pgn], { type: "application/x-chess-pgn" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = `chess-arena-game-${Date.now()}.pgn`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export function GameOver({ game, onRematch, onNewSetup }: GameOverProps) {
  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center p-4 py-10">
      <Card className="w-full max-w-xl border-border/60">
        <CardContent className="flex flex-col gap-6 pt-2">
          <GameResult game={game} />
          <GameSummary game={game} />
          <AccuracyBar game={game} />
          <MoveReview san={game.san} />
          <PostGameExplanation san={game.san} />

          <div className="flex flex-col gap-2 sm:flex-row">
            <Button className="flex-1" onClick={onRematch}>
              <RotateCcwIcon data-icon="inline-start" />
              Rematch
            </Button>
            <Button variant="outline" className="flex-1" onClick={onNewSetup}>
              <SettingsIcon data-icon="inline-start" />
              New setup
            </Button>
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => downloadPgn(game.pgn)}
            >
              <DownloadIcon data-icon="inline-start" />
              Download PGN
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
