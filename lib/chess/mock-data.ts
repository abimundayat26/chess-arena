import type {
  Difficulty,
  DifficultyContextConfig,
  ModelOption,
  MoveClassification,
  TimeControlOption,
} from "./types"

export const MODEL_OPTIONS: ModelOption[] = [
  { id: "gpt-5.6", name: "GPT-5.6", provider: "OpenAI" },
  { id: "claude-sonnet", name: "Claude Sonnet", provider: "Anthropic" },
  { id: "gemini-pro", name: "Gemini Pro", provider: "Google" },
  { id: "custom-model", name: "Custom Model", provider: "Bring your own" },
]

export const TIME_CONTROLS: TimeControlOption[] = [
  { id: "3+0", label: "3+0", initialMinutes: 3, incrementSeconds: 0 },
  { id: "3+2", label: "3+2", initialMinutes: 3, incrementSeconds: 2 },
  { id: "5+0", label: "5+0", initialMinutes: 5, incrementSeconds: 0 },
  { id: "5+3", label: "5+3", initialMinutes: 5, incrementSeconds: 3 },
  { id: "10+0", label: "10+0", initialMinutes: 10, incrementSeconds: 0 },
  { id: "10+5", label: "10+5", initialMinutes: 10, incrementSeconds: 5 },
  { id: "15+10", label: "15+10", initialMinutes: 15, incrementSeconds: 10 },
  { id: "20+0", label: "20+0", initialMinutes: 20, incrementSeconds: 0 },
]

export const DIFFICULTIES: { id: Difficulty; label: string; description: string }[] = [
  { id: "casual", label: "Casual", description: "Relaxed, inconsistent play" },
  { id: "standard", label: "Standard", description: "Balanced club-level play" },
  { id: "strong", label: "Strong", description: "Sharp, deliberate play" },
  { id: "custom", label: "Custom", description: "Configure context manually" },
]

export const DEFAULT_DIFFICULTY_CONTEXT: DifficultyContextConfig = {
  boardContext: true,
  moveHistoryContext: true,
  reasoningEffort: 50,
  maxResponseTimeSeconds: 15,
}

function clockLabelFromMinutes(minutes: number, elapsedSeconds: number): string {
  const totalSeconds = Math.max(0, minutes * 60 - elapsedSeconds)
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
}

export function mockClockLabels(initialMinutes: number) {
  return {
    humanClockLabel: clockLabelFromMinutes(initialMinutes, 34),
    modelClockLabel: clockLabelFromMinutes(initialMinutes, 58),
  }
}

export function mockIllegalModelMoves(): number {
  return Math.floor(Math.random() * 4)
}

export function mockAccuracy(): { humanAccuracy: number; modelAccuracy: number } {
  const humanAccuracy = 78 + Math.random() * 18
  const modelAccuracy = 72 + Math.random() * 20
  return {
    humanAccuracy: Math.round(humanAccuracy * 10) / 10,
    modelAccuracy: Math.round(modelAccuracy * 10) / 10,
  }
}

const CLASSIFICATION_POOL: MoveClassification[] = [
  "best",
  "good",
  "good",
  "good",
  "inaccuracy",
  "mistake",
  "blunder",
]

export function mockClassificationForIndex(index: number): MoveClassification | undefined {
  // Leave most moves unclassified so the board stays the focus; sprinkle a few.
  if (index % 5 !== 3) return undefined
  const seed = (index * 7 + 3) % CLASSIFICATION_POOL.length
  return CLASSIFICATION_POOL[seed]
}

export function mockPostGameExplanation(san: string, moveNumberLabel: string): string {
  const templates = [
    `The model appears to have preferred ${san} to improve piece activity and increase pressure toward the center.`,
    `${san} looks aimed at trading off the model's least active piece while keeping king safety intact.`,
    `Here the model likely favored ${san} to contest the open file and limit counterplay.`,
    `${san} seems to prioritize consolidating the pawn structure ahead of an approaching endgame.`,
  ]
  const index = (moveNumberLabel.length + san.length) % templates.length
  return templates[index]
}
