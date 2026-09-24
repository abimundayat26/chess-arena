import { cn } from "@/lib/utils"

interface ChessClockProps {
  label: string
  active: boolean
  low: boolean
}

export function ChessClock({ label, active, low }: ChessClockProps) {
  return (
    <div
      className={cn(
        "rounded-sm border px-3 py-1.5 font-mono text-lg tabular-nums transition-colors",
        active
          ? "border-primary bg-primary/10 text-foreground"
          : "border-border bg-card text-muted-foreground",
        low && "text-accent",
      )}
    >
      {label}
    </div>
  )
}
