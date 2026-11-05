"""Hybrid retrieval: dense semantic search plus exact lexical/symbol matching."""
from __future__ import annotations

import re
from pathlib import Path

from qdrant_client import QdrantClient

from mverify.core.ai.ollama_client import OllamaClient
from mverify.core.rag.indexer import project_collection_name


def _terms(text: str) -> set[str]:
    return {term.lower() for term in re.findall(r"[A-Za-z_$][A-Za-z0-9_$]*", text)}


class ProjectRetriever:
    def __init__(self, qdrant_path: str | Path, ollama: OllamaClient | None = None):
        self.client = QdrantClient(path=str(Path(qdrant_path).expanduser()))
        self.ollama = ollama or OllamaClient()

    def search(self, project_id: str, query: str, limit: int = 8) -> list[dict]:
        collection = project_collection_name(project_id)
        if not self.client.collection_exists(collection):
            return []
        vector = self.ollama.embed([query])[0]
        dense = self.client.query_points(
            collection_name=collection, query=vector, limit=max(limit * 4, 20),
            with_payload=True,
        ).points
        query_terms = _terms(query)
        ranked = []
        for point in dense:
            payload = point.payload or {}
            content = str(payload.get("text", ""))
            content_terms = _terms(content)
            overlap = len(query_terms & content_terms) / max(len(query_terms), 1)
            dense_score = float(point.score or 0.0)
            # Dense relevance is primary. Lexical overlap boosts exact RTL identifiers.
            score = 0.75 * dense_score + 0.25 * overlap
            ranked.append({
                "score": score,
                "dense_score": dense_score,
                "lexical_score": overlap,
                "text": content,
                "source_file": payload.get("source_file", ""),
                "start_line": payload.get("start_line"),
                "end_line": payload.get("end_line"),
                "source_kind": payload.get("source_kind", ""),
            })
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:max(1, limit)]
