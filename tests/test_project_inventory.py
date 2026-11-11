from pathlib import Path
from mverify.core.project_inventory import classify_file, inventory_project

def test_classifies_hdl_file_types():
    assert classify_file(Path("dut.sv")) == "verilog_systemverilog_source"
    assert classify_file(Path("rtl.vhd")) == "vhdl_source"
    assert classify_file(Path("timing.sdc")) == "timing_constraints"
    assert classify_file(Path("sources.f")) == "compile_filelist"

def test_inventory_reports_unknown_and_supported_files(tmp_path):
    (tmp_path / "top.sv").write_text("module top; endmodule")
    (tmp_path / "timing.sdc").write_text("create_clock")
    (tmp_path / "notes.bin").write_bytes(b"x")
    result = inventory_project(tmp_path)
    assert result["total_files"] == 3
    assert result["categories"]["verilog_systemverilog_source"]["count"] == 1
    assert result["categories"]["other"]["count"] == 1
