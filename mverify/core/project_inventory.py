"""Classify project inputs without treating every file as compilable RTL."""
from __future__ import annotations
from pathlib import Path

RTL = {".v", ".vh", ".sv", ".svh"}
HDL = RTL | {".vhd", ".vhdl"}
FILELISTS = {".f", ".flist", ".lst"}
CONSTRAINTS = {".sdc", ".xdc", ".pdc", ".ucf"}
PROJECT = {".qpf", ".qsf", ".xpr", ".prj", ".f", ".tcl", ".mk"}
DOCS = {".pdf", ".docx", ".md", ".rst", ".txt", ".csv", ".xlsx", ".yaml", ".yml", ".json"}
SKIP = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", "build", "dist", ".mverify"}

def classify_file(path: Path) -> str:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix in RTL: return "verilog_systemverilog_source"
    if suffix in {".vhd", ".vhdl"}: return "vhdl_source"
    if suffix in FILELISTS: return "compile_filelist"
    if suffix in CONSTRAINTS: return "timing_constraints"
    if suffix in PROJECT or name in {"makefile", "cmakelists.txt"}: return "project_build_metadata"
    if suffix == ".tcl": return "eda_automation_script"
    if suffix in DOCS: return "specification_or_documentation"
    if suffix in {".do", ".sh", ".py", ".csh", ".bash"}: return "automation_or_support_script"
    return "other"

def inventory_project(project_dir: Path) -> dict:
    root = Path(project_dir).expanduser().resolve()
    buckets: dict[str, list[str]] = {}
    total = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in SKIP for part in path.relative_to(root).parts):
            continue
        total += 1
        buckets.setdefault(classify_file(path), []).append(str(path))
    return {
        "root": str(root), "total_files": total,
        "categories": {k: {"count": len(v), "files": v} for k, v in sorted(buckets.items())},
        "supported_analysis": ["Verilog", "SystemVerilog", "VHDL file discovery"],
        "not_yet_semantically_parsed": ["VHDL", "timing constraints", "Tcl", "vendor project databases"],
        "note": "Discovery does not imply parsing or semantic support. Unsupported files are reported, not silently ignored."
    }
