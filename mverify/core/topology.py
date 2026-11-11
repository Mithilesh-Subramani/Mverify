"""Evidence-labelled hierarchy and top-level port topology helpers."""
from __future__ import annotations

def build_topology(report: dict, top: str | None = None) -> dict:
    modules = report.get("module_details", [])
    selected = top or report.get("selected_top")
    by_name = {m.get("name"): m for m in modules}
    if selected not in by_name:
        candidates = report.get("top_candidates", [])
        selected = candidates[0] if len(candidates) == 1 else None
    if not selected:
        return {"top": None, "nodes": [], "edges": [], "status": "top_selection_required"}
    edges = [e for e in report.get("hierarchy", []) if e.get("parent") == selected]
    mod = by_name[selected]
    ports = []
    for p in mod.get("ports", []):
        ports.append({"name": p.get("name"), "direction": p.get("direction", "unknown"),
                      "width": p.get("width", "unspecified"),
                      "evidence": "module port declaration", "connection_status": "top_level_pin"})
    graph = report.get("design_graph", {})
    return {
        "top": selected, "source_file": mod.get("source_file"), "ports": ports,
        "instances": edges,
        "nodes": graph.get("nodes", []), "edges": graph.get("edges", []),
        "connectivity_status": "hierarchy_candidates_only",
        "limitations": [
            "Instance port expressions are not resolved by the lightweight parser.",
            "Port names and directions are declaration evidence, not proof of electrical connectivity.",
            "Install and run Surelog/UHDM or another standards-compliant elaborator for resolved connectivity."
        ]
    }
