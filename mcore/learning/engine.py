"""Evidence-gated engineering experience and learning loop for Mcore.

This module stores outcomes and reviewed lessons. It never changes model weights.
"""
from __future__ import annotations
import datetime, hashlib, json, sqlite3, uuid
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS experiences (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, project_id TEXT, task_type TEXT NOT NULL,
 task_json TEXT NOT NULL, prediction_json TEXT NOT NULL, outcome_json TEXT NOT NULL,
 evidence_json TEXT NOT NULL, status TEXT NOT NULL, notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS lessons (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, experience_id TEXT NOT NULL,
 lesson TEXT NOT NULL, domain TEXT NOT NULL, evidence_json TEXT NOT NULL,
 status TEXT NOT NULL, consent INTEGER NOT NULL DEFAULT 0, reviewer TEXT,
 content_hash TEXT NOT NULL UNIQUE, FOREIGN KEY(experience_id) REFERENCES experiences(id)
);
CREATE TABLE IF NOT EXISTS evaluations (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, suite TEXT NOT NULL,
 model TEXT, metrics_json TEXT NOT NULL, baseline_json TEXT,
 decision TEXT NOT NULL, notes TEXT NOT NULL DEFAULT ''
);
'''

class LearningEngine:
    def __init__(self, path):
        self.path = str(Path(path).expanduser())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.executescript(SCHEMA)

    def record_experience(self, task_type, task, prediction, outcome, evidence,
                          project_id=None, notes=''):
        if not task_type or not isinstance(task, dict) or not isinstance(prediction, dict) or not isinstance(outcome, dict):
            raise ValueError('task_type and task, prediction, outcome objects are required')
        if not isinstance(evidence, (dict, list)) or not evidence:
            raise ValueError('Non-empty evidence is required to record an engineering experience')
        eid = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO experiences VALUES (?,?,?,?,?,?,?,?,?,?)',
                (eid, now, project_id, task_type, json.dumps(task), json.dumps(prediction),
                 json.dumps(outcome), json.dumps(evidence), 'recorded', notes))
        return {'id': eid, 'status': 'recorded', 'learning_applied': False}

    def propose_lesson(self, experience_id, lesson, domain, evidence):
        if not lesson or not domain or not evidence:
            raise ValueError('lesson, domain and supporting evidence are required')
        with sqlite3.connect(self.path) as db:
            row = db.execute('SELECT id FROM experiences WHERE id=?', (experience_id,)).fetchone()
        if not row:
            raise ValueError('Experience not found')
        digest = hashlib.sha256((experience_id+'\0'+domain+'\0'+lesson).encode()).hexdigest()
        lid = str(uuid.uuid4())
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT OR IGNORE INTO lessons VALUES (?,?,?,?,?,?,?,?,?,?)',
                (lid, datetime.datetime.now(datetime.timezone.utc).isoformat(), experience_id,
                 lesson, domain, json.dumps(evidence), 'pending_review', 0, None, digest))
            existing = db.execute('SELECT id,status FROM lessons WHERE content_hash=?', (digest,)).fetchone()
        return {'id': existing[0], 'status': existing[1], 'requires_human_review': True}

    def review_lesson(self, lesson_id, approve=False, consent=False, reviewer=None):
        if approve and not consent:
            raise ValueError('Explicit consent is required before a lesson can enter shared Mcore knowledge')
        status = 'validated' if approve else 'rejected'
        with sqlite3.connect(self.path) as db:
            cur = db.execute('UPDATE lessons SET status=?, consent=?, reviewer=? WHERE id=? AND status=?',
                (status, int(bool(approve and consent)), reviewer, lesson_id, 'pending_review'))
            if cur.rowcount != 1:
                raise ValueError('Pending lesson not found; it may already be reviewed')
        return {'id': lesson_id, 'status': status, 'knowledge_promotion_allowed': bool(approve and consent)}

    def list_experiences(self, limit=100):
        with sqlite3.connect(self.path) as db:
            rows = db.execute('SELECT id,created_at,project_id,task_type,status,notes FROM experiences ORDER BY created_at DESC LIMIT ?',
                              (max(1,min(int(limit),500)),)).fetchall()
        keys = ['id','created_at','project_id','task_type','status','notes']
        return [dict(zip(keys, row)) for row in rows]

    def list_lessons(self, status=None, limit=100):
        sql = 'SELECT id,created_at,experience_id,lesson,domain,status,consent,reviewer FROM lessons'
        args=[]
        if status:
            sql += ' WHERE status=?'; args.append(status)
        sql += ' ORDER BY created_at DESC LIMIT ?'; args.append(max(1,min(int(limit),500)))
        with sqlite3.connect(self.path) as db: rows=db.execute(sql,args).fetchall()
        keys=['id','created_at','experience_id','lesson','domain','status','consent','reviewer']
        return [dict(zip(keys,row)) for row in rows]

    def record_evaluation(self, suite, metrics, model=None, baseline=None, notes=''):
        if not suite or not isinstance(metrics, dict) or not metrics:
            raise ValueError('suite and non-empty metrics are required')
        # Promotion is blocked unless the caller supplies comparable baseline metrics.
        decision = 'improved' if isinstance(baseline, dict) and _strictly_better(metrics, baseline) else 'not_proven'
        eid=str(uuid.uuid4())
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO evaluations VALUES (?,?,?,?,?,?,?,?)',
                (eid,datetime.datetime.now(datetime.timezone.utc).isoformat(),suite,model,
                 json.dumps(metrics),json.dumps(baseline) if baseline is not None else None,decision,notes))
        return {'id':eid,'decision':decision,'metrics':metrics,'baseline':baseline,
                'warning':None if decision=='improved' else 'Improvement is not established against a comparable baseline.'}

    def status(self):
        with sqlite3.connect(self.path) as db:
            counts={table:db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
                    for table in ('experiences','lessons','evaluations')}
            pending=db.execute("SELECT COUNT(*) FROM lessons WHERE status='pending_review'").fetchone()[0]
            validated=db.execute("SELECT COUNT(*) FROM lessons WHERE status='validated' AND consent=1").fetchone()[0]
        return {'counts':counts,'pending_lessons':pending,'validated_consented_lessons':validated,
                'model_weights_updated':False,'autonomous_learning_enabled':False,
                'learning_mode':'evidence-gated experience memory; human-reviewed lesson promotion'}

def _strictly_better(current, baseline):
    """Conservative metric comparison. Lower error metrics and higher accuracy metrics are better."""
    common=set(current)&set(baseline)
    if not common: return False
    directions={'accuracy':1,'pass_rate':1,'coverage':1,'precision':1,'recall':1,
                'error_rate':-1,'failure_rate':-1,'false_positive_rate':-1,'latency_ms':-1}
    comparable=[]
    for key in common:
        if key not in directions: continue
        try: a=float(current[key]); b=float(baseline[key])
        except (TypeError,ValueError): continue
        comparable.append(a>b if directions[key]==1 else a<b)
    return bool(comparable) and all(comparable)
