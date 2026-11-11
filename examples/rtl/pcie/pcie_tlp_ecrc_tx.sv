module pcie_tlp_ecrc_tx (
  input  logic                   clk,
  input  logic                   rst_n,
  input  logic                   generate_enable,
  input  logic                   tlp_valid,
  output logic                   tlp_ready,
  input  pcie_pkg::tlp_packet_t  tlp,
  output logic                   protected_valid,
  input  logic                   protected_ready,
  output pcie_pkg::tlp_packet_t  protected_tlp
);
  import pcie_pkg::*;

  typedef enum logic [1:0] {IDLE, CALC, OUTPUT_PACKET} state_e;
  state_e state;
  logic crc_ready, crc_valid;
  logic [31:0] crc_result;

  // Capture the packet and enable atomically. Configuration changes during
  // computation or output backpressure cannot change an accepted packet.
  assign tlp_ready = (state == IDLE) && (!generate_enable || crc_ready);
  assign protected_valid = (state == OUTPUT_PACKET);

  pcie_packet_crc u_crc (
    .clk(clk), .rst_n(rst_n),
    .in_valid(tlp_valid && tlp_ready && generate_enable), .in_ready(crc_ready),
    .in_tlp(tlp), .in_seq(12'b0), .out_valid(crc_valid),
    .out_ready(state == CALC), .out_crc(crc_result)
  );

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state <= IDLE;
      protected_tlp <= '0;
    end else begin
      case (state)
        IDLE: if (tlp_valid && tlp_ready) begin
          protected_tlp <= tlp;
          protected_tlp.digest_present <= generate_enable;
          protected_tlp.ecrc <= '0;
          state <= generate_enable ? CALC : OUTPUT_PACKET;
        end
        CALC: if (crc_valid) begin
          protected_tlp.ecrc <= crc_result;
          state <= OUTPUT_PACKET;
        end
        OUTPUT_PACKET: if (protected_ready) state <= IDLE;
        default: state <= IDLE;
      endcase
    end
  end
endmodule
