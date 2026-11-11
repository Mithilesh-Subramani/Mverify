"""Bounded, project-scoped context and provenance builder for Mcore."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _item_id(project_id: str, source: str, content: str, kind: str, symbol: str | None) -> str:
    digest = hashlib.sha256((project_id + "\0" + source + "\0" + kind + "\0" + str(symbol or "") + "\0" + content).encode()).hexdigest()
    return "ev_" + digest[:24]


def build_engineering_context(*, project_id: str, task: str, project_context: dict | None = None,
                              rtl_evidence: dict | None = None, spec_evidence: list | dict | None = None,
                              tool_evidence: dict | None = None, retrieved_knowledge: list | None = None,
                              validated_experiences: list | None = None, max_chars: int | None = None,
                              max_evidence: int = 32) -> dict:
    """Select compact evidence and assign stable IDs without embedding full RTL files."""
    if not project_id or project_id == "*":
        raise ValueError("A concrete project_id is required for engineering context")
    budget = max_chars or int(os.environ.get("MCORE_CONTEXT_MAX_CHARS", "18000"))
    project = dict(project_context or {})
    rtl = rtl_evidence or {}
    specs = spec_evidence or []
    if isinstance(specs, dict):
        specs = specs.get("requirements", []) if isinstance(specs.get("requirements", []), list) else [specs]
    evidence: list[dict] = []

    def add(kind: str, source: str, value: Any, *, classification: str, module: str | None = None,
            symbol: str | None = None, line_start: int | None = None, line_end: int | None = None,
            fact_key: str | None = None, fact_value: Any = None) -> None:
        content = value if isinstance(value, str) else _canonical(value)
        if len(content) > 5000:
            content = content[:5000] + "\n[truncated]"
        entry = {"id": _item_id(project_id, source, content, kind, symbol), "project_id": project_id,
                 "kind": kind, "source": source, "module": module, "symbol": symbol,
                 "line_start": line_start, "line_end": line_end,
                 "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                 "content": content, "classification": classification}
        if fact_key is not None:
            entry["fact_key"] = fact_key
            entry["fact_value"] = fact_value
        evidence.append(entry)

    top = rtl.get("dut_top") or project.get("dut_top")
    module = rtl.get("selected_module") or {}
    if module:
        source = str(module.get("source_file") or module.get("source") or "rtl_parser:selected_module")
        compact = {k: module.get(k) for k in ("name", "source_file", "port_style", "ports") if k in module}
        add("rtl_module", source, compact, classification="CONFIRMED_FROM_PARSER", module=module.get("name") or top)
        for port in module.get("ports", [])[:128]:
            pname = port.get("name")
            add("rtl_port", source, {k: port.get(k) for k in ("name", "direction", "width", "declaration")},
                classification="CONFIRMED_FROM_PARSER", module=module.get("name") or top, symbol=pname,
                fact_key=f"port:{module.get('name') or top}:{pname}:direction",
                fact_value=port.get("direction"))

    udm = rtl.get("universal_design_model") or {}
    if udm:
        design = {k: udm.get(k) for k in ("schema", "project", "design_scope", "hierarchy", "top_interface", "design_characteristics", "evidence_policy", "analysis_limits") if k in udm}
        add("udm_summary", "mverify:universal_design_model", design,
            classification="INFERRED_FROM_RTL", module=top)
    plan = rtl.get("adaptive_verification_plan")
    if plan:
        add("verification_plan", "mverify:adaptive_verification_plan", plan,
            classification="INFERRED_FROM_RTL", module=top)
    summary = rtl.get("project_summary") or rtl.get("summary")
    if summary:
        add("project_summary", "mverify:project_scan", summary, classification="CONFIRMED_FROM_PARSER", module=top)

    for i, requirement in enumerate(specs[:128]):
        if not isinstance(requirement, dict):
            continue
        text = requirement.get("statement") or requirement.get("requirement") or requirement.get("text") or requirement.get("description") or requirement.get("normalized_text") or requirement
        source = str(requirement.get("source") or requirement.get("document") or "specification")
        add("specification_requirement", source, {"requirement_id": requirement.get("requirement_id", f"spec_{i+1}"),
            "text": text, "review_status": requirement.get("review_status"), "revision": requirement.get("revision"),
            "clause_heading_context":requirement.get("clause_heading_context"),
            "context_before":requirement.get("context_before"),"context_after":requirement.get("context_after")},
            classification="CONFIRMED_FROM_SPEC", module=requirement.get("module"), symbol=requirement.get("signal"),
            line_start=requirement.get("source_line",requirement.get("line_start")), line_end=requirement.get("line_end"))

    accepted_retrieval = []
    for item in retrieved_knowledge or []:
        if item.get("project_id") != project_id:
            continue
        compact = {k: item.get(k) for k in ("topic", "content", "score", "lexical_score", "semantic_score", "retrieval_method", "source", "source_sha256") if k in item}
        add("retrieved_project_knowledge", str(item.get("source") or "knowledge_store"), compact,
            classification="CONFIRMED_FROM_PARSER" if item.get("topic") == "rtl_source" else "INFERRED_FROM_RTL",
            module=item.get("module"), symbol=item.get("symbol"), line_start=item.get("line_start"), line_end=item.get("line_end"))
        accepted_retrieval.append(item.get("source"))

    for item in validated_experiences or []:
        if item.get("project_id") != project_id or item.get("validation_status") != "validated":
            continue
        add("validated_engineering_experience", "mcore:validated_experience", item,
            classification="ENGINEER_APPROVED", module=item.get("module"))

    if tool_evidence:
        add("simulator_evidence", "mverify:toolchain", tool_evidence, classification="CONFIRMED_FROM_PARSER", module=top)

    # Priority is deterministic: selected RTL/UDM/spec facts precede RAG and tools.
    selected = []
    used = len(task) + len(_canonical({"project_id": project_id, "dut_top": top, "project": project}))
    truncated = 0
    for item in evidence:
        if len(selected) >= max_evidence or used + len(item["content"]) > budget:
            truncated += 1
            continue
        selected.append(item)
        used += len(item["content"])
    return {"schema_version": "mcore.context.v1", "project_id": project_id, "task": task,
            "project_context": {"project_id": project_id, "dut_top": top,
                                "active_project": project.get("project_name") or project.get("project_dir"),
                                "udm_schema": udm.get("schema")},
            "evidence": selected, "evidence_ids": [x["id"] for x in selected],
            "retrieval": {"scope": "project_only", "selected_sources": accepted_retrieval,
                          "candidate_count": len(retrieved_knowledge or [])},
            "budget": {"max_chars": budget, "used_chars_approx": used, "truncated_evidence_count": truncated}}
