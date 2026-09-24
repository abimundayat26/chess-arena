import { mockClassificationForIndex, mockPostGameExplanation } from "@/lib/chess/mock-data"
import type { MoveClassification } from "@/lib/chess/types"

function moveLabel(index: number, san: string): string {
  const moveNumber = Math.floor(index / 2) + 1
  return index % 2 === 0 ? `${moveNumber}. ${san}` : `${moveNumber}...${san}`
}

function pickHighlightIndex(san: string[]): number | null {
  if (san.length === 0) return null

  const priority: MoveClassification[] = ["blunder", "mistake", "inaccuracy"]
  for (const target of priority) {
    for (let i = san.length - 1; i >= 0; i--) {
      if (mockClassificationForIndex(i) === target) return i
    }
  }

  for (let i = san.length - 1; i >= 0; i--) {
    if (mockClassificationForIndex(i)) return i
  }

  return san.length - 1
}

export function PostGameExplanation({ san }: { san: string[] }) {
  const index = pickHighlightIndex(san)
  if (index === null) return null

  const label = moveLabel(index, san[index])
  const explanation = mockPostGameExplanation(san[index], label)

  return (
    <div className="rounded-sm border border-border bg-card p-4">
      <h3 className="mb-1 font-heading text-sm font-semibold text-foreground">
        Post-game explanation
      </h3>
      <p className="mb-2 font-mono text-sm text-muted-foreground">{label}</p>
      <p className="text-sm text-foreground/90 leading-relaxed">{explanation}</p>
    </div>
  )
}
