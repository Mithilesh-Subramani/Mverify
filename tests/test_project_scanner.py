from pathlib import Path
from mverify.core.project_scanner import scan_project

def test_scan_finds_top_candidate(tmp_path: Path):
    (tmp_path / "child.sv").write_text("module child(input logic a); endmodule")
    (tmp_path / "top.sv").write_text("module top(input logic clk); child u_child(.a(clk)); endmodule")
    report = scan_project(tmp_path)
    assert report["summary"]["rtl_files"] == 2
    assert "top" in report["top_candidates"]
