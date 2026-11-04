"""Project discovery and conservative module hierarchy analysis."""
from pathlib import Path
import logging
import re

from .rtl_parser import parse_rtl_file, _remove_comments
from mverify.protocols.pcie.discovery import discover_pcie

LOG = logging.getLogger(__name__)
RTL_SUFFIXES = {".v", ".vh", ".sv", ".svh"}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist"}


def _rtl_files(project_dir: Path):
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in RTL_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def _find_instances(module_details):
    """Find likely child-module instantiations inside parsed module bodies."""
    known = {m["name"] for m in module_details}
    edges = []
    # Supports: child u_child (...); and child #(...) u_child (...);
    for parent in module_details:
        body = parent.get("body", "")
        for child in known:
            if child == parent["name"]:
                # Recursive instantiation is still worth reporting if present.
                pass
            pattern = re.compile(
                rf"(?<![\w$]){re.escape(child)}\s*"
                rf"(?:#\s*\((?:[^()]|\([^()]*\))*\)\s*)?"
                rf"(?P<instance>[A-Za-z_$][\w$]*)\s*\(",
                re.MULTILINE,
            )
            for match in pattern.finditer(body):
                # Avoid treating procedural/task calls as hierarchy evidence.
                prefix = body[max(0, match.start()-30):match.start()]
                if re.search(r"\b(function|task|typedef|class|virtual)\s*$", prefix):
                    continue
                edges.append({"parent": parent["name"], "child": child,
                              "instance": match.group("instance")})
    return edges


def scan_project(project_dir: Path, requested_top: str | None = None) -> dict:
    project_dir = Path(project_dir).expanduser().resolve()
    files = list(_rtl_files(project_dir))
    module_details, warnings, source_texts = [], [], []
    for path in files:
        modules, file_warnings = parse_rtl_file(path)
        try:
            source_texts.append(_remove_comments(path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            pass
        module_details.extend(modules)
        warnings.extend(file_warnings)

    names = [m["name"] for m in module_details]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        warnings.append("Duplicate module declarations found: " + ", ".join(duplicates))

    edges = _find_instances(module_details)
    instantiated = {edge["child"] for edge in edges}
    candidates = sorted(set(names) - instantiated)
    selected_top = requested_top if requested_top in names else None
    if requested_top and not selected_top:
        warnings.append(f"Requested top module '{requested_top}' was not found.")
    if len(candidates) > 1:
        warnings.append("Multiple possible top modules were found. Select the correct DUT top manually.")
    if not candidates and names:
        warnings.append("No top-level candidate could be inferred. Check hierarchy and parser limitations.")
    if not files:
        warnings.append("No Verilog/SystemVerilog source files were found in the selected directory.")

    # Remove parser-only body text from UI/report module details.
    public_modules = [{k: v for k, v in m.items() if k != "body"} for m in module_details]
    report = {
        "project_dir": str(project_dir),
        "summary": {"rtl_files": len(files), "modules": len(module_details),
                    "hierarchy_instances": len(edges), "warnings": len(warnings)},
        "files": [str(p) for p in files],
        "module_details": public_modules,
        "hierarchy": edges,
        "top_candidates": candidates,
        "selected_top": selected_top,
        "warnings": warnings,
        "analysis_scope": (
            "Structural first-pass scan only. Hierarchy and ports are heuristic evidence. "
            "No protocol compliance or functional pass/fail is inferred."
        ),
    }
    report["_source_text"] = source_texts
    report["architecture_discovery"] = discover_pcie(report)
    report.pop("_source_text", None)
    return report
