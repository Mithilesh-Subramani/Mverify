"""Local specification ingestion and evidence-linked requirement mapping.

Text extraction is intentionally conservative. Extracted statements are candidate
requirements and require engineer review before they become verification criteria.
"""
from __future__ import annotations
from pathlib import Path
import csv
import re
import hashlib

SUPPORTED_TEXT = {".txt", ".md", ".rst", ".csv"}

def extract_spec_text(path: Path) -> str:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_TEXT:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF support needs pypdf. Install it with: pip install pypdf") from exc
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("DOCX support needs python-docx. Install it with: pip install python-docx") from exc
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    raise ValueError(f"Unsupported specification format: {suffix or '(no extension)'}")

def _clean_statement(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" \t-*•")

def extract_candidate_requirements(text: str, source_name: str = "specification") -> list[dict]:
    """Extract normative-looking lines, not arbitrary prose."""
    results, seen = [], set()
    normative = re.compile(
        r"\b(shall|must|required|is required to|shall not|must not|should)\b", re.I
    )
    lines = text.splitlines()
    current_clause = ""
    current_heading = ""
    for line_no, raw in enumerate(lines, start=1):
        heading = _clean_statement(raw)
        # Preserve common numbered clause headings as context, but do not claim
        # they are authoritative clause IDs unless the source actually contains them.
        if re.match(r"^(?:[0-9]+(?:\.[0-9A-Za-z]+){0,6}|[A-Z]\.[0-9]+)\s+\S", heading):
            current_clause = heading.split()[0]
            current_heading = heading[:300]
        statement = heading
        if len(statement) < 18 or len(statement) > 1200 or not normative.search(statement):
            continue
        digest = hashlib.sha1(statement.lower().encode("utf-8")).hexdigest()[:10]
        if digest in seen:
            continue
        seen.add(digest)
        results.append({
            "requirement_id": f"REQ-{len(results)+1:04d}",
            "statement": statement,
            "source": source_name,
            "source_line": line_no,
            "detected_clause_candidate": current_clause,
            "clause_heading_context": current_heading,
            "context_before": _clean_statement(lines[line_no-2])[:500] if line_no > 1 else "",
            "context_after": _clean_statement(lines[line_no])[:500] if line_no < len(lines) else "",
            "category": "unclassified",
            "review_status": "needs_review",
            "extraction_method": "normative_keyword_line",
        })
    return results

def load_requirements_csv(path: Path) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    output = []
    for index, row in enumerate(rows, start=1):
        statement = (row.get("statement") or row.get("requirement") or "").strip()
        if not statement:
            continue
        output.append({
            "requirement_id": (row.get("requirement_id") or f"REQ-{index:04d}").strip(),
            "statement": statement,
            "source": (row.get("source") or Path(path).name).strip(),
            "source_line": row.get("source_line") or "",
            "category": (row.get("category") or "unclassified").strip(),
            "review_status": (row.get("review_status") or "approved").strip(),
            "extraction_method": "csv_import",
        })
    return output

def _tokens(text: str) -> set[str]:
    stop = {"shall","must","should","will","with","from","that","this","when","where",
            "into","onto","each","any","all","the","and","for","are","was","were",
            "not","does","doesnt","have","has","been","being","its","their","they"}
    return {t for t in re.findall(r"[a-z][a-z0-9_]{2,}", text.lower()) if t not in stop}

def map_requirements(requirements: list[dict], scan_report: dict) -> list[dict]:
    """Map requirements to observable structural evidence, never assert functionality."""
    modules = scan_report.get("module_details", [])
    hierarchy = scan_report.get("hierarchy", [])
    layers = scan_report.get("architecture_discovery", {}).get("layers", {})
    feature_inventory = scan_report.get("feature_analysis", {}).get("features", [])
    semantic_modules = scan_report.get("semantic_analysis", {}).get("modules", [])
    semantic_by_module = {m.get("module"): m for m in semantic_modules}
    module_text = []
    for m in modules:
        ports = " ".join(p.get("name", "") for p in m.get("ports", []))
        module_text.append({
            "module": m.get("name", ""),
            "text": (m.get("name", "") + " " + ports).lower(),
            "ports": [p.get("name", "") for p in m.get("ports", [])],
        })
    edges_text = " ".join(
        f'{e.get("parent","")} {e.get("child","")} {e.get("instance","")}'
        for e in hierarchy
    ).lower()
    mapped = []
    for req in requirements:
        statement = req.get("statement", "")
        terms = _tokens(statement)
        hits = []
        for m in module_text:
            overlap = sorted(t for t in terms if t in m["text"])
            if overlap:
                hits.append({"module": m["module"], "matched_terms": overlap,
                             "evidence_type": "module_or_port_name"})
        edge_terms = sorted(t for t in terms if t in edges_text)
        if edge_terms:
            hits.append({"module": None, "matched_terms": edge_terms,
                         "evidence_type": "hierarchy_name"})
        # Feature-level evidence is protocol-agnostic and can cross layer boundaries.
        # Match requirement terms against semantic evidence candidates as well as names.
        semantic_hits = []
        for module_name, sem in semantic_by_module.items():
            signals = set(sem.get("write_candidates", [])) | set(sem.get("read_identifier_candidates", []))
            state_names = {x.get("selector", "") for x in sem.get("state_machine_candidates", [])}
            state_names.update(y for x in sem.get("state_machine_candidates", []) for y in x.get("case_labels", []))
            evidence_terms = {x.lower() for x in signals | state_names if x}
            overlap = sorted(t for t in terms if t in evidence_terms)
            if overlap:
                semantic_hits.append({
                    "module": module_name,
                    "matched_signal_or_state_terms": overlap,
                    "write_candidates": sorted(signals & set(overlap)),
                    "state_machine_candidates": [x for x in sem.get("state_machine_candidates", [])
                                                 if x.get("selector", "").lower() in overlap
                                                 or any(y.lower() in overlap for y in x.get("case_labels", []))],
                    "evidence_type": "lexical_semantic_signal_state_candidate",
                })
        feature_hits = []
        for feature in feature_inventory:
            feature_terms = _tokens(feature.get("feature", "") + " " + feature.get("feature_id", ""))
            overlap = sorted(terms & feature_terms)
            if overlap:
                feature_hits.append({
                    "feature": feature.get("feature"),
                    "feature_id": feature.get("feature_id"),
                    "modules_involved": feature.get("modules_involved", []),
                    "matched_terms": overlap,
                    "confidence": feature.get("confidence"),
                })
        # Protocol category can add layer-level structural evidence.
        layer_hits = []
        category = (req.get("category") or "").lower()
        statement_l = statement.lower()
        layer_keywords = {
            "transaction_layer": ("tlp","transaction","completion","memory read","memory write","byte enable","tag"),
            "data_link_layer": ("dllp","data link","replay","lcrc","ack","nak","flow control","credit","sequence number"),
            "physical_layer": ("ltssm","pipe","physical layer","ordered set","link training","speed negotiation"),
        }
        for layer, keywords in layer_keywords.items():
            if any(k in statement_l for k in keywords) or category.replace(" ", "_") == layer:
                detail = layers.get(layer, {})
                if detail.get("evidence"):
                    layer_hits.append({"layer": layer, "status": detail.get("status"),
                                       "evidence": detail.get("evidence", [])})
        if hits or layer_hits or semantic_hits:
            status = "structural_evidence_found"
            evidence_groups = len(hits) + len(layer_hits) + len(semantic_hits)
            confidence = "medium" if evidence_groups > 1 else "low"
        else:
            status, confidence = "no_matching_structural_evidence", "low"
        mapped.append({
            **req,
            "mapping_status": status,
            "mapping_confidence": confidence,
            "rtl_evidence": hits,
            "layer_evidence": layer_hits,
            "feature_evidence": feature_hits,
            "semantic_evidence": semantic_hits,
            "verification_status": "not_verified",
            "mapping_note": "Evidence is a lexical candidate match against module/port names, feature candidates, or semantic signal/state candidates. It is not a resolved driver-to-consumer trace and does not prove functional implementation."
        })
    return mapped
