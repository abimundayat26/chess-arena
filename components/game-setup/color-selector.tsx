"use client"

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { ColorPreference } from "@/lib/chess/types"

interface ColorSelectorProps {
  value: ColorPreference
  onChange: (value: ColorPreference) => void
}

const OPTIONS: { id: ColorPreference; label: string }[] = [
  { id: "white", label: "White" },
  { id: "black", label: "Black" },
  { id: "random", label: "Random" },
]

export function ColorSelector({ value, onChange }: ColorSelectorProps) {
  return (
    <div>
      <h3 className="font-heading text-sm font-semibold text-foreground">Play as</h3>
      <ToggleGroup
        type="single"
        value={value}
        onValueChange={(next) => {
          if (next) onChange(next as ColorPreference)
        }}
        className="mt-3 w-full gap-2"
      >
        {OPTIONS.map((option) => (
          <ToggleGroupItem
            key={option.id}
            value={option.id}
            className="flex-1 gap-2 rounded-sm border border-border data-[state=on]:border-primary data-[state=on]:bg-primary/10 data-[state=on]:text-foreground"
          >
            <span
              aria-hidden
              className="size-2.5 rounded-full border border-foreground/40"
              style={{
                background:
                  option.id === "white"
                    ? "oklch(0.93 0.025 80)"
                    : option.id === "black"
                      ? "oklch(0.3 0.02 55)"
                      : "linear-gradient(135deg, oklch(0.93 0.025 80) 50%, oklch(0.3 0.02 55) 50%)",
              }}
            />
            {option.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  )
}
