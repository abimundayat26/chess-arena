import { Handshake, Trophy, XCircle } from "lucide-react"

import type { CompletedGame } from "@/lib/chess/types"

function headline(game: CompletedGame): string {
  const { gameOver, extras, config } = game
  if (gameOver.winner === "draw") return "Draw"
  const humanWon =
    (gameOver.winner === "white" && extras.humanColor === "white") ||
    (gameOver.winner === "black" && extras.humanColor === "black")
  return humanWon ? `You defeated ${config.model.name}` : `${config.model.name} won`
}

export function GameResult({ game }: { game: CompletedGame }) {
  const { gameOver } = game
  const isDraw = gameOver.winner === "draw"
  const humanWon =
    !isDraw &&
    ((gameOver.winner === "white" && game.extras.humanColor === "white") ||
      (gameOver.winner === "black" && game.extras.humanColor === "black"))

  const resultLabel =
    gameOver.result === "1-0" ? "1–0" : gameOver.result === "0-1" ? "0–1" : "½–½"

  return (
    <div className="text-center">
      <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full border border-border bg-card">
        {isDraw ? (
          <Handshake className="size-5 text-muted-foreground" />
        ) : humanWon ? (
          <Trophy className="size-5 text-primary" />
        ) : (
          <XCircle className="size-5 text-accent" />
        )}
      </div>
      <h1 className="font-heading text-2xl font-semibold text-foreground">
        {headline(game)}
      </h1>
      <p className="mt-1 font-mono text-lg text-muted-foreground">{resultLabel}</p>
    </div>
  )
}
