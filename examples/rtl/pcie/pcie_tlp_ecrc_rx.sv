module pcie_tlp_ecrc_rx (
  input  logic                   clk,
  input  logic                   rst_n,
  input  logic                   check_enable,
  input  logic                   tlp_valid,
  output logic                   tlp_ready,
  input  pcie_pkg::tlp_packet_t  tlp,
  output logic                   checked_valid,
  input  logic                   checked_ready,
  output pcie_pkg::tlp_packet_t  checked_tlp,
  output logic                   ecrc_error,
  output logic [31:0]            ecrc_error_count
);
  import pcie_pkg::*;

  typedef enum logic [1:0] {IDLE, CALC, OUTPUT_PACKET} state_e;
  state_e state;
  logic crc_ready, crc_valid, must_check;
  logic [31:0] crc_result;

  assign must_check = check_enable && tlp.digest_present;
  assign tlp_ready = (state == IDLE) && (!must_check || crc_ready);
  assign checked_valid = (state == OUTPUT_PACKET);

  pcie_packet_crc u_crc (
    .clk(clk), .rst_n(rst_n),
    .in_valid(tlp_valid && tlp_ready && must_check), .in_ready(crc_ready),
    .in_tlp(tlp), .in_seq(12'b0), .out_valid(crc_valid),
    .out_ready(state == CALC), .out_crc(crc_result)
  );

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state <= IDLE;
      checked_tlp <= '0;
      ecrc_error <= 1'b0;
      ecrc_error_count <= '0;
    end else begin
      case (state)
        IDLE: if (tlp_valid && tlp_ready) begin
          checked_tlp <= tlp;
          ecrc_error <= 1'b0;
          state <= must_check ? CALC : OUTPUT_PACKET;
        end
        CALC: if (crc_valid) begin
          ecrc_error <= (checked_tlp.ecrc != crc_result);
          state <= OUTPUT_PACKET;
        end
        OUTPUT_PACKET: if (checked_ready) begin
          // Count once on delivery, never once per stalled output cycle.
          if (ecrc_error) ecrc_error_count <= ecrc_error_count + 1'b1;
          state <= IDLE;
        end
        default: state <= IDLE;
      endcase
    end
  end
endmodule
