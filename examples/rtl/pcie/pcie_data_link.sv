// Complete packetized DLL boundary: replay/LCRC plus independent FC paths.
module pcie_data_link #(
  parameter int REPLAY_TIMEOUT = 1024,
  parameter bit FC_ENABLE = 1'b1,
  parameter bit CPL_ENABLE = 1'b0,
  parameter int FC_HEADER_CREDITS = 4,
  parameter int FC_DATA_CREDITS = FC_HEADER_CREDITS * ((pcie_pkg::MAX_PAYLOAD_DW+3)/4),
  parameter int FC_REFRESH_CYCLES = 128
) (
  input logic clk, rst_n,
  input logic tx_valid,
  output logic tx_ready,
  input pcie_pkg::tlp_packet_t tx_tlp,
  input logic cpl_valid,
  output logic cpl_ready,
  input pcie_pkg::tlp_packet_t cpl_tlp,
  output logic rx_valid,
  input logic rx_ready,
  output pcie_pkg::tlp_packet_t rx_tlp,
  output logic link_tx_valid,
  input logic link_tx_ready,
  output pcie_pkg::dll_packet_t link_tx_packet,
  input logic link_rx_valid,
  output logic link_rx_ready,
  input pcie_pkg::dll_packet_t link_rx_packet,
  input logic link_ack_valid, link_ack_is_nak,
  input logic [11:0] link_ack_seq,
  output logic rx_ack_valid,
  input logic rx_ack_ready,
  output logic rx_ack_is_nak,
  output logic [11:0] rx_ack_seq,
  input logic link_fc_rx_valid,
  output logic link_fc_rx_ready,
  input pcie_pkg::fc_dllp_t link_fc_rx_packet,
  output logic link_fc_tx_valid,
  input logic link_fc_tx_ready,
  output pcie_pkg::fc_dllp_t link_fc_tx_packet,
  output logic fc_initialized, fc_protocol_error,
  output logic [31:0] replay_count, crc_error_count, sequence_error_count
);
  import pcie_pkg::*;
  logic permit, dll_tx_ready, raw_valid, raw_ready;
  logic selected_valid;
  tlp_packet_t raw_tlp, selected_tlp;
  fc_credits_t available;
  pcie_tlp_tx_arbiter #(.FC_ENABLE(FC_ENABLE), .CPL_ENABLE(CPL_ENABLE)) u_tx_arbiter (
    .clk(clk), .rst_n(rst_n), .initialized(fc_initialized), .available(available),
    .req_valid(tx_valid), .req_ready(tx_ready), .req_tlp(tx_tlp),
    .cpl_valid(cpl_valid), .cpl_ready(cpl_ready), .cpl_tlp(cpl_tlp),
    .out_valid(selected_valid), .out_ready(dll_tx_ready && permit), .out_tlp(selected_tlp)
  );
  pcie_dll_tx #(.REPLAY_TIMEOUT(REPLAY_TIMEOUT)) u_tx (
    .clk(clk), .rst_n(rst_n), .tlp_valid(selected_valid && permit), .tlp_ready(dll_tx_ready), .tlp(selected_tlp),
    .link_valid(link_tx_valid), .link_ready(link_tx_ready), .link_packet(link_tx_packet),
    .ack_valid(link_ack_valid), .ack_is_nak(link_ack_is_nak), .ack_seq(link_ack_seq),
    .replay_count(replay_count)
  );
  pcie_dll_rx u_rx (
    .clk(clk), .rst_n(rst_n), .link_valid(link_rx_valid), .link_ready(link_rx_ready),
    .link_packet(link_rx_packet), .tlp_valid(raw_valid), .tlp_ready(raw_ready), .tlp(raw_tlp),
    .ack_valid(rx_ack_valid), .ack_ready(rx_ack_ready), .ack_is_nak(rx_ack_is_nak), .ack_seq(rx_ack_seq),
    .crc_error_count(crc_error_count), .sequence_error_count(sequence_error_count)
  );
  generate if (FC_ENABLE) begin : g_fc
    logic init1_done, init2_done, tx_error, rx_error;
    fc_credits_t credit_limit;
    pcie_fc_tx u_tx_credits (
      .clk(clk), .rst_n(rst_n), .fc_valid(link_fc_rx_valid), .fc_ready(link_fc_rx_ready),
      .fc_packet(link_fc_rx_packet), .peer_tlp_seen(raw_valid), .local_initialized(fc_initialized),
      .tlp(selected_tlp), .consume(selected_valid && dll_tx_ready && permit), .permit(permit),
      .init1_done(init1_done), .init2_done(init2_done), .available(available), .protocol_error(tx_error)
    );
    pcie_fc_rx_buffer #(.HEADER_CREDITS(FC_HEADER_CREDITS), .DATA_CREDITS(FC_DATA_CREDITS)) u_rx_buffer (
      .clk(clk), .rst_n(rst_n), .initialized(fc_initialized),
      .in_valid(raw_valid), .in_ready(raw_ready), .in_tlp(raw_tlp),
      .out_valid(rx_valid), .out_ready(rx_ready), .out_tlp(rx_tlp),
      .credit_limit(credit_limit), .protocol_error(rx_error)
    );
    pcie_fc_dllp_tx #(.REFRESH_CYCLES(FC_REFRESH_CYCLES)) u_advertise (
      .clk(clk), .rst_n(rst_n), .peer_init1_done(init1_done), .peer_init2_done(init2_done),
      .credit_limit(credit_limit), .initialized(fc_initialized),
      .fc_valid(link_fc_tx_valid), .fc_ready(link_fc_tx_ready), .fc_packet(link_fc_tx_packet)
    );
    assign fc_protocol_error = tx_error || rx_error;
  end else begin : g_legacy
    // Explicit compatibility/testing option only; not credit-safe on a real link.
    assign permit = 1'b1;
    assign available = '1;
    assign rx_valid = raw_valid;
    assign raw_ready = rx_ready;
    assign rx_tlp = raw_tlp;
    assign fc_initialized = rst_n;
    assign fc_protocol_error = 1'b0;
    assign link_fc_rx_ready = rst_n;
    assign link_fc_tx_valid = 1'b0;
    assign link_fc_tx_packet = '0;
  end endgenerate
endmodule
