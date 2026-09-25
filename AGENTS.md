# AGENTS.md

## Purpose

This file defines how AI coding agents should work inside the Multi-Model Chess Arena repository.

Before changing code, agents must read:

```text
SPEC.md
AGENTS.md
ROADMAP.md
```

If `DESIGN.md` exists, frontend agents must also read:

```text
DESIGN.md
```

The documents have different responsibilities:

```text
SPEC.md      Current product requirements
AGENTS.md    Agent behavior and ownership
ROADMAP.md   Future architecture and planned phases
DESIGN.md    Approved visual design system
```

Current requirements in `SPEC.md` take priority over future ideas in `ROADMAP.md`.

---

# 1. Current Development Phase

The project has completed and reviewed:

```text
Phases 7–10 and the configured-provider frontend hookup
```

The current contracts are in `SPEC.md`. Agents must not implement Phase 11 onward unless explicitly instructed.

The fact that functionality appears in `ROADMAP.md` does NOT authorize its implementation.

---

# 2. Repository as Source of Truth

GitHub is the shared source of truth.

Agents should:

- make focused changes
- preserve existing architecture where reasonable
- avoid unrelated rewrites
- inspect current files before creating replacements
- run relevant tests/checks before declaring work complete
- clearly summarize files changed

Do not silently redesign major architecture.

---

# 3. v0 Ownership

During Phase 1, v0 primarily owns:

```text
frontend visual design
React components
Tailwind styling
shadcn/ui usage
responsive layouts
interaction design
frontend chessboard UX
mock frontend state
```

v0 may scaffold the frontend if the repository does not yet contain one.

v0 should focus particularly on:

```text
Game Setup
Active Game
Game Over
```

The Active Game screen has highest visual priority.

---

# 4. v0 May Use chess.js

v0 is explicitly allowed to use:

```text
chess.js
```

for lightweight frontend chess functionality.

Approved uses include:

- legal move generation
- legal move highlighting
- client-side move validation
- drag/drop validation
- check/checkmate detection
- stalemate/draw detection
- castling
- en passant
- promotions
- FEN
- PGN

This is deliberately included in Phase 1 because legal move highlighting and realistic board interaction materially improve frontend design testing.

Do not interpret this as permission to build the production chess backend.

---

# 5. v0 Must Not Implement

Unless explicitly instructed, v0 must not implement:

```text
FastAPI
python-chess
Stockfish
real LLM API calls
OpenAI SDK
Anthropic SDK
Gemini SDK
OpenRouter SDK
authentication
databases
cloud persistence
production backend routes
server-side chess state
```

Do not add infrastructure simply because it might eventually be useful.

---

# 6. Future Backend Agent Ownership

In later phases, Codex or Claude will primarily own:

```text
backend/
tests/
authoritative chess logic
clock logic
model provider abstractions
API integration
illegal-move retry behavior
persistence
Stockfish analysis
```

Frontend agents may read these systems but should not modify them casually.

---

# 7. Shared Boundaries

Future architecture should maintain this distinction:

```text
Frontend chess.js
    =
fast UI feedback and move visualization

Backend python-chess
    =
authoritative production game state
```

When the backend exists, frontend validation is convenience only.

The server must independently validate every move.

Never trust frontend legality as authoritative.

---

# 8. Game State Requirements

The frontend should explicitly model:

```text
setup
playing
game-over
```

Do not infer application state entirely from component visibility.

All terminal game conditions must transition to:

```text
game-over
```

This includes:

- checkmate
- stalemate
- chess-rule draw
- resignation
- accepted draw
- future timeout

Once the game is over:

- no further board moves are allowed
- clocks should stop when real clock logic exists
- game controls intended for active play should be disabled/hidden
- final result information should be retained
- Game Over screen should appear

---

# 9. Mocking Rules

During Phase 1, mock:

- model identity
- provider behavior
- model move generation
- AI thinking
- Stockfish accuracy
- move classifications
- illegal AI move metrics
- post-game AI explanation

Do not mock chessboard legality if chess.js can handle it cheaply.

Use real local chess state where practical.

---

# 10. Design Rules

Until `DESIGN.md` exists, follow the design direction in `SPEC.md`.

The interface should remain:

```text
minimal
warm
cozy
calm
premium
chess-first
```

Avoid:

- generic SaaS layouts
- unnecessary dashboards
- excessive nested cards
- purple AI gradients
- glassmorphism
- esports styling
- visual clutter

The board is the primary object.

---

# 11. Component Rules

Prefer small reusable components.

Do not create abstraction solely for abstraction's sake.

Keep domain state separate from visual components where reasonable.

Prefer something conceptually similar to:

```text
GameSetup
ActiveGame
GameOver

ChessBoard
ChessClock
MoveList
PlayerIdentity
GameControls
```

Do not create a large global architecture prematurely.

---

# 12. Dependency Rules

Before adding a dependency:

1. determine whether an existing dependency already solves the need
2. prefer mature, lightweight packages
3. avoid adding large libraries for trivial functionality
4. document significant new dependencies

Approved Phase 1 chess dependency:

```text
chess.js
```

---

# 13. API Rules

During Phase 1:

```text
No external API calls.
```

Do not use:

```text
fetch()
axios()
provider SDKs
```

for real external services.

Local frontend behavior is allowed.

---

# 14. Git Workflow

Agents should work on dedicated branches when multiple agents are active.

Example:

```text
main

feat/frontend-v0
feat/game-core
feat/model-providers
feat/postgame-analysis
```

Do not allow multiple agents to make broad overlapping changes to the same files unnecessarily.

Agents should commit cohesive units of work.

---

# 15. Cross-Agent Changes

If an agent needs to modify an area normally owned by another agent:

1. inspect the existing interface first
2. make the smallest necessary change
3. avoid breaking existing contracts
4. document why the cross-boundary change was necessary

Future API contracts should not be changed casually by frontend design work.

---

# 16. Testing Expectations

During Phase 1, verify at minimum:

- app builds
- TypeScript passes
- linting passes if configured
- setup → game transition works
- legal chess moves work
- illegal chess moves are rejected
- legal move indicators work
- drag/drop works
- click-to-move works
- promotion works
- checkmate triggers Game Over
- draw states trigger Game Over
- resignation triggers Game Over
- accepted draw triggers Game Over
- New Game returns to setup

Do not claim functionality has been tested unless it actually has been run.

---

# 17. Completion Reports

When finishing a task, summarize:

```text
What changed
Files changed
Tests/checks run
Known limitations
```

Keep reports concise.

Do not claim future roadmap features are complete.

---

# 18. Scope Discipline

Agents should optimize for the current milestone.

Do not implement features because:

- they seem easy
- they appear in ROADMAP.md
- they might be useful someday

Implement only what the current task or current specification requires.

A small, coherent system is preferred over speculative infrastructure.

---

# 19. Documentation Updates

If an implementation decision materially changes the product contract:

```text
update SPEC.md
```

If it changes agent workflow:

```text
update AGENTS.md
```

If it changes future architecture or sequencing:

```text
update ROADMAP.md
```

If it changes the approved visual language:

```text
update DESIGN.md
```
Backend workflow:
1. Implementer builds a focused milestone and commits.
2. Tester/reviewer branches from that commit.
3. Tester adds adversarial tests and fixes only verified issues.
4. Reviewed work is merged only after full tests pass.

Do not place all project information into one document again.
