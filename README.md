# Chess Arena

Play timed chess against a large language model. The model gets the position and has to find its own moves: no Stockfish, no engine hints, nothing but the prompt. Once the game ends, Stockfish comes in to grade both sides.

I built it as a benchmark for chess enthusiasts. Instead of reading someone else's eval numbers, anyone who plays can sit down, pick a model and a time control, and find out for themselves how well it really plays without an engine to lean on, and how much it improves when it's given more context about the position.

## What it does

- **Pick an opponent.** OpenAI, Anthropic, Gemini, or anything on OpenRouter. There's also a built-in demo opponent if you don't have an API key.
- **Pick a time control.** Anything from 3+0 to 20+0. The clock is real: the model's thinking time comes off its clock, and its time budget for each move shrinks as it runs low.
- **Pick how much the model sees.** Casual gives it the board and the legal moves. Standard adds the move history and both clocks. Strong adds piece and material facts on top of that.
- **Illegal moves cost it.** The model gets retries if it suggests an illegal move, but five illegal attempts in one turn and it forfeits.
- **The model handles draw offers.** Offer it a draw and it decides whether to accept.
- **Review afterward.** Finished games export as PGN, and Stockfish gives each side an accuracy score and flags every inaccuracy, mistake, and blunder.

Games are saved to SQLite, so restarting the server picks up where it left off, with the time that passed charged to whoever was on move.

## Stack

FastAPI and python-chess on the backend, Next.js and React on the frontend, SQLite for storage, and Stockfish for post-game analysis. Playwright covers the end-to-end tests.

## Running it locally

Backend:

```sh
uv sync --group dev
uv run uvicorn backend.app:app --reload
```

Frontend, in a second terminal:

```sh
npm ci
npm run dev
```

Then open http://localhost:3000. The frontend proxies `/api/*` to the backend on port 8000.

To play a real model, set its key and model ID before starting the backend, e.g. `CHESS_OPENAI_API_KEY` and `CHESS_OPENAI_MODEL`. The other providers follow the same `CHESS_<PROVIDER>_API_KEY` / `CHESS_<PROVIDER>_MODEL` pattern. Keys stay on the server and are never sent to the browser. Post-game analysis needs a Stockfish binary on your PATH, or set `CHESS_STOCKFISH_PATH` to point at one.

## Tests

```sh
uv run pytest          # backend
npm run typecheck && npm run lint
npx playwright install chromium
npm run test:e2e       # full games in a real browser
```

## API

Interactive docs are at http://127.0.0.1:8000/docs once the backend is running.

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/providers` | List configured model providers |
| POST | `/games` | Start a game (time control, opponent, color, context level) |
| GET | `/games/{id}` | Current game state |
| POST | `/games/{id}/moves` | Play a move, e.g. `{"uci": "e2e4"}` |
| POST | `/games/{id}/model-turn` | Ask the model for its move |
| POST | `/games/{id}/draw-offer` | Offer a draw |
| POST | `/games/{id}/resign` | Resign |
| GET | `/games/{id}/pgn` | Download the PGN (finished games) |
| POST | `/games/{id}/analysis` | Run Stockfish review (finished games) |
| GET | `/games/{id}/metrics` | Per-game model stats (finished games) |

## Hosting it publicly

`compose.public.yml` runs the API (with Stockfish), the frontend, and a Caddy HTTPS proxy. In public mode visitors bring their own API key, which only lives in server memory and is never written to disk. Each session is capped at four active games, and Stockfish runs one analysis at a time. Copy `.env.public.example` to `.env`, set your domain and the model IDs you want to allow, then:

```sh
docker compose -f compose.public.yml up --build -d
```

## License

MIT
