"""Project-scoped hybrid knowledge store with optional Ollama embeddings.

Lexical retrieval always works. Vector retrieval is enabled when an embedding
model is configured and the Ollama /api/embed endpoint is available.
"""
from __future__ import annotations
import sqlite3, hashlib, datetime, re, json, math
from pathlib import Path


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{1,}", (text or "").lower())


def _cosine(a, b):
    if not a or not b or len(a) != len(b): return 0.0
    dot=sum(x*y for x,y in zip(a,b)); na=math.sqrt(sum(x*x for x in a)); nb=math.sqrt(sum(y*y for y in b))
    return dot/(na*nb) if na and nb else 0.0


class KnowledgeStore:
    def __init__(self, path, embedder=None):
        self.path=str(Path(path).expanduser()); self.embedder=embedder
        self._embedding_disabled = False
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, source TEXT, sha256 TEXT UNIQUE, topic TEXT, content TEXT, created_at TEXT)")
            cols={r[1] for r in c.execute("PRAGMA table_info(chunks)")}
            if "project_id" not in cols: c.execute("ALTER TABLE chunks ADD COLUMN project_id TEXT NOT NULL DEFAULT '__legacy__'")
            if "embedding" not in cols: c.execute("ALTER TABLE chunks ADD COLUMN embedding TEXT")
            c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id)")

    @staticmethod
    def chunk_text(text, max_chars=1800, overlap=180):
        text=(text or "").strip()
        if not text: return []
        paras=re.split(r"\n\s*\n",text); chunks=[]; buf=""
        for para in paras:
            para=para.strip()
            if not para: continue
            if len(para)>max_chars:
                if buf: chunks.append(buf); buf=""
                start=0
                while start<len(para):
                    end=min(len(para),start+max_chars); chunks.append(para[start:end])
                    if end==len(para): break
                    start=end-overlap
            elif len(buf)+len(para)+2<=max_chars: buf=(buf+"\n\n"+para).strip()
            else: chunks.append(buf); buf=para
        if buf: chunks.append(buf)
        return chunks

    def _embedding(self, text):
        if not self.embedder or self._embedding_disabled: return None
        try:
            vector=self.embedder(text)
            if not vector: self._embedding_disabled=True
            return vector
        except Exception:
            # Avoid repeatedly waiting on a missing/unreachable embedding model.
            self._embedding_disabled=True
            return None

    def ingest_text(self, source, text, topic="unclassified", project_id="__legacy__"):
        chunks=self.chunk_text(text); now=datetime.datetime.now(datetime.timezone.utc).isoformat(); inserted=0
        with sqlite3.connect(self.path) as c:
            for content in chunks:
                digest=hashlib.sha256((str(project_id)+"\0"+str(source)+"\0"+str(topic)+"\0"+content).encode()).hexdigest()
                emb=self._embedding(content)
                cur=c.execute("INSERT OR IGNORE INTO chunks(source,sha256,topic,content,created_at,project_id,embedding) VALUES(?,?,?,?,?,?,?)",
                    (str(source),digest,str(topic),content,now,str(project_id),json.dumps(emb) if emb else None))
                inserted+=cur.rowcount
        return {"source_sha256":hashlib.sha256((text or "").encode()).hexdigest(),"chunks":len(chunks),"inserted":inserted,"project_id":project_id}

    def clear_project(self, project_id):
        with sqlite3.connect(self.path) as c: cur=c.execute("DELETE FROM chunks WHERE project_id=?",(str(project_id),))
        return {"project_id":project_id,"deleted_chunks":cur.rowcount}

    def project_status(self, project_id):
        with sqlite3.connect(self.path) as c:
            row=c.execute("SELECT COUNT(*),COUNT(DISTINCT source),MAX(created_at) FROM chunks WHERE project_id=?",(str(project_id),)).fetchone()
        return {"project_id":project_id,"chunks":row[0],"sources":row[1],"last_indexed_at":row[2]}

    def search(self, query, limit=8, project_id=None):
        terms=list(dict.fromkeys(_tokens(query)))
        if not terms: return []
        qemb=self._embedding(query)
        with sqlite3.connect(self.path) as c:
            if project_id is None:
                rows=c.execute("SELECT source,topic,content,created_at,project_id,embedding FROM chunks").fetchall()
            else:
                rows=c.execute("SELECT source,topic,content,created_at,project_id,embedding FROM chunks WHERE project_id=?",(str(project_id),)).fetchall()
        scored=[]
        for source,topic,content,created,pid,rawemb in rows:
            low=content.lower(); lex=sum(low.count(t) for t in terms)
            vec=0.0
            if qemb and rawemb:
                try: vec=max(0.0,_cosine(qemb,json.loads(rawemb)))
                except Exception: pass
            # Hybrid score: normalized lexical signal plus semantic cosine.
            score=(0.55*(lex/(lex+3.0)) + 0.45*vec) if qemb else (lex/(lex+3.0))
            if lex or vec>=0.18:
                scored.append((score,lex,vec,source,topic,content,created,pid))
        scored.sort(key=lambda x:(x[0],x[1],x[6]),reverse=True)
        return [{"source":s,"topic":t,"content":content,"score":round(score,4),"lexical_score":lex,
                 "semantic_score":round(vec,4),"created_at":dt,"project_id":pid}
                for score,lex,vec,s,t,content,dt,pid in scored[:max(1,min(int(limit),50))]]
