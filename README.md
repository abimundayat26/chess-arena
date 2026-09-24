# Multi-Model Chess Arena backend

Phase 2 provides an in-memory FastAPI chess API. The server validates UCI moves with `python-chess` and returns authoritative FEN, PGN, legal moves, and game result state.

```sh
uv sync --group dev
uv run uvicorn backend.app:app --reload
uv run pytest
```

The API is documented at `/docs` while the server is running. Its endpoints are:

| Method | Path | Body |
| --- | --- | --- |
| POST | `/games` | none |
| GET | `/games/{game_id}` | none |
| POST | `/games/{game_id}/moves` | `{"uci":"e2e4"}` |
| POST | `/games/{game_id}/resign` | `{"color":"white"}` or `{"color":"black"}` |
| POST | `/games/{game_id}/draw-offer` | `{"accepted":true}` or `{"accepted":false}` |

The draw response is a placeholder supplied by the caller. Games exist only in the process that created them and disappear when it exits. Use one server worker for this milestone.
