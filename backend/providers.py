"""Provider-independent, single-turn chess model adapters."""

from dataclasses import dataclass
import os
from typing import Protocol

import httpx


@dataclass(frozen=True)
class ModelPosition:
    fen: str
    side_to_move: str
    legal_moves: tuple[str, ...]
    pgn: str | None = None
    time_remaining_ms: int | None = None
    pieces: tuple[tuple[str, str], ...] | None = None
    material_counts: tuple[tuple[str, int, int], ...] | None = None
    castling_rights: str | None = None
    fullmove_number: int | None = None


class ChessModel(Protocol):
    async def choose_move(self, position: ModelPosition) -> str: ...


class ProviderError(Exception):
    """Safe, public failure category; never includes upstream response text."""


@dataclass(frozen=True)
class ProviderBinding:
    model_id: str
    adapter: ChessModel


def _prompt(position: ModelPosition) -> str:
    prompt = (
        "Choose one legal chess move. Reply with only its UCI notation, no prose.\n"
        f"FEN: {position.fen}\n"
        f"Side to move: {position.side_to_move}\n"
        f"Legal UCI moves: {', '.join(position.legal_moves)}"
    )
    if position.pgn is not None:
        prompt += f"\nPGN: {position.pgn}\nTime remaining (ms): {position.time_remaining_ms}"
    if position.pieces is not None:
        prompt += "\nPieces (square=piece): " + ", ".join(
            f"{square}={piece}" for square, piece in position.pieces
        )
        prompt += "\nMaterial counts (piece: white, black): " + ", ".join(
            f"{name}: {white}, {black}" for name, white, black in position.material_counts or ()
        )
        prompt += f"\nCastling rights: {position.castling_rights}"
        prompt += f"\nFull move number: {position.fullmove_number}"
    return prompt


class HttpModel:
    url: str

    def __init__(
        self, api_key: str, model_id: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._api_key = api_key
        self._model_id = model_id
        self._transport = transport

    async def _post(self, url: str, headers: dict, payload: dict) -> dict:
        try:
            async with httpx.AsyncClient(
                timeout=60.0, transport=self._transport, trust_env=False
            ) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Invalid response")
                return data
        except (httpx.HTTPError, ValueError):
            raise ProviderError("Model provider failed") from None

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ProviderError("Model provider returned no move")
        return value.strip()


class OpenAIAdapter(HttpModel):
    async def choose_move(self, position: ModelPosition) -> str:
        data = await self._post(
            "https://api.openai.com/v1/responses",
            {"Authorization": f"Bearer {self._api_key}"},
            {"model": self._model_id, "input": _prompt(position), "max_output_tokens": 64, "store": False},
        )
        try:
            if data.get("status") != "completed":
                raise ProviderError("Model provider returned no move")
            for item in data["output"]:
                if item.get("type") == "message":
                    for part in item["content"]:
                        if part.get("type") == "output_text":
                            return self._text(part.get("text"))
        except (KeyError, TypeError, AttributeError) as exc:
            raise ProviderError("Model provider returned no move") from exc
        raise ProviderError("Model provider returned no move")


class AnthropicAdapter(HttpModel):
    async def choose_move(self, position: ModelPosition) -> str:
        data = await self._post(
            "https://api.anthropic.com/v1/messages",
            {"Authorization": f"Bearer {self._api_key}", "anthropic-version": "2023-06-01"},
            {"model": self._model_id, "max_tokens": 64, "messages": [{"role": "user", "content": _prompt(position)}]},
        )
        try:
            if data.get("stop_reason") not in (None, "end_turn", "stop_sequence"):
                raise ProviderError("Model provider returned no move")
            for part in data["content"]:
                if part.get("type") == "text":
                    return self._text(part.get("text"))
        except (KeyError, TypeError, AttributeError) as exc:
            raise ProviderError("Model provider returned no move") from exc
        raise ProviderError("Model provider returned no move")


class GeminiAdapter(HttpModel):
    async def choose_move(self, position: ModelPosition) -> str:
        data = await self._post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self._model_id}:generateContent",
            {"x-goog-api-key": self._api_key},
            {"contents": [{"parts": [{"text": _prompt(position)}]}]},
        )
        try:
            candidate = data["candidates"][0]
            if candidate.get("finishReason") not in (None, "STOP"):
                raise ProviderError("Model provider returned no move")
            return self._text(candidate["content"]["parts"][0]["text"])
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ProviderError("Model provider returned no move") from exc


class OpenRouterAdapter(HttpModel):
    async def choose_move(self, position: ModelPosition) -> str:
        data = await self._post(
            "https://openrouter.ai/api/v1/chat/completions",
            {"Authorization": f"Bearer {self._api_key}"},
            {"model": self._model_id, "messages": [{"role": "user", "content": _prompt(position)}], "max_tokens": 64},
        )
        try:
            choice = data["choices"][0]
            if choice.get("finish_reason") not in (None, "stop"):
                raise ProviderError("Model provider returned no move")
            return self._text(choice["message"]["content"])
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ProviderError("Model provider returned no move") from exc


ADAPTERS = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
    "openrouter": OpenRouterAdapter,
}


def configured_providers() -> dict[str, ProviderBinding]:
    configured = {}
    for name, adapter_type in ADAPTERS.items():
        prefix = f"CHESS_{name.upper()}"
        api_key = os.environ.get(f"{prefix}_API_KEY")
        model_id = os.environ.get(f"{prefix}_MODEL")
        if api_key and model_id:
            configured[name] = ProviderBinding(model_id, adapter_type(api_key, model_id))
    return configured
