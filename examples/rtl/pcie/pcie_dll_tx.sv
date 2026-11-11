module pcie_dll_tx #(
  parameter int REPLAY_TIMEOUT = 1024
) (
  input  logic                    clk,
  input  logic                    rst_n,
  input  logic                    tlp_valid,
  output logic                    tlp_ready,
  input  pcie_pkg::tlp_packet_t   tlp,

  output logic                    link_valid,
  input  logic                    link_ready,
  output pcie_pkg::dll_packet_t   link_packet,

  input  logic                    ack_valid,
  input  logic                    ack_is_nak,
  input  logic [11:0]             ack_seq,
  output logic [31:0]             replay_count
);
  import pcie_pkg::*;
  localparam int TIMEOUT_W = (REPLAY_TIMEOUT <= 1) ? 1 : $clog2(REPLAY_TIMEOUT);

  typedef enum logic [1:0] {IDLE, CALC, SEND, WAIT_ACK} state_e;
  state_e state;
  dll_packet_t replay_packet;
  logic [11:0] next_seq;
  logic [TIMEOUT_W-1:0] timeout_counter;
  logic crc_ready, crc_valid;
  logic [31:0] crc_result;

  assign tlp_ready = (state == IDLE) && crc_ready;
  assign link_valid = (state == SEND);
  assign link_packet = replay_packet;

  pcie_packet_crc #(.LINK_CRC(1'b1)) u_crc (
    .clk(clk), .rst_n(rst_n),
    .in_valid(tlp_valid && tlp_ready), .in_ready(crc_ready),
    .in_tlp(tlp), .in_seq(next_seq), .out_valid(crc_valid),
    .out_ready(state == CALC), .out_crc(crc_result)
  );

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state           <= IDLE;
      replay_packet   <= '0;
      next_seq        <= '0;
      timeout_counter <= '0;
      replay_count    <= '0;
    end else begin
      case (state)
        IDLE: begin
          timeout_counter <= '0;
          if (tlp_valid && tlp_ready) begin
            replay_packet.seq  <= next_seq;
            replay_packet.tlp  <= tlp;
            replay_packet.lcrc <= '0;
            state <= CALC;
          end
        end

        CALC: if (crc_valid) begin
          replay_packet.lcrc <= crc_result;
          state <= SEND;
        end

        SEND: begin
          if (link_valid && link_ready) begin
            timeout_counter <= '0;
            state <= WAIT_ACK;
          end
        end

        WAIT_ACK: begin
          if (ack_valid && ack_is_nak) begin
            timeout_counter <= '0;
            replay_count <= replay_count + 1'b1;
            state <= SEND;
          end else if (ack_valid && !ack_is_nak &&
                       (ack_seq == replay_packet.seq)) begin
            timeout_counter <= '0;
            next_seq <= next_seq + 1'b1;
            state <= IDLE;
          end else if (timeout_counter == TIMEOUT_W'(REPLAY_TIMEOUT-1)) begin
            timeout_counter <= '0;
            replay_count <= replay_count + 1'b1;
            state <= SEND;
          end else begin
            timeout_counter <= timeout_counter + 1'b1;
          end
        end

        default: state <= IDLE;
      endcase
    end
  end
`ifndef SYNTHESIS
  initial if (REPLAY_TIMEOUT < 1) $fatal(1, "REPLAY_TIMEOUT must be positive");
`endif
endmodule
