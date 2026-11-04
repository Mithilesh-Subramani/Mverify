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
    for line_no, raw in enumerate(text.splitlines(), start=1):
        statement = _clean_statement(raw)
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
        if hits or layer_hits:
            status = "structural_evidence_found"
            confidence = "medium" if len(hits) + len(layer_hits) > 1 else "low"
        else:
            status, confidence = "no_matching_structural_evidence", "low"
        mapped.append({
            **req,
            "mapping_status": status,
            "mapping_confidence": confidence,
            "rtl_evidence": hits,
            "layer_evidence": layer_hits,
            "verification_status": "not_verified",
            "mapping_note": "A name or structural match is not proof that the requirement is implemented correctly or has passed simulation."
        })
    return mapped
