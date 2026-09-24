"use client"

import { MODEL_OPTIONS } from "@/lib/chess/mock-data"
import type { ModelOption } from "@/lib/chess/types"
import { cn } from "@/lib/utils"

interface ModelSelectorProps {
  value: ModelOption
  onChange: (model: ModelOption) => void
}

export function ModelSelector({ value, onChange }: ModelSelectorProps) {
  return (
    <div>
      <h3 className="font-heading text-sm font-semibold text-foreground">Opponent</h3>
      <p className="mt-1 text-xs text-muted-foreground">
        Choose the language model you will play against.
      </p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {MODEL_OPTIONS.map((model) => {
          const selected = model.id === value.id
          return (
            <button
              key={model.id}
              type="button"
              onClick={() => onChange(model)}
              aria-pressed={selected}
              className={cn(
                "flex flex-col items-start gap-0.5 rounded-sm border px-3 py-2.5 text-left transition-colors",
                selected
                  ? "border-primary bg-primary/10"
                  : "border-border bg-card hover:border-foreground/30",
              )}
            >
              <span className="text-sm font-medium text-foreground">{model.name}</span>
              <span className="text-xs text-muted-foreground">{model.provider}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
