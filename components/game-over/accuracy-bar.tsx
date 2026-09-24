import { Progress } from "@/components/ui/progress"
import type { CompletedGame } from "@/lib/chess/types"

export function AccuracyBar({ game }: { game: CompletedGame }) {
  const rows = [
    { label: "You", value: game.extras.humanAccuracy },
    { label: game.config.model.name, value: game.extras.modelAccuracy },
  ]

  return (
    <div className="rounded-sm border border-border bg-card p-4">
      <h3 className="mb-3 font-heading text-sm font-semibold text-foreground">
        Accuracy <span className="text-muted-foreground">(mocked)</span>
      </h3>
      <div className="flex flex-col gap-3">
        {rows.map((row) => (
          <div key={row.label}>
            <div className="mb-1.5 flex items-baseline justify-between text-sm">
              <span className="text-foreground">{row.label}</span>
              <span className="font-mono text-foreground">{row.value.toFixed(1)}%</span>
            </div>
            <Progress value={row.value} className="h-1.5" />
          </div>
        ))}
      </div>
    </div>
  )
}
