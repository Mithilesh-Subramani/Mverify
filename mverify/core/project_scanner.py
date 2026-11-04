from pathlib import Path
import logging

from .rtl_parser import parse_rtl_file

LOG = logging.getLogger(__name__)
RTL_SUFFIXES = {".v", ".vh", ".sv", ".svh"}

def scan_project(project_dir: Path, requested_top: str | None = None) -> dict:
    files = sorted(p for p in project_dir.rglob("*") if p.is_file() and p.suffix.lower() in RTL_SUFFIXES)
    module_details = []
    warnings = []
    for path in files:
        try:
            modules, file_warnings = parse_rtl_file(path)
            module_details.extend(modules)
            warnings.extend(file_warnings)
        except OSError as exc:
            warnings.append(f"Could not read {path}: {exc}")

    module_names = [m["name"] for m in module_details]
    instantiated = set()
    # Heuristic only: detect module names followed by an instance-like identifier and '('.
    import re
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name in module_names:
            if re.search(rf"\b{re.escape(name)}\s+[A-Za-z_$][\w$]*\s*\(", text):
                instantiated.add(name)

    candidates = sorted(set(module_names) - instantiated)
    selected_top = requested_top if requested_top in module_names else None
    if requested_top and not selected_top:
        warnings.append(f"Requested top module '{requested_top}' was not found.")
    if len(candidates) > 1:
        warnings.append("Multiple possible top modules were found. Select the correct DUT top manually.")
    if not candidates and module_names:
        warnings.append("No top-level candidate could be inferred. Check hierarchy and parser limitations.")

    return {
        "project_dir": str(project_dir.resolve()),
        "summary": {
            "rtl_files": len(files),
            "modules": len(module_details),
            "warnings": len(warnings),
        },
        "files": [str(p) for p in files],
        "module_details": module_details,
        "top_candidates": candidates,
        "selected_top": selected_top,
        "warnings": warnings,
        "analysis_scope": "Structural first-pass scan only. No protocol compliance or functional pass/fail is inferred.",
    }
