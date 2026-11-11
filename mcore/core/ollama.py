"""Ollama adapter for local Qwen generation and optional embedding models."""
from __future__ import annotations
import json, urllib.request

class OllamaClient:
    def __init__(self, base_url="http://localhost:11434", model="qwen2.5-coder:7b", timeout=120, embedding_model="nomic-embed-text"):
        self.base_url=base_url.rstrip("/"); self.model=model; self.timeout=timeout; self.embedding_model=embedding_model
    def _post(self,path,payload):
        req=urllib.request.Request(self.base_url+path,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=self.timeout) as r:return json.loads(r.read().decode())
    def list_models(self):
        req=urllib.request.Request(self.base_url+"/api/tags")
        with urllib.request.urlopen(req,timeout=self.timeout) as r:return json.loads(r.read().decode())
    def embed(self,text):
        # Current Ollama endpoint. Missing embedding model falls back to lexical retrieval.
        data=self._post("/api/embed",{"model":self.embedding_model,"input":text})
        vectors=data.get("embeddings") or []
        return vectors[0] if vectors else None
    def generate_json(self,prompt: str) -> dict:
        data=self._post("/api/generate",{"model":self.model,"prompt":prompt,"stream":False,"format":"json"})
        return json.loads(data.get("response","{}"))
