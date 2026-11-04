from pathlib import Path
from mverify.core.rtl_parser import parse_rtl_file

def test_parse_simple_ansi_module(tmp_path: Path):
    source = """
    module demo (
      input logic clk,
      input logic [7:0] data_in,
      output logic ready
    );
    endmodule
    """
    file_path = tmp_path / "demo.sv"
    file_path.write_text(source)
    modules, warnings = parse_rtl_file(file_path)
    assert len(modules) == 1
    assert modules[0]["name"] == "demo"
    assert [p["name"] for p in modules[0]["ports"]] == ["clk", "data_in", "ready"]
    assert modules[0]["ports"][1]["width"] == "[7:0]"
    assert not warnings

def test_comments_do_not_create_modules(tmp_path: Path):
    file_path = tmp_path / "empty.sv"
    file_path.write_text("// module fake(input a); endmodule\\n")
    modules, _ = parse_rtl_file(file_path)
    assert modules == []
