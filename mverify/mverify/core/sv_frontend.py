"""Optional standards-oriented SystemVerilog frontend integration.

The lightweight scanner remains available when Surelog is absent. When present,
Surelog is run with the project's filelist and its outputs/logs are retained.
This module never treats a successful process exit as functional verification.
"""
from __future__ import annotations
import json, shutil, subprocess
from pathlib import Path

def run_surelog(project_dir, build_inputs, top=None, output_dir=None, timeout=300):
    exe = shutil.which("surelog")
    result = {
        "frontend": "surelog", "available": bool(exe), "status": "not_run",
        "executable": exe, "top": top, "command": [], "returncode": None,
        "log": None, "limitations": [
            "Surelog parsing/elaboration is not simulation or protocol compliance.",
            "UHDM semantic extraction is not enabled unless a compatible UHDM reader is installed."
        ]
    }
    if not exe:
        result["status"] = "unavailable"
        result["message"] = "Surelog was not found on PATH. Lightweight analysis remains active."
        return result
    files = build_inputs.get("compile_sources") or []
    if not files:
        result["status"] = "blocked_no_filelist_sources"
        result["message"] = "No compile sources were resolved from .f files."
        return result
    out = Path(output_dir or (Path(project_dir)/".mverify"/"surelog")).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cmd = [exe, "-parse", "-elabuhdm"]
    if top: cmd += ["-top", top]
    for inc in build_inputs.get("include_dirs", []): cmd += ["+incdir+"+inc]
    for define in build_inputs.get("defines", []): cmd += ["+define+"+define]
    cmd += files
    result["command"] = cmd
    try:
        proc = subprocess.run(cmd, cwd=str(project_dir), capture_output=True,
                              text=True, timeout=timeout, check=False)
        log = out/"surelog.log"
        log.write_text((proc.stdout or "")+"\n--- STDERR ---\n"+(proc.stderr or ""))
        result.update(status="passed" if proc.returncode == 0 else "failed",
                      returncode=proc.returncode, log=str(log))
    except subprocess.TimeoutExpired as exc:
        result.update(status="timeout", message=str(exc))
    except OSError as exc:
        result.update(status="error", message=str(exc))
    return result

def build_design_graph(scan_report):
    """Build a conservative evidence graph from extracted module/port/instance data."""
    nodes, edges = [], []
    for mod in scan_report.get("module_details", []):
        mid = "module:"+mod["name"]
        nodes.append({"id":mid,"type":"module","name":mod["name"],"source":mod.get("source_file")})
        for port in mod.get("ports", []):
            pid=f"port:{mod['name']}.{port['name']}"
            nodes.append({"id":pid,"type":"port","name":port["name"],"direction":port.get("direction"),
                          "width":port.get("width"),"source":mod.get("source_file")})
            edges.append({"source":mid,"target":pid,"relation":"HAS_PORT","evidence":"module port declaration"})
    for inst in scan_report.get("hierarchy", []):
        edges.append({"source":"module:"+inst["parent"],"target":"module:"+inst["child"],
                      "relation":"INSTANTIATES","instance":inst.get("instance"),
                      "evidence":"lexically detected instance; elaboration not guaranteed"})
    semantic=scan_report.get("semantic_analysis",{})
    for mod in semantic.get("modules",[]):
        for fsm in mod.get("state_machine_candidates",[]):
            fid=f"fsm_candidate:{mod.get('module')}:{fsm.get('selector')}"
            nodes.append({"id":fid,"type":"fsm_candidate","name":fsm.get("selector"),
                          "states":fsm.get("case_labels"),"transition_targets":fsm.get("transition_targets"),
                          "source":mod.get("source_file"),"confidence":"candidate"})
            edges.append({"source":"module:"+str(mod.get("module")),"target":fid,"relation":"CONTAINS_CANDIDATE"})
    return {"schema_version":"1.0","nodes":nodes,"edges":edges,
            "analysis_scope":"Conservative graph from lightweight lexical extraction. Use Surelog/UHDM for elaborated connectivity."}
