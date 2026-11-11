// RX data path: one arrival-ordered FIFO, with three independently reserved
// capacity pools. The sum of advertised header credits is backed by storage.
module pcie_fc_rx_buffer #(
  parameter int HEADER_CREDITS = 4,
  parameter int DATA_CREDITS = HEADER_CREDITS * ((pcie_pkg::MAX_PAYLOAD_DW+3)/4)
) (
  input logic clk, rst_n, initialized,
  input logic in_valid,
  output logic in_ready,
  input pcie_pkg::tlp_packet_t in_tlp,
  output logic out_valid,
  input logic out_ready,
  output pcie_pkg::tlp_packet_t out_tlp,
  output pcie_pkg::fc_credits_t credit_limit,
  output logic protocol_error
);
  import pcie_pkg::*;
  fc_credits_t occupied;
  fc_class_e in_class, out_class;
  logic [11:0] in_cost, out_cost;
  logic fifo_ready, push, pop, space_ok;
  assign in_class = tlp_fc_class(in_tlp);
  assign out_class = tlp_fc_class(out_tlp);
  assign in_cost = tlp_fc_data_cost(in_tlp);
  assign out_cost = tlp_fc_data_cost(out_tlp);
  always_comb begin
    space_ok = 1'b0;
    if (tlp_fc_supported(in_tlp))
      space_ok = (int'(occupied.header[in_class]) < HEADER_CREDITS) &&
                 ((int'(occupied.data[in_class]) + int'(in_cost)) <= DATA_CREDITS);
  end
  assign in_ready = rst_n && initialized && fifo_ready && space_ok;
  assign push = in_valid && in_ready;
  assign pop = out_valid && out_ready;
  pcie_sync_fifo #(.WIDTH($bits(tlp_packet_t)), .DEPTH(3*HEADER_CREDITS)) u_storage (
    .clk(clk), .rst_n(rst_n), .in_valid(push), .in_ready(fifo_ready),
    .in_data(in_tlp), .out_valid(out_valid), .out_ready(out_ready), .out_data(out_tlp)
  );
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      occupied <= '0;
      protocol_error <= 1'b0;
      for (int c = 0; c < 3; c++) begin
        credit_limit.header[c] <= 8'(HEADER_CREDITS);
        credit_limit.data[c] <= 12'(DATA_CREDITS);
      end
    end else begin
      if (in_valid && initialized && !tlp_fc_supported(in_tlp)) protocol_error <= 1'b1;
      for (int c = 0; c < 3; c++) begin
        // One assignment per counter handles simultaneous allocate/release.
        occupied.header[c] <= occupied.header[c] + 8'(push && (int'(in_class) == c))
                                               - 8'(pop && (int'(out_class) == c));
        occupied.data[c] <= occupied.data[c] + ((push && (int'(in_class) == c)) ? in_cost : 12'd0)
                                           - ((pop && (int'(out_class) == c)) ? out_cost : 12'd0);
        if (pop && (int'(out_class) == c)) begin
          credit_limit.header[c] <= credit_limit.header[c] + 8'd1;
          credit_limit.data[c] <= credit_limit.data[c] + out_cost;
        end
      end
    end
  end
`ifndef SYNTHESIS
  initial begin
    if (HEADER_CREDITS < 1 || HEADER_CREDITS > 127) $fatal(1, "FC header capacity must be 1..127");
    if (DATA_CREDITS < 1 || DATA_CREDITS > 2047 ||
        DATA_CREDITS > HEADER_CREDITS*((MAX_PAYLOAD_DW+3)/4))
      $fatal(1, "FC data capacity must be finite, 1..2047, and backed by RX storage");
  end
  always @(posedge clk) if (rst_n) begin
    for (int c = 0; c < 3; c++) begin
      assert (int'(occupied.header[c]) <= HEADER_CREDITS) else $fatal(1, "FC RX header overflow");
      assert (int'(occupied.data[c]) <= DATA_CREDITS) else $fatal(1, "FC RX data overflow");
    end
  end
`endif
endmodule
