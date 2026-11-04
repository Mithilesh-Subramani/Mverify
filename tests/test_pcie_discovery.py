from pathlib import Path
from mverify.core.project_scanner import scan_project

def test_discovers_integrated_pcie_tl_and_dll_structure(tmp_path: Path):
    (tmp_path / "dut.sv").write_text("""module dut(input logic clk, input logic req_valid, output logic req_ready, output logic link_tx_valid, input logic link_tx_ready, output pcie_pkg::dll_packet_t link_tx_packet, output pcie_pkg::rx_meta_t rx_meta); pcie_tx_control u_req(); pcie_data_link #(.FC_ENABLE(1'b1)) u_dll(); endmodule""")
    d=scan_project(tmp_path,"dut")["architecture_discovery"]
    assert d["protocol"]["value"] == "PCIe"
    assert d["layers"]["transaction_layer"]["status"] != "not_observed"
    assert d["layers"]["data_link_layer"]["status"] != "not_observed"
    assert d["generation"]["value"] == "unknown"

def test_does_not_call_generic_design_pcie(tmp_path: Path):
    (tmp_path / "dut.sv").write_text("module dut(input logic clk); endmodule")
    assert scan_project(tmp_path)["architecture_discovery"]["protocol"]["value"] == "unknown"

def test_pipe_evidence_is_separate_from_dll_evidence(tmp_path: Path):
    (tmp_path / "dut.sv").write_text("module dut(input logic pipe_clk, input logic pipe_rx_valid, output logic pipe_tx_valid, input logic ltssm_active); endmodule")
    d=scan_project(tmp_path)["architecture_discovery"]
    assert d["layers"]["physical_layer"]["status"] != "not_observed"
