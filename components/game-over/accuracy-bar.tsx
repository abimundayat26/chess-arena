import { Progress } from "@/components/ui/progress"
import type { CompletedGame } from "@/lib/chess/types"
import type { GameAnalysis } from "@/lib/chess/api"

export function AccuracyBar({ game, analysis }: { game: CompletedGame; analysis: GameAnalysis }) {
  const human = game.extras.humanColor === "white" ? analysis.white_accuracy : analysis.black_accuracy
  const model = game.extras.humanColor === "white" ? analysis.black_accuracy : analysis.white_accuracy
  const rows = [
    { label: "You", value: human },
    { label: game.config.model.name, value: model },
  ]

  return (
    <div className="rounded-sm border border-border bg-card p-4">
      <h3 className="mb-3 font-heading text-sm font-semibold text-foreground">
        Accuracy
      </h3>
      <div className="flex flex-col gap-3">
        {rows.map((row) => (
          <div key={row.label}>
            <div className="mb-1.5 flex items-baseline justify-between text-sm">
              <span className="text-foreground">{row.label}</span>
              <span className="font-mono text-foreground">{row.value == null ? "—" : `${row.value.toFixed(1)}%`}</span>
            </div>
            <Progress value={row.value ?? 0} className="h-1.5" />
          </div>
        ))}
      </div>
    </div>
  )
}
