# Multi-Model Chess Arena

## Phase 14 — public BYOK deployment preparation

`CHESS_PUBLIC_MODE=1` enables the public contract; local mode retains configured server keys and existing behavior. In public mode `GET /providers` lists providers with server-approved `CHESS_<PROVIDER>_MODEL` IDs and no credentials. A visitor selects a provider and enters its key in the setup form. `POST /credentials` accepts only `{provider, api_key}` (8–512 characters), stores the key in process memory under a fresh random HTTP-only, Secure, SameSite=Strict session cookie, and returns 204. Keys are never stored in SQLite, browser storage, API responses, or logs. The setup form clears the key after credential submission. A process restart drops credentials; users must re-enter them to continue a bound game. Only the selected provider adapter receives that key. Server model IDs, provider URLs, context levels, and thinking budgets remain server-controlled.

Every public game is bound to the SHA-256 digest of its creator's session token in its saved record. All game reads, moves, resignations, draw decisions, PGN, metrics, and analysis return 404 to a different or missing session. Creating a bound game requires an in-memory key for that selected provider, otherwise 503. A cost-bearing model turn or draw requires both game ownership and that key, otherwise 503. Each game permits at most 200 provider attempts; once exhausted, further cost-bearing actions return 429 without a provider call. No more than four active games may be created by one session. Mutation requests reject a mismatched `Origin` relative to their external host with 403. Requests above 8 KiB and malformed or extra credential fields are rejected generically. Public mode requires HTTPS at the reverse proxy and one backend worker; session cookies are never placed in URLs. Unknown game IDs reveal no data.

An unrecognized session cookie is replaced with a newly generated token before accepting a credential or creating a game. In public mode, at most one Stockfish analysis runs at a time; a concurrent uncached analysis request returns 429 without starting another engine process. Completed cached analyses remain readable.

Production configuration consists of a single-worker FastAPI container with persistent SQLite and Stockfish, a Next.js container proxying `/api` to FastAPI, and a Caddy HTTPS entrypoint. Only model IDs, database location, domain, and optional deployment settings are configured. No provider credentials are required in deployment environment. Operators must set `CHESS_DOMAIN`, DNS, and approved model IDs before launch. Failure of an upstream provider returns existing generic 502 behavior. Neither deploy nor a real paid credential connection is authorized by this milestone.

---

## Phase 13 — measured game metrics

`GET /games/{id}/metrics` returns only for terminal games (404 unknown, 409 active). It includes the result, provider and frozen model ID, actual illegal model proposal count, per-side legal move time samples in milliseconds, provider attempt count, provider failure count, retry count, and average/median model move time. A move time sample is the nonnegative authoritative clock consumption since that side's preceding legal move (or game start) through its current legal move, before the increment; rejected moves, provider latency, retries, and downtime are included. It excludes increment. Average and median use the model side's samples and are null when no bound model has completed a move. Provider attempts count each actual `choose_move` or `choose_draw` invocation. Provider failures count transport/format exceptions, nontext output, and expired thinking budgets; illegal chess proposals are tracked separately. Retry count increments only when another provider move attempt is made within one model turn after an illegal proposal. All counters and samples are saved atomically with the game and survive restart. They do not include mock demo opponent behavior. If a completed Stockfish analysis exists, the metrics include its measured white/black accuracy; otherwise accuracy is null. The Game Over UI displays these measured metrics, with unavailable values shown as such.

---

## Phase 12 — terminal Stockfish analysis

`POST /games/{id}/analysis` is available only after authoritative termination (404 unknown, 409 active). It returns `status: complete` with per-ply SAN, UCI, mover, white-perspective centipawn evaluation after the move, centipawn loss, and classification, plus white and black accuracy; or `status: unavailable` with a stable generic reason (`engine_unavailable`, `engine_failed`, or `game_too_long`). The executable is `CHESS_STOCKFISH_PATH` (default `stockfish`). Analysis opens a fresh UCI process after checking terminal status and never imports into the live model/context/provider path. At most 160 plies are analyzed; a longer game is unavailable rather than sampled. The engine receives a 0.05 second per-position limit and the operation has a 30 second outer deadline. A missing, crashing, malformed, or timed-out engine yields unavailable with no fabricated evaluations. A completed analysis is saved with the game and reused after restart. Unavailable results may be retried.

For each ply the engine evaluates the position before and after from White's perspective, with mate represented as plus/minus 10,000 centipawns. Centipawn loss is `max(0, mover_sign × (before − after))`. Classifications use loss thresholds: best ≤15, good ≤50, inaccuracy ≤100, mistake ≤250, blunder >250. Side accuracy is the arithmetic mean of `max(0, 100 − loss/5)` for its analyzed moves, rounded to one decimal; a side with no moves has null accuracy. These are bounded engine estimates, not claims of perfect chess accuracy. The frontend displays this data only on a terminal game, shows an unavailable state when appropriate, and does not show mock measured values.

---

## Phase 11 — authoritative PGN export

`GET /games/{id}/pgn` returns a UTF-8 `application/x-chess-pgn` attachment only for a terminal game (404 unknown, 409 active). It is generated from the saved initial FEN and authoritative UCI move stack. Its required headers are `Event`, `Site`, `Date`, `Round`, `White`, `Black`, `Result`, and `TimeControl`; `Date` is the UTC creation date and `TimeControl` is the PGN seconds-plus-increment form. The model side uses the configured model display ID frozen at creation; the other side is `Human`. Unbound games use `Demo model` as Black and `Human` as White. Bound exports also have `AIProvider` and `AIModel`; all exports have `Termination` and `IllegalModelMoves`. Header values are escaped through python-chess; carriage returns and line feeds in configured model IDs are replaced with spaces because PGN tags cannot contain line breaks. The movetext result equals the header and authoritative result. A nonstandard initial FEN uses PGN `SetUp` and `FEN`. These fields survive restart. The Game Over download action fetches this endpoint and reports a generic failure if it cannot download.

---

## Current milestone — frontend provider hookup

`GET /providers` returns only configured provider names and their server-side model display IDs; it never returns keys or accepts client credentials. Setup always offers the existing unbound demo opponent and additionally lists configured providers. Selecting a real provider creates a bound game with the opposite model color and a server-supported context level. The real setup context choices map to `minimal`, `game_context`, and `structured_position`; client reasoning-effort and deadline overrides are not sent. The server still chooses the provider's actual model ID and adaptive deadline.

For a bound game, the frontend calls `/model-turn` whenever it is the model's turn and `/draw-offer` with `{}` when the human offers a draw. The backend owns retries, clock charges, draw decisions, and final results. The UI shows thinking while a request runs, offers a manual retry after a generic failure, reconciles a lost response by reading the game, and stops all play controls on a terminal state. The displayed illegal-attempt count comes from the server. Provider errors are shown as a generic action failure; keys, upstream bodies, and provider exception text never reach the browser. The unbound demo keeps its mocked opponent and draw behavior. Real-model Game Over screens omit mock accuracy, classifications, and explanations.

---

## Current milestone — Phase 10 local game persistence

The default API process stores each authoritative game in a local SQLite file at `CHESS_DB_PATH` or `.data/chess-arena.sqlite3` relative to its working directory. `GameStore()` without a path remains ephemeral for isolated tests. A saved record contains the game ID, initial board position and UCI move stack, status, result, termination reason, time control, model provider/color, context level, actual illegal-attempt count, both exact clock values, and the active clock at the save point. No provider credentials, prompt text, raw provider output, or engine analysis are stored. Each state mutation and clock charge is committed atomically before its API response; a new process using the same path can retrieve the same game ID and continue it. Completed games retain frozen clocks.

On restart, the store charges the nonnegative wall-clock interval since the last save to the saved active clock, clamps it at zero, and applies normal timeout and insufficient-material rules. It then resumes the board side's clock from the recovery instant. An in-flight model turn or draw decision is abandoned; its elapsed downtime is charged to the saved model clock, no proposed move or draw answer is applied, and its call guard is cleared. A wall clock that moved backward contributes zero elapsed time. Client snapshots continue to use the authoritative monotonic clock while the process runs. Corrupt or unknown records are never silently replaced with a new game; retrieval fails safely.

---

## Current milestone — Phase 9 bound-model draw decisions

For an unbound game, `POST /games/{id}/draw-offer` keeps the existing `{"accepted": boolean}` contract. For a bound game, the client sends `{}`; supplying `accepted` is rejected with 422. The server snapshots the same allowlisted live context as a move turn, adds the bound model's color, and asks its bound provider to return exactly `ACCEPT` or `DECLINE`. The provider cannot initiate an offer. A valid `ACCEPT` returns 200 with a stopped `draw_agreement` game; `DECLINE` returns 200 with the unchanged board and playing state. Draw decisions do not change the illegal-move count and never award an increment.

Only one provider action per game may run at a time. A pending draw rejects another draw, model turn, or board move with 409. Resignation and timeout may end the game during a pending decision; a later provider answer cannot alter that result. The decision uses the model clock, temporarily pausing the other clock when necessary, and shares the Phase 6 adaptive budget computed at decision start. If the model clock hits zero, timeout wins and returns the final state. If the shorter budget expires, the request is cancelled and returns generic 502; the game remains active with the board unchanged. Provider errors and invalid decision text also return generic 502. On decline, failure, or request cancellation, the prior side's clock resumes with no double charge. Unbound games retain their existing local draw behavior.

---

## Current milestone — Phase 8 live-game information boundary

The only data sent to a live model move request is the frozen, server-derived `ModelPosition` allowlist: FEN, side to move, legal UCI moves, the selected Phase 5 context fields, and Phase 7 invalid-move feedback. Draw decisions additionally include the bound model's color. The provider adapters share one live prompt builder. No client field can add prompt text, an evaluation, candidate ranking, principal variation, tablebase answer, opening advice, or engine-derived hint. Legal UCI moves are chess-rule legality, not recommendations. Future analysis code must remain outside the live prompt and provider adapter modules, and cannot be imported or called from the live-game path. API game snapshots likewise expose no evaluation, recommendation, tablebase, or opening field. Tests must intercept all four provider transports and assert that the outgoing request contains only approved live context, including on retry.

---

## Current milestone — Phase 7 illegal model moves

One `POST /games/{id}/model-turn` request permits at most five invalid UCI proposals (five total attempts). A malformed, empty, unparsable, wrong-side, impossible promotion, or otherwise illegal proposed move increments the persisted-in-game `illegal_model_move_count` exactly once; this count is returned in every game snapshot, including completed games. The next provider request receives the same authoritative position plus the previous invalid proposal and an instruction to select a listed legal UCI move. Provider exceptions or missing/non-text content are service failures, not invalid chess proposals, and return generic 502 without increasing the count.

All attempts share the original adaptive thinking budget; it is never reset on retry. Every attempt and retry consumes the active model clock. A legal proposal strictly before the deadline is applied once and earns one increment. At the deadline with time remaining, return generic 502 with no board change or increment. At clock zero, timeout takes precedence over all proposals and failure states. On the fifth invalid proposal before either deadline, end the game by `model_forfeit`, award the human side the win, stop clocks, and return 200 with the final state. No illegal proposal is ever applied or awarded an increment. Concurrent, stale, and terminal requests retain their existing conflict behavior.

Phase 8 onward remains out of scope for this milestone.

---

## Current milestone — Phases 5 and 6 model context and adaptive thinking time

`POST /games` accepts optional `context_level`: `minimal` (default), `game_context`, or `structured_position`. It is fixed for the game and returned as `context_level` in every game state. Unknown levels or extra creation fields return 422; `model_provider` and `model_color` remain a required pair for bound games. The same default applies to unbound games. Clients cannot supply credentials, model IDs, provider URLs, prompt text, or a custom context configuration.

The server builds an immutable position at the start of each model turn. `minimal` sends exactly the Phase 4 FEN, side to move, and legal UCI moves. `game_context` adds the authoritative PGN and the model's remaining clock in integer milliseconds. `structured_position` includes everything in `game_context`, plus a square-to-piece map (white uppercase and black lowercase FEN letters), white and black counts for pawn/knight/bishop/rook/queen, castling rights in FEN notation (`-` when absent), and the full move number. These fields come only from python-chess and the authoritative game clock. No live prompt may include evaluation, candidate ranking, suggested move, principal variation, tablebase or opening recommendation, or any other engine-derived hint. Legal moves are the existing chess-rule legality list, not engine suggestions.

`POST /games/{game_id}/model-turn` derives a per-call budget from the model's remaining clock after charging elapsed time at turn start. Remaining time `>=600` seconds allows 15 seconds; `>=300` allows 10; `>=120` allows 6; `>=30` allows 3; below 30 allows 1. The budget is capped at the exact remaining clock time. The boundaries are inclusive. This budget is server-controlled and is not a request field. All provider elapsed time, including failed, illegal, and cancelled calls, is charged to the authoritative model clock. If the clock reaches zero before a move is applied, return 200 with the authoritative timeout game state, regardless of provider output or budget expiry. If the shorter budget expires with clock time remaining, cancel the provider call and return 502 `{"detail":"Model turn failed"}`; leave the board unchanged and award no increment. Other provider and illegal-output failures keep the Phase 4 502 behavior. A successful legal move within both deadlines earns the usual increment. A call whose measured elapsed time reaches its budget cannot apply a move, even if its provider returns at that boundary. Only one model call may be in flight per game; concurrent, stale, wrong-turn, unbound, and terminal requests retain the Phase 4 conflict behavior. Cancellation releases the call guard after charging time. There are no automatic retries or metrics.

Phase 7 retries and metrics, Stockfish, persistence, authentication, and unrelated frontend work remain out of scope.

---

## Prior milestone — Phase 4 model provider architecture

Phase 4 adds one server-initiated model turn while retaining the reviewed Phase 3 chess and clock authority. The approved providers are OpenAI, Anthropic, Gemini, and OpenRouter. Each has a server-side adapter behind one `choose_move(position)` interface. The shared position contains only FEN, side to move, and legal UCI moves. Adapters request one UCI move; they do not receive engine evaluations or a configurable context level. Provider API keys and model IDs come only from server environment variables (`CHESS_<PROVIDER>_API_KEY` and `CHESS_<PROVIDER>_MODEL`). The server never accepts credentials or arbitrary provider URLs from a client, and never returns or logs keys or raw provider errors. The HTTP transport uses the providers' documented REST APIs via `httpx`; no provider SDK is needed.

`POST /games` may include `model_provider` (`openai`, `anthropic`, `gemini`, or `openrouter`) and `model_color` (`white` or `black`); both must be supplied together. Creation returns 503 if that provider is not configured. Existing requests without these fields still create unbound games for the current mock frontend. The response includes `model_provider` and `model_color` (or null), but no credentials. A bound game's model side cannot be moved through `/moves`.

`POST /games/{game_id}/model-turn` runs exactly one turn for the bound model when it is that side's turn. Only one model call per game may be in flight. The server snapshots the position, awaits the provider, charges all elapsed time to the model's Phase 3 clock, and validates the returned UCI move with python-chess before applying it and awarding the normal increment. If time expires during the call, the response is the authoritative timeout game state and no move is applied. A provider failure returns 502 with a generic message; a malformed or illegal move returns 502 with a generic message. In either case the board stays unchanged, the model clock is charged, and there is no automatic retry. Wrong-turn, concurrent, stale, terminal, or unbound calls return 409; unknown games return 404. Provider decisions never bypass backend legality or clock checks. The frontend may continue its existing mock opponent path for unbound games; wiring selection to real providers is outside this one-turn backend milestone.

This earlier one-turn contract is superseded by the current context and timing rules above.

---

## Prior milestone — Phase 3 production clocks (September 2026)

The reviewed Phase 2 API remains authoritative for chess state. Phase 3 makes it authoritative for both clocks and timeout results. Game creation accepts one of `3+0`, `3+2`, `5+0`, `5+3`, `10+0`, `10+5`, `15+10`, or `20+0` (default `10+5` for existing clients). API responses include the time control, each side's remaining milliseconds, and the active clock. The server measures elapsed time with a monotonic source on every game read or action, including rejected moves and mocked opponent turns. A legal move consumes the mover's elapsed time and adds its increment; an illegal move earns no increment. At zero, the game ends with `termination_reason = "timeout"` and a win for the other side, except when that side cannot possibly mate, in which case the result is a draw. Later moves and game-ending actions return 409. Finished clocks stop. The frontend displays a local projection between server responses, then replaces it with authoritative clock values on every response and periodic refresh. `chess.js` remains local move feedback only. Model APIs, Stockfish, persistence, and authentication remain out of scope.

The Phase 1 prototype requirements below describe the original UI. This current milestone supersedes their mock-clock and frontend-only clauses.

---

## Prior frontend–backend integration milestone

The Phase 1 sections below document the frontend prototype. The current milestone connects that frontend to the reviewed Phase 2 in-memory FastAPI backend. For this milestone, the backend owns FEN, PGN, legal moves, status, result, and termination reason. The UI uses chess.js for immediate move selection and legal indicators, then reconciles with each backend response. Game creation, retrieval, moves, resignation, and draw offers use the local API. Mock opponent moves also go through that API. Model identity, draw acceptance decisions, analysis, and clocks remain mocked. Games disappear when the backend process stops. No provider APIs, persistence, or production clocks are part of this milestone.

The integration contract above supersedes Phase 1 statements below that call for frontend-only state or prohibit a backend. The frontend design and other Phase 1 requirements still apply.

---

## 1. Product Overview

Multi-Model Chess Arena is a web application where a human can play timed chess games against AI language models.

Unlike traditional chess engines, the AI opponent must choose moves using only the selected language model. During live gameplay, no Stockfish or other chess engine may provide the AI with evaluations, candidate moves, principal variations, or other assistance.

The eventual application will support multiple AI providers, configurable model context, timed games, game persistence, post-game Stockfish analysis, and future mechanistic-interpretability-based chess tutoring.

The current development phase is focused on establishing the frontend experience.

---

# 2. Current Phase

## Phase 1 — Frontend Prototype

The immediate goal is to establish:

- visual design
- page layout
- frontend component architecture
- interaction feel
- chessboard interaction
- responsive behavior
- basic frontend game-state transitions

Most application data should remain mocked.

Phase 1 should NOT include:

- backend services
- real model API calls
- authentication
- databases
- real persistence
- Stockfish integration
- production clock logic
- production AI gameplay

The frontend should nevertheless be structured so these systems can be connected later without requiring a redesign.

---

# 3. Phase 1 Technology

Preferred stack:

```text
React
TypeScript
Tailwind CSS
shadcn/ui where useful
chess.js
```

`chess.js` is explicitly allowed in Phase 1.

Its purpose is to provide lightweight frontend chess behavior including:

- legal move generation
- move validation
- legal destination highlighting
- check detection
- checkmate detection
- stalemate detection
- draw-state detection
- castling
- en passant
- promotion
- FEN generation
- PGN generation

This frontend chess state is for prototype interaction and immediate UI feedback.

It is NOT intended to become the authoritative production game-state implementation.

A future backend using `python-chess` will become authoritative.

---

# 4. Required Screens

The frontend prototype contains three primary application states:

1. Game Setup
2. Active Game
3. Game Over / Post-Game Analysis

The Active Game screen is the central product experience and should receive the most design attention.

---

# 5. Application State Flow

The high-level state machine is:

```text
GAME_SETUP
     |
     | Start Game
     v
ACTIVE_GAME
     |
     | checkmate
     | stalemate
     | chess draw
     | resignation
     | accepted draw
     | timeout (future)
     v
GAME_OVER
     |
     | New Game
     v
GAME_SETUP
```

The application should explicitly represent these states rather than relying on which components happen to be visible.

Example:

```ts
type AppState =
  | "setup"
  | "playing"
  | "game-over"
```

---

# 6. Game-Termination Behavior

Any completed game must transition immediately from the Active Game state to the Game Over state.

Game-ending triggers include:

- checkmate
- stalemate
- insufficient material
- threefold repetition where applicable
- fifty-move draw where applicable
- resignation
- accepted draw offer
- timeout in a future phase

For Phase 1, `chess.js` should detect board-state-based endings.

Resignation and draw acceptance should be handled through local frontend state.

Once a game ends:

```text
gameState = "game-over"
```

The Active Game interface should no longer accept moves.

The Game Over screen should receive the final game information.

---

# 7. Screen 1 — Game Setup

The setup screen configures a new match.

## Model Selection

Use mocked models such as:

- GPT-5.6
- Claude Sonnet
- Gemini Pro
- Custom Model

Show provider information subtly.

Example:

```text
Claude Sonnet
Anthropic
```

This is visual data only during Phase 1.

---

## Player Color

Options:

```text
White
Black
Random
```

Prefer a compact segmented control.

---

## Time Control

Support only blitz and rapid.

Suggested presets:

```text
3+0
3+2
5+0
5+3
10+0
10+5
15+10
20+0
```

Do not expose starting times above 20 minutes.

Clocks may be mocked or minimally simulated during Phase 1.

Production clock behavior comes later.

---

## AI Difficulty

Provide:

```text
Casual
Standard
Strong
Custom
```

These settings are currently visual only.

Custom may expose mock controls such as:

- board context
- move-history context
- reasoning effort
- maximum response time

Do not connect these controls to a model.

---

## Start Game

Primary action:

```text
Start Game
```

Starting a game should:

1. initialize a new local chess.js game
2. initialize mocked match metadata
3. determine player color
4. change application state to `playing`

---

# 8. Screen 2 — Active Game

This is the primary screen.

The chessboard must visually dominate the experience.

The application should feel like a chess application rather than:

- an AI chatbot
- an analytics dashboard
- a generic SaaS application

---

# 9. Chessboard Interaction

Use `chess.js` for lightweight client-side move enforcement.

The board should support:

- click source then destination
- drag and drop
- selected-square highlighting
- legal destination indicators
- last-move highlighting

When a user selects a piece, display only legal destination squares returned by the local chess state.

Example conceptual flow:

```text
User selects knight on f3
        ↓
chess.js legal moves
        ↓
[e5, g5, h4, d4, d2, e1, g1, h2]
        ↓
UI highlights available destinations
```

An illegal move should never update the displayed board state.

---

# 10. Move Execution

For Phase 1:

```text
UI interaction
    ↓
chess.js validation
    ↓
legal?
   /    \
 no      yes
 |        |
ignore   update board
          |
          v
      update history
          |
          v
     check game over
```

The model's replies remain mocked during Phase 1.

A mocked AI move may be selected from legal moves for demonstration purposes.

Do not call an external model API.

---

# 11. Promotion

When a pawn reaches the final rank, display a small promotion selector.

Options:

```text
Queen
Rook
Bishop
Knight
```

The selected promotion should then be submitted through chess.js.

---

# 12. Opponent Display

Represent the AI as the opponent rather than as a configuration object.

Display:

- model name
- provider
- clock

Example:

```text
Claude Sonnet
Anthropic

08:42
```

Avoid API-card styling.

---

# 13. Human Display

Display:

```text
You
09:16
```

The human and model identities should visually resemble two players sitting across a board.

---

# 14. Move History

Display actual moves generated through the local chess.js prototype.

Example:

```text
1. e4    e5
2. Nf3   Nc6
3. Bb5   a6
4. Ba4   Nf6
5. O-O   Be7
```

Move history should remain visually secondary to the board.

---

# 15. Game Controls

During play, include:

```text
Offer Draw
Resign
```

Do NOT include:

```text
Undo
Takeback
```

---

# 16. Resignation

When the player selects:

```text
Resign
```

request a lightweight confirmation.

After confirmation:

1. set the result appropriately
2. record termination reason as `resignation`
3. change application state to `game-over`
4. show the Game Over screen

No moves may be made afterward.

---

# 17. Draw Offers

During Phase 1, draw interaction may be mocked.

Selecting:

```text
Offer Draw
```

may display a simulated AI response.

Possible outcomes:

```text
Draw declined
Draw accepted
```

If declined:

```text
remain in ACTIVE_GAME
```

If accepted:

```text
result = draw
terminationReason = draw_agreement
gameState = game-over
```

The architecture should later allow the AI model itself to decide whether to accept.

---

# 18. Automatic Board Endings

After every successful move, check the chess state.

If the position is terminal, transition immediately to Game Over.

Example:

```ts
makeMove()

if (game.isGameOver()) {
  finishGame()
}
```

The Game Over state should distinguish among applicable reasons such as:

```text
checkmate
stalemate
insufficient_material
repetition
fifty_move_rule
draw
resignation
```

Exact library APIs may determine implementation details.

---

# 19. Model Thinking State

Provide a subtle mocked state:

```text
Thinking…
```

The board should temporarily prevent additional player moves while it is supposedly the model's turn.

No AI request should actually occur during Phase 1.

---

# 20. Hidden Information During Gameplay

Do NOT show:

- Stockfish evaluation
- evaluation bar
- suggested move
- best move
- accuracy
- AI analysis
- AI explanation
- tactical hints

The human should simply play the game.

---

# 21. Screen 3 — Game Over / Post-Game Analysis

Every completed game lands on this screen.

Example:

```text
You defeated Claude Sonnet
1–0
```

or:

```text
Draw
½–½
```

---

# 22. Game Summary

Display:

- result
- termination reason
- model
- provider
- player color
- time control
- game length
- illegal AI move attempts

Example:

```text
Result              1–0
Ended by            Resignation
Opponent            Claude Sonnet
Time control        10+5
Moves               38
Illegal AI moves    2
```

Use mocked values where real systems have not yet been implemented.

---

# 23. Accuracy

Display mocked future Stockfish accuracy.

Example:

```text
You
91.4%

Claude Sonnet
84.7%
```

Prefer restrained bars or numeric emphasis.

Do not create an oversized analytics dashboard.

---

# 24. Move Review

Display move history with occasional mocked classifications such as:

```text
Good
Inaccuracy
Mistake
Blunder
```

These classifications are placeholders only.

Stockfish will calculate them in a future phase.

---

# 25. Post-Game Explanation

Provide a section for future model explanations.

Example:

```text
18...Nc5

Post-game explanation

The model appears to have preferred Nc5 to improve piece activity
and pressure the center.
```

Call this:

```text
Post-game explanation
```

Do NOT label it:

```text
Chain of thought
Internal reasoning
True reasoning
```

Post-hoc explanations and actual internal model computation are different things.

---

# 26. Post-Game Actions

Include:

```text
New Game
Download PGN
```

`New Game` should:

```text
gameState = "setup"
```

and reset local match state.

Because chess.js already contains PGN generation, the Phase 1 prototype may allow a real local PGN download if it remains simple and entirely frontend-side.

Do not introduce backend persistence for this.

---

# 27. Mock Data

Metadata that is not naturally produced through chess.js should remain mocked.

Example:

```ts
const mockMatch = {
  humanColor: "white",
  model: "Claude Sonnet",
  provider: "Anthropic",
  timeControl: "10+5",

  humanClock: "09:16",
  modelClock: "08:42",

  illegalModelMoves: 2,

  humanAccuracy: 91.4,
  modelAccuracy: 84.7,
}
```

Board state and move history should preferably come from the local chess.js instance rather than duplicated mock state.

---

# 28. Frontend Component Architecture

Prefer reusable components such as:

```text
AppShell

GameSetup
├── ModelSelector
├── ColorSelector
├── TimeControlSelector
└── DifficultySelector

ActiveGame
├── ChessBoard
├── ChessClock
├── PlayerIdentity
├── MoveList
├── ThinkingIndicator
└── GameControls

GameOver
├── GameResult
├── GameSummary
├── AccuracyBar
├── MoveReview
└── PostGameExplanation
```

Avoid unnecessary abstraction.

---

# 29. State Architecture

Keep gameplay state separate from presentation where practical.

Example conceptual organization:

```text
App State
├── screen
├── match configuration
├── chess.js game
├── result
└── termination reason
```

Do not create production global-state infrastructure unless needed.

React state/context is sufficient for the prototype.

---

# 30. Visual Direction

Desired aesthetic:

```text
minimal
warm
cozy
premium
calm
chess-focused
```

The product should evoke:

- a modern chess study
- a quiet reading room
- a tasteful chess club

It should not resemble:

- generic SaaS
- esports
- crypto dashboards
- corporate analytics tools
- AI chat applications

---

# 31. Visual Characteristics

Favor:

- warm neutral backgrounds
- cream
- stone
- warm gray
- restrained green
- brown
- burgundy
- muted amber
- subtle borders
- strong typography
- efficient spacing
- tactile details
- restrained rounding
- minimal shadows

Avoid:

- neon
- glassmorphism
- giant pills
- excessive cards
- excessive gradients
- generic purple AI styling
- heavy shadows
- unnecessary animation

The chessboard remains the dominant visual object.

---

# 32. Responsive Design

Desktop is the primary target.

On narrower displays:

- board remains prominent
- side panel may move underneath
- clocks remain associated with their player
- controls remain usable
- no page-level horizontal overflow

Do not over-optimize mobile during Phase 1.

---

# 33. Phase 1 Restrictions

Do NOT add:

```text
FastAPI
python-chess
Stockfish
OpenAI SDK
Anthropic SDK
Gemini SDK
OpenRouter SDK
databases
authentication
production persistence
```

Do NOT make external model calls.

Do NOT create model-provider infrastructure yet.

Do NOT implement future roadmap phases simply because they are described elsewhere.

---

# 34. Phase 1 Acceptance Criteria

Phase 1 is complete when:

1. Application runs locally.
2. Game Setup exists.
3. Active Game exists.
4. Game Over exists.
5. Navigation between states works.
6. Player can choose White, Black, or Random.
7. Time controls are displayed.
8. Model and difficulty selectors exist.
9. Chessboard supports click-to-move.
10. Chessboard supports drag-and-drop.
11. Legal destinations are shown in real time.
12. Illegal human moves are rejected locally.
13. Legal moves update the board.
14. Move history reflects actual frontend moves.
15. Castling works locally.
16. En passant works locally.
17. Promotion works locally.
18. Checkmate triggers Game Over.
19. Drawn board states trigger Game Over.
20. Resignation triggers Game Over.
21. Accepted draw offer triggers Game Over.
22. Active board interaction stops once game ends.
23. Offer Draw exists.
24. Resign exists.
25. No Undo exists.
26. No Takeback exists.
27. Mock thinking state exists.
28. Accuracy display exists post-game.
29. Illegal-model-move metric appears post-game.
30. New Game returns to setup.
31. Layout is polished on desktop.
32. Layout remains usable on smaller displays.
33. Components are reusable.
34. No backend exists.
35. No external API calls exist.
36. No model SDK exists.
37. No Stockfish integration exists.
38. No database exists.
39. Frontend can later be connected to an authoritative backend without redesigning the UI.
