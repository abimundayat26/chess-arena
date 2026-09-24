import { cn } from "@/lib/utils"

interface ChessClockProps {
  name: string
  label: string
  active: boolean
  low: boolean
}

export function ChessClock({ name, label, active, low }: ChessClockProps) {
  return (
    <div
      role="timer"
      aria-label={`${name} clock`}
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
