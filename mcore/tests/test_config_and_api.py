import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from mcore.config import load_config
from mcore.core.knowledge import KnowledgeStore
from mcore.core.ollama import OllamaClient
from mcore.api import server as api


def test_config_defaults_and_loopback_security():
    config=load_config({})
    assert config.host=="127.0.0.1"
    assert config.model=="qwen2.5-coder:14b"
    assert config.embedding_model=="nomic-embed-text:latest"
    with pytest.raises(ValueError): load_config({"MCORE_HOST":"0.0.0.0"})


def test_missing_model_is_never_silently_replaced(monkeypatch):
    client=OllamaClient(model="qwen2.5-coder:14b")
    monkeypatch.setattr(client,"list_models",lambda:{"models":[{"name":"qwen2.5-coder:7b"}]})
    with pytest.raises(RuntimeError,match="not installed"):
        client.generate_json("{}")


def test_versioned_local_api_and_project_scoping(tmp_path):
    api.initialize_services(tmp_path,force=True)
    api.KNOWLEDGE=KnowledgeStore(tmp_path/"isolated-test.sqlite3")
    http=ThreadingHTTPServer(("127.0.0.1",0),api.Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    base=f"http://127.0.0.1:{http.server_address[1]}/api/v1"
    def request(path,payload=None):
        body=None if payload is None else json.dumps(payload).encode()
        req=urllib.request.Request(base+path,data=body,headers={"Content-Type":"application/json"} if body else {})
        try:
            with urllib.request.urlopen(req,timeout=3) as response:return response.status,json.loads(response.read())
        except urllib.error.HTTPError as exc:return exc.code,json.loads(exc.read())
    try:
        code,health=request("/health")
        assert code==200 and health["api_version"]=="1.0" and health["request_id"]
        request("/knowledge/ingest",{"source":"a.sv","text":"alu add result","project_id":"project-a","module":"alu","symbol":"result"})
        request("/knowledge/ingest",{"source":"b.sv","text":"private pcie replay","project_id":"project-b","module":"pcie"})
        code,search=request("/knowledge/search",{"query":"alu result","project_id":"project-a"})
        assert code==200 and search["results"]
        assert all(x["project_id"]=="project-a" for x in search["results"])
        code,missing=request("/engineering/reason",{"task":"explain this"})
        assert code==400 and missing["error"]=="project_id_required"
        code,blocked=request("/training/export",{"filename":"../outside.jsonl"})
        assert code==400 and blocked["error"]=="filename_must_be_a_plain_filename"
        code,exported=request("/training/export",{"filename":"approved.jsonl"})
        assert code==200 and str(tmp_path / "training_exports" / "approved.jsonl")==exported["path"]
    finally:
        http.shutdown();http.server_close();thread.join(timeout=2)
