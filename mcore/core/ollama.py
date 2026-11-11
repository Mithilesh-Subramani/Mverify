"""Ollama adapter for local Qwen generation and optional embedding models."""
from __future__ import annotations
import json, os, urllib.request
from mcore.config import load_config

class OllamaClient:
    def __init__(self, base_url=None, model=None, timeout=None, embedding_model=None):
        config=load_config()
        self.base_url=(base_url or config.ollama_url).rstrip("/")
        self.model=model or config.model
        self.timeout=timeout or config.request_timeout
        self.embedding_model=embedding_model or config.embedding_model
    def _post(self,path,payload):
        req=urllib.request.Request(self.base_url+path,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=self.timeout) as r:return json.loads(r.read().decode())
    def list_models(self):
        req=urllib.request.Request(self.base_url+"/api/tags")
        with urllib.request.urlopen(req,timeout=self.timeout) as r:return json.loads(r.read().decode())
    def model_status(self):
        payload=self.list_models()
        models=payload.get("models",[]) if isinstance(payload,dict) else []
        names=[x.get("name") for x in models if isinstance(x,dict) and x.get("name")]
        return {"ollama_url":self.base_url,"configured_model":self.model,"model_available":self.model in names,
                "embedding_model":self.embedding_model,"embedding_model_available":self.embedding_model in names,
                "available_models":names,"fallback_selected":False}
    def embed(self,text):
        # Current Ollama endpoint. Missing embedding model falls back to lexical retrieval.
        data=self._post("/api/embed",{"model":self.embedding_model,"input":text})
        vectors=data.get("embeddings") or []
        return vectors[0] if vectors else None
    def generate_json(self,prompt: str) -> dict:
        status=self.model_status()
        if not status["model_available"]:
            raise RuntimeError("Configured Mcore model is not installed: %s. Available models: %s. Select an explicit fallback or install the configured model." % (self.model, ", ".join(status["available_models"]) or "none"))
        data=self._post("/api/generate",{"model":self.model,"prompt":prompt,"stream":False,"format":"json"})
        return json.loads(data.get("response","{}"))
