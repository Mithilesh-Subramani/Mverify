"""Mcore local API: retrieval, evidence-first reasoning and training review."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
from pathlib import Path
import uuid

from mcore.config import load_config
from mcore.core.ollama import OllamaClient
from mcore.core.knowledge import KnowledgeStore
from mcore.training.dataset import TrainingDataset
from mcore.learning.engine import LearningEngine
from mcore.reasoning.engineering_rules import list_rules
from mcore.reasoning.engineering_reasoner import EngineeringReasoner
from mcore.reasoning.evaluation import evaluate_claim_ledger
from mcore.reasoning.evaluation import validate_engineering_claims
from mcore.reasoning.context_builder import build_engineering_context
from mcore.migrations.runner import run_migrations
from mcore.evaluation.retrieval import evaluate_retrieval

CONFIG = load_config()
API_VERSION = "1.0"
DATA = Path(os.environ.get("MCORE_HOME", os.path.expanduser("~/.mcore"))).expanduser()
_EMBED_CLIENT = None
KNOWLEDGE = None
TRAINING = None
LEARNING = None


def initialize_services(data_dir=None, force=False):
    """Run backup-first migrations and initialize independent local stores."""
    global DATA, _EMBED_CLIENT, KNOWLEDGE, TRAINING, LEARNING
    if KNOWLEDGE is not None and not force: return {"status":"already_initialized"}
    DATA = Path(data_dir or os.environ.get("MCORE_HOME", Path.home()/".mcore")).expanduser().resolve()
    migration = run_migrations(DATA)
    _EMBED_CLIENT = OllamaClient(base_url=CONFIG.ollama_url, model=CONFIG.model,
        embedding_model=CONFIG.embedding_model, timeout=CONFIG.embedding_timeout)
    KNOWLEDGE = KnowledgeStore(DATA / "knowledge.sqlite3", embedder=_EMBED_CLIENT.embed)
    TRAINING = TrainingDataset(DATA / "training.sqlite3")
    LEARNING = LearningEngine(DATA / "learning.sqlite3")
    return migration


def _json(handler, status, obj):
    obj = dict(obj) if isinstance(obj, dict) else {"data": obj}
    obj.setdefault("request_id", getattr(handler, "request_id", None))
    body = json.dumps(obj, ensure_ascii=False).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("Mcore:", getattr(self, "request_id", "no-request-id"), fmt % args, flush=True)

    def _body(self):
        try: length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError): raise ValueError("Invalid Content-Length")
        if length < 0 or length > CONFIG.max_request_bytes:
            raise ValueError("Request body exceeds configured size limit")
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict): raise ValueError("Request JSON must be an object")
        return value

    def do_GET(self):
        self.request_id = self.headers.get("X-Request-ID") or uuid.uuid4().hex
        parsed = urlparse(self.path)
        route = parsed.path.removeprefix("/api/v1") or "/"
        if route == "/health":
            return _json(self, 200, {"service": "Mcore", "status": "ready",
                                     "version": "0.16.0", "api_version": API_VERSION,
                                     "data_dir": str(DATA), "ollama_url": CONFIG.ollama_url,
                                     "configured_model": CONFIG.model, "embedding_model": CONFIG.embedding_model,
                                     "bind_host": CONFIG.host})
        if route == "/rules":
            domain = parse_qs(parsed.query).get("domain", [None])[0]
            return _json(self, 200, {"rules": list_rules(domain)})
        if route == "/models":
            try:
                return _json(self, 200, OllamaClient().model_status())
            except Exception as exc:
                return _json(self, 503, {"error": str(exc), "configured_model": CONFIG.model, "fallback_selected": False})
        if route == "/training/examples":
            status = parse_qs(parsed.query).get("status", [None])[0]
            return _json(self, 200, {"examples": TRAINING.list(status=status)})
        if route == "/learning/status":
            return _json(self, 200, LEARNING.status())
        if route == "/learning/experiences":
            project_id=parse_qs(parsed.query).get("project_id",[None])[0]
            status=parse_qs(parsed.query).get("status",[None])[0]
            return _json(self, 200, {"experiences": LEARNING.list_experiences(project_id=project_id,status=status)})
        if route == "/learning/lessons":
            status = parse_qs(parsed.query).get("status", [None])[0]
            return _json(self, 200, {"lessons": LEARNING.list_lessons(status=status)})
        return _json(self, 404, {"error": "not_found"})

    def do_POST(self):
        self.request_id = self.headers.get("X-Request-ID") or uuid.uuid4().hex
        try:
            data = self._body()
        except Exception as exc:
            return _json(self, 400, {"error": str(exc)})

        route = urlparse(self.path).path.removeprefix("/api/v1") or "/"
        if route in ("/reason", "/reason/engineering", "/engineering/reason"):
            task_value = data.get("task", data.get("prompt", ""))
            task = task_value if isinstance(task_value, str) else ""
            task = task.strip()
            if not task:
                return _json(self, 400, {"error": "task_required"})
            if len(task) > 8000:
                return _json(self, 413, {"error": "task_too_large"})
            project_id = str(data.get("project_id") or "").strip()
            if not project_id:
                return _json(self, 400, {"error": "project_id_required", "retrieval_scope": "project_only"})
            rtl_evidence = data.get("rtl_evidence") or {}
            # Expand short generic questions (for example "what are the risks?")
            # with identifiers from the active DUT so retrieval remains project-aware.
            feature_data = rtl_evidence.get("feature_analysis", {})
            feature_items = feature_data.get("features", []) if isinstance(feature_data, dict) else []
            feature_names = [x.get("feature", "") for x in feature_items if isinstance(x, dict)]
            ports = rtl_evidence.get("ports", [])
            port_names = [x.get("name", "") for x in ports if isinstance(x, dict)]
            retrieval_query = " ".join([task, str(rtl_evidence.get("dut_top", "")),
                " ".join(rtl_evidence.get("all_module_names", [])),
                " ".join(feature_names), " ".join(port_names)])
            try: knowledge_limit = max(1, min(int(data.get("knowledge_limit", 8)), 16))
            except (TypeError, ValueError): knowledge_limit = 8
            retrieved = KNOWLEDGE.search(retrieval_query, limit=knowledge_limit, project_id=project_id)
            try:
                client = OllamaClient(
                    base_url=data.get("ollama_url") or CONFIG.ollama_url,
                    model=data.get("model") or CONFIG.model,
                    timeout=min(max(1, int(data.get("timeout", CONFIG.request_timeout))), CONFIG.request_timeout),
                    embedding_model=CONFIG.embedding_model,
                )
                context = build_engineering_context(project_id=project_id, task=task,
                    project_context=data.get("project_context"), rtl_evidence=rtl_evidence,
                    spec_evidence=data.get("spec_evidence"), tool_evidence=data.get("tool_evidence"),
                    retrieved_knowledge=retrieved,
                    validated_experiences=LEARNING.list_validated_experiences(project_id, limit=6),
                    max_chars=CONFIG.max_context_chars)
                response = EngineeringReasoner(client).reason(
                    task, project_context=context.get("project_context"),
                    evidence_context=context,
                )
                response["retrieved_sources"] = [
                    {"source": item["source"], "topic": item["topic"], "score": item["score"],
                     "lexical_score": item.get("lexical_score"), "semantic_score": item.get("semantic_score"),
                     "retrieval_method": "hybrid" if item.get("semantic_score") else "lexical",
                     "project_id": item.get("project_id")}
                    for item in retrieved
                ]
                response["project_id"] = project_id
                response["retrieval_scope"] = "project_only"
                response["retrieval_query"] = retrieval_query
                response["evidence_context"] = {"schema_version": context["schema_version"],
                    "evidence_ids": context["evidence_ids"], "budget": context["budget"],
                    "retrieval": context["retrieval"]}
                return _json(self, 200, response)
            except Exception as exc:
                return _json(self, 503, {"error": str(exc), "model": data.get("model") or CONFIG.model,
                                         "fallback_selected": False, "validation_status": "ENGINEERING_REVIEW_REQUIRED"})

        if route in ("/reason/evaluate", "/engineering/evaluate"):
            project_id = str(data.get("project_id") or "").strip()
            if not project_id: return _json(self, 400, {"error": "project_id_required"})
            evidence = data.get("evidence", [])
            if not isinstance(evidence, list): return _json(self, 400, {"error": "evidence_must_be_array"})
            return _json(self, 200, validate_engineering_claims(data.get("result", {}), evidence, project_id))

        if route == "/evaluation/retrieval":
            cases=data.get("cases")
            if not isinstance(cases,list) or len(cases)>100: return _json(self,400,{"error":"cases_must_be_array_max_100"})
            try: return _json(self,200,evaluate_retrieval(KNOWLEDGE,cases,data.get("k",5)))
            except (TypeError,ValueError) as exc: return _json(self,400,{"error":str(exc)})

        if route == "/knowledge/ingest":
            if not isinstance(data.get("text", ""), str): return _json(self,400,{"error":"text_must_be_string"})
            project_id = str(data.get("project_id") or "__legacy__")
            try:
                line_start=int(data["line_start"]) if data.get("line_start") is not None else None
                line_end=int(data["line_end"]) if data.get("line_end") is not None else None
            except (TypeError,ValueError): return _json(self,400,{"error":"line_range_must_be_integer"})
            result = KNOWLEDGE.ingest_text(
                data.get("source", "unknown"), data.get("text", ""),
                data.get("topic", "unclassified"), project_id,
                module=data.get("module"),symbol=data.get("symbol"),line_start=line_start,
                line_end=line_end,source_sha256=data.get("source_sha256"),
            )
            return _json(self, 201, result)
        if route == "/knowledge/search":
            project_id = str(data.get("project_id") or "__legacy__")
            query=data.get("query","")
            if not isinstance(query,str): return _json(self,400,{"error":"query_must_be_string"})
            return _json(self, 200, {"results": KNOWLEDGE.search(
                query, data.get("limit", 8), project_id,module=data.get("module"),symbol=data.get("symbol")),
                "project_id": project_id, "retrieval_scope": "project_only",
                "embedding_status": KNOWLEDGE.embedding_status()})
        if route == "/knowledge/project/clear":
            project_id=data.get("project_id")
            if not project_id: return _json(self,400,{"error":"project_id_required"})
            return _json(self,200,KNOWLEDGE.clear_project(project_id))
        if route == "/knowledge/project/status":
            project_id=data.get("project_id")
            if not project_id: return _json(self,400,{"error":"project_id_required"})
            return _json(self,200,KNOWLEDGE.project_status(project_id))
        if route == "/learning/experience":
            try:
                result = LEARNING.record_experience(
                    data.get("task_type"), data.get("task", {}),
                    data.get("prediction", {}), data.get("outcome", {}),
                    data.get("evidence", {}), data.get("project_id"), data.get("notes", ""))
                return _json(self, 201, result)
            except Exception as exc:
                return _json(self, 400, {"error": str(exc)})

        if route == "/learning/experience/review":
            try:
                result=LEARNING.review_experience(data.get("id",""),data.get("reviewer"),data.get("validation",{}))
                return _json(self,200,result)
            except Exception as exc:
                return _json(self,400,{"error":str(exc)})

        if route == "/learning/lesson/propose":
            try:
                result = LEARNING.propose_lesson(data.get("experience_id", ""),
                    data.get("lesson", ""), data.get("domain", "general"), data.get("evidence", {}))
                return _json(self, 201, result)
            except Exception as exc:
                return _json(self, 400, {"error": str(exc)})

        if route == "/learning/lesson/review":
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

        if route == "/learning/evaluation":
            try:
                return _json(self, 201, LEARNING.record_evaluation(data.get("suite", ""),
                    data.get("metrics", {}), data.get("model"), data.get("baseline"), data.get("notes", "")))
            except Exception as exc:
                return _json(self, 400, {"error": str(exc)})

        if route == "/training/submit":
            result = TRAINING.submit(
                data.get("task_type", "unknown"), data.get("input", {}),
                data.get("target", {}), data.get("evidence", {}),
                data.get("source_project"), False, data.get("notes", ""),
            )
            return _json(self, 201, result)
        if route == "/training/approve":
            try:
                return _json(self, 200, TRAINING.approve(data.get("id", ""), consent=bool(data.get("consent", False)), reviewer=data.get("reviewer")))
            except Exception as exc:
                return _json(self, 400, {"error": str(exc)})
        if route == "/training/reject":
            try:
                return _json(self, 200, TRAINING.reject(data.get("id", ""), data.get("reason", "")))
            except Exception as exc:
                return _json(self, 400, {"error": str(exc)})
        if route == "/training/export":
            filename = data.get("filename", "approved_training.jsonl")
            if not isinstance(filename, str) or Path(filename).name != filename or filename in (".", ".."):
                return _json(self, 400, {"error": "filename_must_be_a_plain_filename"})
            try:
                export_dir = (DATA / "training_exports").resolve()
                export_dir.mkdir(parents=True, exist_ok=True)
                path = (export_dir / filename).resolve()
                if export_dir not in path.parents:
                    return _json(self, 400, {"error": "export_path_outside_mcore_data_dir"})
                count = TRAINING.export_jsonl(path)
                return _json(self, 200, {"status": "exported", "count": count, "path": str(Path(path).expanduser())})
            except Exception as exc:
                return _json(self, 400, {"error": str(exc)})
        return _json(self, 404, {"error": "not_found"})


def main():
    migration=initialize_services()
    print("Mcore migrations:",json.dumps(migration,ensure_ascii=False),flush=True)
    server = ThreadingHTTPServer((CONFIG.host, CONFIG.port), Handler)
    print("Mcore API v%s listening on http://%s:%s" % ((API_VERSION,)+server.server_address), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
