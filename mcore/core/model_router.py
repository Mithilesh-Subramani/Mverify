"""Policy-gated hybrid LLM routing.

Local Ollama is always the default. Cloud inference requires all three:
(1) MCORE_CLOUD_ENABLED=true, (2) cloud endpoint credentials, and
(3) an explicit per-request cloud_approved=True with data_classification
'approved_for_cloud'. Sensitive RTL/specification context is local-only.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


class OpenAICompatibleJSONClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 180):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate_json(self, prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Return valid JSON only. Do not invent evidence."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.api_key},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Cloud model response must be a JSON object")
        return parsed


class HybridModelRouter:
    """Route approved non-sensitive prompts to cloud; keep all others local."""
    def __init__(self, local_client, cloud_client=None):
        self.local_client = local_client
        self.cloud_client = cloud_client or self._configured_cloud_client()
        self.last_route = "local"

    @staticmethod
    def _configured_cloud_client():
        if os.getenv("MCORE_CLOUD_ENABLED", "false").lower() not in {"1", "true", "yes"}:
            return None
        base_url = os.getenv("MCORE_CLOUD_BASE_URL", "").strip()
        api_key = os.getenv("MCORE_CLOUD_API_KEY", "").strip()
        model = os.getenv("MCORE_CLOUD_MODEL", "").strip()
        if not (base_url and api_key and model):
            return None
        return OpenAICompatibleJSONClient(base_url, api_key, model,
                                          int(os.getenv("MCORE_CLOUD_TIMEOUT", "180")))

    def generate_json_with_policy(self, prompt: str, *, cloud_approved: bool = False,
                                  data_classification: str = "sensitive") -> dict[str, Any]:
        approved = cloud_approved and data_classification == "approved_for_cloud"
        if approved and self.cloud_client is not None:
            self.last_route = "cloud_approved_request"
            return self.cloud_client.generate_json(prompt)
        self.last_route = "local_ollama"
        return self.local_client.generate_json(prompt)

    def generate_json(self, prompt: str) -> dict[str, Any]:
        return self.generate_json_with_policy(prompt)
