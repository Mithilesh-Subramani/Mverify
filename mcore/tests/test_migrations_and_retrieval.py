import sqlite3

from mcore.migrations.runner import run_migrations
from mcore.core.knowledge import KnowledgeStore
from mcore.evaluation.retrieval import evaluate_retrieval


def test_backup_first_migration_adds_project_and_provenance_columns(tmp_path):
    knowledge=tmp_path/"knowledge.sqlite3"
    with sqlite3.connect(knowledge) as db:
        db.execute("CREATE TABLE chunks(id INTEGER PRIMARY KEY,source TEXT,sha256 TEXT UNIQUE,topic TEXT,content TEXT,created_at TEXT)")
        db.execute("INSERT INTO chunks(source,sha256,topic,content,created_at) VALUES('old.sv','x','rtl','module alu','now')")
    result=run_migrations(tmp_path)
    assert result["status"]=="migrated" and result["backups"]
    cols={row[1] for row in sqlite3.connect(knowledge).execute("PRAGMA table_info(chunks)")}
    assert {"project_id","embedding","module","symbol","source_sha256"} <= cols
    assert all(__import__("pathlib").Path(path).is_file() for path in result["backups"])


def test_retrieval_benchmark_reports_metrics_and_isolation(tmp_path):
    store=KnowledgeStore(tmp_path/"knowledge.sqlite3")
    store.ingest_text("rtl/alu.sv","module alu: result from add operation","rtl","project-a",module="alu",symbol="result")
    store.ingest_text("rtl/other.sv","unrelated arbiter request grant","rtl","project-b",module="arbiter")
    report=evaluate_retrieval(store,[{"id":"alu-result","project_id":"project-a","query":"alu result add",
        "expected":{"source":"rtl/alu.sv","module":"alu","symbol":"result"}}],k=3)
    assert report["recall_at_3"]==1.0 and report["mrr"]==1.0
    assert report["project_isolation_violations"]==0
