from pathlib import Path
from mverify.core.uvm_generator import generate_uvm_project

def test_generates_uvm_tree_from_scanned_ports(tmp_path):
    report = {
      "module_details": [{"name":"dut_top","ports":[
        {"name":"clk","direction":"input","declaration":"logic clk","width":"scalar/unspecified"},
        {"name":"req_valid","direction":"input","declaration":"logic req_valid","width":"scalar/unspecified"},
        {"name":"req_ready","direction":"output","declaration":"logic req_ready","width":"scalar/unspecified"},
        {"name":"rx_data","direction":"output","declaration":"logic [31:0] rx_data","width":"[31:0]"}]}],
      "selected_top":"dut_top","top_candidates":["dut_top"],"files":["rtl/dut.sv"],"hierarchy":[]}
    result=generate_uvm_project(report,tmp_path/"mverify_uvm_generated")
    out=Path(result["output_dir"])
    assert (out/"mverify_uvm_pkg.sv").exists()
    assert (out/"mverify_tb_top.sv").exists()
    assert (out/"agents/req_agent.sv").exists()
    agent=(out/"agents/req_agent.sv").read_text()
    assert "mverify_req_monitor" in agent
    assert "driver.seq_item_port.connect" not in agent
    assert "mverify_scoreboard" in (out/"env/mverify_env.sv").read_text()
    assert "Topology-only compile smoke test" in (out/"tests/mverify_base_test.sv").read_text()
    assert (out/"GENERATION_STATUS.md").exists()


def test_generated_interfaces_do_not_repeat_dut_port_directions(tmp_path):
    report = {
      "module_details": [{"name":"dut_top","ports":[
        {"name":"clk","direction":"input","declaration":"input logic clk","width":"scalar/unspecified"},
        {"name":"backend_req_valid","direction":"output","declaration":"output logic backend_req_valid","width":"scalar/unspecified"},
        {"name":"backend_req","direction":"output","declaration":"output pcie_pkg::cpl_backend_req_t backend_req","width":"scalar/unspecified"}]}],
      "selected_top":"dut_top","top_candidates":["dut_top"],"files":[],"hierarchy":[]}
    result=generate_uvm_project(report,tmp_path/"generated")
    interface=(Path(result["output_dir"])/"interfaces/mverify_backend_if.sv").read_text()
    assert "output logic backend_req_valid;" not in interface
    assert "input logic backend_req_valid;" not in interface
    assert "pcie_pkg::cpl_backend_req_t backend_req;" in interface


def test_generator_is_passive_and_filelist_does_not_compile_included_items_twice(tmp_path):
    report = {
      "module_details": [{"name":"dut_top","ports":[
        {"name":"clk","direction":"input","declaration":"input logic clk","width":"scalar/unspecified"},
        {"name":"in_valid","direction":"input","declaration":"input logic in_valid","width":"scalar/unspecified"},
        {"name":"out_valid","direction":"output","declaration":"output logic out_valid","width":"scalar/unspecified"}]}],
      "selected_top":"dut_top","top_candidates":["dut_top"],"files":[],"hierarchy":[]}
    result=generate_uvm_project(report,tmp_path/"passive")
    out=Path(result["output_dir"])
    flist=(out/"mverify.f").read_text()
    assert "mverify_items.sv" not in flist
    assert "mverify_uvm_pkg.sv" in flist
    assert not (out/"sequences/mverify_smoke_sequence.sv").exists()
    assert "generation_mode" in (out/"mverify_generation_manifest.json").read_text()
