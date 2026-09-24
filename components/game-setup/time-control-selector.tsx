"use client"

import { TIME_CONTROLS } from "@/lib/chess/mock-data"
import type { TimeControlOption } from "@/lib/chess/types"
import { cn } from "@/lib/utils"

interface TimeControlSelectorProps {
  value: TimeControlOption
  onChange: (value: TimeControlOption) => void
}

export function TimeControlSelector({ value, onChange }: TimeControlSelectorProps) {
  return (
    <div>
      <h3 className="font-heading text-sm font-semibold text-foreground">Time control</h3>
      <p className="mt-1 text-xs text-muted-foreground">Blitz and rapid, up to 20 minutes.</p>
      <div className="mt-3 grid grid-cols-4 gap-2">
        {TIME_CONTROLS.map((option) => {
          const selected = option.id === value.id
          return (
            <button
              key={option.id}
              type="button"
              onClick={() => onChange(option)}
              aria-pressed={selected}
              className={cn(
                "rounded-sm border px-2 py-2 text-center font-mono text-sm transition-colors",
                selected
                  ? "border-primary bg-primary/10 text-foreground"
                  : "border-border bg-card text-muted-foreground hover:border-foreground/30",
              )}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
