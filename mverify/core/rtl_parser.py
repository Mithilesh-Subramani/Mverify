"""Conservative first-pass parser for common Verilog/SystemVerilog module headers.

This is not a complete IEEE Verilog/SystemVerilog parser. It extracts useful
structural evidence and reports limitations rather than guessing.
"""
from pathlib import Path
import re

MODULE_RE = re.compile(
    r"\bmodule\s+(?:automatic\s+|static\s+)?([A-Za-z_$][\w$]*)\s*(.*?)\bendmodule\b",
    re.DOTALL,
)
ANSI_PORT_RE = re.compile(
    r"(?:(input|output|inout)\s+)?"
    r"(?:(?:wire|reg|logic|bit|tri)\s+)?"
    r"(?:(signed|unsigned)\s+)?"
    r"(\[[^\]]+\]\s*)?"
    r"([A-Za-z_$][\w$]*)"
)

def _remove_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    return re.sub(r"//.*?$", " ", text, flags=re.MULTILINE)

def parse_rtl_file(path: Path) -> tuple[list[dict], list[str]]:
    source = _remove_comments(path.read_text(encoding="utf-8", errors="replace"))
    modules = []
    warnings = []
    for match in MODULE_RE.finditer(source):
        name, header = match.group(1), match.group(2)
        ports = []
        # ANSI-style port list: module name (...);
        open_paren = header.find("(")
        close_paren = header.find(")", open_paren + 1) if open_paren >= 0 else -1
        if open_paren >= 0 and close_paren >= 0:
            port_text = header[open_paren + 1:close_paren]
            inherited_direction = None
            for raw_port in port_text.split(","):
                token = raw_port.strip()
                if not token:
                    continue
                direction_match = re.search(r"\b(input|output|inout)\b", token)
                if direction_match:
                    inherited_direction = direction_match.group(1)
                name_match = re.search(r"([A-Za-z_$][\w$]*)\s*$", token)
                if name_match:
                    direction = direction_match.group(1) if direction_match else inherited_direction
                    width_match = re.search(r"(\[[^\]]+\])", token)
                    ports.append({
                        "name": name_match.group(1),
                        "direction": direction or "unspecified",
                        "width": width_match.group(1) if width_match else "scalar/unspecified",
                    })
        else:
            warnings.append(f"{path.name}: module {name} has no simple ANSI-style port list.")
        modules.append({"name": name, "ports": ports, "source_file": str(path)})
    if not modules and re.search(r"\bmodule\b", source):
        warnings.append(f"{path.name}: module declaration found, but the basic parser could not extract it.")
    return modules, warnings
