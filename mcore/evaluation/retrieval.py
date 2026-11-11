"""Retrieval benchmark metrics. Scores measure retrieval only, never correctness."""
from __future__ import annotations

import os


def _matches(item: dict, expected: dict, project_id: str) -> bool:
    if item.get("project_id") != project_id: return False
    source=expected.get("source")
    if source and os.path.normcase(str(item.get("source",""))) != os.path.normcase(str(source)): return False
    module=expected.get("module")
    if module and str(item.get("module") or "").lower()!=str(module).lower(): return False
    symbol=expected.get("symbol")
    if symbol and str(item.get("symbol") or "").lower()!=str(symbol).lower(): return False
    return bool(source or module or symbol)


def evaluate_retrieval(store, cases: list[dict], k: int = 5) -> dict:
    if not isinstance(cases,list) or not cases: raise ValueError("non-empty retrieval cases are required")
    k=max(1,min(int(k),20)); rows=[]; total_relevant=0; total_hits=0; reciprocal=0.0; isolation_violations=0
    for index,case in enumerate(cases):
        project_id=str(case.get("project_id") or "")
        query=case.get("query")
        expected=case.get("expected",{})
        if not project_id or not isinstance(query,str) or not query or not isinstance(expected,dict):
            raise ValueError(f"case {index} requires project_id, query and expected metadata")
        results=store.search(query,limit=k,project_id=project_id)
        if any(item.get("project_id")!=project_id for item in results): isolation_violations+=1
        rank=next((i+1 for i,item in enumerate(results) if _matches(item,expected,project_id)),None)
        total_relevant+=1; hit=rank is not None
        total_hits+=int(hit)
        if hit: reciprocal+=1.0/rank
        rows.append({"case_id":case.get("id",f"case_{index+1}"),"project_id":project_id,
            "expected":expected,"rank":rank,"hit_at_k":hit,"retrieval_method":results[0].get("retrieval_method") if results else "none",
            "top_results":[{k0:item.get(k0) for k0 in ("source","module","symbol","score","lexical_score","semantic_score","project_id")} for item in results]})
    precision=total_hits/(len(cases)*k) if cases else 0.0
    recall=total_hits/total_relevant if total_relevant else 0.0
    return {"schema_version":"mcore.retrieval-evaluation.v1","case_count":len(cases),"k":k,
        f"recall_at_{k}":round(recall,4),f"precision_at_{k}":round(precision,4),
        "mrr":round(reciprocal/total_relevant,4) if total_relevant else 0.0,
        "project_isolation_violations":isolation_violations,"cases":rows,
        "interpretation":"Retrieval metrics measure expected-source ranking and project scoping, not engineering correctness."}
