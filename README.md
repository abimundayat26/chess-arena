# Multi-Model Chess Arena

The frontend uses the reviewed in-memory FastAPI chess backend. The backend validates every move and returns authoritative FEN, PGN, legal moves, status, and result. `chess.js` supplies local board feedback. Opponent moves and draw decisions are mocked, but both actions are submitted to the backend.

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
| POST | `/games` | none |
| GET | `/games/{game_id}` | none |
| POST | `/games/{game_id}/moves` | `{"uci":"e2e4"}` |
| POST | `/games/{game_id}/resign` | `{"color":"white"}` or `{"color":"black"}` |
| POST | `/games/{game_id}/draw-offer` | `{"accepted":true}` or `{"accepted":false}` |

Games exist only in the FastAPI process that created them; use one backend worker. Restarting it loses active games. Model providers, persistence, production clocks, and analysis are not connected.
