"use client"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { GameResult } from "@/components/game-over/game-result"
import { GameSummary } from "@/components/game-over/game-summary"
import { AccuracyBar } from "@/components/game-over/accuracy-bar"
import { MoveReview } from "@/components/game-over/move-review"
import type { CompletedGame } from "@/lib/chess/types"
import { gameApi, type GameAnalysis, type GameMetrics } from "@/lib/chess/api"
import { useEffect, useState } from "react"
import { DownloadIcon, RotateCcwIcon, SettingsIcon } from "lucide-react"

interface GameOverProps {
  game: CompletedGame
  onRematch: () => void
  onNewSetup: () => void
  starting?: boolean
  startError?: string | null
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

export function GameOver({
  game,
  onRematch,
  onNewSetup,
  starting = false,
  startError,
}: GameOverProps) {
  const [downloadError, setDownloadError] = useState(false)
  const [analysis, setAnalysis] = useState<GameAnalysis | null>(null)
  const [metrics, setMetrics] = useState<GameMetrics | null>(null)
  useEffect(() => {
    let mounted = true
    void gameApi.analysis(game.gameId).then((value) => {
      if (mounted) setAnalysis(value)
    }).catch(() => {
      if (mounted) setAnalysis({ status: "unavailable", reason: "engine_failed" })
    })
    return () => { mounted = false }
  }, [game.gameId])
  useEffect(() => {
    let mounted = true
    void gameApi.metrics(game.gameId).then((value) => {
      if (mounted) setMetrics(value)
    }).catch(() => {})
    return () => { mounted = false }
  }, [game.gameId, analysis])
  async function handleDownload() {
    try {
      setDownloadError(false)
      downloadPgn(await gameApi.pgn(game.gameId))
    } catch {
      setDownloadError(true)
    }
  }
  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center p-4 py-10">
      <Card className="w-full max-w-xl border-border/60">
        <CardContent className="flex flex-col gap-6 pt-2">
          <GameResult game={game} />
          <GameSummary game={game} />
          {metrics && <div className="rounded-sm border border-border bg-card p-4 text-sm">
            <h3 className="mb-3 font-heading font-semibold">Measured performance</h3>
            <dl className="grid grid-cols-2 gap-2">
              <dt>Provider attempts</dt><dd className="text-right">{metrics.provider_attempt_count}</dd>
              <dt>Provider failures</dt><dd className="text-right">{metrics.provider_failure_count}</dd>
              <dt>Illegal move retries</dt><dd className="text-right">{metrics.retry_count}</dd>
              <dt>Average model move time</dt><dd className="text-right">{metrics.average_model_move_time_ms == null ? "Unavailable" : `${(metrics.average_model_move_time_ms / 1000).toFixed(1)}s`}</dd>
              <dt>Median model move time</dt><dd className="text-right">{metrics.median_model_move_time_ms == null ? "Unavailable" : `${(metrics.median_model_move_time_ms / 1000).toFixed(1)}s`}</dd>
            </dl>
          </div>}
          {analysis?.status === "complete" && (
            <>
              <AccuracyBar game={game} analysis={analysis} />
              <MoveReview san={game.san} analysis={analysis} />
            </>
          )}
          {analysis?.status === "unavailable" && <p className="text-sm text-muted-foreground">Stockfish analysis unavailable.</p>}
          {!analysis && <p className="text-sm text-muted-foreground">Analyzing completed game…</p>}

          {startError && (
            <p role="alert" className="text-sm text-accent">
              {startError}
            </p>
          )}
          {downloadError && <p role="alert" className="text-sm text-accent">Could not download PGN. Try again.</p>}
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button className="flex-1" disabled={starting} onClick={onRematch}>
              <RotateCcwIcon data-icon="inline-start" />
              {starting ? "Starting…" : "Rematch"}
            </Button>
            <Button variant="outline" className="flex-1" onClick={onNewSetup}>
              <SettingsIcon data-icon="inline-start" />
              New setup
            </Button>
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => void handleDownload()}
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
