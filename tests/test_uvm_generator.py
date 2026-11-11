from pathlib import Path
from mverify.core.uvm_generator import generate_uvm_project


def sample_report():
    return {
        "selected_top": "dut_top",
        "top_candidates": ["dut_top"],
        "module_details": [{
            "name": "dut_top",
            "source_file": "dut_top.sv",
            "ports": [
                {"name": "clk", "direction": "input", "declaration": "input logic clk", "width": "scalar/unspecified"},
                {"name": "req_valid", "direction": "input", "declaration": "input logic req_valid", "width": "scalar/unspecified"},
                {"name": "req_data", "direction": "input", "declaration": "input logic [31:0] req_data", "width": "[31:0]"},
                {"name": "rx_data", "direction": "output", "declaration": "output logic [31:0] rx_data", "width": "[31:0]"},
                {"name": "backend_req", "direction": "output", "declaration": "output pcie_pkg::cpl_backend_req_t backend_req", "width": "scalar/unspecified"},
            ],
        }],
        "files": [],
        "hierarchy": [],
    }


def test_generator_emits_complete_passive_uvm_tree(tmp_path):
    result = generate_uvm_project(sample_report(), tmp_path/"generated")
    out = Path(result["output_dir"])
    expected = [
        "mverify_uvm_pkg.sv", "mverify_tb_top.sv", "mverify.f",
        "interfaces/mverify_dut_if.sv", "agents/mverify_monitor.sv",
        "agents/mverify_agent.sv", "env/mverify_env.sv",
        "env/mverify_scoreboard.sv", "tests/mverify_base_test.sv",
        "tests/mverify_tests.sv", "sequences/mverify_protocol_sequence_TEMPLATE.sv",
        "mverify_generation_manifest.json", "verification_testcases.json",
        "uvm_topology.txt",
    ]
    for rel in expected:
        assert (out/rel).is_file(), rel
    assert result["topology_print"] is True


def test_generated_test_prints_runtime_uvm_topology_and_connects_monitor(tmp_path):
    out = Path(generate_uvm_project(sample_report(), tmp_path/"generated")["output_dir"])
    base = (out/"tests/mverify_base_test.sv").read_text()
    env = (out/"env/mverify_env.sv").read_text()
    assert "uvm_top.print_topology();" in base
    assert "dut_agent.ap.connect(scoreboard.observed_export)" in env


def test_all_ports_are_connected_and_sampled_without_guessed_drivers(tmp_path):
    out = Path(generate_uvm_project(sample_report(), tmp_path/"generated")["output_dir"])
    top = (out/"mverify_tb_top.sv").read_text()
    monitor = (out/"agents/mverify_monitor.sv").read_text()
    driver_template = (out/"sequences/mverify_protocol_sequence_TEMPLATE.sv").read_text()
    assert ".req_valid(dut_if.req_valid)" in top
    assert ".backend_req(dut_if.backend_req)" in top
    assert "tr.req_valid = vif.req_valid;" in monitor
    assert "tr.rx_data = vif.rx_data;" in monitor
    assert "TODO: Add a dedicated driver" in driver_template
    assert "seq_item_port.get_next_item" not in monitor


def test_generated_filelist_compiles_package_once(tmp_path):
    out = Path(generate_uvm_project(sample_report(), tmp_path/"generated")["output_dir"])
    flist = (out/"mverify.f").read_text()
    assert "mverify_uvm_pkg.sv" in flist
    assert "mverify_items.sv" not in flist
    assert "mverify_tb_top.sv" in flist
