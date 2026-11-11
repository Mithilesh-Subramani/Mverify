"""Ollama-compatible model adapter. Qwen is a teacher/advisor, not an automatic trainer."""
from __future__ import annotations
import json, urllib.request

class OllamaClient:
    def __init__(self, base_url="http://localhost:11434", model="qwen2.5-coder:7b", timeout=120):
        self.base_url=base_url.rstrip("/"); self.model=model; self.timeout=timeout
    def list_models(self):
        req=urllib.request.Request(self.base_url+"/api/tags")
        with urllib.request.urlopen(req,timeout=self.timeout) as r: return json.loads(r.read().decode())
    def generate_json(self, prompt: str) -> dict:
        payload=json.dumps({"model":self.model,"prompt":prompt,"stream":False,"format":"json"}).encode()
        req=urllib.request.Request(self.base_url+"/api/generate",data=payload,headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=self.timeout) as r: data=json.loads(r.read().decode())
        return json.loads(data.get("response","{}"))
