"""Deterministic protocol-interface and runtime verification intelligence.

This module deliberately separates static candidates from verified protocol
semantics. Signal names can suggest an interface, but only an engineer-approved
contract or specification can establish its meaning.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RTL_SUFFIXES = {".v", ".vh", ".sv", ".svh"}
SNAPSHOT_SUFFIXES = RTL_SUFFIXES | {".f", ".flist", ".sdc", ".xdc", ".tcl"}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", "build", "dist", ".mverify"}


def _suffix_match(name: str, kind: str) -> str | None:
    """Return a normalized interface stem for valid/ready-like names."""
    value = name.lower()
    patterns = {
        "valid": r"(?:^|_)(?:valid|vld)(?:_[io])?$",
        "ready": r"(?:^|_)(?:ready|rdy)(?:_[io])?$",
    }
    match = re.search(patterns[kind], value)
    if not match:
        return None
    stem = value[:match.start()].rstrip("_")
    return stem or "default"


def discover_interface_contracts(scan_report: dict[str, Any]) -> list[dict[str, Any]]:
    """Find valid/ready port pairs by exact normalized stem and direction.

    Results are candidates. This function does not infer payload stability,
    clock domain, reset behavior, or protocol compliance.
    """
    contracts: list[dict[str, Any]] = []
    for module in scan_report.get("module_details", []):
        ports = module.get("ports", [])
        valid_by_stem: dict[str, list[dict[str, Any]]] = {}
        ready_by_stem: dict[str, list[dict[str, Any]]] = {}
        for port in ports:
            name = str(port.get("name", ""))
            valid_stem = _suffix_match(name, "valid")
            ready_stem = _suffix_match(name, "ready")
            if valid_stem is not None:
                valid_by_stem.setdefault(valid_stem, []).append(port)
            if ready_stem is not None:
                ready_by_stem.setdefault(ready_stem, []).append(port)
        for stem in sorted(set(valid_by_stem) & set(ready_by_stem)):
            for valid in valid_by_stem[stem]:
                for ready in ready_by_stem[stem]:
                    vd, rd = valid.get("direction", "unknown"), ready.get("direction", "unknown")
                    complementary = {vd, rd} == {"input", "output"}
                    contracts.append({
                        "interface_id": f"{module.get('name', 'module')}::{stem}",
                        "module": module.get("name", "unknown"),
                        "valid_signal": valid.get("name"),
                        "valid_direction": vd,
                        "ready_signal": ready.get("name"),
                        "ready_direction": rd,
                        "candidate_quality": "direction_complementary_candidate" if complementary else "name_only_candidate",
                        "acceptance_expression": f"{valid.get('name')} && {ready.get('name')}",
                        "classification": "INFERRED_FROM_PORT_NAMES_AND_DIRECTIONS",
                        "review_required": True,
                        "not_established": [
                            "clock association", "reset semantics", "payload association",
                            "payload stability while stalled", "protocol-specific acceptance semantics"
                        ],
                    })
    return contracts


def _logic_one(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    text = str(value).strip().lower().replace("_", "")
    if text in {"1", "1'b1", "1'h1", "true", "high"}:
        return True
    if text in {"0", "1'b0", "1'h0", "false", "low"}:
        return False
    if text in {"x", "z", "1'bx", "1'bz", "", "nan", "none"}:
        return None
    try:
        return int(text, 0) == 1
    except ValueError:
        return None


def analyze_handshake_samples(samples: list[dict[str, Any]], contracts: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure valid/ready acceptance and stall runs from cycle samples."""
    results = []
    ordered = sorted(samples, key=lambda x: int(x.get("cycle", 0)))
    for contract in contracts:
        valid_name, ready_name = contract.get("valid_signal"), contract.get("ready_signal")
        accepted = 0
        stall_cycles = 0
        longest_stall = 0
        current_stall = 0
        unknown = 0
        first_stall_cycle = None
        for sample in ordered:
            signals = sample.get("signals", sample)
            valid = _logic_one(signals.get(valid_name))
            ready = _logic_one(signals.get(ready_name))
            cycle = int(sample.get("cycle", 0))
            if valid is None or ready is None:
                unknown += 1
                current_stall = 0
                continue
            if valid and ready:
                accepted += 1
                current_stall = 0
            elif valid and not ready:
                stall_cycles += 1
                current_stall += 1
                first_stall_cycle = cycle if first_stall_cycle is None else first_stall_cycle
                longest_stall = max(longest_stall, current_stall)
            else:
                current_stall = 0
        results.append({
            "interface_id": contract.get("interface_id"),
            "module": contract.get("module"),
            "valid_signal": valid_name,
            "ready_signal": ready_name,
            "accepted_cycles": accepted,
            "stalled_cycles": stall_cycles,
            "longest_observed_stall_cycles": longest_stall,
            "first_stall_cycle": first_stall_cycle,
            "unknown_or_missing_samples": unknown,
            "sample_count": len(ordered),
            "classification": "MEASURED_FROM_IMPORTED_SIGNAL_SAMPLES",
            "interpretation_limit": "A stall is measured as valid=1 and ready=0. No maximum legal latency is assumed.",
        })
    return {"schema": "mverify.handshake_analysis.v1", "interfaces": results,
            "sample_count": len(ordered), "status": "measured" if ordered else "no_samples"}


def load_signal_csv(path: Path) -> list[dict[str, Any]]:
    """Load a wide CSV (cycle, signal_a, signal_b, ...) or long CSV (cycle,signal,value)."""
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return []
    fields = set(rows[0])
    if {"cycle", "signal", "value"}.issubset(fields):
        grouped: dict[int, dict[str, Any]] = {}
        for row in rows:
            cycle = int(row["cycle"])
            grouped.setdefault(cycle, {})[row["signal"]] = row["value"]
        return [{"cycle": cycle, "signals": signals} for cycle, signals in sorted(grouped.items())]
    if "cycle" not in fields:
        raise ValueError("CSV must contain a 'cycle' column.")
    return [{"cycle": int(row["cycle"]), "signals": {k: v for k, v in row.items() if k != "cycle"}}
            for row in rows]


def capture_project_snapshot(project_dir: Path) -> dict[str, Any]:
    """Hash RTL/build inputs and persist an immutable project snapshot."""
    root = Path(project_dir).expanduser().resolve()
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SNAPSHOT_SUFFIXES:
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in relative_parts):
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            files[path.relative_to(root).as_posix()] = {"sha256": digest, "size_bytes": path.stat().st_size}
        except OSError:
            continue
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    snapshot = {"schema": "mverify.project_snapshot.v1", "project_root": str(root),
                "snapshot_id": timestamp, "created_at": datetime.now(timezone.utc).isoformat(),
                "file_count": len(files), "files": files}
    target = root / ".mverify" / "snapshots" / f"{timestamp}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return {**snapshot, "snapshot_path": str(target)}


def compare_project_snapshots(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Compare two manifests and return added, removed and modified source inputs."""
    before, after = previous.get("files", {}), current.get("files", {})
    old_names, new_names = set(before), set(after)
    added = sorted(new_names - old_names)
    removed = sorted(old_names - new_names)
    modified = sorted(name for name in old_names & new_names
                      if before[name].get("sha256") != after[name].get("sha256"))
    changed = set(added + removed + modified)
    return {"schema": "mverify.change_impact.v1", "added": added, "removed": removed,
            "modified": modified, "changed_files": sorted(changed),
            "change_count": len(changed),
            "status": "changes_detected" if changed else "no_changes",
            "note": "File-level change detection only. Semantic impact requires a fresh RTL scan and requirement/test traceability."}


def build_verification_readiness(scan_report: dict[str, Any], requirements: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Summarize structural readiness without turning candidates into compliance claims."""
    contracts = discover_interface_contracts(scan_report)
    semantic = scan_report.get("semantic_analysis", {})
    state_machines = []
    for module in semantic.get("modules", []):
        for fsm in module.get("state_machine_candidates", []):
            state_machines.append({"module": module.get("module"), **fsm,
                                   "classification": "INFERRED_FROM_RTL"})
    requirements = requirements or []
    approved = sum(1 for item in requirements if item.get("review_status") == "approved")
    return {
        "schema": "mverify.verification_readiness.v1",
        "project": scan_report.get("project_dir", ""),
        "selected_top": scan_report.get("selected_top"),
        "interface_contract_candidates": contracts,
        "state_machine_candidates": state_machines,
        "requirements": {"total": len(requirements), "approved": approved,
                         "needs_review": len(requirements) - approved},
        "readiness_gates": {
            "rtl_scan_available": bool(scan_report.get("module_details")),
            "top_selected": bool(scan_report.get("selected_top")),
            "interface_contract_review": "required" if contracts else "not_detected",
            "requirements_review": "required" if requirements and approved < len(requirements) else "not_available_or_complete",
            "simulation_evidence": "not_assessed_by_static_scan",
            "protocol_compliance": "not_established",
        },
        "limitations": [
            "Interface candidates are inferred from names and directions; confirm their protocol meaning.",
            "FSM candidates are static source evidence, not runtime state observations.",
            "No protocol compliance or functional correctness is inferred from RTL structure alone.",
        ],
    }
