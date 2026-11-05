"""Project-scoped RTL/specification ingestion into a local Qdrant index."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

from qdrant_client import QdrantClient
from qdrant_client.http import models

from mverify.core.ai.ollama_client import OllamaClient

TEXT_SUFFIXES = {".v", ".vh", ".sv", ".svh", ".txt", ".md", ".rst", ".csv"}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist"}


def project_collection_name(project_id: str) -> str:
    """Return a stable, isolated collection name for one project/tenant."""
    token = re.sub(r"[^a-zA-Z0-9_]", "_", project_id).strip("_").lower() or "project"
    digest = hashlib.sha1(project_id.encode("utf-8")).hexdigest()[:10]
    return f"mv_{token[:32]}_{digest}"


def _iter_sources(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            if not any(part in SKIP_DIRS for part in path.parts):
                yield path


def _chunks(path: Path, root: Path, text: str, max_lines: int = 80) -> list[dict]:
    lines = text.splitlines()
    output = []
    for start in range(0, len(lines), max_lines):
        body = "\n".join(lines[start:start + max_lines]).strip()
        if not body:
            continue
        relative = str(path.relative_to(root))
        digest = hashlib.sha256(f"{relative}:{start + 1}:{body}".encode()).hexdigest()
        suffix = path.suffix.lower()
        kind = "rtl" if suffix in {".v", ".vh", ".sv", ".svh"} else "spec_or_document"
        output.append({
            "id": digest[:32],
            "text": body,
            "source_file": relative,
            "start_line": start + 1,
            "end_line": min(start + max_lines, len(lines)),
            "source_kind": kind,
            "content_hash": digest,
        })
    return output


class ProjectIndexer:
    def __init__(self, qdrant_path: str | Path, ollama: OllamaClient | None = None):
        self.client = QdrantClient(path=str(Path(qdrant_path).expanduser()))
        self.ollama = ollama or OllamaClient()

    def index_project(self, project_id: str, project_dir: str | Path) -> dict:
        root = Path(project_dir).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"Project directory does not exist: {root}")
        collection = project_collection_name(project_id)
        chunks = []
        for path in _iter_sources(root):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            chunks.extend(_chunks(path, root, text))
        if not chunks:
            return {"collection": collection, "files_indexed": 0, "chunks_indexed": 0}

        vectors = self.ollama.embed([item["text"] for item in chunks])
        vector_size = len(vectors[0])
        if not self.client.collection_exists(collection):
            self.client.create_collection(
                collection_name=collection,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
            )
        else:
            info = self.client.get_collection(collection)
            if info.config.params.vectors.size != vector_size:
                raise ValueError("Embedding dimension changed. Use a new collection or re-index with the same embedding model.")
        points = []
        for item, vector in zip(chunks, vectors):
            payload = {k: v for k, v in item.items() if k != "id"}
            points.append(models.PointStruct(id=item["id"], vector=vector, payload=payload))
        # Replace this project's collection contents atomically at the collection level.
        self.client.delete_collection(collection_name=collection)
        self.client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )
        self.client.upsert(collection_name=collection, points=points)
        return {
            "collection": collection,
            "files_indexed": len({x["source_file"] for x in chunks}),
            "chunks_indexed": len(chunks),
        }
