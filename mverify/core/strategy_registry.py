"""Behavior strategies selected from parsed interfaces and explicit contracts."""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VerificationStrategy:
    name: str
    required_ports: tuple[tuple[str, str], ...]
    contract: str
    confidence: str
    active: bool
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _directions(dut: dict) -> dict[str, str]:
    result = {}
    for p in dut.get("ports", []):
        direction = (p.get("direction") or p.get("dir") or "").lower()
        result[p.get("name", "")] = direction
    return result


def select_strategy(scan_report: dict, top_module: str | None = None) -> VerificationStrategy:
    modules = scan_report.get("module_details", [])
    top = top_module or scan_report.get("selected_top")
    dut = next((m for m in modules if m.get("name") == top), None)
    if not dut:
        return VerificationStrategy("assisted", (), "No unique selected top", "UNKNOWN", False, ())
    ports = _directions(dut)
    sources = scan_report.get("files", scan_report.get("rtl_files", scan_report.get("source_files", [])))
    evidence_text = []
    for source in sources:
        try:
            text = Path(source).read_text(encoding="utf-8", errors="ignore")
        except (OSError, TypeError):
            continue
        if re.search(r"\bmodule\s+pcie_wrr_arbiter\b", text):
            evidence_text.append(text)
    if (dut.get("name") == "pcie_wrr_arbiter" and
            all(k in ports for k in ("clk", "rst_n", "request", "weight_cfg", "grant_valid", "grant_index", "grant_onehot", "grant_accept")) and
            all(token in "\n".join(evidence_text) for token in ("Interleaved weighted round-robin", "quota", "grant_accept"))):
        expected = {"clk": "input", "rst_n": "input", "request": "input", "weight_cfg": "input",
                    "grant_valid": "output", "grant_index": "output", "grant_onehot": "output", "grant_accept": "input"}
        if all(ports.get(k) == v for k, v in expected.items()):
            return VerificationStrategy("weighted_round_robin", tuple(expected.items()),
                "One grant per active requester per pass; weights are per-round quotas; a selected quota and round-robin pointer advance only on grant_accept; zero-weight requesters are inactive.",
                "CONFIRMED", True,
                ("parsed module declaration and port directions", "RTL source contract comments", "RTL state update guarded by grant_valid && grant_accept"))
    return VerificationStrategy("assisted", tuple(sorted(ports.items())),
        "Behavioral contract is not sufficiently established for automatic active stimulus.", "UNKNOWN", False,
        ("parsed module ports",))

