module pcie_dll_rx (
  input  logic                    clk,
  input  logic                    rst_n,
  input  logic                    link_valid,
  output logic                    link_ready,
  input  pcie_pkg::dll_packet_t   link_packet,

  output logic                    tlp_valid,
  input  logic                    tlp_ready,
  output pcie_pkg::tlp_packet_t   tlp,

  output logic                    ack_valid,
  input  logic                    ack_ready,
  output logic                    ack_is_nak,
  output logic [11:0]             ack_seq,
  output logic [31:0]             crc_error_count,
  output logic [31:0]             sequence_error_count
);
  import pcie_pkg::*;

  logic [11:0] expected_seq;
  logic tlp_pending;
  logic ack_pending;
  logic crc_good;
  logic expected_packet;
  logic duplicate_packet;
  logic tlp_slot_available;
  logic ack_slot_available;
  logic busy, crc_ready, crc_valid, crc_accept;
  logic [31:0] crc_result;
  dll_packet_t packet_q;

  assign crc_good = (packet_q.lcrc == crc_result);
  assign expected_packet = crc_good && (packet_q.seq == expected_seq);
  assign duplicate_packet = crc_good &&
                            (packet_q.seq == (expected_seq - 12'd1));
  assign tlp_slot_available = !tlp_pending || tlp_ready;
  assign ack_slot_available = !ack_pending || ack_ready;

  // Input capture is independent of the CRC comparison. The CRC result and
  // packet remain paired until all required output slots are available.
  assign link_ready = !busy && crc_ready;
  assign crc_accept = busy && ack_slot_available &&
                      (!expected_packet || tlp_slot_available);
  assign tlp_valid = tlp_pending;
  assign ack_valid = ack_pending;

  pcie_packet_crc #(.LINK_CRC(1'b1)) u_crc (
    .clk(clk), .rst_n(rst_n),
    .in_valid(link_valid && link_ready), .in_ready(crc_ready),
    .in_tlp(link_packet.tlp), .in_seq(link_packet.seq),
    .out_valid(crc_valid), .out_ready(crc_accept), .out_crc(crc_result)
  );

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      busy                <= 1'b0;
      packet_q            <= '0;
      expected_seq        <= '0;
      tlp_pending         <= 1'b0;
      ack_pending         <= 1'b0;
      tlp                 <= '0;
      ack_is_nak          <= 1'b0;
      ack_seq             <= '0;
      crc_error_count     <= '0;
      sequence_error_count <= '0;
    end else begin
      if (tlp_pending && tlp_ready)
        tlp_pending <= 1'b0;
      if (ack_pending && ack_ready)
        ack_pending <= 1'b0;

      if (link_valid && link_ready) begin
        packet_q <= link_packet;
        busy <= 1'b1;
      end

      if (crc_valid && crc_accept) begin
        busy <= 1'b0;
        ack_pending <= 1'b1;

        if (expected_packet) begin
          tlp <= packet_q.tlp;
          tlp_pending <= 1'b1;
          ack_is_nak <= 1'b0;
          ack_seq <= packet_q.seq;
          expected_seq <= expected_seq + 1'b1;
        end else if (duplicate_packet) begin
          // The original ACK may have been lost. Do not deliver the TLP twice.
          ack_is_nak <= 1'b0;
          ack_seq <= packet_q.seq;
        end else begin
          ack_is_nak <= 1'b1;
          ack_seq <= expected_seq;
          if (!crc_good)
            crc_error_count <= crc_error_count + 1'b1;
          else
            sequence_error_count <= sequence_error_count + 1'b1;
        end
      end
    end
  end
endmodule
