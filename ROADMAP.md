# Multi-Model Chess Arena — Roadmap

## Purpose

This document describes future architecture and planned development after the current frontend prototype.

It is NOT the active implementation specification.

Agents must not implement roadmap items unless the current task explicitly activates that phase.

Current requirements live in:

```text
SPEC.md
```

---

# Phase 1 — Frontend Prototype

Status:

```text
COMPLETED PROTOTYPE
```

Primary goals:

- establish visual identity
- build Game Setup
- build Active Game
- build Game Over
- establish reusable frontend components
- integrate lightweight `chess.js`
- support realistic local chess interaction
- support legal move highlighting
- establish terminal game-state transitions

Phase 1 remains frontend-only.

See `SPEC.md` for authoritative requirements.

---

# Prior milestone — Frontend–backend integration

Connect the Phase 1 frontend to the reviewed in-memory Phase 2 API. The backend is authoritative; chess.js remains for local board feedback. Model moves and draw acceptance remain mocked. See the current integration contract in `SPEC.md`.

---

# Phase 2 — Authoritative Chess Backend

Implemented and reviewed as the in-memory chess API:

```text
Python
FastAPI
python-chess
```

The backend becomes authoritative for production game state.

Future state should include:

```text
game_id
FEN
PGN
side_to_move
legal_moves
white_clock
black_clock
game_status
result
termination_reason
illegal_model_move_count
model_configuration
```

Frontend chess.js remains useful for immediate interaction but no longer determines authoritative legality.

Conceptual flow:

```text
Frontend attempts move
        ↓
Local chess.js validation
        ↓
Fast UI feedback
        ↓
Backend receives move
        ↓
python-chess validates independently
        ↓
Authoritative state returned
```

---

# Phase 3 — Production Clock System

Status: **COMPLETED AND REVIEWED**. The authoritative contract is in `SPEC.md`.

Implement real timed chess.

Supported formats remain blitz and rapid with at most 20 minutes starting time per side.

Potential presets:

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

Clock state must be authoritative on the backend.

AI request latency counts against AI time.

Illegal-move retries also count against AI time.

Terminal timeout transitions to:

```text
game-over
```

just like:

- checkmate
- resignation
- draw

---

# Phase 4 — Model Provider Architecture

Status: **COMPLETED AND REVIEWED**. The implementation contract is in `SPEC.md`.

Create a provider-independent interface.

Conceptually:

```text
ChessModel
├── OpenAIAdapter
├── AnthropicAdapter
├── GeminiAdapter
└── OpenRouterAdapter
```

Possible interface:

```python
class ChessModel:
    async def choose_move(
        self,
        position,
        legal_moves,
        game_history,
        time_remaining,
        difficulty_config,
    ) -> ModelMove:
        ...
```

The rest of the application should not rely on provider-specific behavior.

---

# Phase 5 — Model Context Levels

Users should be able to control what information the model receives.

This provides one dimension of difficulty.

## Minimal

```text
FEN
legal moves
time remaining
```

## Game Context

```text
FEN
PGN
legal moves
time remaining
```

## Structured Position

Potentially include:

```text
piece locations
material counts
castling rights
side to move
move number
```

## Custom

Allow individual configuration.

No chess-engine-derived evaluation may be included during live play.

---

# Phase 6 — Adaptive AI Thinking Time

Model compute should scale according to remaining clock.

Normal maximum target:

```text
approximately 15 seconds
```

Initial heuristic may resemble:

```text
> 10 minutes remaining
up to 15 seconds

5–10 minutes
up to 10 seconds

2–5 minutes
up to 6 seconds

30–120 seconds
up to 3 seconds

< 30 seconds
approximately 1 second
```

Later versions may incorporate:

- increment
- move number
- phase of game
- position complexity
- API latency history

Time spent on failed/illegal responses remains real clock consumption.

---

# Phase 7 — Illegal Model Move Handling

Status: **COMPLETED AND REVIEWED**. The bounded retry contract is in `SPEC.md`.

Every model move must be independently validated.

Preferred machine-readable format:

```json
{
  "move": "g1f3"
}
```

UCI is preferred internally because it is simple to parse.

If a model proposes:

- illegal move
- malformed move
- impossible promotion
- wrong-side move
- unparsable output

then:

```text
illegal_model_move_count += 1
```

The model should automatically receive a retry.

Example:

```text
Your previous proposed move g1g5 was illegal.

Choose exactly one legal move from the supplied legal moves.
```

Potential maximum:

```text
MAX_MOVE_RETRIES = 5
```

If the model fails repeatedly, the game may terminate as a model failure/forfeit.

All retries count against its clock.

---

# Phase 8 — No-Engine Gameplay Enforcement

Status: **COMPLETED AND REVIEWED**. The live prompt boundary is in `SPEC.md`.

During live gameplay the model must never receive:

- Stockfish evaluations
- Stockfish candidate moves
- Stockfish principal variations
- tablebase answers
- opening-database recommendations
- engine-derived tactical hints

The purpose is to measure the language model's own chess ability.

Stockfish must remain architecturally separated from the live model pathway.

---

# Phase 9 — Draw Decisions

Status: **COMPLETED AND REVIEWED**. The bound-model decision contract is in `SPEC.md`.

Eventually draw offers should involve the actual model.

Human flow:

```text
Human offers draw
      ↓
Model receives current position + game state
      ↓
accept / decline
```

Accepted:

```text
result = 1/2-1/2
termination_reason = draw_agreement
state = game-over
```

Declined:

```text
state remains playing
```

A future version may allow the AI itself to offer draws.

---

# Phase 10 — Game Persistence

Status: **COMPLETED AND REVIEWED**. Local SQLite recovery is in `SPEC.md`.

Store games locally by default.

Possible metadata:

```text
game_id
timestamp
PGN
final FEN
result
termination_reason
time_control
human_color
model_provider
model_name
model_configuration
illegal_move_count
move timings
API latency
```

Initial persistence does not require user accounts.

---

# Phase 11 — PGN Export

Users should be able to export completed games.

Example:

```text
[Event "Multi-Model Chess Arena"]
[White "Human"]
[Black "Claude Sonnet"]
[TimeControl "600+5"]
[Result "1-0"]
```

Possible custom metadata:

```text
[AIProvider "Anthropic"]
[AIModel "Claude Sonnet"]
[IllegalMoves "2"]
```

PGN should remain valid for ordinary chess tooling.

---

# Phase 12 — Post-Game Stockfish Analysis

Stockfish becomes available only after the game reaches:

```text
game-over
```

Initial analysis should provide:

- human accuracy
- model accuracy
- move evaluations
- basic move classifications

Possible classifications:

```text
Best
Excellent
Good
Inaccuracy
Mistake
Blunder
```

Live games must never expose Stockfish information.

---

# Phase 13 — Model Performance Metrics

Store metrics such as:

```text
result
accuracy
illegal_move_count
average_move_time
median_move_time
API failures
retry count
time used per move
```

Future aggregate views might compare models.

Example:

```text
Model
Games
Win %
Draw %
Loss %
Average accuracy
Illegal moves / game
```

These should be based on actual recorded games.

---

# Phase 14 — Public Deployment

The application should eventually be deployable.

Because model API calls cost money, the preferred public architecture is:

```text
BYOK
Bring Your Own Key
```

Users supply credentials for their chosen provider.

Potential providers:

- OpenAI
- Anthropic
- Google
- OpenRouter
- compatible future providers

Keys must not be permanently stored by default.

They must never appear in logs.

Security architecture should be reviewed before public deployment.

---

# Phase 15 — Mechanistic Interpretability Foundation

Future move records should support interpretability data.

Possible structure:

```json
{
  "ply": 24,
  "fen": "...",
  "move": "f3e5",
  "provider": "future-interpretable-model",

  "policy_probability": null,
  "concept_scores": null,
  "interventions": null
}
```

Possible future analysis:

- activation probes
- concept directions
- policy probabilities
- causal interventions
- activation patching
- policy changes following ablation
- human-readable strategic concepts

---

# Phase 16 — Mechanistically Grounded Chess Tutor

Long-term pipeline:

```text
Player game
    ↓
Mistake detected
    ↓
Stronger continuation identified
    ↓
Relevant model representations analyzed
    ↓
Chess concept attribution
    ↓
Human-readable lesson
    ↓
Targeted training position
```

Example:

```text
You repeatedly underestimated stable knight outposts.

In this position, Nd5 was important because:

• Black lacked a pawn capable of challenging the knight.
• The knight restricted Black's pieces.
• The knight increased pressure near the king.
```

The central research objective is to distinguish genuinely model-grounded explanations from plausible post-hoc explanations.

---

# Research Principle

Always distinguish:

```text
engine evaluation
model move
post-hoc model explanation
mechanistic evidence
human chess interpretation
```

These are not interchangeable.

A model producing a convincing explanation does not demonstrate that the explanation reflects the computation responsible for its move.

---

# Long-Term Tutor Research

One possible experiment compares:

```text
Engine-only feedback

vs.

Engine + ordinary LLM explanation

vs.

Engine + mechanistic evidence + explanation
```

Measure whether players improve on unseen positions involving the same concepts.

Potential concepts include:

- king safety
- outposts
- passed pawns
- bishop pair
- open files
- space
- piece activity
- pawn structure
- initiative
- compensation

---

# Planned Repository Shape

Long-term:

```text
chess-arena/
│
├── frontend/
│
├── backend/
│   ├── api/
│   ├── chess/
│   ├── providers/
│   ├── analysis/
│   └── storage/
│
├── tests/
│
├── SPEC.md
├── AGENTS.md
├── ROADMAP.md
├── DESIGN.md
└── README.md
```

`DESIGN.md` should be added once the initial v0 design is approved.

---

# Development Sequence

The intended sequence is:

```text
Phase 1
Frontend prototype + chess.js

        ↓

Phase 2
Authoritative chess backend

        ↓

Phase 3
Production clocks

        ↓

Phase 4–7
AI providers + context + timing + retries

        ↓

Phase 8–9
No-engine enforcement + draw behavior

        ↓

Phase 10–12
Persistence + PGN + Stockfish

        ↓

Phase 13–14
Metrics + deployment

        ↓

Phase 15–16
Mechanistic interpretability + tutoring
```

The project should progress through these stages incrementally rather than attempting to construct the final architecture at once.
