from pathlib import Path
from mverify.core.rtl_parser import parse_rtl_file, parse_rtl_text


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


def test_parameterized_module_uses_actual_port_list():
    source = """
    module controller #(
      parameter int WIDTH = 32,
      parameter int DEPTH = (1 << 4)
    ) (
      input logic clk,
      input logic rst_n,
      input logic [WIDTH-1:0] data_i,
      output logic [WIDTH-1:0] data_o,
      output logic valid_o
    );
      child #(.WIDTH(WIDTH)) u_child (.clk(clk));
    endmodule
    """
    modules, warnings = parse_rtl_text(source)
    assert len(modules) == 1
    assert [p["name"] for p in modules[0]["ports"]] == [
        "clk", "rst_n", "data_i", "data_o", "valid_o"
    ]
    assert modules[0]["ports"][2]["width"] == "[WIDTH-1:0]"
    assert not warnings


def test_inherited_direction_and_nested_commas():
    source = """
    module sample (
      input logic [7:0] a, b,
      output logic [3:0] c,
      input logic ready
    );
    endmodule
    """
    modules, warnings = parse_rtl_text(source)
    assert [p["name"] for p in modules[0]["ports"]] == ["a", "b", "c", "ready"]
    assert [p["direction"] for p in modules[0]["ports"]] == [
        "input", "input", "output", "input"
    ]
    assert not warnings
