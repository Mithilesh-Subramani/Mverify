from pathlib import Path
from mverify.core.project_scanner import scan_project
from mverify.core.adaptive_verification import plan_adaptive_verification


def _scan(tmp_path: Path, source: str, top: str):
    (tmp_path / "design.sv").write_text(source)
    return scan_project(tmp_path, top)


def test_alu_gets_compact_combinational_plan(tmp_path):
    report = _scan(tmp_path, """
    module alu(input logic [7:0] a, b, input logic [2:0] op,
               output logic [7:0] result, output logic zero);
      always_comb begin
        case (op)
          0: result = a + b;
          1: result = a - b;
          default: result = 0;
        endcase
        zero = (result == 0);
      end
    endmodule
    """, "alu")
    udm = report["universal_design_model"]
    plan = report["adaptive_verification_plan"]
    assert udm["project"]["selected_top"] == "alu"
    assert plan["architecture"] == "combinational_unit"
    assert "virtual-sequence coordinator" not in " ".join(plan["topology_recommendation"])
    assert any(x["id"] == "input_space" for x in plan["candidate_tests"])
    assert plan["generation_gates"]["active_driver"].startswith("blocked")


def test_fifo_gets_storage_and_handshake_tests(tmp_path):
    report = _scan(tmp_path, """
    module fifo(input logic clk, rst_n, input logic wr_valid, output logic wr_ready,
                input logic [31:0] wr_data, input logic rd_ready,
                output logic rd_valid, output logic [31:0] rd_data);
      logic [31:0] mem [0:7];
      logic [3:0] count;
      always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) count <= 0;
        else if (wr_valid && wr_ready) count <= count + 1'b1;
      end
      assign wr_ready = (count < 8);
      assign rd_valid = (count != 0);
    endmodule
    """, "fifo")
    plan = report["adaptive_verification_plan"]
    ids = {x["id"] for x in plan["candidate_tests"]}
    assert plan["architecture"] == "sequential_or_interface_block"
    assert "storage_boundaries" in ids
    assert "handshake_backpressure" in ids


def test_arbiter_gets_contention_test(tmp_path):
    report = _scan(tmp_path, """
    module arbiter(input logic clk, rst_n, input logic [3:0] request,
                   output logic [3:0] grant);
      logic [1:0] state;
      always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) state <= 0;
        else if (|request) state <= state + 1'b1;
      assign grant = request & 4'b0001;
    endmodule
    """, "arbiter")
    ids = {x["id"] for x in report["adaptive_verification_plan"]["candidate_tests"]}
    assert "contention_fairness" in ids
    assert "storage_boundaries" not in ids
    assert "handshake_backpressure" not in ids


def test_soc_scope_does_not_create_agent_per_internal_module(tmp_path):
    source = """
    module leaf(input logic clk, input logic [7:0] a, output logic [7:0] y);
      assign y = a;
    endmodule
    module soc(input logic clk, input logic [7:0] a, output logic [7:0] y);
      leaf u0(.clk(clk), .a(a), .y(y));
    endmodule
    """
    report = _scan(tmp_path, source, "soc")
    udm = report["universal_design_model"]
    assert udm["project"]["selected_top"] == "soc"
    assert udm["hierarchy"]["instance_count"] == 1
    assert udm["design_scope"] == "single_ip_or_subsystem_candidate"
    assert report["adaptive_verification_plan"]["dut_top"] == "soc"
    assert report["adaptive_verification_plan"]["architecture"] == "subsystem_or_soc"
    assert [x["id"] for x in report["adaptive_verification_plan"]["candidate_tests"]] == ["subsystem_boundary_interactions"]


def test_plan_marks_unknowns_and_never_authorizes_active_driver():
    plan = plan_adaptive_verification({
        "project": {"selected_top": "mystery"}, "design_scope": "single_ip_or_subsystem_candidate",
        "design_characteristics": {}, "top_interface": {"ports": [], "signal_relationship_candidates": {}},
        "hierarchy": {"instance_count": 0},
    })
    assert plan["generation_gates"]["active_driver"].startswith("blocked")
    assert plan["status"] == "adaptive_plan_generated_not_functionally_verified"
    assert plan["unknowns_and_review_items"]
