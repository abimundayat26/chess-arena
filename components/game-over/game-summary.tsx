import type { CompletedGame, TerminationReason } from "@/lib/chess/types"

const TERMINATION_LABELS: Record<TerminationReason, string> = {
  checkmate: "Checkmate",
  stalemate: "Stalemate",
  insufficient_material: "Insufficient material",
  repetition: "Threefold repetition",
  fifty_move_rule: "Fifty-move rule",
  resignation: "Resignation",
  draw_agreement: "Draw agreement",
  variant_win: "Variant win",
  variant_loss: "Variant loss",
  variant_draw: "Variant draw",
}

export function GameSummary({ game }: { game: CompletedGame }) {
  const resultLabel =
    game.gameOver.result === "1-0"
      ? "1–0"
      : game.gameOver.result === "0-1"
        ? "0–1"
        : "½–½"

  const rows: [string, string][] = [
    ["Result", resultLabel],
    ["Ended by", TERMINATION_LABELS[game.gameOver.terminationReason]],
    ["Opponent", `${game.config.model.name} · ${game.config.model.provider}`],
    ["Your color", game.extras.humanColor === "white" ? "White" : "Black"],
    ["Time control", game.config.timeControl.label],
    ["Moves", String(Math.ceil(game.san.length / 2))],
    ["Illegal AI moves", String(game.extras.illegalModelMoves)],
  ]

  return (
    <div className="rounded-sm border border-border bg-card p-4">
      <h3 className="mb-3 font-heading text-sm font-semibold text-foreground">
        Game summary
      </h3>
      <dl className="flex flex-col gap-2">
        {rows.map(([label, value]) => (
          <div
            key={label}
            className="flex items-baseline justify-between gap-4 text-sm"
          >
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="font-medium text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
