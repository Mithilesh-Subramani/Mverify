"""Consent-aware Mcore training data lifecycle."""
from __future__ import annotations
import sqlite3, json, uuid, datetime
from pathlib import Path
SCHEMA="""CREATE TABLE IF NOT EXISTS examples (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, source_project TEXT, task_type TEXT NOT NULL,
 input_json TEXT NOT NULL, target_json TEXT NOT NULL, evidence_json TEXT NOT NULL,
 status TEXT NOT NULL, consent INTEGER NOT NULL DEFAULT 0, notes TEXT)"""
class TrainingDataset:
 def __init__(self,path):
  self.path=str(Path(path).expanduser()); Path(self.path).parent.mkdir(parents=True,exist_ok=True)
  with sqlite3.connect(self.path) as c: c.execute(SCHEMA)
 def submit(self,task_type,input_data,target_data,evidence,source_project=None,consent=False,notes=""):
  eid=str(uuid.uuid4()); now=datetime.datetime.now(datetime.timezone.utc).isoformat()
  with sqlite3.connect(self.path) as c:
   c.execute("INSERT INTO examples VALUES (?,?,?,?,?,?,?,?,?,?)",(eid,now,source_project,task_type,json.dumps(input_data),json.dumps(target_data),json.dumps(evidence),"pending_review",int(bool(consent)),notes))
  return {"id":eid,"status":"pending_review","consent_recorded":bool(consent)}
 def list(self,status=None,limit=100):
  sql="SELECT id,created_at,source_project,task_type,status,consent,notes FROM examples"; args=[]
  if status: sql+=" WHERE status=?"; args.append(status)
  sql+=" ORDER BY created_at DESC LIMIT ?"; args.append(max(1,min(int(limit),500)))
  with sqlite3.connect(self.path) as c: rows=c.execute(sql,args).fetchall()
  keys=["id","created_at","source_project","task_type","status","consent","notes"]
  return [dict(zip(keys,r)) for r in rows]
 def approve(self,eid,consent=False):
  if not consent: raise ValueError("Explicit data-use consent is required before training approval.")
  with sqlite3.connect(self.path) as c:
   cur=c.execute("UPDATE examples SET status='training_ready', consent=1 WHERE id=?",(eid,))
   if cur.rowcount!=1: raise ValueError("Training example not found.")
  return {"id":eid,"status":"training_ready"}
 def reject(self,eid,reason=""):
  with sqlite3.connect(self.path) as c:
   cur=c.execute("UPDATE examples SET status='rejected', notes=? WHERE id=?",(reason,eid))
   if cur.rowcount!=1: raise ValueError("Training example not found.")
  return {"id":eid,"status":"rejected"}
 def get(self,eid):
  with sqlite3.connect(self.path) as c: row=c.execute("SELECT id,created_at,source_project,task_type,input_json,target_json,evidence_json,status,consent,notes FROM examples WHERE id=?",(eid,)).fetchone()
  if not row:return None
  keys=["id","created_at","source_project","task_type","input","target","evidence","status","consent","notes"]
  values=list(row); values[4:7]=[json.loads(x) for x in values[4:7]]
  return dict(zip(keys,values))
 def export_jsonl(self,path):
  with sqlite3.connect(self.path) as c: rows=c.execute("SELECT input_json,target_json,evidence_json FROM examples WHERE status='training_ready' AND consent=1").fetchall()
  out=Path(path).expanduser(); out.parent.mkdir(parents=True,exist_ok=True)
  with out.open('w',encoding='utf-8') as f:
   for a,b,e in rows: f.write(json.dumps({"input":json.loads(a),"target":json.loads(b),"evidence":json.loads(e)},ensure_ascii=False)+"\n")
  return len(rows)
