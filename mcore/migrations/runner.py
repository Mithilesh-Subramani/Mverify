from __future__ import annotations

import datetime
import json
import os
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1


def _backup(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target=backup_dir/(db_path.stem+".pre-v0.16."+stamp+db_path.suffix)
    with sqlite3.connect(db_path) as source, sqlite3.connect(target) as dest:
        source.backup(dest)
    try: os.chmod(target,0o600)
    except OSError: pass
    return target


def run_migrations(data_dir: str | Path) -> dict:
    root=Path(data_dir).expanduser().resolve(); root.mkdir(parents=True,exist_ok=True)
    state_path=root/"schema_version.json"
    old=json.loads(state_path.read_text()) if state_path.is_file() else {"schema_version":0}
    if int(old.get("schema_version",0)) >= SCHEMA_VERSION:
        return {"status":"current","schema_version":SCHEMA_VERSION,"backups":[]}
    existing=[root/name for name in ("knowledge.sqlite3","training.sqlite3","learning.sqlite3") if (root/name).is_file()]
    backups=[str(_backup(p,root/"backups")) for p in existing]
    details=[]
    for name in ("knowledge.sqlite3","training.sqlite3","learning.sqlite3"):
        path=root/name
        if not path.is_file(): continue
        with sqlite3.connect(path) as db:
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if name=="knowledge.sqlite3" and "chunks" in tables:
                cols={r[1] for r in db.execute("PRAGMA table_info(chunks)")}
                if "project_id" not in cols: db.execute("ALTER TABLE chunks ADD COLUMN project_id TEXT NOT NULL DEFAULT '__legacy__'")
                if "embedding" not in cols: db.execute("ALTER TABLE chunks ADD COLUMN embedding TEXT")
                for column,decl in (("module","TEXT"),("symbol","TEXT"),("line_start","INTEGER"),("line_end","INTEGER"),("source_sha256","TEXT")):
                    if column not in cols: db.execute(f"ALTER TABLE chunks ADD COLUMN {column} {decl}")
                db.execute("CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_chunks_project_module ON chunks(project_id,module,symbol)")
                details.append({"database":name,"migration":"project_isolation_and_embedding_columns"})
            elif name=="training.sqlite3" and "examples" in tables:
                cols={r[1] for r in db.execute("PRAGMA table_info(examples)")}
                if "reviewer" not in cols: db.execute("ALTER TABLE examples ADD COLUMN reviewer TEXT")
                if "content_hash" not in cols: db.execute("ALTER TABLE examples ADD COLUMN content_hash TEXT")
                db.execute("CREATE INDEX IF NOT EXISTS idx_training_status ON examples(status,consent)")
                details.append({"database":name,"migration":"review_provenance_and_dataset_deduplication"})
            elif name=="learning.sqlite3":
                details.append({"database":name,"migration":"preserved_existing_experience_schema"})
    state={"schema_version":SCHEMA_VERSION,"application_version":"0.16.0",
           "migrated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "changes":details,"backups":backups}
    temp=state_path.with_suffix(".tmp")
    temp.write_text(json.dumps(state,indent=2),encoding="utf-8")
    temp.replace(state_path)
    return {"status":"migrated","schema_version":SCHEMA_VERSION,"changes":details,"backups":backups}


if __name__=="__main__":
    import os
    location=Path(os.environ.get("MCORE_HOME",Path.home()/".mcore"))
    print(json.dumps(run_migrations(location),indent=2))
