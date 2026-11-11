"""Environment-driven, loopback-only defaults shared by Mcore services."""
from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class McoreConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    ollama_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5-coder:14b"
    embedding_model: str = "nomic-embed-text:latest"
    request_timeout: int = 240
    embedding_timeout: int = 30
    max_request_bytes: int = 4 * 1024 * 1024
    max_context_chars: int = 18000


def load_config(env: dict[str, str] | None = None) -> McoreConfig:
    e = os.environ if env is None else env
    host = e.get("MCORE_HOST", "127.0.0.1")
    try:
        is_loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = host.lower() == "localhost"
    if not is_loopback:
        raise ValueError("Mcore binds to loopback only. Do not expose the local engineering API to a network.")
    return McoreConfig(host=host, port=int(e.get("MCORE_PORT", "8765")),
        ollama_url=e.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/"),
        model=e.get("MCORE_MODEL", e.get("OLLAMA_MODEL", "qwen2.5-coder:14b")),
        embedding_model=e.get("MCORE_EMBEDDING_MODEL", "nomic-embed-text:latest"),
        request_timeout=max(1, int(e.get("MCORE_REQUEST_TIMEOUT", "240"))),
        embedding_timeout=max(1, int(e.get("MCORE_EMBEDDING_TIMEOUT", "30"))),
        max_request_bytes=max(1024, int(e.get("MCORE_MAX_REQUEST_BYTES", str(4*1024*1024)))),
        max_context_chars=max(2000, int(e.get("MCORE_CONTEXT_MAX_CHARS", "18000"))))
