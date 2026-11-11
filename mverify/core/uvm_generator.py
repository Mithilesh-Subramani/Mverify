
from pathlib import Path
import json, re
from datetime import datetime, timezone
from .testcase_engine import generate_testcases

def safe(name):
    return re.sub(r"[^A-Za-z0-9_]", "_", name)

def sv_type(port):
    decl=(port.get("declaration") or "").strip()
    name=port.get("name","")
    pos=decl.rfind(name)
    prefix=decl[:pos].strip() if pos>=0 else ""
    # A DUT port declaration includes its direction (input/output/inout).
    # An interface member is a variable, not a module port declaration.
    prefix=re.sub(r"^\s*(input|output|inout|ref)\b\s*", "", prefix)
    prefix=re.sub(r"\bvar\b", "", prefix).strip()
    if not prefix:
        width=port.get("width","scalar/unspecified")
        prefix="logic "+(width if width!="scalar/unspecified" else "")
    return prefix

def group_for(port):
    n=port.get("name","").lower()
    for prefix in ("req_","rx_","link_","backend_","tc_","cfg_","fc_","replay_","crc_","sequence_","ecrc_","completion_"):
        if n.startswith(prefix): return prefix[:-1]
    if n in ("clk","rst_n","reset","reset_n"): return "clock_reset"
    if "ack" in n or "nak" in n: return "ack"
    return "misc"


def order_rtl_sources(files):
    """Put SystemVerilog packages before modules that import/use them."""
    paths=[str(x) for x in files if str(x).lower().endswith((".sv",".svh",".v",".vh"))]
    package_defs={}
    package_imports={}
    package_refs={}
    for path in paths:
        try:
            source=Path(path).read_text(errors="ignore")
        except Exception:
            continue
        defs=re.findall(r"\bpackage\s+(?!end\b)([A-Za-z_]\w*)\s*;",source)
        imports=re.findall(r"\bimport\s+([A-Za-z_]\w*)\s*::",source)
        # Package-qualified type references, e.g. pcie_pkg::txn_kind_e.
        refs=re.findall(r"\b([A-Za-z_]\w*)\s*::",source)
        for name in defs:
            package_defs[name]=path
            package_imports.setdefault(path,set()).update(imports)
            package_refs.setdefault(path,set()).update(refs)
    package_paths=set(package_defs.values())
    deps={}
    for pkg,path in package_defs.items():
        needed=(package_imports.get(path,set()) | package_refs.get(path,set()))
        deps.setdefault(path,set()).update(package_defs[x] for x in needed if x in package_defs and package_defs[x]!=path)
    ordered=[]
    visiting=set()
    visited=set()
    def visit(path):
        if path in visited: return
        if path in visiting: return
        visiting.add(path)
        for dep in sorted(deps.get(path,())): visit(dep)
        visiting.remove(path)
        visited.add(path)
        ordered.append(path)
    for path in sorted(package_paths): visit(path)
    # Keep non-package RTL after package declarations. Preserve original relative order.
    ordered.extend(x for x in paths if x not in package_paths)
    return ordered, sorted(package_defs.keys())

def generate_uvm_project(scan_report, output_dir, top_module=None, architecture=None):
    modules=scan_report.get("module_details",[])
    top=top_module or scan_report.get("selected_top")
    if not top:
        c=scan_report.get("top_candidates",[])
        if len(c)==1: top=c[0]
    dut=next((m for m in modules if m.get("name")==top),None)
    if not dut: raise ValueError("Select a valid DUT top module before UVM generation.")
    ports=dut.get("ports",[])
    if not ports: raise ValueError("No DUT ports were parsed. Generation stopped to avoid inventing an interface.")
    out=Path(output_dir).expanduser().resolve()
    for d in ("interfaces","agents","env","sequences","tests"): (out/d).mkdir(parents=True,exist_ok=True)
    groups={}
    for p in ports: groups.setdefault(group_for(p),[]).append(p)
    interfaces=[]
    for g, plist in sorted(groups.items()):
        iname="mverify_"+safe(g)+"_if"
        lines=["interface %s(input logic clk);"%iname]
        for p in plist:
            if p["name"].lower() not in ("clk", "clock"):
                lines.append("  %s %s;"%(sv_type(p),p["name"]))
        lines += ["  // DUT port directions: "+", ".join("%s=%s"%(p["name"],p.get("direction")) for p in plist),"endinterface"]
        (out/"interfaces"/(iname+".sv")).write_text("\n".join(lines)+"\n")
        interfaces.append("interfaces/"+iname+".sv")
    (out/"mverify_items.sv").write_text(
        "class mverify_transaction extends uvm_sequence_item;\n"
        "  `uvm_object_utils(mverify_transaction)\n"
        "  rand bit [31:0] data;\n"
        "  int unsigned sample_cycle;\n"
        "  function new(string name=\"mverify_transaction\"); super.new(name); endfunction\n"
        "endclass\n"
        "class mverify_smoke_sequence extends uvm_sequence #(mverify_transaction);\n"
        "  `uvm_object_utils(mverify_smoke_sequence)\n"
        "  int unsigned item_count=16;\n"
        "  function new(string name=\"mverify_smoke_sequence\"); super.new(name); endfunction\n"
        "  task body(); mverify_transaction tr; repeat(item_count) begin\n"
        "    tr=mverify_transaction::type_id::create(\"tr\");\n"
        "    start_item(tr); if(!tr.randomize()) `uvm_fatal(\"RAND\",\"Smoke item randomization failed\"); finish_item(tr);\n"
        "  end endtask\n"
        "endclass\n")
    agent_names=[]
    pkg=["package mverify_uvm_pkg;","  import uvm_pkg::*;","  `include \"uvm_macros.svh\"",
         "  `include \"mverify_items.sv\""]
    for g in sorted(groups): pkg.append('  `include "agents/%s_agent.sv"'%safe(g))
    pkg += ['  `include "env/mverify_scoreboard.sv"','  `include "env/mverify_env.sv"',
            '  `include "tests/mverify_base_test.sv"',"endpackage"]
    (out/"mverify_uvm_pkg.sv").write_text("\n".join(pkg)+"\n")
    for g, plist in sorted(groups.items()):
        gn=safe(g); a="mverify_"+gn+"_agent"; agent_names.append(a)
        vif="mverify_%s_if"%gn
        # Generate bounded structural smoke stimulus only for non-reset DUT inputs.
        # This is not labelled as protocol-legal traffic without an approved model.
        drive_ports=[p for p in plist if p.get("direction")=="input" and p.get("name") not in ("clk","clock") and p.get("name"," ").lower() not in ("rst","rst_n","reset","reset_n","aresetn","areset")]
        active=bool(drive_ports)
        prefix="mverify_"+gn
        drive_stmt=(" ".join("vif.%s <= tr.data;"%x["name"] for x in drive_ports)) if drive_ports else "/* no non-reset input on this interface */"
        output_ports=[p for p in plist if p.get("direction")=="output"]
        sample_stmt=("tr.data = vif.%s;"%output_ports[0]["name"]) if output_ports else "tr.data = '0;"
        lines=[
          "class %s_sequencer extends uvm_sequencer #(mverify_transaction);"%prefix,
          "  `uvm_component_utils(%s_sequencer)"%prefix,
          '  function new(string name="%s_sequencer", uvm_component parent=null); super.new(name,parent); endfunction'%prefix,
          "endclass",
          "class %s_driver extends uvm_driver #(mverify_transaction);"%prefix,
          "  `uvm_component_utils(%s_driver)"%prefix,
          "  virtual %s vif;"%vif,
          '  function new(string name="%s_driver", uvm_component parent=null); super.new(name,parent); endfunction'%prefix,
          "  function void build_phase(uvm_phase phase); super.build_phase(phase);",
          '    if (!uvm_config_db#(virtual %s)::get(this, "", "vif", vif)) `uvm_fatal("NOVIF", "Virtual interface not configured")'%vif,
          "  endfunction",
          "  task run_phase(uvm_phase phase); mverify_transaction tr; forever begin",
          "    seq_item_port.get_next_item(tr);",
          "    @(negedge vif.clk); %s"%drive_stmt,
          "    @(posedge vif.clk); seq_item_port.item_done();",
          "  end endtask",
          "endclass",
          "class %s_monitor extends uvm_monitor;"%prefix,
          "  `uvm_component_utils(%s_monitor)"%prefix,
          "  virtual %s vif;"%vif,
          "  uvm_analysis_port #(mverify_transaction) ap;",
          '  function new(string name="%s_monitor", uvm_component parent=null); super.new(name,parent); endfunction'%prefix,
          "  function void build_phase(uvm_phase phase); super.build_phase(phase); ap=new(\"ap\",this);",
          '    if (!uvm_config_db#(virtual %s)::get(this, "", "vif", vif)) `uvm_fatal("NOVIF", "Virtual interface not configured")'%vif,
          "  endfunction",
          "  int unsigned cycle_count=0;",
          "  task run_phase(uvm_phase phase); mverify_transaction tr; forever begin @(posedge vif.clk); cycle_count++;",
          "    tr=mverify_transaction::type_id::create(\"observed\"); tr.sample_cycle=cycle_count; %s ap.write(tr);"%sample_stmt,
          "  end endtask",
          "endclass",
          "class %s extends uvm_agent;"%a,
          "  `uvm_component_utils(%s)"%a,
          "  %s_monitor monitor;"%prefix,
          "  uvm_analysis_port #(mverify_transaction) ap;",
        ]
        if active:
            lines += ["  %s_sequencer sequencer;"%prefix,"  %s_driver driver;"%prefix]
        lines += [
          '  function new(string name="%s", uvm_component parent=null); super.new(name,parent); endfunction'%a,
          "  function void build_phase(uvm_phase phase); super.build_phase(phase);",
          '    monitor=%s_monitor::type_id::create("monitor",this);'%prefix]
        if active:
            lines += ['    sequencer=%s_sequencer::type_id::create("sequencer",this);'%prefix,
                      '    driver=%s_driver::type_id::create("driver",this);'%prefix]
        lines += ["    ap=new(\"ap\",this);","  endfunction",
                  "  function void connect_phase(uvm_phase phase); super.connect_phase(phase);"]
        if active: lines += ["    driver.seq_item_port.connect(sequencer.seq_item_export);"]
        lines += ["    monitor.ap.connect(ap);","  endfunction","endclass"]
        (out/"agents"/(gn+"_agent.sv")).write_text("\n".join(lines)+"\n")
    (out/"env/mverify_scoreboard.sv").write_text(
        "class mverify_scoreboard extends uvm_component;\n"
        "  `uvm_component_utils(mverify_scoreboard)\n"
        "  uvm_analysis_imp #(mverify_transaction,mverify_scoreboard) observed_export;\n"
        "  int unsigned observed_count=0; int unsigned unknown_sample_count=0;\n"
        "  int unsigned functional_checks=0; int unsigned functional_errors=0;\n"
        "  function new(string name=\"mverify_scoreboard\", uvm_component parent=null); super.new(name,parent); endfunction\n"
        "  function void build_phase(uvm_phase phase); super.build_phase(phase); observed_export=new(\"observed_export\",this); endfunction\n"
        "  function void write(mverify_transaction tr); observed_count++;\n"
        "    if ($isunknown(tr.data)) begin unknown_sample_count++; `uvm_error(\"MVERIFY_X\",$sformatf(\"Unknown observed output at cycle %0d\",tr.sample_cycle)); end\n"
        "    // Functional comparisons are enabled only when a requirement-derived reference model is attached.\n"
        "  endfunction\n"
        "  function void report_phase(uvm_phase phase); super.report_phase(phase);\n"
        "    `uvm_info(\"MVERIFY_SCOREBOARD\",$sformatf(\"observed=%0d unknown_samples=%0d functional_checks=%0d functional_errors=%0d\",observed_count,unknown_sample_count,functional_checks,functional_errors),UVM_LOW)\n"
        "    if(observed_count==0) `uvm_warning(\"MVERIFY_NO_OBS\",\"No monitor observations were received\");\n"
        "  endfunction\n"
        "endclass\n")
    env=["class mverify_env extends uvm_env;","  `uvm_component_utils(mverify_env)",
         "  mverify_scoreboard scoreboard;"]
    names=[]
    for a in agent_names:
        n=a.replace("mverify_","").replace("_agent","_agt"); names.append((a,n)); env.append("  %s %s;"%(a,n))
    env += ['  function new(string name="mverify_env", uvm_component parent=null); super.new(name,parent); endfunction',
            "  function void build_phase(uvm_phase phase); super.build_phase(phase);",
            '    scoreboard = mverify_scoreboard::type_id::create("scoreboard", this);']
    for a,n in names: env.append('    %s = %s::type_id::create("%s", this);'%(n,a,n))
    env += ["  endfunction","  function void connect_phase(uvm_phase phase); super.connect_phase(phase);"]
    for a,n in names: env.append("    %s.monitor.ap.connect(scoreboard.observed_export);"%n)
    env += ["  endfunction","endclass"]
    (out/"env/mverify_env.sv").write_text("\n".join(env)+"\n")
    base_lines=[
        'class mverify_base_test extends uvm_test;',
        '  `uvm_component_utils(mverify_base_test)',
        '  mverify_env env;',
        '  function new(string name="mverify_base_test", uvm_component parent=null); super.new(name,parent); endfunction',
        '  function void build_phase(uvm_phase phase); super.build_phase(phase); env=mverify_env::type_id::create("env",this); endfunction',
        '  task run_phase(uvm_phase phase); phase.raise_objection(this);',
        '    `uvm_info("MVERIFY_SMOKE", "Running bounded structural input activity and output observation. This is not protocol-functional verification.", UVM_LOW)',
    ]
    for a,n in names:
        group=a.replace("mverify_","").replace("_agent","")
        if any(p.get("direction")=="input" and p.get("name") not in ("clk","clock") and p.get("name"," ").lower() not in ("rst","rst_n","reset","reset_n","aresetn","areset") for p in groups.get(group,[])):
            base_lines.append('    begin mverify_smoke_sequence seq; seq=mverify_smoke_sequence::type_id::create("seq_%s"); seq.start(env.%s_agt.sequencer); end'%(group,group))
    base_lines += ['    #20; phase.drop_objection(this);','  endtask','endclass']
    (out/"tests/mverify_base_test.sv").write_text("\n".join(base_lines)+"\n")
    top_lines=["module mverify_tb_top;","  import uvm_pkg::*;","  import mverify_uvm_pkg::*;",
               "  bit clk=0; always #5 clk=~clk;"]
    for g in sorted(groups): top_lines.append("  mverify_%s_if %s(clk);"%(safe(g),safe(g)+"_vif"))
    top_lines.append("  %s u_dut ("%top)
    connections=[]
    for port in ports:
        pn=port["name"]
        if pn.lower() in ("clk", "clock"): expr="clk"
        else:
            g=safe(group_for(port))
            expr="%s_vif.%s"%(g,pn)
        connections.append("    .%s(%s)"%(pn,expr))
    top_lines.append(",\n".join(connections))
    top_lines += ["  );","  initial begin"]
    for port in ports:
        pn=port.get("name","")
        low=pn.lower()
        if port.get("direction")=="input" and (low in ("rst","rst_n","reset","reset_n","aresetn","areset") or low.endswith("_reset") or low.endswith("_rst_n")):
            g=safe(group_for(port)); vif=safe(g)+"_vif"
            active_level="1'b0" if low.endswith("_n") or low=="aresetn" else "1'b1"
            inactive_level="1'b1" if active_level=="1'b0" else "1'b0"
            top_lines.append("    %s.%s = %s;"%(vif,pn,active_level))
            top_lines.append("    repeat (5) @(posedge clk);")
            top_lines.append("    %s.%s = %s;"%(vif,pn,inactive_level))
    for g in sorted(groups):
        vif="mverify_%s_if"%safe(g)
        path="uvm_test_top.env.%s_agt.*"%safe(g)
        top_lines.append('    uvm_config_db#(virtual %s)::set(null, "%s", "vif", %s_vif);'%(vif,path,safe(g)))
    top_lines += ['    run_test("mverify_base_test");',"  end","endmodule"]
    (out/"mverify_tb_top.sv").write_text("\n".join(top_lines)+"\n")
    testcase_catalog=generate_testcases(scan_report)
    (out/"verification_testcases.json").write_text(json.dumps(testcase_catalog,indent=2))
    manifest={"dut_top":top,"dut_ports":ports,"interface_groups":groups,
              "hierarchy":scan_report.get("hierarchy",[]),"rtl_files":scan_report.get("files",[]),
              "generated_at":datetime.now(timezone.utc).isoformat(),
              "generation_mode":"structural_smoke_with_observation",
              "limitations":["This output is a compile/topology scaffold, not a functional PCIe testbench.",
                             "Bounded structural input activity is generated for non-reset inputs; it is not protocol-legal stimulus.",
                             "Monitors sample one representative output per interface group; functional scoreboarding requires an approved reference model.",
                             "Review declarations against source package typedefs.",
               "Protocol-specific transaction decoding, independent reference models, assertions and functional coverage require approved interface semantics.",
               "No simulator compile or execution was performed."]}
    (out/"mverify_generation_manifest.json").write_text(json.dumps(manifest,indent=2))
    ordered_rtl, discovered_packages = order_rtl_sources(manifest["rtl_files"])
    manifest["rtl_package_order"] = discovered_packages
    manifest["rtl_compile_order"] = ordered_rtl
    (out/"mverify_generation_manifest.json").write_text(json.dumps(manifest,indent=2))
    flist=["+incdir+.", "+incdir+interfaces", "+incdir+agents", "+incdir+env", "+incdir+tests"]
    flist += ordered_rtl+interfaces+["mverify_uvm_pkg.sv","mverify_tb_top.sv"]
    (out/"mverify.f").write_text("\n".join(flist)+"\n")
    (out/"compile_vcs.sh").write_text(
        "#!/bin/bash\nset -e\n"
        "vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps "
        "-f mverify.f -top mverify_tb_top -o simv_mverify\n")
    (out/"compile_vcs.sh").chmod(0o755)
    (out/"README_GENERATED.md").write_text(
        "# Mverify generated UVM project\n\nDUT top: `%s`\n\n"%top+
        "This is an editable UVM 1.2 structural smoke environment. It creates bounded input activity for non-reset input ports, samples representative outputs, connects monitor analysis ports to a scoreboard, and reports unknown observations.\n\n"
        "## Before functional verification\n1. Review reset polarity, timing, interface directions and generated drive assignments.\n2. Confirm that the structural smoke stimulus is legal for this DUT.\n3. Add an independent requirement-derived reference model and functional comparisons.\n4. Add protocol transaction decoding, assertions and functional coverage.\n5. Compile with VCS and resolve project-specific dependencies.\n\nThe base test performs bounded structural input activity. The scoreboard counts observations and reports unknown samples. This is not a protocol-functional pass or PCIe compliance result. Suggested scenarios are proposals and require engineer approval. See `verification_testcases.json`.\n")
    (out/"GENERATION_STATUS.md").write_text(
        "# Mverify generated UVM status\n\n"
        "Generation mode: **bounded structural stimulus and output observation**.\n\n"
        "The generated driver applies the same bounded 32-bit smoke value to non-reset input signals in its interface group. The monitor samples one representative output per group. The scoreboard counts observations and flags unknown samples. It does not contain a DUT-specific functional oracle.\n\n"
        "A successful run proves only that this structural smoke environment executes. It does not prove protocol functionality or PCIe compliance. Use the generated scenario catalog and approved requirements to add an independent reference model.\n")
    architecture = architecture or {"id":"passive", "name":"Passive observation-first", "agents":[]}
    (out/"APPROVED_ARCHITECTURE.json").write_text(json.dumps({
        "selected_architecture": architecture,
        "dut_top": top,
        "approval_scope": "Topology proposal only. Signal semantics and active pin-level drivers require explicit review.",
        "interface_candidates": groups,
        "active_driver_generation": "blocked_until_signal_mapping_approval"
    }, indent=2))
    manifest["selected_architecture"] = architecture
    manifest["active_driver_generation"] = "blocked_until_signal_mapping_approval"
    (out/"mverify_generation_manifest.json").write_text(json.dumps(manifest,indent=2))
    return {"output_dir":str(out),"top":top,"ports":len(ports),"agents":agent_names,
            "interfaces":interfaces,"files":len(list(out.rglob("*")))}
