"""Small, dependency-free client for a local Ollama server."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class OllamaError(RuntimeError):
    """Raised when Ollama is unavailable or returns an invalid response."""


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        chat_model: str | None = None,
        embedding_model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.chat_model = chat_model or os.getenv("OLLAMA_CHAT_MODEL", "qwen3-coder:30b")
        self.embedding_model = embedding_model or os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        self.timeout = timeout or int(os.getenv("OLLAMA_TIMEOUT", "300"))

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{endpoint}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OllamaError(f"Ollama request failed at {endpoint}: {exc}") from exc
        if not isinstance(result, dict):
            raise OllamaError(f"Ollama returned an invalid response at {endpoint}.")
        return result

    def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.1,
             json_mode: bool = False) -> str:
        payload: dict[str, Any] = {
            "model": self.chat_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "16384"))},
        }
        if json_mode:
            payload["format"] = "json"
        result = self._post("/api/chat", payload)
        message = result.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise OllamaError("Ollama chat response did not contain message.content.")
        return content

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        result = self._post("/api/embed", {"model": self.embedding_model, "input": texts})
        embeddings = result.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise OllamaError("Ollama embedding response count does not match input count.")
        if any(not isinstance(vector, list) or not vector for vector in embeddings):
            raise OllamaError("Ollama returned an empty or invalid embedding.")
        return embeddings
