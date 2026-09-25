import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { GameAnalysis } from "@/lib/chess/api"
import type { MoveClassification } from "@/lib/chess/types"

const CLASSIFICATION_LABEL: Record<MoveClassification, string> = {
  best: "Best",
  good: "Good",
  inaccuracy: "Inaccuracy",
  mistake: "Mistake",
  blunder: "Blunder",
}

const CLASSIFICATION_VARIANT: Record<
  MoveClassification,
  "secondary" | "outline" | "destructive"
> = {
  best: "secondary",
  good: "secondary",
  inaccuracy: "outline",
  mistake: "destructive",
  blunder: "destructive",
}

function MoveCell({ san, classification }: { san?: string; classification?: MoveClassification }) {
  if (!san) return <span />
  return (
    <span className="flex items-center gap-1.5">
      <span className="text-foreground">{san}</span>
      {classification ? (
        <Badge variant={CLASSIFICATION_VARIANT[classification]} className="text-[10px]">
          {CLASSIFICATION_LABEL[classification]}
        </Badge>
      ) : null}
    </span>
  )
}

export function MoveReview({ san, analysis }: { san: string[]; analysis: GameAnalysis }) {
  const rows: { number: number; whiteIndex: number; blackIndex: number }[] = []
  for (let i = 0; i < san.length; i += 2) {
    rows.push({ number: i / 2 + 1, whiteIndex: i, blackIndex: i + 1 })
  }

  return (
    <div className="rounded-sm border border-border bg-card">
      <div className="border-b border-border px-4 py-2">
        <h3 className="font-heading text-sm font-semibold text-foreground">Move review</h3>
        <p className="text-xs text-muted-foreground">Stockfish review</p>
      </div>
      <ScrollArea className="h-40">
        <ol className="divide-y divide-border/60">
          {rows.map((row) => (
            <li
              key={row.number}
              className="grid grid-cols-[2rem_1fr_1fr] gap-2 px-4 py-1.5 font-mono text-sm"
            >
              <span className="text-muted-foreground">{row.number}.</span>
              <MoveCell san={san[row.whiteIndex]} classification={analysis.moves?.[row.whiteIndex]?.classification} />
              <MoveCell san={san[row.blackIndex]} classification={analysis.moves?.[row.blackIndex]?.classification} />
            </li>
          ))}
        </ol>
      </ScrollArea>
    </div>
  )
}
