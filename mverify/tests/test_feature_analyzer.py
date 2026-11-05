from pathlib import Path
from mverify.core.project_scanner import scan_project


def test_feature_inventory_finds_features_without_layer_names(tmp_path: Path):
    (tmp_path / "dut.sv").write_text("""
    module dut(input logic clk, input logic rst_n,
               input logic in_valid, output logic in_ready,
               input logic [31:0] data_i, output logic [31:0] data_o);
      logic [2:0] state;
      logic [3:0] fifo_count;
      logic [7:0] retry_counter;
      logic [31:0] crc_reg;
      always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
          state <= 0;
          retry_counter <= 0;
        end else begin
          if (in_valid && in_ready) begin
            fifo_count <= fifo_count + 1'b1;
            crc_reg <= crc_reg ^ data_i;
          end
          if (retry_counter == 8'd10) state <= 3'd2;
          else retry_counter <= retry_counter + 1'b1;
        end
      end
    endmodule
    """)
    report = scan_project(tmp_path, "dut")
    found = {x["feature_id"] for x in report["feature_analysis"]["features"]}
    assert "handshake" in found
    assert "state_machine" in found
    assert "buffering" in found
    assert "retry_recovery" in found
    assert "integrity_check" in found
    assert report["feature_analysis"]["module_inventory"][0]["module"] == "dut"


def test_feature_analysis_does_not_require_pcie(tmp_path: Path):
    (tmp_path / "arb.sv").write_text("""
    module arb(input logic clk, input logic [3:0] request_vector,
               output logic [3:0] grant_vector);
      logic [1:0] priority_ptr;
      always_comb begin
        grant_vector = 0;
        casez (request_vector)
          4'b???1: grant_vector = 4'b0001;
          default: grant_vector = 0;
        endcase
      end
    endmodule
    """)
    report = scan_project(tmp_path)
    assert report["architecture_discovery"]["protocol"]["value"] == "unknown"
    assert any(x["feature_id"] == "arbitration"
               for x in report["feature_analysis"]["features"])
