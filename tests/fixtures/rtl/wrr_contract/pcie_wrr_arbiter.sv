// SYNTHETIC CONTRACT FIXTURE ONLY. Not a DUT, not copied from the user's project,
// and never used as hardware verification evidence.
// Interleaved weighted round-robin contract fixture: per-requester quota is
// consumed only when grant_accept is asserted; round quota reloads on exhaustion.
module pcie_wrr_arbiter #(
  parameter int NUM_TC = 8,
  parameter int WEIGHT_W = 8
) (
  input logic clk,
  input logic rst_n,
  input logic [NUM_TC-1:0] request,
  input logic [NUM_TC*WEIGHT_W-1:0] weight_cfg,
  output logic grant_valid,
  output logic [((NUM_TC > 1) ? $clog2(NUM_TC) : 1)-1:0] grant_index,
  output logic [NUM_TC-1:0] grant_onehot,
  input logic grant_accept
);
  // Deliberately no implementation. Static generator tests only.
endmodule
