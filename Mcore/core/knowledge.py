"""Local VLSI knowledge store with provenance-aware chunking and lexical retrieval."""
from __future__ import annotations
import sqlite3, hashlib, datetime, re
from pathlib import Path

class KnowledgeStore:
    def __init__(self, path):
        self.path=str(Path(path).expanduser()); Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, source TEXT, sha256 TEXT UNIQUE, topic TEXT, content TEXT, created_at TEXT)")
    @staticmethod
    def chunk_text(text, max_chars=1800, overlap=180):
        text=(text or "").strip()
        if not text: return []
        # Prefer paragraph boundaries, then split oversized paragraphs safely.
        paras=re.split(r"\n\s*\n", text)
        chunks=[]; buf=""
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
            elif len(buf)+len(para)+2<=max_chars:
                buf=(buf+"\n\n"+para).strip()
            else:
                chunks.append(buf); buf=para
        if buf: chunks.append(buf)
        return chunks
    def ingest_text(self, source, text, topic="unclassified"):
        chunks=self.chunk_text(text)
        now=datetime.datetime.now(datetime.timezone.utc).isoformat(); inserted=0
        with sqlite3.connect(self.path) as c:
            for index,content in enumerate(chunks):
                digest=hashlib.sha256((str(source)+"\\0"+str(topic)+"\\0"+content).encode()).hexdigest()
                cur=c.execute("INSERT OR IGNORE INTO chunks(source,sha256,topic,content,created_at) VALUES(?,?,?,?,?)",
                              (source,digest,topic,content,now))
                inserted += cur.rowcount
        return {"source_sha256":hashlib.sha256((text or "").encode()).hexdigest(),"chunks":len(chunks),"inserted":inserted}
    def search(self, query, limit=8):
        terms=[x.lower() for x in re.findall(r"[A-Za-z0-9_+-]{3,}",query or "")]
        if not terms: return []
        with sqlite3.connect(self.path) as c:
            rows=c.execute("SELECT source,topic,content,created_at FROM chunks").fetchall()
        scored=[]
        for source,topic,content,created in rows:
            low=content.lower(); score=sum(low.count(t) for t in terms)
            if score: scored.append((score,source,topic,content,created))
        return [{"source":s,"topic":t,"content":c,"score":n,"created_at":dt}
                for n,s,t,c,dt in sorted(scored,key=lambda x:(x[0],x[4]),reverse=True)[:max(1,min(int(limit),50))]]
