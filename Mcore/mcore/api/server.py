"""Mcore local API: retrieval, evidence-first reasoning and training review."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
from pathlib import Path

from mcore.core.ollama import OllamaClient
from mcore.core.knowledge import KnowledgeStore
from mcore.training.dataset import TrainingDataset
from mcore.learning.engine import LearningEngine
from mcore.reasoning.engineering_rules import list_rules
from mcore.reasoning.engineering_reasoner import EngineeringReasoner
from mcore.reasoning.evaluation import evaluate_claim_ledger

DATA = Path(os.environ.get("MCORE_HOME", os.path.expanduser("~/.mcore"))).expanduser()
KNOWLEDGE = KnowledgeStore(DATA / "knowledge.sqlite3")
TRAINING = TrainingDataset(DATA / "training.sqlite3")
LEARNING = LearningEngine(DATA / "learning.sqlite3")


def _json(handler, status, obj):
    body = json.dumps(obj, ensure_ascii=False).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("Mcore:", fmt % args, flush=True)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 20 * 1024 * 1024:
            raise ValueError("Request body exceeds 20 MB limit")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            return _json(self, 200, {"service": "Mcore", "status": "ready",
                                     "version": os.environ.get("MCORE_VERSION", "0.4.0"), "data_dir": str(DATA),
                                     "model": os.environ.get("MCORE_MODEL", "qwen2.5-coder:7b"),
                                     "ollama_url": os.environ.get("MCORE_OLLAMA_URL", "http://localhost:11434")})
        if parsed.path == "/rules":
            domain = parse_qs(parsed.query).get("domain", [None])[0]
            return _json(self, 200, {"rules": list_rules(domain)})
        if parsed.path == "/models":
            try:
                return _json(self, 200, OllamaClient().list_models())
            except Exception as exc:
                return _json(self, 503, {"error": str(exc)})
        if parsed.path == "/training/examples":
            status = parse_qs(parsed.query).get("status", [None])[0]
            return _json(self, 200, {"examples": TRAINING.list(status=status)})
        if parsed.path == "/learning/status":
            return _json(self, 200, LEARNING.status())
        if parsed.path == "/learning/experiences":
            return _json(self, 200, {"experiences": LEARNING.list_experiences()})
        if parsed.path == "/learning/lessons":
            status = parse_qs(parsed.query).get("status", [None])[0]
            return _json(self, 200, {"lessons": LEARNING.list_lessons(status=status)})
        return _json(self, 404, {"error": "not_found"})

    def do_POST(self):
        try:
            data = self._body()
        except Exception as exc:
            return _json(self, 400, {"error": str(exc)})

        if self.path == "/reason/engineering":
            task = (data.get("task") or "").strip()
            if not task:
                return _json(self, 400, {"error": "task_required"})
            retrieved = KNOWLEDGE.search(task, limit=data.get("knowledge_limit", 8))
            try:
                client = OllamaClient(
                    base_url=data.get("ollama_url") or os.environ.get("MCORE_OLLAMA_URL"),
                    model=data.get("model") or os.environ.get("MCORE_MODEL"),
                    timeout=int(data.get("timeout", 240)),
                )
                response = EngineeringReasoner(client).reason(
                    task, data.get("rtl_evidence"), data.get("spec_evidence"),
                    data.get("tool_evidence"), retrieved,
                )
                response["retrieved_sources"] = [
                    {"source": item["source"], "topic": item["topic"], "score": item["score"]}
                    for item in retrieved
                ]
                return _json(self, 200, response)
            except Exception as exc:
                return _json(self, 503, {"error": str(exc)})

        if self.path == "/reason/evaluate":
            return _json(self, 200, evaluate_claim_ledger(
                data.get("result", {}), data.get("evidence_ids", [])
            ))

        if self.path == "/reason":
            prompt = (data.get("prompt") or "").strip()
            if not prompt:
                return _json(self, 400, {"error": "prompt_required"})
            retrieved = KNOWLEDGE.search(prompt, limit=data.get("knowledge_limit", 6))
            context = "\\n\\n".join(
                "[Source: %s | Topic: %s]\\n%s" %
                (item["source"], item["topic"], item["content"])
                for item in retrieved
            )
            grounded = (
                "Use the evidence below. Separate confirmed facts from inference. "
                "If evidence is missing, state what is unknown. Do not invent protocol requirements."
                "\\n\\nRETRIEVED KNOWLEDGE:\\n" + context + "\\n\\nUSER TASK:\\n" + prompt
            ) if context else prompt
            try:
                model = data.get("model") or os.environ.get("MCORE_MODEL")
                result = OllamaClient(
                    base_url=data.get("ollama_url", "http://localhost:11434"),
                    model=model, timeout=int(data.get("timeout", 180)),
                ).generate_json(grounded)
                return _json(self, 200, {
                    "result": result,
                    "retrieved_sources": [{"source": x["source"], "topic": x["topic"], "score": x["score"]} for x in retrieved],
                    "teacher_model": model,
                    "training_performed": False,
                })
            except Exception as exc:
                return _json(self, 503, {"error": str(exc)})

        if self.path == "/knowledge/ingest":
            result = KNOWLEDGE.ingest_text(
                data.get("source", "unknown"), data.get("text", ""),
                data.get("topic", "unclassified"),
            )
            return _json(self, 201, result)
        if self.path == "/knowledge/search":
            return _json(self, 200, {"results": KNOWLEDGE.search(data.get("query", ""), data.get("limit", 8))})
        if self.path == "/learning/experience":
            try:
                result = LEARNING.record_experience(
                    data.get("task_type"), data.get("task", {}),
                    data.get("prediction", {}), data.get("outcome", {}),
                    data.get("evidence", {}), data.get("project_id"), data.get("notes", ""))
                return _json(self, 201, result)
            except Exception as exc:
                return _json(self, 400, {"error": str(exc)})

        if self.path == "/learning/lesson/propose":
            try:
                result = LEARNING.propose_lesson(data.get("experience_id", ""),
                    data.get("lesson", ""), data.get("domain", "general"), data.get("evidence", {}))
                return _json(self, 201, result)
            except Exception as exc:
                return _json(self, 400, {"error": str(exc)})

        if self.path == "/learning/lesson/review":
            try:
                result = LEARNING.review_lesson(data.get("id", ""),
                    approve=bool(data.get("approve", False)), consent=bool(data.get("consent", False)),
                    reviewer=data.get("reviewer"))
                if result["status"] == "validated":
                    lesson = next((x for x in LEARNING.list_lessons() if x["id"] == data.get("id")), None)
                    if lesson:
                        KNOWLEDGE.ingest_text("validated_lesson:" + lesson["id"], lesson["lesson"], lesson["domain"])
                return _json(self, 200, result)
            except Exception as exc:
                return _json(self, 400, {"error": str(exc)})

        if self.path == "/learning/evaluation":
            try:
                return _json(self, 201, LEARNING.record_evaluation(data.get("suite", ""),
                    data.get("metrics", {}), data.get("model"), data.get("baseline"), data.get("notes", "")))
            except Exception as exc:
                return _json(self, 400, {"error": str(exc)})

        if self.path == "/training/submit":
            result = TRAINING.submit(
                data.get("task_type", "unknown"), data.get("input", {}),
                data.get("target", {}), data.get("evidence", {}),
                data.get("source_project"), False, data.get("notes", ""),
            )
            return _json(self, 201, result)
        if self.path == "/training/approve":
            try:
                return _json(self, 200, TRAINING.approve(data.get("id", ""), consent=bool(data.get("consent", False))))
            except Exception as exc:
                return _json(self, 400, {"error": str(exc)})
        if self.path == "/training/reject":
            try:
                return _json(self, 200, TRAINING.reject(data.get("id", ""), data.get("reason", "")))
            except Exception as exc:
                return _json(self, 400, {"error": str(exc)})
        if self.path == "/training/export":
            path = data.get("path")
            if not path:
                return _json(self, 400, {"error": "path_required"})
            try:
                count = TRAINING.export_jsonl(path)
                return _json(self, 200, {"status": "exported", "count": count, "path": str(Path(path).expanduser())})
            except Exception as exc:
                return _json(self, 400, {"error": str(exc)})
        return _json(self, 404, {"error": "not_found"})


def main():
    host = os.environ.get("MCORE_HOST", "127.0.0.1")
    port = int(os.environ.get("MCORE_PORT", "8765"))
    server = ThreadingHTTPServer((host, port), Handler)
    print("Mcore API listening on http://%s:%s" % server.server_address, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
