"""Consent-aware, deduplicated, reviewer-gated engineering examples."""
from __future__ import annotations

import datetime
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path


SCHEMA = """CREATE TABLE IF NOT EXISTS examples (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, source_project TEXT, task_type TEXT NOT NULL,
 input_json TEXT NOT NULL, target_json TEXT NOT NULL, evidence_json TEXT NOT NULL,
 status TEXT NOT NULL, consent INTEGER NOT NULL DEFAULT 0, notes TEXT,
 reviewer TEXT, content_hash TEXT)"""


def _hash(task_type, input_data, target_data, evidence):
    material=json.dumps([task_type,input_data,target_data,evidence],ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return hashlib.sha256(material.encode()).hexdigest()


class TrainingDataset:
    VERSION = "1.0"

    def __init__(self, path):
        self.path=str(Path(path).expanduser())
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute(SCHEMA)
            cols={row[1] for row in db.execute("PRAGMA table_info(examples)")}
            if "reviewer" not in cols: db.execute("ALTER TABLE examples ADD COLUMN reviewer TEXT")
            if "content_hash" not in cols: db.execute("ALTER TABLE examples ADD COLUMN content_hash TEXT")
            rows=db.execute("SELECT id,input_json,target_json,evidence_json FROM examples WHERE content_hash IS NULL").fetchall()
            for eid,a,b,e in rows:
                digest=hashlib.sha256((a+"\0"+b+"\0"+e+"\0"+eid).encode()).hexdigest()
                db.execute("UPDATE examples SET content_hash=? WHERE id=?",(digest,eid))
            db.execute("CREATE INDEX IF NOT EXISTS idx_training_status ON examples(status,consent)")

    def submit(self, task_type, input_data, target_data, evidence, source_project=None, consent=False, notes=""):
        if not task_type or not isinstance(input_data,dict) or not isinstance(target_data,dict) or not isinstance(evidence,(dict,list)) or not evidence:
            raise ValueError("task_type, input, target and non-empty evidence are required")
        digest=_hash(task_type,input_data,target_data,evidence)
        with sqlite3.connect(self.path) as db:
            existing=db.execute("SELECT id,status FROM examples WHERE content_hash=?",(digest,)).fetchone()
            if existing: return {"id":existing[0],"status":existing[1],"duplicate":True,"requires_human_review":True}
            eid=str(uuid.uuid4()); now=datetime.datetime.now(datetime.timezone.utc).isoformat()
            db.execute("INSERT INTO examples(id,created_at,source_project,task_type,input_json,target_json,evidence_json,status,consent,notes,content_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (eid,now,source_project,task_type,json.dumps(input_data,ensure_ascii=False),json.dumps(target_data,ensure_ascii=False),json.dumps(evidence,ensure_ascii=False),"pending_review",0,notes,digest))
        return {"id":eid,"status":"pending_review","consent_recorded":False,"duplicate":False}

    def list(self,status=None,limit=100):
        sql="SELECT id,created_at,source_project,task_type,status,consent,notes,reviewer FROM examples"; args=[]
        if status: sql+=" WHERE status=?"; args.append(status)
        sql+=" ORDER BY created_at DESC LIMIT ?"; args.append(max(1,min(int(limit),500)))
        with sqlite3.connect(self.path) as db: rows=db.execute(sql,args).fetchall()
        keys=["id","created_at","source_project","task_type","status","consent","notes","reviewer"]
        return [dict(zip(keys,row)) for row in rows]

    def approve(self,eid,consent=False,reviewer=None):
        if not consent: raise ValueError("Explicit data-use consent is required before training approval.")
        if not reviewer: raise ValueError("A reviewer identity is required for approval.")
        with sqlite3.connect(self.path) as db:
            row=db.execute("SELECT evidence_json,status FROM examples WHERE id=?",(eid,)).fetchone()
            if not row: raise ValueError("Training example not found.")
            evidence=json.loads(row[0])
            is_negative=bool(evidence.get("negative_example")) if isinstance(evidence,dict) else False
            evidence_status=evidence.get("validation_status") if isinstance(evidence,dict) else None
            if not is_negative and evidence_status!="EVIDENCE_VALIDATED":
                raise ValueError("Only evidence-validated examples or explicitly labelled negative examples may be approved.")
            if row[1]!="pending_review": raise ValueError("Only pending examples can be approved.")
            cur=db.execute("UPDATE examples SET status='training_ready',consent=1,reviewer=? WHERE id=? AND status='pending_review'",(str(reviewer),eid))
            if cur.rowcount!=1: raise ValueError("Training approval was not committed.")
        return {"id":eid,"status":"training_ready","reviewer":str(reviewer),"consent":True,"training_performed":False}

    def reject(self,eid,reason=""):
        with sqlite3.connect(self.path) as db:
            cur=db.execute("UPDATE examples SET status='rejected',notes=? WHERE id=? AND status='pending_review'",(reason,eid))
            if cur.rowcount!=1: raise ValueError("Pending training example not found.")
        return {"id":eid,"status":"rejected"}

    def get(self,eid):
        with sqlite3.connect(self.path) as db: row=db.execute("SELECT id,created_at,source_project,task_type,input_json,target_json,evidence_json,status,consent,notes,reviewer,content_hash FROM examples WHERE id=?",(eid,)).fetchone()
        if not row:return None
        keys=["id","created_at","source_project","task_type","input","target","evidence","status","consent","notes","reviewer","content_hash"]
        values=list(row); values[4:7]=[json.loads(x) for x in values[4:7]]
        return dict(zip(keys,values))

    def export_jsonl(self,path):
        with sqlite3.connect(self.path) as db:
            rows=db.execute("SELECT id,source_project,task_type,input_json,target_json,evidence_json,reviewer,content_hash FROM examples WHERE status='training_ready' AND consent=1 ORDER BY created_at").fetchall()
        out=Path(path).expanduser(); out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('w',encoding='utf-8') as f:
            for eid,project,task,a,b,e,reviewer,digest in rows:
                f.write(json.dumps({"id":eid,"source_project":project,"task_type":task,"input":json.loads(a),
                    "target":json.loads(b),"evidence":json.loads(e),"reviewer":reviewer,
                    "dataset_version":self.VERSION,"content_hash":digest},ensure_ascii=False)+"\n")
        return len(rows)
