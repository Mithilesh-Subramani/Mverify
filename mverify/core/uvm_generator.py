
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


def generate_uvm_project(scan_report, output_dir, top_module=None, architecture=None,
                         requirements=None, observation_cycles=20):
    """Generate a passive, compile-oriented UVM environment plus reviewed test stubs.

    No DUT input is driven automatically. Port-name heuristics are not a safe
    substitute for a protocol mapping. The generated topology and monitors are
    real; active sequences are explicit templates pending engineer approval.
    """
    modules = scan_report.get("module_details", [])
    top = top_module or scan_report.get("selected_top")
    if not top:
        candidates = scan_report.get("top_candidates", [])
        if len(candidates) == 1:
            top = candidates[0]
    dut = next((m for m in modules if m.get("name") == top), None)
    if not dut:
        raise ValueError("Select a valid DUT top module before UVM generation.")
    ports = dut.get("ports", [])
    if not ports:
        raise ValueError("No DUT ports were parsed. Generation stopped.")

    out = Path(output_dir).expanduser().resolve()
    for folder in ("interfaces", "agents", "env", "sequences", "tests", "scripts"):
        (out/folder).mkdir(parents=True, exist_ok=True)

    def ident(value):
        return safe(value) or "unnamed"

    # One DUT interface avoids speculative signal grouping and cross-interface
    # connection errors. All parsed top-level ports are connected exactly once.
    if_name = "mverify_dut_if"
    interface_lines = [f"interface {if_name}(input logic clk);"]
    type_packages = sorted({pkg for port in ports
                            for pkg in re.findall(r"\b([A-Za-z_]\w*)\s*::", port.get("declaration", ""))})
    for package_name in type_packages:
        interface_lines.append(f"  import {package_name}::*;")
    for port in ports:
        name = port.get("name", "")
        if not name or name.lower() in ("clk", "clock"):
            continue
        width = port.get("width", "scalar/unspecified")
        decl = sv_type(port)
        if not decl or decl == "logic":
            decl = "logic"
        interface_lines.append(f"  {decl} {name};")
    interface_lines += ["endinterface", ""]
    (out/"interfaces"/(if_name+".sv")).write_text("\n".join(interface_lines))

    # Preserve typed per-port observations in the transaction.
    item = [
        "class mverify_observation extends uvm_sequence_item;",
        "  `uvm_object_utils(mverify_observation)",
        "  int unsigned sample_cycle;"
    ]
    for port in ports:
        name = port.get("name", "")
        if not name or name.lower() in ("clk", "clock"):
            continue
        item_type = sv_type(port) or "logic"
        item.append(f"  {item_type} {name};")
    item += [
        '  function new(string name="mverify_observation"); super.new(name); endfunction',
        "endclass", ""
    ]
    (out/"mverify_items.sv").write_text("\n".join(item))

    # Passive monitor samples every DUT output. Inputs are sampled as context.
    sample_assignments = []
    for port in ports:
        name = port.get("name", "")
        if name and name.lower() not in ("clk", "clock"):
            sample_assignments.append(f"      tr.{name} = vif.{name};")
    monitor = [
        "class mverify_monitor extends uvm_monitor;",
        "  `uvm_component_utils(mverify_monitor)",
        f"  virtual {if_name} vif;",
        "  uvm_analysis_port #(mverify_observation) ap;",
        "  int unsigned cycle_count=0;",
        '  function new(string name="mverify_monitor", uvm_component parent=null); super.new(name,parent); endfunction',
        "  function void build_phase(uvm_phase phase);",
        "    super.build_phase(phase); ap=new(\"ap\",this);",
        f'    if (!uvm_config_db#(virtual {if_name})::get(this, "", "vif", vif))',
        '      `uvm_fatal("NOVIF", "mverify_dut_if was not configured")',
        "  endfunction",
        "  task run_phase(uvm_phase phase);",
        "    mverify_observation tr;",
        "    forever begin",
        "      @(posedge vif.clk); cycle_count++;",
        '      tr=mverify_observation::type_id::create("observation");',
        "      tr.sample_cycle=cycle_count;"
    ] + sample_assignments + [
        "      ap.write(tr);",
        "    end",
        "  endtask",
        "endclass", ""
    ]
    (out/"agents/mverify_monitor.sv").write_text("\n".join(monitor))

    scoreboard = [
        "class mverify_scoreboard extends uvm_component;",
        "  `uvm_component_utils(mverify_scoreboard)",
        "  uvm_analysis_imp #(mverify_observation,mverify_scoreboard) observed_export;",
        "  int unsigned observed_count=0;",
        '  function new(string name="mverify_scoreboard", uvm_component parent=null); super.new(name,parent); endfunction',
        '  function void build_phase(uvm_phase phase); super.build_phase(phase); observed_export=new("observed_export",this); endfunction',
        "  function void write(mverify_observation tr);",
        "    observed_count++;",
        '    `uvm_info("MVERIFY_OBS",$sformatf("cycle=%0d observation=%0d",tr.sample_cycle,observed_count),UVM_HIGH)',
        "  endfunction",
        "  function void report_phase(uvm_phase phase);",
        "    super.report_phase(phase);",
        '    `uvm_info("MVERIFY_SCOREBOARD",$sformatf("Observed samples: %0d",observed_count),UVM_LOW)',
        '    if (observed_count==0) `uvm_warning("MVERIFY_NO_OBS","No DUT observations were captured")',
        "  endfunction",
        "endclass", ""
    ]
    (out/"env/mverify_scoreboard.sv").write_text("\n".join(scoreboard))

    agent = [
        "class mverify_agent extends uvm_agent;",
        "  `uvm_component_utils(mverify_agent)",
        "  mverify_monitor monitor;",
        "  uvm_analysis_port #(mverify_observation) ap;",
        '  function new(string name="mverify_agent", uvm_component parent=null); super.new(name,parent); endfunction',
        "  function void build_phase(uvm_phase phase);",
        '    super.build_phase(phase); monitor=mverify_monitor::type_id::create("monitor",this); ap=new("ap",this);',
        "  endfunction",
        "  function void connect_phase(uvm_phase phase); super.connect_phase(phase); monitor.ap.connect(ap); endfunction",
        "endclass", ""
    ]
    (out/"agents/mverify_agent.sv").write_text("\n".join(agent))

    env = [
        "class mverify_env extends uvm_env;",
        "  `uvm_component_utils(mverify_env)",
        "  mverify_agent dut_agent;",
        "  mverify_scoreboard scoreboard;",
        '  function new(string name="mverify_env", uvm_component parent=null); super.new(name,parent); endfunction',
        "  function void build_phase(uvm_phase phase);",
        '    super.build_phase(phase); dut_agent=mverify_agent::type_id::create("dut_agent",this);',
        '    scoreboard=mverify_scoreboard::type_id::create("scoreboard",this);',
        "  endfunction",
        "  function void connect_phase(uvm_phase phase);",
        "    super.connect_phase(phase); dut_agent.ap.connect(scoreboard.observed_export);",
        "  endfunction",
        "endclass", ""
    ]
    (out/"env/mverify_env.sv").write_text("\n".join(env))

    # Scenario descriptions are emitted as selectable UVM test classes. They
    # observe the DUT only; stimulus is intentionally not guessed.
    catalog = generate_testcases(scan_report, requirements=requirements or [])
    test_names = []
    test_lines = [
        "class mverify_base_test extends uvm_test;",
        "  `uvm_component_utils(mverify_base_test)",
        "  mverify_env env;",
        '  function new(string name="mverify_base_test", uvm_component parent=null); super.new(name,parent); endfunction',
        "  function void build_phase(uvm_phase phase);",
        '    super.build_phase(phase); env=mverify_env::type_id::create("env",this);',
        "  endfunction",
        "  function void end_of_elaboration_phase(uvm_phase phase);",
        "    super.end_of_elaboration_phase(phase);",
        '    `uvm_info("MVERIFY_TOPOLOGY","Printing UVM component topology",UVM_LOW)',
        "    uvm_top.print_topology();",
        "  endfunction",
        "  task run_phase(uvm_phase phase);",
        "    phase.raise_objection(this);",
        '    `uvm_info("MVERIFY_BASE","Passive DUT observation test. No unapproved input stimulus is applied.",UVM_LOW)',
        f"    repeat ({max(1, int(observation_cycles))}) @(posedge env.dut_agent.monitor.vif.clk);",
        "    phase.drop_objection(this);",
        "  endtask",
        "endclass", ""
    ]
    base_start = next(i for i, line in enumerate(test_lines) if line.startswith("class mverify_base_test"))
    base_end = test_lines.index("endclass", base_start) + 1
    base_source = "\n".join(test_lines[:base_end]) + "\n"
    (out/"tests/mverify_base_test.sv").write_text(base_source)
    scenario_lines = []
    for case in catalog.get("generated", []) + catalog.get("suggested", []):
        cname = "mverify_" + ident(case.get("id", "case")).lower() + "_test"
        test_names.append({"id": case.get("id"), "name": case.get("name"),
                           "uvm_test": cname, "kind": case.get("kind"),
                           "oracle": case.get("oracle")})
        scenario_lines += [
            f"class {cname} extends mverify_base_test;",
            f"  `uvm_component_utils({cname})",
            f'  function new(string name="{cname}", uvm_component parent=null); super.new(name,parent); endfunction',
            "  function void end_of_elaboration_phase(uvm_phase phase);",
            "    super.end_of_elaboration_phase(phase);",
            f'    `uvm_info("MVERIFY_CASE","Scenario: {case.get("name","").replace(chr(34), chr(39))}",UVM_LOW)',
            '    `uvm_warning("MVERIFY_REVIEW","This case is an observation/scenario stub. Add approved stimulus and an independent expected-result model before claiming functional verification.")',
            "  endfunction",
            "endclass", ""
        ]
    (out/"tests/mverify_tests.sv").write_text("\n".join(scenario_lines) + "\n")

    pkg = [
        "package mverify_uvm_pkg;",
        "  import uvm_pkg::*;",
        *[f"  import {package_name}::*;" for package_name in type_packages],
        '  `include "uvm_macros.svh"',
        '  `include "mverify_items.sv"',
        '  `include "agents/mverify_monitor.sv"',
        '  `include "agents/mverify_agent.sv"',
        '  `include "env/mverify_scoreboard.sv"',
        '  `include "env/mverify_env.sv"',
        '  `include "tests/mverify_base_test.sv"',
        '  `include "tests/mverify_tests.sv"',
        "endpackage", ""
    ]
    (out/"mverify_uvm_pkg.sv").write_text("\n".join(pkg))

    top_lines = [
        "module mverify_tb_top;",
        "  import uvm_pkg::*;",
        "  import mverify_uvm_pkg::*;",
        "  bit clk=0;",
        "  always #5 clk=~clk;",
        f"  {if_name} dut_if(clk);",
        f"  {top} u_dut ("
    ]
    conns = []
    for port in ports:
        name = port.get("name")
        if not name:
            continue
        expr = "clk" if name.lower() in ("clk", "clock") else f"dut_if.{name}"
        conns.append(f"    .{name}({expr})")
    top_lines += [",\n".join(conns), "  );",
                  "  initial begin",
                  '    uvm_config_db#(virtual mverify_dut_if)::set(null,"uvm_test_top.env.dut_agent.monitor","vif",dut_if);',
                  '    run_test();',
                  "  end",
                  "endmodule", ""]
    (out/"mverify_tb_top.sv").write_text("\n".join(top_lines))

    # Sequence template is deliberately non-runnable until the engineer maps
    # a legal transaction to actual DUT pins and adds protocol timing.
    seq_template = [
        "// REVIEW TEMPLATE ONLY: do not add to compile list until signal mapping is approved.",
        "class mverify_protocol_sequence extends uvm_sequence #(mverify_observation);",
        "  `uvm_object_utils(mverify_protocol_sequence)",
        '  function new(string name="mverify_protocol_sequence"); super.new(name); endfunction',
        "  task body();",
        '    `uvm_warning("MVERIFY_TODO","Map a legal protocol transaction to confirmed DUT inputs before enabling a driver.")',
        "    // TODO: Add requirement-derived fields, constraints and legal timing.",
        "    // TODO: Add a dedicated driver/sequencer after clock/reset/handshake review.",
        "  endtask",
        "endclass", ""
    ]
    (out/"sequences/mverify_protocol_sequence_TEMPLATE.sv").write_text("\n".join(seq_template))

    topology_preview = [
        "UVM TOPOLOGY PREVIEW (generated hierarchy; runtime output is printed by UVM)",
        "uvm_test_top : mverify_base_test",
        "  env : mverify_env",
        "    dut_agent : mverify_agent",
        "      monitor : mverify_monitor",
        "    scoreboard : mverify_scoreboard",
        "",
        "Runtime topology is printed during end_of_elaboration_phase with uvm_top.print_topology().",
        "This preview is the expected component tree. Use the simulator log for the actual factory-built topology."
    ]
    (out/"uvm_topology.txt").write_text("\\n".join(topology_preview) + "\\n")

    ordered_rtl, discovered_packages = order_rtl_sources(scan_report.get("files", []))
    manifest = {
        "dut_top": top, "dut_ports": ports,
        "hierarchy": scan_report.get("hierarchy", []),
        "rtl_files": scan_report.get("files", []),
        "rtl_package_order": discovered_packages,
        "rtl_compile_order": ordered_rtl,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_mode": "passive_observation_with_test_stubs",
        "uvm_tests": test_names,
        "topology_print": "uvm_top.print_topology() in mverify_base_test.end_of_elaboration_phase",
        "limitations": [
            "All DUT top-level ports are connected to one virtual interface. This is a top-level pin map, not resolved internal connectivity.",
            "No DUT input is driven automatically. Signal names do not establish protocol semantics.",
            "Generated test classes are selectable observation/scenario stubs, not functional tests.",
            "The protocol sequence file is a review template and is not compiled.",
            "A functional scoreboard requires a requirement-derived independent reference model.",
            "Compile and simulate with the target simulator. Mverify does not claim simulation success."
        ],
        "selected_architecture": architecture or {"id":"passive","name":"Passive observation-first"}
    }
    (out/"mverify_generation_manifest.json").write_text(json.dumps(manifest, indent=2))
    (out/"verification_testcases.json").write_text(json.dumps(catalog, indent=2))
    (out/"APPROVED_ARCHITECTURE.json").write_text(json.dumps({
        "selected_architecture": manifest["selected_architecture"],
        "dut_top": top, "mode": "passive_observation",
        "approval_scope": "Top-level pin map and passive monitor only; active stimulus not approved."
    }, indent=2))

    flist = ["+incdir+.", "+incdir+interfaces", "+incdir+agents", "+incdir+env", "+incdir+tests"]
    flist += ordered_rtl + ["interfaces/"+if_name+".sv", "mverify_uvm_pkg.sv", "mverify_tb_top.sv"]
    (out/"mverify.f").write_text("\n".join(flist)+"\n")
    (out/"compile_vcs.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "vcs -full64 -sverilog -ntb_opts uvm-1.2 -timescale=1ns/1ps "
        "-debug_access+all -f mverify.f -top mverify_tb_top -o simv_mverify -l compile.log\n")
    (out/"run_vcs.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "TEST_NAME=\"${1:-mverify_base_test}\"\n"
        "./simv_mverify +UVM_TESTNAME=\"$TEST_NAME\" +UVM_VERBOSITY=UVM_MEDIUM -l sim.log\n")
    for script in ("compile_vcs.sh", "run_vcs.sh"):
        (out/script).chmod(0o755)

    testcase_lines = "\n".join(
        f"- `{x['uvm_test']}` — {x['name']} ({x['kind']}; oracle: {x['oracle']})"
        for x in test_names
    ) or "- No scenarios were discovered."
    (out/"README_GENERATED.md").write_text(
        f"# Generated UVM environment: {top}\n\n"
        "This release creates a passive UVM environment. It connects every parsed top-level port to `mverify_dut_if`, "
        "samples all non-clock ports, connects the monitor analysis port to a scoreboard, and prints the UVM component "
        "topology during end-of-elaboration.\n\n"
        "## Compile and run (VCS / UVM 1.2)\n\n"
        "```bash\n./compile_vcs.sh\n./run_vcs.sh mverify_base_test\n```\n\n"
        "## Generated test names\n\n" + testcase_lines + "\n\n"
        "These tests are observation/scenario stubs. They do not apply protocol stimulus or prove functional correctness. "
        "Review `mverify_generation_manifest.json`, `verification_testcases.json`, and the sequence template before "
        "adding active drivers and an independent reference model.\n")
    (out/"GENERATION_STATUS.md").write_text(
        "# Generation status\n\n"
        "- Top-level port interface: generated from parsed declarations.\n"
        "- Passive monitor: samples every parsed non-clock top-level port.\n"
        "- Scoreboard: receives observations and reports count.\n"
        "- UVM topology: printed with `uvm_top.print_topology()`.\n"
        "- Scenario test classes: generated as selectable observation stubs.\n"
        "- Active protocol stimulus: not generated until a reviewed signal/protocol mapping exists.\n"
        "- Functional oracle: not inferred from RTL port names.\n")
    return {"output_dir": str(out), "top": top, "ports": len(ports),
            "tests": len(test_names), "files": len(list(out.rglob("*"))),
            "topology_print": True, "mode": "passive_observation_with_test_stubs"}
