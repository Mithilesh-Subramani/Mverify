
from pathlib import Path
import json, re
from datetime import datetime

def safe(name):
    return re.sub(r"[^A-Za-z0-9_]", "_", name)

def sv_type(port):
    decl=(port.get("declaration") or "").strip()
    name=port.get("name","")
    pos=decl.rfind(name)
    prefix=decl[:pos].strip() if pos>=0 else ""
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

def generate_uvm_project(scan_report, output_dir, top_module=None):
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
            if p["name"] != "clk":
                lines.append("  %s %s;"%(sv_type(p),p["name"]))
        lines += ["  // DUT port directions: "+", ".join("%s=%s"%(p["name"],p.get("direction")) for p in plist),"endinterface"]
        (out/"interfaces"/(iname+".sv")).write_text("\n".join(lines)+"\n")
        interfaces.append("interfaces/"+iname+".sv")
    (out/"mverify_items.sv").write_text(
        "class mverify_transaction extends uvm_sequence_item;\n"
        "  `uvm_object_utils(mverify_transaction)\n"
        "  rand bit [31:0] data;\n"
        "  function new(string name=\"mverify_transaction\"); super.new(name); endfunction\n"
        "endclass\n")
    (out/"sequences/mverify_smoke_sequence.sv").write_text(
        'class mverify_smoke_sequence extends uvm_sequence #(mverify_transaction);\\n'
        '  `uvm_object_utils(mverify_smoke_sequence)\\n'
        '  function new(string name="mverify_smoke_sequence"); super.new(name); endfunction\\n'
        '  task body(); mverify_transaction tr; tr=mverify_transaction::type_id::create("tr");\\n'
        '    start_item(tr); if (!tr.randomize()) `uvm_error("RAND","Randomization failed"); finish_item(tr);\\n'
        '  endtask\\nendclass\\n')
    agent_names=[]
    pkg=["package mverify_uvm_pkg;","  import uvm_pkg::*;","  `include \"uvm_macros.svh\"",
         "  `include \"mverify_items.sv\""]
    for g in sorted(groups): pkg.append('  `include "agents/%s_agent.sv"'%safe(g))
    pkg += ['  `include "sequences/mverify_smoke_sequence.sv"',
            '  `include "env/mverify_scoreboard.sv"','  `include "env/mverify_env.sv"',
            '  `include "tests/mverify_base_test.sv"',"endpackage"]
    (out/"mverify_uvm_pkg.sv").write_text("\n".join(pkg)+"\n")
    for g, plist in sorted(groups.items()):
        gn=safe(g); a="mverify_"+gn+"_agent"; agent_names.append(a)
        vif="mverify_%s_if"%gn
        active=(gn != "clock_reset" and any(x.get("direction") in ("input","inout") and x.get("name") not in ("clk","rst_n","reset","reset_n") for x in plist))
        prefix="mverify_"+gn
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
          "    // TODO: drive the actual DUT input signals listed in this interface.",
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
          "  task run_phase(uvm_phase phase); forever begin @(posedge vif.clk);",
          "    // TODO: sample DUT outputs and publish decoded transactions.",
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
        "  function new(string name=\"mverify_scoreboard\", uvm_component parent=null); super.new(name,parent); endfunction\n"
        "  // TODO: compare observed transactions with an expected model derived from approved requirements.\n"
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
    env += ["  endfunction","  function void connect_phase(uvm_phase phase); super.connect_phase(phase);",
            "    // TODO: connect each monitor analysis port to scoreboard and coverage subscribers.",
            "  endfunction","endclass"]
    (out/"env/mverify_env.sv").write_text("\n".join(env)+"\n")
    active_name = None
    for g, plist in sorted(groups.items()):
        if g != "clock_reset" and any(x.get("direction") in ("input", "inout") and x.get("name") not in ("clk", "rst_n", "reset", "reset_n") for x in plist):
            active_name = safe(g) + "_agt"
            break
    seq_start = ('    mverify_smoke_sequence seq; seq=mverify_smoke_sequence::type_id::create("seq"); seq.start(env.%s.sequencer);\n' % active_name) if active_name else '    // No active DUT input interface was identified.\n'
    (out/"tests/mverify_base_test.sv").write_text(
        'class mverify_base_test extends uvm_test;\n'
        '  `uvm_component_utils(mverify_base_test)\n'
        '  mverify_env env;\n'
        '  function new(string name="mverify_base_test", uvm_component parent=null); super.new(name,parent); endfunction\n'
        '  function void build_phase(uvm_phase phase); super.build_phase(phase); env=mverify_env::type_id::create("env",this); endfunction\n'
        '  task run_phase(uvm_phase phase); phase.raise_objection(this);\n'
        + seq_start +
        '    phase.drop_objection(this); endtask\n'
        'endclass\n')
    top_lines=["module mverify_tb_top;","  import uvm_pkg::*;","  import mverify_uvm_pkg::*;",
               "  bit clk=0; always #5 clk=~clk;"]
    for g in sorted(groups): top_lines.append("  mverify_%s_if %s(clk);"%(safe(g),safe(g)+"_vif"))
    top_lines.append("  %s u_dut ("%top)
    connections=[]
    for port in ports:
        pn=port["name"]
        if pn=="clk": expr="clk"
        else:
            g=safe(group_for(port))
            expr="%s_vif.%s"%(g,pn)
        connections.append("    .%s(%s)"%(pn,expr))
    top_lines.append(",\n".join(connections))
    top_lines += ["  );","  initial begin"]
    for g in sorted(groups):
        vif="mverify_%s_if"%safe(g)
        path="uvm_test_top.env.%s_agt.*"%safe(g)
        top_lines.append('    uvm_config_db#(virtual %s)::set(null, "%s", "vif", %s_vif);'%(vif,path,safe(g)))
    top_lines += ['    run_test("mverify_base_test");',"  end","endmodule"]
    (out/"mverify_tb_top.sv").write_text("\n".join(top_lines)+"\n")
    manifest={"dut_top":top,"dut_ports":ports,"interface_groups":groups,
              "hierarchy":scan_report.get("hierarchy",[]),"rtl_files":scan_report.get("files",[]),
              "generated_at":datetime.utcnow().isoformat()+"Z",
              "limitations":["Review declarations against source package typedefs.",
               "DUT instance, port connections, virtual-interface config_db, protocol drivers/sequences, scoreboard and coverage need engineering completion.",
               "No simulator compile or execution was performed."]}
    (out/"mverify_generation_manifest.json").write_text(json.dumps(manifest,indent=2))
    ordered_rtl, discovered_packages = order_rtl_sources(manifest["rtl_files"])
    manifest["rtl_package_order"] = discovered_packages
    manifest["rtl_compile_order"] = ordered_rtl
    (out/"mverify_generation_manifest.json").write_text(json.dumps(manifest,indent=2))
    flist=["+incdir+.", "+incdir+interfaces", "+incdir+agents", "+incdir+env", "+incdir+tests"]
    flist += ordered_rtl+interfaces+["mverify_items.sv","mverify_uvm_pkg.sv","mverify_tb_top.sv"]
    (out/"mverify.f").write_text("\n".join(flist)+"\n")
    (out/"compile_vcs.sh").write_text(
        "#!/bin/bash\\nset -e\\n"
        "vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps "
        "-f mverify.f -top mverify_tb_top -o simv_mverify\\n")
    (out/"compile_vcs.sh").chmod(0o755)
    (out/"README_GENERATED.md").write_text(
        "# Mverify generated UVM skeleton\n\nDUT top: `%s`\n\n"%top+
        "This is an editable UVM 1.2 architecture skeleton. It uses parsed DUT port declarations and creates signal-family interfaces, UVM agents, an environment, scoreboard, base test and compile file list.\n\n"
        "## Required before simulation\n1. Review generated interface types and compile order.\n2. Add the DUT instance and named port connections.\n3. Add virtual-interface config_db setup.\n4. Implement protocol-specific sequence items, drivers and monitors.\n5. Connect monitor analysis ports to scoreboard and coverage.\n6. Compile with VCS and resolve project-specific dependencies.\n\nNo compile, simulation, functional pass, or compliance result is claimed.\n")
    return {"output_dir":str(out),"top":top,"ports":len(ports),"agents":agent_names,
            "interfaces":interfaces,"files":len(list(out.rglob("*")))}
