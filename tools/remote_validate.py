"""RHEL-local, fixed-action validation runner. This module is not an API endpoint."""
from __future__ import annotations

import datetime
import hashlib
import json
import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def _http_json(url, payload=None, timeout=12):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,headers={"Content-Type":"application/json"} if data else {})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as res:return res.status,json.loads(res.read())
    except urllib.error.HTTPError as exc:
        try: body=json.loads(exc.read())
        except Exception: body={"error":str(exc)}
        return exc.code,body
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return None,{"error":str(exc)}


def _run(name, argv, cwd, logs, timeout=1800, env=None):
    started=time.monotonic(); path=logs/(name.replace("/","_")+".log")
    try:
        result=subprocess.run(argv,cwd=str(cwd),env=env,capture_output=True,text=True,timeout=timeout,check=False)
        out=(result.stdout or "")+"\n--- STDERR ---\n"+(result.stderr or "")
        status="PASSED" if result.returncode==0 else "FAILED"
        code=result.returncode
    except subprocess.TimeoutExpired as exc:
        stdout=exc.stdout or ""; stderr=exc.stderr or ""
        if isinstance(stdout,bytes): stdout=stdout.decode(errors="replace")
        if isinstance(stderr,bytes): stderr=stderr.decode(errors="replace")
        out=stdout+"\nVALIDATION_TIMEOUT\n"+stderr; status="TIMED_OUT"; code=None
    except OSError as exc:
        out=str(exc); status="BLOCKED"; code=None
    path.write_text(out,encoding="utf-8",errors="replace")
    return {"name":name,"status":status,"command":list(argv),"exit_code":code,
        "runtime_seconds":round(time.monotonic()-started,3),"log":str(path),"output_tail":out[-4000:]}


def _validate_project(project_path: str, top: str, results: Path, run_vcs: bool, scenario: str, seed: str) -> dict:
    from mverify.core.project_scanner import scan_project
    from mverify.core.strategy_registry import select_strategy
    from mverify.core.uvm_generator import generate_uvm_project
    from mverify.core.simulator_backend import discover_tools,run_compile,run_simulation

    project=Path(project_path).expanduser().resolve()
    roots=[Path(x.strip()).expanduser().resolve() for x in os.environ.get("MVERIFY_ALLOWED_PROJECT_ROOTS","").split(os.pathsep) if x.strip()]
    if not roots or not any(project==root or root in project.parents for root in roots):
        return {"status":"BLOCKED_ALLOWLIST","message":"Set MVERIFY_ALLOWED_PROJECT_ROOTS to server-local roots explicitly approved by the operator."}
    if not project.is_dir(): return {"status":"FAILED","message":"Allowlisted project directory does not exist."}
    project_hash=hashlib.sha256(str(project).encode()).hexdigest()[:16]
    output=results/"projects"/project_hash
    output.mkdir(parents=True,exist_ok=True)
    old_handler=signal.signal(signal.SIGALRM,lambda signum,frame: (_ for _ in ()).throw(TimeoutError("project validation exceeded 7200 second action timeout")))
    signal.alarm(7200)
    try:
        report=scan_project(project,requested_top=top or None)
        selected=report.get("selected_top")
        if not selected:return {"status":"ENGINEER_SELECTION_REQUIRED","summary":report.get("summary"),"top_candidates":report.get("top_candidates"),"warnings":report.get("warnings")}
        strategy=select_strategy(report,selected)
        generation=generate_uvm_project(report,output/"uvm",selected)
        result={"status":"ANALYZED","project_sha256_prefix":project_hash,"dut_top":selected,
            "scan_summary":report.get("summary"),"warning_count":len(report.get("warnings",[])),
            "udm_schema":report.get("universal_design_model",{}).get("schema_version"),
            "strategy":strategy.to_dict(),"generation":{k:generation.get(k) for k in ("mode","tests","files","output_dir")},
            "source_paths_remain_on_server":True}
        if not run_vcs:
            result["hardware_status"]="NOT_REQUESTED"
            return result
        if not strategy.active:
            result["hardware_status"]="BLOCKED_NO_CONFIRMED_ACTIVE_STRATEGY"
            return result
        from mverify.core.wrr_uvm_generator import SCENARIOS
        if scenario not in SCENARIOS:return {**result,"hardware_status":"FAILED_INVALID_SCENARIO"}
        tools=discover_tools(); vcs=tools["vcs"].executable
        if not vcs:return {**result,"hardware_status":"BLOCKED_VCS_NOT_FOUND"}
        compile_result=run_compile(vcs,output/"uvm"/"mverify.f",output/"uvm"/"build")
        result["compile"]={k:v for k,v in compile_result.items() if k!="output"}
        if compile_result["status"]!="COMPILE_PASSED":result["hardware_status"]="COMPILE_FAILED";return result
        simulation=run_simulation(compile_result["simulator_executable"],"wrr_test",seed,output/"uvm"/"build",
            plusargs=["+MVERIFY_SCENARIO="+scenario],dut_name=selected,simulator_version=compile_result.get("simulator_version"))
        result["simulation"]={k:v for k,v in simulation.items() if k!="output"}
        result["hardware_status"]=simulation["status"]
        return result
    except TimeoutError as exc:
        return {"status":"TIMED_OUT","project_sha256_prefix":project_hash,"error":str(exc)}
    except Exception as exc:
        return {"status":"FAILED","project_sha256_prefix":project_hash,"error":str(exc)}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM,old_handler)


def main() -> int:
    parser=argparse.ArgumentParser(description="Run fixed, local engineering validation actions on an approved RHEL host.")
    parser.add_argument("--approve-rtl",action="store_true",help="Approve reading the explicitly configured, allowlisted RTL project for scan and UVM generation.")
    parser.add_argument("--approve-vcs",action="store_true",help="Approve the fixed VCS compile/simulation action for that project.")
    args=parser.parse_args()
    results=Path(os.environ.get("MVERIFY_VALIDATION_DIR",ROOT/".mverify-validation")).expanduser().resolve()
    results.mkdir(parents=True,exist_ok=True)
    report={"schema_version":"mverify.remote-validation.v1","started_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "host":os.uname().nodename if hasattr(os,"uname") else os.environ.get("COMPUTERNAME"),
        "workspace":str(ROOT),"private_rtl_uploaded":False,"checks":[]}
    python=sys.executable
    commands=[("python_regression",[python,"-m","pytest","-q"],ROOT),
        ("project_isolated_rag_tests",[python,"-m","pytest","-q","tests/test_project_scoped_hybrid_rag.py","Mcore/tests/test_migrations_and_retrieval.py"],ROOT),
        ("engineering_reasoning_tests",[python,"-m","pytest","-q","Mcore/tests/test_engineering_reasoning.py","Mcore/tests/test_context_and_claim_validation.py"],ROOT),
        ("uvm_generation_tests",[python,"-m","pytest","-q","tests/test_uvm_generator.py","tests/test_active_verification.py"],ROOT)]
    for name,argv,cwd in commands:report["checks"].append(_run(name,argv,cwd,results))
    api_url=os.environ.get("MCORE_API_URL","http://127.0.0.1:8765/api/v1").rstrip("/")
    status,health=_http_json(api_url+"/health")
    report["mcore_health"]={"status":"PASSED" if status==200 and health.get("service")=="Mcore" else "BLOCKED",
        "http_status":status,"response":health}
    status,models=_http_json(api_url+"/models")
    report["model_status"]={"status":"PASSED" if status==200 and models.get("model_available") else "BLOCKED",
        "http_status":status,"response":models,"fallback_selected":False}
    from mcore.config import load_config
    from mcore.core.ollama import OllamaClient
    cfg=load_config()
    try:
        vector=OllamaClient().embed("synthetic retrieval health check")
        report["embedding_check"]={"status":"PASSED" if vector and isinstance(vector,list) else "FAILED",
            "model":cfg.embedding_model,"dimensions":len(vector) if vector else 0,"synthetic_input":True}
    except Exception as exc:
        report["embedding_check"]={"status":"BLOCKED","model":cfg.embedding_model,"error":str(exc),"synthetic_input":True}
    project=os.environ.get("MVERIFY_RTL_PROJECT")
    if project and args.approve_rtl:
        report["actual_rtl_integration"]=_validate_project(project,os.environ.get("MVERIFY_DUT_TOP",""),results,
            args.approve_vcs,os.environ.get("MVERIFY_SCENARIO","random_requests"),os.environ.get("MVERIFY_SEED","12345"))
    elif project:
        report["actual_rtl_integration"]={"status":"BLOCKED_APPROVAL_REQUIRED","message":"Review the allowlisted project path and rerun with --approve-rtl. Add --approve-vcs only to authorize the fixed compile/simulation action."}
    else:
        report["actual_rtl_integration"]={"status":"SKIPPED_NOT_CONFIGURED","message":"No private RTL path is read unless explicitly supplied and allowlisted on this server."}
    statuses=[x["status"] for x in report["checks"]]
    blockers=[report[x]["status"] for x in ("mcore_health","model_status","embedding_check")]
    if "FAILED" in statuses or report["actual_rtl_integration"].get("hardware_status") in ("COMPILE_FAILED","SIMULATION_FAILED","FAILED_INVALID_SCENARIO"):
        overall="FAILED"
    elif any(x!="PASSED" for x in blockers):overall="BLOCKED"
    elif report["actual_rtl_integration"].get("status") not in ("ANALYZED",) and not report["actual_rtl_integration"].get("hardware_status"):
        overall="INCOMPLETE"
    else:overall="VALIDATED_WITH_REPORTED_SCOPE"
    report["overall_status"]=overall
    report["completed_at"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
    report_path=results/"remote_validation.json"
    report_path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"overall_status":overall,"report":str(report_path)},indent=2))
    return 0 if overall=="VALIDATED_WITH_REPORTED_SCOPE" else 2


if __name__=="__main__":raise SystemExit(main())
