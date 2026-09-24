"use client"

import { DIFFICULTIES } from "@/lib/chess/mock-data"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import type { Difficulty, DifficultyContextConfig } from "@/lib/chess/types"
import { cn } from "@/lib/utils"

interface DifficultySelectorProps {
  value: Difficulty
  onChange: (value: Difficulty) => void
  context: DifficultyContextConfig
  onContextChange: (context: DifficultyContextConfig) => void
}

export function DifficultySelector({
  value,
  onChange,
  context,
  onContextChange,
}: DifficultySelectorProps) {
  return (
    <div>
      <h3 className="font-heading text-sm font-semibold text-foreground">AI difficulty</h3>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {DIFFICULTIES.map((option) => {
          const selected = option.id === value
          return (
            <button
              key={option.id}
              type="button"
              onClick={() => onChange(option.id)}
              aria-pressed={selected}
              className={cn(
                "flex flex-col items-start gap-0.5 rounded-sm border px-3 py-2 text-left transition-colors",
                selected
                  ? "border-primary bg-primary/10"
                  : "border-border bg-card hover:border-foreground/30",
              )}
            >
              <span className="text-sm font-medium text-foreground">{option.label}</span>
              <span className="text-xs text-muted-foreground">{option.description}</span>
            </button>
          )
        })}
      </div>

      {value === "custom" && (
        <div className="mt-4 rounded-sm border border-dashed border-border bg-muted/40 p-4">
          <p className="mb-3 text-xs text-muted-foreground">
            Visual mock controls only — not connected to a model in Phase 1.
          </p>
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <FieldLabel htmlFor="board-context">Board context</FieldLabel>
                <FieldDescription>Give the model the full FEN position.</FieldDescription>
              </div>
              <Switch
                id="board-context"
                checked={context.boardContext}
                onCheckedChange={(checked) =>
                  onContextChange({ ...context, boardContext: checked })
                }
              />
            </div>
            <div className="flex items-center justify-between gap-4">
              <div>
                <FieldLabel htmlFor="history-context">Move-history context</FieldLabel>
                <FieldDescription>Include PGN move history.</FieldDescription>
              </div>
              <Switch
                id="history-context"
                checked={context.moveHistoryContext}
                onCheckedChange={(checked) =>
                  onContextChange({ ...context, moveHistoryContext: checked })
                }
              />
            </div>
            <Field>
              <FieldLabel htmlFor="reasoning-effort">
                Reasoning effort — {context.reasoningEffort}%
              </FieldLabel>
              <Slider
                id="reasoning-effort"
                value={context.reasoningEffort}
                max={100}
                step={5}
                onValueChange={(reasoningEffort) =>
                  onContextChange({ ...context, reasoningEffort: reasoningEffort as number })
                }
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="max-response-time">
                Max response time — {context.maxResponseTimeSeconds}s
              </FieldLabel>
              <Slider
                id="max-response-time"
                value={context.maxResponseTimeSeconds}
                max={30}
                min={1}
                step={1}
                onValueChange={(maxResponseTimeSeconds) =>
                  onContextChange({
                    ...context,
                    maxResponseTimeSeconds: maxResponseTimeSeconds as number,
                  })
                }
              />
            </Field>
          </div>
        </div>
      )}
    </div>
  )
}
