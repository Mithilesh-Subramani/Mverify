"""Controlled VCS/Verdi discovery and subprocess workflows.

All subprocesses use argument vectors, retain caller license settings, and save
machine-readable evidence beside their logs. Remote Linux tools can be reached
through SSH by setting MVERIFY_REMOTE_HOST; no shell payload is interpolated.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


STATES = {"NOT_STARTED", "VALIDATING", "COMPILING", "COMPILE_FAILED", "COMPILE_PASSED",
          "SIMULATING", "SIMULATION_FAILED", "SIMULATION_PASSED", "TIMED_OUT", "CANCELLED"}


@dataclass
class ToolInfo:
    name: str
    executable: str | None
    version: str | None = None
    remote_host: str | None = None
    available: bool = False


def discover_tools(env: dict[str, str] | None = None) -> dict[str, ToolInfo]:
    env = os.environ if env is None else env
    host = env.get("MVERIFY_REMOTE_HOST")
    vcs_candidates = [env.get("VCS_BIN"), shutil.which("vcs"), "/tools/synopsys/verdi_supp/U-2023.03-SP1/bin/vcs", "/tools/synopsys/vcs/U-2023.03/linux/bin/vcs"]
    verdi_candidates = [env.get("VERDI_BIN"), shutil.which("verdi"), "/tools/synopsys/verdi/U-2023.03-SP1/bin/verdi"]
    def pick(candidates: list[str | None]) -> str | None:
        return next((x for x in candidates if x and (Path(x).exists() if os.path.isabs(x) else shutil.which(x))), None)
    vcs, verdi = pick(vcs_candidates), pick(verdi_candidates)
    return {
        "vcs": ToolInfo("vcs", vcs, remote_host=host, available=bool(vcs)),
        "verdi": ToolInfo("verdi", verdi, remote_host=host, available=bool(verdi)),
        "license": ToolInfo("license", env.get("SNPSLMD_LICENSE_FILE") or env.get("LM_LICENSE_FILE"), available=bool(env.get("SNPSLMD_LICENSE_FILE") or env.get("LM_LICENSE_FILE"))),
        "uvm": ToolInfo("uvm", env.get("UVM_HOME"), available=bool(env.get("UVM_HOME"))),
    }


def parse_tool_version(executable: str, timeout: float = 10.0) -> str | None:
    try:
        p = subprocess.run([executable, "-ID"], capture_output=True, text=True, timeout=timeout, check=False)
        data = p.stdout + "\n" + p.stderr
        match = re.search(r"script version\s*:\s*([^\s]+)", data, re.I)
        return match.group(1) if match else (data.strip().splitlines()[0][:240] if data.strip() else None)
    except (OSError, subprocess.TimeoutExpired):
        return None


def write_filelist(output: str | Path, sources: Sequence[str | Path], include_dirs: Sequence[str | Path] = (), defines: Sequence[str] = ()) -> Path:
    out = Path(output).resolve()
    lines = [f"+incdir+{Path(p).resolve()}" for p in include_dirs]
    lines.extend(f"+define+{d}" for d in defines)
    lines.extend(str(Path(p).resolve()) for p in sources)
    if not sources:
        raise ValueError("No RTL or testbench source files were provided")
    source_status = analyze_source_set(sources)
    if source_status["duplicate_modules"] or source_status["duplicate_packages"]:
        raise ValueError("Duplicate RTL definitions: " + ", ".join(source_status["duplicate_modules"] + source_status["duplicate_packages"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def analyze_source_set(sources: Sequence[str | Path]) -> dict:
    modules: dict[str, list[str]] = {}; packages: dict[str, list[str]] = {}; imports: dict[str, set[str]] = {}
    for item in sources:
        path = Path(item)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name in re.findall(r"\bmodule\s+(?!automatic\b|static\b)([A-Za-z_$][\w$]*)", text):
            modules.setdefault(name, []).append(str(path))
        for name in re.findall(r"\bpackage\s+(?!end\b)([A-Za-z_]\w*)\s*;", text):
            packages.setdefault(name, []).append(str(path))
        imports.setdefault(str(path), set()).update(re.findall(r"\bimport\s+([A-Za-z_]\w*)\s*::", text))
    defined = set(packages) | {"uvm_pkg"}
    unresolved = sorted({name for names in imports.values() for name in names if name not in defined})
    return {"duplicate_modules": sorted(k for k, v in modules.items() if len(v) > 1),
            "duplicate_packages": sorted(k for k, v in packages.items() if len(v) > 1),
            "unresolved_imports": unresolved,
            "module_definitions": {k:v for k,v in modules.items()},
            "package_definitions": {k:v for k,v in packages.items()}}


def compile_command(vcs: str, filelist: str | Path, build_dir: str | Path, flags: Sequence[str] = ()) -> list[str]:
    return [vcs, "-full64", "-sverilog", "-ntb_opts", "uvm-1.2", "-timescale=1ns/1ps", "-debug_access+all",
            "-f", str(Path(filelist).resolve()), "-top", "mverify_tb_top",
            "-o", str((Path(build_dir) / "simv_mverify").resolve()), *flags]


def simulation_command(executable: str | Path, test_name: str, seed: int | str = "random", plusargs: Sequence[str] = ()) -> list[str]:
    return [str(Path(executable).resolve()), f"+UVM_TESTNAME={test_name}", f"+ntb_random_seed={seed}", *plusargs]


def classify_log(text: str, exit_code: int, expected_marker: str = "MVERIFY_TEST_COMPLETE") -> tuple[str, dict]:
    fatal = len(re.findall(r"UVM_FATAL\s*:", text))
    errors = len(re.findall(r"UVM_ERROR\s*:", text))
    functional_errors = len(re.findall(r"\bMVERIFY_(?:MISMATCH|ASSERT_FAIL|FUNCTIONAL_ERROR)\b", text))
    marker = expected_marker in text
    functional_pass = "MVERIFY_FUNCTIONAL_PASS" in text
    license_error = bool(re.search(r"license.*(?:not available|checkout failed|denied)", text, re.I))
    shared_library = bool(re.search(r"error while loading shared libraries", text, re.I))
    score = re.search(r"comparisons\s*=\s*(\d+)\s+mismatches\s*=\s*(\d+)", text, re.I)
    cov = re.search(r"MVERIFY_COVERAGE.*?coverage\s*=\s*([\d.]+)", text, re.I)
    requester_grants = {int(i): int(n) for i, n in re.findall(r"requester_(\d+)_grants\s*=\s*(\d+)", text, re.I)}
    if not marker and re.search(r"(?:timeout|timed out)", text, re.I):
        status = "TIMED_OUT"
    elif exit_code != 0 or fatal or errors or functional_errors or not marker or not functional_pass:
        status = "SIMULATION_FAILED"
    else:
        status = "SIMULATION_PASSED"
    return status, {"uvm_fatal": fatal, "uvm_error": errors, "functional_errors": functional_errors,
                    "completion_marker": marker, "functional_pass_marker": functional_pass,
                    "scoreboard_comparisons": int(score.group(1)) if score else 0,
                    "scoreboard_mismatches": int(score.group(2)) if score else functional_errors,
                    "coverage_percent": float(cov.group(1)) if cov else None,
                    "requester_grants": requester_grants,
                    "license_error": license_error, "missing_shared_library": shared_library}


def run_process(args: Sequence[str], cwd: str | Path, log_path: str | Path, timeout: float = 3600,
                env: dict[str, str] | None = None, on_output: Callable[[str], None] | None = None) -> dict:
    start = time.monotonic()
    log = Path(log_path).resolve(); log.parent.mkdir(parents=True, exist_ok=True)
    try:
        p = subprocess.run(list(args), cwd=str(Path(cwd).resolve()), env=env, capture_output=True, text=True,
                           timeout=timeout, check=False)
        output = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
        code, timed_out = p.returncode, False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""; stderr = exc.stderr or ""
        if isinstance(stdout, bytes): stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes): stderr = stderr.decode(errors="replace")
        output = stdout + "\nMVERIFY_PROCESS_TIMEOUT\n" + stderr
        code, timed_out = -1, True
    except OSError as exc:
        output, code, timed_out = f"MVERIFY_PROCESS_START_ERROR: {exc}\n", -1, False
    log.write_text(output, encoding="utf-8", errors="replace")
    if on_output:
        for line in output.splitlines(): on_output(line)
    return {"command": list(args), "cwd": str(Path(cwd).resolve()), "exit_code": code,
            "runtime_seconds": round(time.monotonic()-start, 3), "timed_out": timed_out,
            "log": str(log), "output": output}


def run_compile(vcs: str, filelist: str | Path, build_dir: str | Path, flags: Sequence[str] = (), timeout: float = 900) -> dict:
    build = Path(build_dir).resolve(); build.mkdir(parents=True, exist_ok=True)
    flist = Path(filelist).resolve()
    rtl_paths = [flist.parent / line for line in flist.read_text(encoding="utf-8", errors="replace").splitlines()
                 if line.strip() and not line.startswith("+")]
    source_status = analyze_source_set(rtl_paths)
    if source_status["duplicate_modules"] or source_status["duplicate_packages"]:
        raise ValueError("Duplicate RTL definitions: " + ", ".join(source_status["duplicate_modules"] + source_status["duplicate_packages"]))
    cmd = compile_command(vcs, filelist, build, flags)
    result = run_process(cmd, Path(filelist).resolve().parent, build / "compile.log", timeout)
    simv = build / "simv_mverify"
    result["status"] = "COMPILE_PASSED" if result["exit_code"] == 0 and simv.exists() else "COMPILE_FAILED"
    result["simulator_executable"] = str(simv) if simv.exists() else None
    result["simulator_version"] = parse_tool_version(vcs)
    result["source_analysis"] = source_status
    (build / "compile.result.json").write_text(json.dumps({k:v for k,v in result.items() if k!="output"}, indent=2), encoding="utf-8")
    return result


def run_simulation(simv: str | Path, test_name: str, seed: int | str, build_dir: str | Path, timeout: float = 3600,
                   plusargs: Sequence[str] = (), dut_name: str | None = None, simulator_version: str | None = None) -> dict:
    build = Path(build_dir).resolve()
    result = run_process(simulation_command(simv, test_name, seed, plusargs), build, build / f"{test_name}.log", timeout)
    result["status"], result["checks"] = classify_log(result["output"], result["exit_code"])
    report = {k: v for k, v in result.items() if k != "output"}
    report.update({"dut": dut_name, "test_name": test_name, "seed": seed, "simulator_version": simulator_version,
                   "uvm_version": "1.2", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "waveform": None})
    (build / f"{test_name}.result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return result


def waveform_info(path: str | Path) -> dict:
    p = Path(path)
    result = {"path": str(p.resolve()), "exists": p.is_file(), "size_bytes": p.stat().st_size if p.is_file() else 0, "valid": False}
    if result["exists"] and result["size_bytes"]:
        try:
            head = p.read_bytes()[:4096]
            result["valid"] = (b"$enddefinitions" in head or b"$scope" in head or b"FSDB" in head[:16])
        except OSError:
            pass
    return result


def verdi_command(verdi: str, waveform: str | Path, filelist: str | Path | None = None, fsdb: bool = False) -> list[str]:
    return [verdi, "-ssf" if fsdb else "-vcd", str(Path(waveform).resolve()), *( ["-f", str(Path(filelist).resolve())] if filelist else [])]

