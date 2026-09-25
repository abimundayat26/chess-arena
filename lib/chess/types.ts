export type AppScreen = "setup" | "playing" | "game-over"

export type PlayerColor = "white" | "black"

export type ColorPreference = PlayerColor | "random"

export interface ModelOption {
  id: string
  name: string
  provider: string
  backendProvider?: "openai" | "anthropic" | "gemini" | "openrouter"
}

export interface TimeControlOption {
  id: string
  label: string
  initialMinutes: number
  incrementSeconds: number
}

export type Difficulty = "casual" | "standard" | "strong" | "custom"

export interface DifficultyContextConfig {
  boardContext: boolean
  moveHistoryContext: boolean
  reasoningEffort: number
  maxResponseTimeSeconds: number
}

export interface MatchConfig {
  model: ModelOption
  colorPreference: ColorPreference
  difficulty: Difficulty
  difficultyContext: DifficultyContextConfig
  timeControl: TimeControlOption
}

export type TerminationReason =
  | "checkmate"
  | "stalemate"
  | "insufficient_material"
  | "repetition"
  | "fifty_move_rule"
  | "resignation"
  | "draw_agreement"
  | "timeout"
  | "variant_win"
  | "variant_loss"
  | "variant_draw"
  | "model_forfeit"

export type GameResultValue = "1-0" | "0-1" | "1/2-1/2"

export interface GameOverInfo {
  result: GameResultValue
  terminationReason: TerminationReason
  winner: PlayerColor | "draw"
}

export type MoveClassification =
  "best" | "good" | "inaccuracy" | "mistake" | "blunder"

export interface MatchExtras {
  humanColor: PlayerColor
  humanClockLabel: string
  modelClockLabel: string
  illegalModelMoves: number
  humanAccuracy: number
  modelAccuracy: number
}

export interface CompletedGame {
  gameId: string
  config: MatchConfig
  extras: MatchExtras
  pgn: string
  san: string[]
  fen: string
  gameOver: GameOverInfo
}
