# Multi-Model Chess Arena

The frontend uses the FastAPI chess backend for authoritative moves, clocks, model turns, and results. `chess.js` supplies local board feedback. A demo opponent is available without provider credentials; configured providers use real model turns and draw decisions.

## Run locally

In one terminal:

```sh
uv sync --group dev
uv run uvicorn backend.app:app --reload
```

In another:

```sh
npm ci
npm run dev
```

Open `http://localhost:3000`. The development server proxies `/api/*` to `http://127.0.0.1:8000/*`. Set `CHESS_API_URL` before starting Next.js to use another local backend address.

To enable a provider, set its server-side key and model ID before starting FastAPI, for example `CHESS_OPENAI_API_KEY` and `CHESS_OPENAI_MODEL`. Anthropic, Gemini, and OpenRouter use the same `CHESS_<PROVIDER>_API_KEY` and `CHESS_<PROVIDER>_MODEL` pattern. The browser never receives keys. Games are stored in `.data/chess-arena.sqlite3` by default; set `CHESS_DB_PATH` to use another local file. Run one backend worker so in-flight request guards remain authoritative.

## Checks

```sh
uv run pytest
npm run build
npm run typecheck
npm run lint
npx playwright install chromium
npm run test:e2e
```

Backend endpoints are documented at `http://127.0.0.1:8000/docs`.

| Method | Path | Body |
| --- | --- | --- |
| GET | `/providers` | none |
| POST | `/games` | time control; optional configured provider, model color, and context level |
| GET | `/games/{game_id}` | none |
| POST | `/games/{game_id}/moves` | `{"uci":"e2e4"}` |
| POST | `/games/{game_id}/resign` | `{"color":"white"}` or `{"color":"black"}` |
| POST | `/games/{game_id}/model-turn` | none |
| POST | `/games/{game_id}/draw-offer` | `{}` for bound games; `{"accepted":true}` or `{"accepted":false}` for demo games |

Restarting the backend recovers saved games and charges elapsed wall time to the active clock. Post-game engine analysis is not included.
