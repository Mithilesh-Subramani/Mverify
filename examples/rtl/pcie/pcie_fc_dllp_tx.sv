// RX control path: advertise capacity, then cumulative returned credits.
// Output packets are registered and remain stable under link backpressure.
module pcie_fc_dllp_tx #(
  parameter int REFRESH_CYCLES = 128
) (
  input logic clk, rst_n,
  input logic peer_init1_done, peer_init2_done,
  input pcie_pkg::fc_credits_t credit_limit,
  output logic initialized,
  output logic fc_valid,
  input logic fc_ready,
  output pcie_pkg::fc_dllp_t fc_packet
);
  import pcie_pkg::*;
  localparam int AGE_W = (REFRESH_CYCLES < 2) ? 1 : $clog2(REFRESH_CYCLES+1);
  typedef enum logic [1:0] {INIT1, INIT2, ACTIVE} state_e;
  state_e state;
  fc_class_e scan_class;
  fc_credits_t advertised;
  logic [AGE_W-1:0] age [0:2];
  logic due;
  assign initialized = (state == ACTIVE);
  assign due = (credit_limit.header[scan_class] != advertised.header[scan_class]) ||
               (credit_limit.data[scan_class] != advertised.data[scan_class]) ||
               (age[scan_class] == AGE_W'(REFRESH_CYCLES));
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state <= INIT1;
      scan_class <= FC_POSTED;
      fc_valid <= 1'b0;
      fc_packet <= '0;
      advertised <= '0;
      for (int c = 0; c < 3; c++) age[c] <= '0;
    end else begin
      for (int c = 0; c < 3; c++)
        if (age[c] < AGE_W'(REFRESH_CYCLES)) age[c] <= age[c] + 1'b1;
      if (fc_valid) begin
        if (fc_ready) begin
          fc_valid <= 1'b0;
          advertised.header[scan_class] <= fc_packet.header_limit;
          advertised.data[scan_class] <= fc_packet.data_limit;
          age[scan_class] <= '0;
          scan_class <= (scan_class == FC_COMPLETION) ? FC_POSTED : fc_class_e'(scan_class + 2'd1);
          if (scan_class == FC_COMPLETION) begin
            if (state == INIT1 && peer_init1_done) state <= INIT2;
            if (state == INIT2 && peer_init2_done) state <= ACTIVE;
          end
        end
      end else if ((state != ACTIVE) || due) begin
        fc_valid <= 1'b1;
        fc_packet.kind <= (state == INIT1) ? FC_INIT1 : ((state == INIT2) ? FC_INIT2 : FC_UPDATE);
        fc_packet.credit_class <= scan_class;
        fc_packet.vc <= 3'd0;
        fc_packet.header_limit <= credit_limit.header[scan_class];
        fc_packet.data_limit <= credit_limit.data[scan_class];
      end else begin
        scan_class <= (scan_class == FC_COMPLETION) ? FC_POSTED : fc_class_e'(scan_class + 2'd1);
      end
    end
  end
`ifndef SYNTHESIS
  initial if (REFRESH_CYCLES < 1) $fatal(1, "FC refresh period must be positive");
`endif
endmodule
