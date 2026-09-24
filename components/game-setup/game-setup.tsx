"use client"

import { useState } from "react"
import { Swords } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import {
  DEFAULT_DIFFICULTY_CONTEXT,
  MODEL_OPTIONS,
  TIME_CONTROLS,
} from "@/lib/chess/mock-data"
import type { MatchConfig } from "@/lib/chess/types"

import { ColorSelector } from "./color-selector"
import { DifficultySelector } from "./difficulty-selector"
import { ModelSelector } from "./model-selector"
import { TimeControlSelector } from "./time-control-selector"

interface GameSetupProps {
  onStart: (config: MatchConfig) => void
  starting?: boolean
}

export function GameSetup({ onStart, starting = false }: GameSetupProps) {
  const [model, setModel] = useState(MODEL_OPTIONS[1])
  const [colorPreference, setColorPreference] =
    useState<MatchConfig["colorPreference"]>("white")
  const [timeControl, setTimeControl] = useState(TIME_CONTROLS[5])
  const [difficulty, setDifficulty] =
    useState<MatchConfig["difficulty"]>("standard")
  const [difficultyContext, setDifficultyContext] = useState(
    DEFAULT_DIFFICULTY_CONTEXT
  )

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-8 text-center">
        <div className="mx-auto mb-4 flex size-11 items-center justify-center rounded-full border border-border bg-card">
          <Swords className="size-5 text-primary" />
        </div>
        <h1 className="font-heading text-2xl font-semibold text-foreground">
          New Match
        </h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Configure your opponent and sit down at the board.
        </p>
      </div>

      <Card className="gap-0 border-border p-6">
        <div className="flex flex-col gap-6">
          <ModelSelector value={model} onChange={setModel} />
          <Separator />
          <ColorSelector
            value={colorPreference}
            onChange={setColorPreference}
          />
          <Separator />
          <TimeControlSelector value={timeControl} onChange={setTimeControl} />
          <Separator />
          <DifficultySelector
            value={difficulty}
            onChange={setDifficulty}
            context={difficultyContext}
            onContextChange={setDifficultyContext}
          />
        </div>

        <Separator className="my-6" />

        <Button
          size="lg"
          className="w-full"
          disabled={starting}
          onClick={() =>
            onStart({
              model,
              colorPreference,
              timeControl,
              difficulty,
              difficultyContext,
            })
          }
        >
          {starting ? "Starting…" : "Start Game"}
        </Button>
      </Card>
    </div>
  )
}
