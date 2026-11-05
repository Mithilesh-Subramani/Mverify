"""Ollama-compatible model adapter with environment-based defaults."""
from __future__ import annotations

import json
import os
import urllib.request


class OllamaClient:
    """Small Ollama API client.

    Model and URL are configurable. The client does not select or download a model.
    """

    def __init__(self, base_url=None, model=None, timeout=120):
        self.base_url = (base_url or os.environ.get(
            "MCORE_OLLAMA_URL", "http://localhost:11434"
        )).rstrip("/")
        self.model = model or os.environ.get("MCORE_MODEL", "qwen2.5-coder:7b")
        self.timeout = int(timeout)

    def list_models(self):
        request = urllib.request.Request(self.base_url + "/api/tags")
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def generate_json(self, prompt: str) -> dict:
        if not self.model:
            raise ValueError("No Ollama model configured. Set MCORE_MODEL or pass model.")
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + "/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data.get("response", "{}")
        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("Ollama returned invalid JSON for a JSON-mode request.") from exc
        if not isinstance(result, dict):
            raise ValueError("Ollama JSON response must be an object.")
        return result
