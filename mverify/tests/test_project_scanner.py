from pathlib import Path
from mverify.core.project_scanner import scan_project


def test_scan_finds_top_candidate(tmp_path: Path):
    (tmp_path / "child.sv").write_text("module child(input logic a); endmodule")
    (tmp_path / "top.sv").write_text("module top(input logic clk); child u_child(.a(clk)); endmodule")
    report = scan_project(tmp_path)
    assert report["summary"]["rtl_files"] == 2
    assert "top" in report["top_candidates"]
    assert report["hierarchy"][0]["child"] == "child"


def test_scan_parameterized_child_instance(tmp_path: Path):
    (tmp_path / "child.sv").write_text("module child #(parameter W=8)(input logic [W-1:0] d); endmodule")
    (tmp_path / "top.sv").write_text(
        "module top(input logic [7:0] d); child #(.W(8)) u0(.d(d)); endmodule"
    )
    report = scan_project(tmp_path)
    assert report["top_candidates"] == ["top"]
    assert report["hierarchy"][0]["instance"] == "u0"


def test_scanner_records_vcs_filelist_inputs(tmp_path):
    rtl=tmp_path/"rtl"; rtl.mkdir()
    (rtl/"dut.sv").write_text("module dut(input logic clk); endmodule")
    (tmp_path/"dut.f").write_text("+incdir+rtl\n+define+SIM\nrtl/dut.sv\n")
    report=scan_project(tmp_path)
    assert report["build_inputs"]["filelists"]
    assert any(x.endswith("dut.sv") for x in report["build_inputs"]["compile_sources"])
    assert "SIM" in report["build_inputs"]["defines"]
