# Multi-Model Chess Arena

## Current integration milestone (September 2026)

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