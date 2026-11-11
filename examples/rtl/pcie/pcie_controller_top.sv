module pcie_controller_top #(
  parameter int TC_QUEUE_DEPTH = 4,
  parameter int REPLAY_TIMEOUT = 1024,
  parameter bit FC_ENABLE = 1'b1,
  parameter int FC_HEADER_CREDITS = 4,
  parameter int FC_DATA_CREDITS = FC_HEADER_CREDITS * ((pcie_pkg::MAX_PAYLOAD_DW+3)/4),
  parameter int FC_REFRESH_CYCLES = 128,
  parameter bit BACKEND_ENABLE = 1'b0,
  parameter logic [15:0] COMPLETER_ID = 16'h0000
) (
  input  logic                         clk,
  input  logic                         rst_n,

  // Local memory-mapped transaction request interface.
  input  logic                         req_valid,
  output logic                         req_ready,
  input  logic [63:0]                  req_map_addr,
  input  logic [9:0]                   req_length_dw,
  input  logic [15:0]                  req_requester_id,
  input  logic [7:0]                   req_tag,
  input  logic [3:0]                   req_first_be,
  input  logic [3:0]                   req_last_be,
  input  logic [2:0]                   req_attr,
  input  logic [pcie_pkg::PAYLOAD_W-1:0] req_payload,
  input  logic [pcie_pkg::NUM_TC*8-1:0] tc_weights,
  input  logic                         cfg_ecrc_generate_enable,
  input  logic                         cfg_ecrc_check_enable,
  output logic                         req_reject_valid,
  output logic [2:0]                   req_reject_reason,

  // Decoded receive interface. Metadata and data are transferred together.
  output logic                         rx_valid,
  input  logic                         rx_ready,
  output pcie_pkg::rx_meta_t           rx_meta,
  output logic [pcie_pkg::PAYLOAD_W-1:0] rx_data,
  output logic                         rx_data_present,

  // Non-posted completer service; one request outstanding, response in order.
  output logic                         backend_req_valid,
  input  logic                         backend_req_ready,
  output pcie_pkg::cpl_backend_req_t   backend_req,
  input  logic                         backend_rsp_valid,
  output logic                         backend_rsp_ready,
  input  pcie_pkg::cpl_backend_rsp_t   backend_rsp,
  output logic [31:0]                  completion_error_count,

  // Packetized link interface to a PHY/codec adapter.
  output logic                         link_tx_valid,
  input  logic                         link_tx_ready,
  output pcie_pkg::dll_packet_t        link_tx_packet,
  input  logic                         link_rx_valid,
  output logic                         link_rx_ready,
  input  pcie_pkg::dll_packet_t        link_rx_packet,

  // Simplified DLLP ACK/NAK sideband interface.
  input  logic                         link_ack_valid,
  input  logic                         link_ack_is_nak,
  input  logic [11:0]                  link_ack_seq,
  output logic                         rx_ack_valid,
  input  logic                         rx_ack_ready,
  output logic                         rx_ack_is_nak,
  output logic [11:0]                  rx_ack_seq,

  // Decoded, integrity-checked FC DLLPs; independent of TLP/ACK backpressure.
  input  logic                         link_fc_rx_valid,
  output logic                         link_fc_rx_ready,
  input  pcie_pkg::fc_dllp_t            link_fc_rx_packet,
  output logic                         link_fc_tx_valid,
  input  logic                         link_fc_tx_ready,
  output pcie_pkg::fc_dllp_t            link_fc_tx_packet,
  output logic                         fc_initialized,
  output logic                         fc_protocol_error,

  // Diagnostic counters.
  output logic [31:0]                  replay_count,
  output logic [31:0]                  crc_error_count,
  output logic [31:0]                  sequence_error_count,
  output logic [31:0]                  ecrc_error_count
);
  import pcie_pkg::*;

  tx_entry_t tx_entry;
  logic tx_entry_valid;
  logic tx_entry_ready;
  tlp_packet_t tx_base_tlp;
  logic tx_base_tlp_valid;
  logic tx_base_tlp_ready;
  tlp_packet_t tx_protected_tlp;
  logic tx_protected_tlp_valid;
  logic tx_protected_tlp_ready;

  tlp_packet_t rx_dll_tlp;
  logic rx_dll_tlp_valid;
  logic rx_dll_tlp_ready;
  tlp_packet_t rx_tlp;
  logic rx_tlp_valid;
  logic rx_tlp_ready;
  logic rx_ecrc_error;
  logic rx_ctrl_in_ready;
  logic rx_data_in_ready;
  logic rx_ctrl_out_valid;
  logic rx_ctrl_out_ready;
  logic rx_data_out_valid;
  logic rx_data_out_ready;
  logic cpl_in_ready, is_np;
  logic cpl_valid, cpl_ready, cpl_protected_valid, cpl_protected_ready;
  tlp_packet_t cpl_tlp, cpl_protected_tlp;

  pcie_tx_control u_tx_control (
    .req_valid        (req_valid),
    .req_ready        (req_ready),
    .req_map_addr     (req_map_addr),
    .req_length_dw    (req_length_dw),
    .req_requester_id (req_requester_id),
    .req_tag          (req_tag),
    .req_first_be     (req_first_be),
    .req_last_be      (req_last_be),
    .req_attr         (req_attr),
    .req_payload      (req_payload),
    .entry_valid      (tx_entry_valid),
    .entry_ready      (tx_entry_ready),
    .entry            (tx_entry),
    .reject_valid     (req_reject_valid),
    .reject_reason    (req_reject_reason)
  );

  pcie_tx_data_path #(
    .QUEUE_DEPTH (TC_QUEUE_DEPTH)
  ) u_tx_data_path (
    .clk         (clk),
    .rst_n       (rst_n),
    .entry_valid (tx_entry_valid),
    .entry_ready (tx_entry_ready),
    .entry       (tx_entry),
    .tc_weights  (tc_weights),
    .tlp_valid   (tx_base_tlp_valid),
    .tlp_ready   (tx_base_tlp_ready),
    .tlp         (tx_base_tlp)
  );

  pcie_tlp_ecrc_tx u_tlp_ecrc_tx (
    .clk             (clk),
    .rst_n           (rst_n),
    .generate_enable (cfg_ecrc_generate_enable),
    .tlp_valid       (tx_base_tlp_valid),
    .tlp_ready       (tx_base_tlp_ready),
    .tlp             (tx_base_tlp),
    .protected_valid (tx_protected_tlp_valid),
    .protected_ready (tx_protected_tlp_ready),
    .protected_tlp   (tx_protected_tlp)
  );

  pcie_completer #(.BACKEND_ENABLE(BACKEND_ENABLE), .COMPLETER_ID(COMPLETER_ID)) u_completer (
    .clk(clk), .rst_n(rst_n), .in_valid(rx_tlp_valid && is_np), .in_ready(cpl_in_ready),
    .in_tlp(rx_tlp), .in_ecrc_error(rx_ecrc_error),
    .backend_req_valid(backend_req_valid), .backend_req_ready(backend_req_ready), .backend_req(backend_req),
    .backend_rsp_valid(backend_rsp_valid), .backend_rsp_ready(backend_rsp_ready), .backend_rsp(backend_rsp),
    .cpl_valid(cpl_valid), .cpl_ready(cpl_ready), .cpl_tlp(cpl_tlp), .error_count(completion_error_count)
  );
  // Separate ECRC storage prevents a credit-blocked local request from
  // occupying the only packet slot ahead of a generated completion.
  pcie_tlp_ecrc_tx u_cpl_ecrc_tx (
    .clk(clk), .rst_n(rst_n), .generate_enable(cfg_ecrc_generate_enable),
    .tlp_valid(cpl_valid), .tlp_ready(cpl_ready), .tlp(cpl_tlp),
    .protected_valid(cpl_protected_valid), .protected_ready(cpl_protected_ready), .protected_tlp(cpl_protected_tlp)
  );

  pcie_data_link #(
    .REPLAY_TIMEOUT(REPLAY_TIMEOUT), .FC_ENABLE(FC_ENABLE), .CPL_ENABLE(1'b1),
    .FC_HEADER_CREDITS(FC_HEADER_CREDITS), .FC_DATA_CREDITS(FC_DATA_CREDITS),
    .FC_REFRESH_CYCLES(FC_REFRESH_CYCLES)
  ) u_data_link (
    .clk(clk), .rst_n(rst_n),
    .tx_valid(tx_protected_tlp_valid), .tx_ready(tx_protected_tlp_ready), .tx_tlp(tx_protected_tlp),
    .cpl_valid(cpl_protected_valid), .cpl_ready(cpl_protected_ready), .cpl_tlp(cpl_protected_tlp),
    .rx_valid(rx_dll_tlp_valid), .rx_ready(rx_dll_tlp_ready), .rx_tlp(rx_dll_tlp),
    .link_tx_valid(link_tx_valid), .link_tx_ready(link_tx_ready), .link_tx_packet(link_tx_packet),
    .link_rx_valid(link_rx_valid), .link_rx_ready(link_rx_ready), .link_rx_packet(link_rx_packet),
    .link_ack_valid(link_ack_valid), .link_ack_is_nak(link_ack_is_nak), .link_ack_seq(link_ack_seq),
    .rx_ack_valid(rx_ack_valid), .rx_ack_ready(rx_ack_ready), .rx_ack_is_nak(rx_ack_is_nak), .rx_ack_seq(rx_ack_seq),
    .link_fc_rx_valid(link_fc_rx_valid), .link_fc_rx_ready(link_fc_rx_ready), .link_fc_rx_packet(link_fc_rx_packet),
    .link_fc_tx_valid(link_fc_tx_valid), .link_fc_tx_ready(link_fc_tx_ready), .link_fc_tx_packet(link_fc_tx_packet),
    .fc_initialized(fc_initialized), .fc_protocol_error(fc_protocol_error),
    .replay_count(replay_count), .crc_error_count(crc_error_count), .sequence_error_count(sequence_error_count)
  );

  pcie_tlp_ecrc_rx u_tlp_ecrc_rx (
    .clk              (clk),
    .rst_n            (rst_n),
    .check_enable     (cfg_ecrc_check_enable),
    .tlp_valid        (rx_dll_tlp_valid),
    .tlp_ready        (rx_dll_tlp_ready),
    .tlp              (rx_dll_tlp),
    .checked_valid    (rx_tlp_valid),
    .checked_ready    (rx_tlp_ready),
    .checked_tlp      (rx_tlp),
    .ecrc_error       (rx_ecrc_error),
    .ecrc_error_count (ecrc_error_count)
  );

  // NP requests are owned exclusively by the completer, not duplicated onto
  // application RX (which could otherwise cause a write to execute twice).
  assign is_np = tlp_needs_completion(rx_tlp);
  assign rx_tlp_ready = is_np ? cpl_in_ready : (rx_ctrl_in_ready && rx_data_in_ready);

  pcie_rx_control u_rx_control (
    .clk        (clk),
    .rst_n      (rst_n),
    .tlp_valid  (rx_tlp_valid && !is_np && rx_data_in_ready),
    .tlp_ready  (rx_ctrl_in_ready),
    .tlp        (rx_tlp),
    .ecrc_error (rx_ecrc_error),
    .meta_valid (rx_ctrl_out_valid),
    .meta_ready (rx_ctrl_out_ready),
    .meta       (rx_meta)
  );

  pcie_rx_data_path u_rx_data_path (
    .clk          (clk),
    .rst_n        (rst_n),
    .tlp_valid    (rx_tlp_valid && !is_np && rx_ctrl_in_ready),
    .tlp_ready    (rx_data_in_ready),
    .tlp          (rx_tlp),
    .data_valid   (rx_data_out_valid),
    .data_ready   (rx_data_out_ready),
    .data         (rx_data),
    .data_present (rx_data_present)
  );

  // Rejoin the separately buffered RX control and data paths.
  assign rx_valid = rx_ctrl_out_valid && rx_data_out_valid;
  assign rx_ctrl_out_ready = rx_ready && rx_data_out_valid;
  assign rx_data_out_ready = rx_ready && rx_ctrl_out_valid;
endmodule
