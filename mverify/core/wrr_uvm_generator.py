"""Active UVM generation for the RTL-confirmed pcie_wrr_arbiter contract."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path


SCENARIOS = ("reset", "single_requester", "no_request", "simultaneous", "equal_weights", "different_weights",
             "zero_weight", "maximum_weight", "continuous_contention", "random_requests", "accept_stalls",
             "request_withdrawal", "round_reload", "pointer_wraparound", "non_power_of_two", "back_to_back")


def generate_wrr_uvm(scan_report: dict, out: Path, dut: dict, selected: str, strategy: dict) -> dict:
    from .uvm_generator import order_rtl_sources
    out.mkdir(parents=True, exist_ok=True)
    for folder in ("interfaces", "agents", "env", "sequences", "tests", "build"):
        (out / folder).mkdir(parents=True, exist_ok=True)
    rtl_text = "\n".join(Path(p).read_text(encoding="utf-8", errors="ignore")
                           for p in scan_report.get("files", []) if Path(p).is_file())
    header = re.search(r"module\s+" + re.escape(selected) + r"\s*#\s*\((.*?)\)\s*\(", rtl_text, re.S)
    defaults = {name: int(value, 0) for name, value in re.findall(
        r"parameter\s+(?:int\s+)?(NUM_TC|WEIGHT_W)\s*=\s*(\d+)", header.group(1) if header else "")}
    num_tc = int(os.environ.get("MVERIFY_NUM_TC", defaults.get("NUM_TC", 8)))
    weight_w = int(os.environ.get("MVERIFY_WEIGHT_W", defaults.get("WEIGHT_W", 8)))
    if num_tc < 1 or weight_w < 1:
        raise ValueError("MVERIFY_NUM_TC and MVERIFY_WEIGHT_W must be positive integers")
    (out / "interfaces/mverify_if.sv").write_text("""interface mverify_if #(parameter int N=8, W=8, I=(N>1?$clog2(N):1))(input logic clk);
  logic rst_n; logic [N-1:0] request; logic [N*W-1:0] weight_cfg;
  logic grant_valid; logic [I-1:0] grant_index; logic [N-1:0] grant_onehot; logic grant_accept;
  property onehot; @(posedge clk) disable iff(!rst_n) grant_valid |-> $onehot(grant_onehot); endproperty
  a_onehot: assert property(onehot) else $error("MVERIFY_ASSERT_FAIL onehot");
  property index_ok; @(posedge clk) disable iff(!rst_n) grant_valid |-> grant_onehot[grant_index]; endproperty
  a_index: assert property(index_ok) else $error("MVERIFY_ASSERT_FAIL index");
  property active_only; @(posedge clk) disable iff(!rst_n) grant_valid |-> |(grant_onehot & request); endproperty
  a_active: assert property(active_only) else $error("MVERIFY_ASSERT_FAIL inactive grant");
  property positive_weight; @(posedge clk) disable iff(!rst_n) grant_valid |-> (request[grant_index] && (weight_cfg[grant_index*W+:W]!=0)); endproperty
  a_weight: assert property(positive_weight) else $error("MVERIFY_ASSERT_FAIL zero-weight or inactive grant");
  property reset_quiet; @(posedge clk) !rst_n |-> (!grant_valid && grant_onehot=='0); endproperty
  a_reset: assert property(reset_quiet) else $error("MVERIFY_ASSERT_FAIL reset outputs");
endinterface
""", encoding="utf-8")
    pkg = r'''package mverify_uvm_pkg;
  import uvm_pkg::*; `include "uvm_macros.svh"
  parameter int N=`MVERIFY_NUM_TC, W=`MVERIFY_WEIGHT_W, I=(N>1?$clog2(N):1);
  class wrr_item extends uvm_sequence_item;
    rand bit [N-1:0] req; rand bit [N*W-1:0] weights; rand bit accept; bit drive_reset, reset_value;
    `uvm_object_utils_begin(wrr_item) `uvm_field_int(req,UVM_ALL_ON) `uvm_field_int(weights,UVM_ALL_ON) `uvm_field_int(accept,UVM_ALL_ON) `uvm_field_int(drive_reset,UVM_ALL_ON) `uvm_field_int(reset_value,UVM_ALL_ON) `uvm_object_utils_end
    function new(string name="wrr_item"); super.new(name); endfunction
  endclass
  class wrr_seqr extends uvm_sequencer#(wrr_item); `uvm_component_utils(wrr_seqr) function new(string n,uvm_component p); super.new(n,p); endfunction endclass
  class wrr_driver extends uvm_driver#(wrr_item); `uvm_component_utils(wrr_driver)
    virtual mverify_if#(N,W) vif; function new(string n,uvm_component p); super.new(n,p); endfunction
    function void build_phase(uvm_phase phase); super.build_phase(phase); if(!uvm_config_db#(virtual mverify_if#(N,W))::get(this,"","vif",vif)) `uvm_fatal("NOVIF","No WRR vif") endfunction
    task run_phase(uvm_phase phase); wrr_item tr; forever begin seq_item_port.get_next_item(tr); @(negedge vif.clk); if(tr.drive_reset) begin vif.rst_n=tr.reset_value; vif.request='0; vif.weight_cfg='0; vif.grant_accept=0; end else begin vif.request=tr.req; vif.weight_cfg=tr.weights; vif.grant_accept=tr.accept; end seq_item_port.item_done(); end endtask
  endclass
  class wrr_obs extends uvm_sequence_item; `uvm_object_utils(wrr_obs)
    bit rst_n,valid,accept; bit [N-1:0] req,onehot; bit [N*W-1:0] weights; bit [I-1:0] idx; int cycle;
    function new(string n="wrr_obs"); super.new(n); endfunction endclass
  class wrr_monitor extends uvm_monitor; `uvm_component_utils(wrr_monitor)
    virtual mverify_if#(N,W) vif; uvm_analysis_port#(wrr_obs) ap; int unsigned grants[N],cycle_count;
    covergroup cov; requesters: coverpoint $countones(vif.request) { bins none={0}; bins single={1}; bins multiple={[2:N]}; }
      grant: coverpoint vif.grant_index iff(vif.grant_valid) { bins each[N]={[0:N-1]}; } accept: coverpoint vif.grant_accept;
      weight_cfg: coverpoint vif.weight_cfg[W-1:0] { bins zero={0}; bins nonzero={[1:$]}; }
      grant_x_accept: cross grant,accept; endgroup
    function new(string n,uvm_component p); super.new(n,p); ap=new("ap",this); cov=new(); endfunction
    function void build_phase(uvm_phase phase); super.build_phase(phase); if(!uvm_config_db#(virtual mverify_if#(N,W))::get(this,"","vif",vif)) `uvm_fatal("NOVIF","No monitor vif") endfunction
    task run_phase(uvm_phase phase); wrr_obs tr; forever begin @(posedge vif.clk); cycle_count++; tr=new(); tr.cycle=cycle_count; tr.rst_n=vif.rst_n; tr.req=vif.request; tr.weights=vif.weight_cfg; tr.valid=vif.grant_valid; tr.idx=vif.grant_index; tr.onehot=vif.grant_onehot; tr.accept=vif.grant_accept; if(tr.valid) grants[tr.idx]++; cov.sample(); ap.write(tr); end endtask
    function void report_phase(uvm_phase phase); super.report_phase(phase); `uvm_info("MVERIFY_COVERAGE",$sformatf("coverage=%0.2f",cov.get_coverage()),UVM_LOW) for(int x=0;x<N;x++) `uvm_info("MVERIFY_COVERAGE",$sformatf("requester_%0d_grants=%0d",x,grants[x]),UVM_LOW) endfunction
  endclass
  // Linear scan and explicit quota array are independent of the DUT prefix network.
  class wrr_model; int unsigned quota[N],ptr; function void reset(); ptr=0; foreach(quota[i]) quota[i]=0; endfunction
    function int choose(bit[N-1:0] req,bit[N*W-1:0] weights,output bit reload); bit elig[N]; bit any; int found; any=0;
      for(int i=0;i<N;i++) begin elig[i]=req[i]&&(weights[i*W+:W]!=0)&&(quota[i]!=0); any|=elig[i]; end reload=!any; found=-1;
      for(int k=0;k<N;k++) begin int i; i=(ptr+k)%N; if(found<0&&req[i]&&(weights[i*W+:W]!=0)&&(reload||elig[i])) found=i; end return found; endfunction
    function void accept_grant(int g,bit reload,bit[N-1:0] req,bit[N*W-1:0] weights); if(reload) for(int i=0;i<N;i++) quota[i]=req[i]?weights[i*W+:W]:0; quota[g]--; ptr=(g+1)%N; endfunction endclass
  class wrr_scoreboard extends uvm_component; `uvm_component_utils(wrr_scoreboard)
    uvm_analysis_imp#(wrr_obs,wrr_scoreboard) ap; wrr_model model; int comparisons,mismatches;
    function new(string n,uvm_component p); super.new(n,p); ap=new("ap",this); model=new(); model.reset(); endfunction
    function void write(wrr_obs tr); bit reload; int exp; bit[N-1:0] oh; if(!tr.rst_n) begin model.reset(); return; end exp=model.choose(tr.req,tr.weights,reload); oh='0; if(exp>=0) oh[exp]=1; comparisons++;
      if((exp>=0)!=tr.valid||(exp>=0&&exp!=tr.idx)||oh!=tr.onehot) begin mismatches++; `uvm_error("MVERIFY_MISMATCH",$sformatf("cycle=%0d expected=%0d/%b actual=%0d/%b",tr.cycle,exp,oh,tr.idx,tr.onehot)) end
      if(tr.valid&&tr.accept&&exp>=0) model.accept_grant(exp,reload,tr.req,tr.weights); endfunction
    function void report_phase(uvm_phase phase); super.report_phase(phase); `uvm_info("MVERIFY_SCOREBOARD",$sformatf("comparisons=%0d mismatches=%0d",comparisons,mismatches),UVM_NONE) if(!comparisons||mismatches) `uvm_error("MVERIFY_FUNCTIONAL_ERROR","WRR scoreboard failed") else `uvm_info("MVERIFY_FUNCTIONAL_PASS","WRR reference model passed",UVM_NONE) endfunction endclass
  class wrr_agent extends uvm_agent; `uvm_component_utils(wrr_agent) wrr_seqr seqr; wrr_driver drv; wrr_monitor mon;
    function new(string n,uvm_component p); super.new(n,p); endfunction function void build_phase(uvm_phase phase); super.build_phase(phase); mon=wrr_monitor::type_id::create("mon",this); seqr=wrr_seqr::type_id::create("seqr",this); drv=wrr_driver::type_id::create("drv",this); endfunction
    function void connect_phase(uvm_phase phase); super.connect_phase(phase); drv.seq_item_port.connect(seqr.seq_item_export); endfunction endclass
  class wrr_env extends uvm_env; `uvm_component_utils(wrr_env) wrr_agent agent; wrr_scoreboard sb;
    function new(string n,uvm_component p); super.new(n,p); endfunction function void build_phase(uvm_phase phase); super.build_phase(phase); agent=wrr_agent::type_id::create("agent",this); sb=wrr_scoreboard::type_id::create("sb",this); endfunction
    function void connect_phase(uvm_phase phase); super.connect_phase(phase); agent.mon.ap.connect(sb.ap); endfunction endclass
  class wrr_reset_sequence extends uvm_sequence#(wrr_item); `uvm_object_utils(wrr_reset_sequence)
    function new(string n="wrr_reset_sequence"); super.new(n); endfunction
    task body(); wrr_item t; repeat(2) begin t=wrr_item::type_id::create("reset_item"); start_item(t); t.drive_reset=1; t.reset_value=0; finish_item(t); end
      t=wrr_item::type_id::create("release_item"); start_item(t); t.drive_reset=1; t.reset_value=1; finish_item(t); endtask endclass
  class wrr_sequence extends uvm_sequence#(wrr_item); `uvm_object_utils(wrr_sequence) string scenario="random_requests"; int cycles=400;
    function new(string n="wrr_sequence"); super.new(n); endfunction task body(); wrr_item t; int unsigned wt; for(int c=0;c<cycles;c++) begin t=wrr_item::type_id::create("t"); start_item(t);
      if(scenario=="no_request") t.req='0; else if(scenario=="single_requester") t.req='d1; else if(scenario inside {"simultaneous","continuous_contention","round_reload","pointer_wraparound","back_to_back"}) t.req='1; else t.req=$urandom;
      for(int i=0;i<N;i++) begin if(scenario=="zero_weight") wt=(i==0)?0:1; else if(scenario=="single_requester") wt=1; else if(scenario=="maximum_weight") wt=(i==0)?{W{1'b1}}:1; else if(scenario=="equal_weights") wt=2; else if(scenario inside {"continuous_contention","round_reload","pointer_wraparound","back_to_back"}) wt=1; else if(scenario=="different_weights") wt=(i%((1<<W)-1))+1; else wt=$urandom_range(0,4); t.weights[i*W+:W]=wt; end
      t.accept=(scenario=="accept_stalls")?$urandom_range(0,1):1; if(scenario=="request_withdrawal"&&c%3==2)t.req='0; if(scenario=="non_power_of_two") begin if((N&(N-1))==0) `uvm_error("MVERIFY_FUNCTIONAL_ERROR","Set MVERIFY_NUM_TC to non-power-of-two and recompile") t.req='1; end finish_item(t); end endtask endclass
  class wrr_test extends uvm_test; `uvm_component_utils(wrr_test) wrr_env env; function new(string n,uvm_component p); super.new(n,p); endfunction
    function void build_phase(uvm_phase phase); super.build_phase(phase); env=wrr_env::type_id::create("env",this); endfunction
    function void end_of_elaboration_phase(uvm_phase phase); super.end_of_elaboration_phase(phase); uvm_top.print_topology(); endfunction
    task run_phase(uvm_phase phase); wrr_sequence seq; wrr_reset_sequence rst; string scenario; int cycles; phase.raise_objection(this); if(!$value$plusargs("MVERIFY_SCENARIO=%s",scenario)) scenario="random_requests"; if(!$value$plusargs("MVERIFY_CYCLES=%d",cycles)) cycles=400; rst=wrr_reset_sequence::type_id::create("reset_seq"); rst.start(env.agent.seqr); if(scenario!="reset") begin seq=wrr_sequence::type_id::create("seq"); seq.scenario=scenario; seq.cycles=cycles; seq.start(env.agent.seqr); end repeat(2) @(posedge env.agent.drv.vif.clk); if(scenario=="continuous_contention") for(int i=0;i<N;i++) if(!env.agent.mon.grants[i]) `uvm_error("MVERIFY_FUNCTIONAL_ERROR",$sformatf("Fairness failure: requester %0d was never granted",i)) phase.drop_objection(this); endtask
    function void report_phase(uvm_phase phase); super.report_phase(phase); `uvm_info("MVERIFY_TEST_COMPLETE","test completed",UVM_NONE) endfunction endclass
endpackage
'''
    (out / "mverify_wrr_pkg.sv").write_text(pkg, encoding="utf-8")
    tb = f'''module mverify_tb_top; import uvm_pkg::*; import mverify_uvm_pkg::*;
  localparam int N=`MVERIFY_NUM_TC,W=`MVERIFY_WEIGHT_W,I=(N>1?$clog2(N):1); bit clk=0; always #5 clk=~clk;
  mverify_if#(N,W) vif(clk); {selected}#(.NUM_TC(N),.WEIGHT_W(W)) dut(.clk(clk),.rst_n(vif.rst_n),.request(vif.request),.weight_cfg(vif.weight_cfg),.grant_valid(vif.grant_valid),.grant_index(vif.grant_index),.grant_onehot(vif.grant_onehot),.grant_accept(vif.grant_accept));
  initial begin $dumpfile("mverify.vcd"); $dumpvars(0,mverify_tb_top); vif.rst_n=0; vif.request='0; vif.weight_cfg='0; vif.grant_accept=0; repeat(3) @(negedge clk); vif.rst_n=1; uvm_config_db#(virtual mverify_if#(N,W))::set(null,"uvm_test_top.env.agent.*","vif",vif); run_test(); end
endmodule
'''
    (out / "mverify_tb_top.sv").write_text(tb, encoding="utf-8")
    ordered, packages = order_rtl_sources(scan_report.get("files", []))
    files = ["+incdir+.", f"+define+MVERIFY_NUM_TC={num_tc}", f"+define+MVERIFY_WEIGHT_W={weight_w}", *ordered,
             "interfaces/mverify_if.sv", "mverify_wrr_pkg.sv", "mverify_tb_top.sv"]
    (out / "mverify.f").write_text("\n".join(files)+"\n", encoding="utf-8")
    (out / "compile_vcs.sh").write_text("#!/usr/bin/env bash\nset -euo pipefail\nvcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps -debug_access+all -f mverify.f -top mverify_tb_top -o build/simv_mverify -l build/compile.log\n", encoding="utf-8")
    (out / "run_vcs.sh").write_text("#!/usr/bin/env bash\nset -euo pipefail\ncd \"$(dirname \"$0\")/build\"\nTEST=${1:-wrr_test}\nSCENARIO=${2:-random_requests}\nSEED=${3:-random}\n./simv_mverify +UVM_TESTNAME=$TEST +MVERIFY_SCENARIO=$SCENARIO +ntb_random_seed=$SEED -l $SCENARIO.log\n", encoding="utf-8")
    for script in (out / "compile_vcs.sh", out / "run_vcs.sh"): script.chmod(0o755)
    manifest = {"dut_top": selected, "mode": "active_confirmed_contract", "strategy": strategy,
                "parameters": {"NUM_TC": num_tc, "WEIGHT_W": weight_w},
                "scenarios": list(SCENARIOS), "rtl_files": scan_report.get("files", []), "rtl_compile_order": ordered,
                "package_order": packages, "tests": [{"test": "wrr_test", "scenario": s} for s in SCENARIOS],
                "status": "GENERATED", "verification_claim": "No compile, simulation, functional or coverage claim is made until the backend produces evidence."}
    (out / "mverify_generation_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "README_GENERATED.md").write_text("# Active WRR UVM 1.2 environment\n\nThe generated agent drives requests, weights and acceptance; its monitor samples outputs; an independent linear quota model feeds a functional scoreboard. Assertions cover one-hot, index consistency and active-request grants. Run `./compile_vcs.sh` then `./run_vcs.sh wrr_test simultaneous 1234`. Scenario profiles are parameterized by the generated NUM_TC/WEIGHT_W defines. Generated code is not verified until an actual VCS run completes.\n", encoding="utf-8")
    return {"output_dir": str(out), "top": selected, "ports": len(dut.get("ports", [])), "tests": len(SCENARIOS),
            "files": len(list(out.rglob("*"))), "mode": "active_confirmed_contract", "strategy": "weighted_round_robin"}
