"""Explainable requirement triage. Approval is not implementation or simulation pass."""
import re
REJECT_PATTERNS = (
 r"^\s*(?:\d+(?:\.\d+)*\.?\s+)?(?:open items|required documents|revision history|table of contents)\b",
 r"\b(proposed verification topology|agent partitioning|uvm architecture|testbench topology)\b",
)
TESTABLE=re.compile(r"\b(shall|must|required|shall not|must not|is prohibited|is not permitted)\b",re.I)
OBSERVABLE=re.compile(r"\b(valid|ready|handshake|reset|clock|timeout|sequence|ack|nak|replay|crc|credit|packet|tlp|dllp|request|response|error|state|grant|arbiter|payload|completion|backpressure|data|address|latency|stall)\b",re.I)
GENERIC=re.compile(r"\b(must be confirmed|should be reviewed|see section|as described|refer to|must be reviewed)\b",re.I)
def assess_requirement(req,mapping=None):
 statement=(req.get("statement") or "").strip()
 if not statement or any(re.search(p,statement,re.I) for p in REJECT_PATTERNS):
  return {"decision":"rejected","confidence":0.99,"reason":"Heading, documentation text, or verification-process description; not a DUT behavior requirement."}
 if GENERIC.search(statement) or len(statement)<24:
  return {"decision":"needs_review","confidence":0.35,"reason":"Incomplete statement or review/documentation text; human review is required."}
 if not TESTABLE.search(statement) or not OBSERVABLE.search(statement):
  return {"decision":"needs_review","confidence":0.45,"reason":"No clear normative obligation and observable behavior were both identified."}
 mapping=mapping or {}
 evidence=mapping.get("rtl_evidence",[])+mapping.get("layer_evidence",[])
 if evidence:
  return {"decision":"auto_approved","confidence":0.88,"reason":"Normative observable behavior and related RTL structural evidence were found. Approval only permits verification planning; it does not prove implementation or passing simulation."}
 return {"decision":"needs_review","confidence":0.58,"reason":"Potentially testable requirement, but no supporting RTL evidence was found."}
def apply_auto_triage(requirements,mapped=None):
 by_id={x.get("requirement_id"):x for x in (mapped or [])}
 result=[]
 for item in requirements:
  row=dict(item); d=assess_requirement(row,by_id.get(row.get("requirement_id")))
  row["review_status"]="approved" if d["decision"]=="auto_approved" else ("rejected" if d["decision"]=="rejected" else "needs_review")
  row["auto_decision"]=d["decision"]; row["auto_confidence"]=d["confidence"]; row["auto_reason"]=d["reason"]
  result.append(row)
 return result
