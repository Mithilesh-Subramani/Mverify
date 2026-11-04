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
    assert "sequencer" in agent and "driver.seq_item_port.connect" in agent
    assert "mverify_scoreboard" in (out/"env/mverify_env.sv").read_text()
