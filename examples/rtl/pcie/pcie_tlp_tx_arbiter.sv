// Two independently buffered/ECRC-protected sources. Arbitrate only eligible
// packets; lock a stalled grant so ready/valid data stays stable. Round-robin
// fairness applies between sources; local request TCs still use the WRR block.
module pcie_tlp_tx_arbiter #(
  parameter bit FC_ENABLE = 1'b1,
  parameter bit CPL_ENABLE = 1'b0
) (
  input logic clk, rst_n, initialized,
  input pcie_pkg::fc_credits_t available,
  input logic req_valid,
  output logic req_ready,
  input pcie_pkg::tlp_packet_t req_tlp,
  input logic cpl_valid,
  output logic cpl_ready,
  input pcie_pkg::tlp_packet_t cpl_tlp,
  output logic out_valid,
  input logic out_ready,
  output pcie_pkg::tlp_packet_t out_tlp
);
  import pcie_pkg::*;
  logic req_eligible, cpl_eligible, selected, locked, locked_select, prefer_cpl;
  assign req_eligible = req_valid && (!FC_ENABLE || (initialized && fc_has_credit(req_tlp, available)));
  assign cpl_eligible = CPL_ENABLE && cpl_valid &&
                        (!FC_ENABLE || (initialized && fc_has_credit(cpl_tlp, available)));
  assign selected = locked ? locked_select : cpl_eligible && (!req_eligible || prefer_cpl);
  assign out_valid = rst_n && (selected ? cpl_eligible : req_eligible);
  assign out_tlp = selected ? cpl_tlp : req_tlp;
  assign req_ready = out_valid && out_ready && !selected;
  assign cpl_ready = out_valid && out_ready && selected;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin locked <= 0; locked_select <= 0; prefer_cpl <= 1; end
    else if (out_valid) begin
      if (out_ready) begin locked <= 0; prefer_cpl <= !selected; end
      else begin locked <= 1; locked_select <= selected; end
    end
  end
endmodule
