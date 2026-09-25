import type { PlayerColor } from "./types"

export interface ServerGame {
  game_id: string
  fen: string
  pgn: string
  side_to_move: PlayerColor
  legal_moves: string[]
  game_status: "playing" | "game-over"
  result: "*" | "1-0" | "0-1" | "1/2-1/2"
  termination_reason: string | null
  time_control: string
  white_clock_ms: number
  black_clock_ms: number
  active_clock: PlayerColor | null
  model_provider: string | null
  model_color: PlayerColor | null
  context_level: "minimal" | "game_context" | "structured_position"
  illegal_model_move_count: number
}

export interface ConfiguredProvider {
  provider: "openai" | "anthropic" | "gemini" | "openrouter"
  model: string
}

export class GameApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message)
  }
}

async function request(
  path: string,
  method = "GET",
  body?: object
): Promise<ServerGame> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    })
  } catch {
    throw new GameApiError(
      "Cannot reach the game server. Check that FastAPI is running.",
      0
    )
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : "Game request failed"
    throw new GameApiError(detail, response.status)
  }
  return response.json() as Promise<ServerGame>
}

export const gameApi = {
  pgn: async (id: string): Promise<string> => {
    const response = await fetch(`/api/games/${encodeURIComponent(id)}/pgn`, { cache: "no-store" })
    if (!response.ok) throw new GameApiError("Could not download PGN", response.status)
    return response.text()
  },
  providers: async (): Promise<ConfiguredProvider[]> => {
    const response = await fetch("/api/providers", { cache: "no-store" })
    if (!response.ok) throw new GameApiError("Could not load providers", response.status)
    return response.json() as Promise<ConfiguredProvider[]>
  },
  create: (timeControl: string, modelProvider?: ConfiguredProvider["provider"], modelColor?: PlayerColor, contextLevel?: ServerGame["context_level"]) =>
    request("/games", "POST", {
      time_control: timeControl,
      ...(modelProvider ? { model_provider: modelProvider, model_color: modelColor, context_level: contextLevel } : {}),
    }),
  get: (id: string) => request(`/games/${encodeURIComponent(id)}`),
  move: (id: string, uci: string) =>
    request(`/games/${encodeURIComponent(id)}/moves`, "POST", { uci }),
  resign: (id: string, color: PlayerColor) =>
    request(`/games/${encodeURIComponent(id)}/resign`, "POST", { color }),
  offerDraw: (id: string, accepted: boolean) =>
    request(`/games/${encodeURIComponent(id)}/draw-offer`, "POST", {
      accepted,
    }),
  modelTurn: (id: string) => request(`/games/${encodeURIComponent(id)}/model-turn`, "POST"),
  modelDraw: (id: string) => request(`/games/${encodeURIComponent(id)}/draw-offer`, "POST", {}),
}
