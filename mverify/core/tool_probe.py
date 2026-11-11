"""Discover optional EDA tools without assuming availability."""
from __future__ import annotations
import shutil

def probe_tools() -> dict:
    tools = {
        "surelog": ["surelog"], "slang": ["slang"], "yosys": ["yosys"],
        "iverilog": ["iverilog"], "verilator": ["verilator"],
        "vcs": ["vcs"], "questa": ["vsim"], "verdi": ["verdi"],
        "gtkwave": ["gtkwave"], "ollama": ["ollama"],
    }
    result = {}
    for name, commands in tools.items():
        exe = next((shutil.which(x) for x in commands if shutil.which(x)), None)
        result[name] = {"available": bool(exe), "executable": exe}
    return result
