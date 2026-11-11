// Transaction-layer completer. Never fabricates read data or acknowledges a
// write before the backend response. One operation/response outstanding.
module pcie_completer #(
  parameter bit BACKEND_ENABLE = 1'b0,
  parameter logic [15:0] COMPLETER_ID = 16'h0000
) (
  input logic clk, rst_n,
  input logic in_valid,
  output logic in_ready,
  input pcie_pkg::tlp_packet_t in_tlp,
  input logic in_ecrc_error,
  output logic backend_req_valid,
  input logic backend_req_ready,
  output pcie_pkg::cpl_backend_req_t backend_req,
  input logic backend_rsp_valid,
  output logic backend_rsp_ready,
  input pcie_pkg::cpl_backend_rsp_t backend_rsp,
  output logic cpl_valid,
  input logic cpl_ready,
  output pcie_pkg::tlp_packet_t cpl_tlp,
  output logic [31:0] error_count
);
  import pcie_pkg::*;
  typedef enum logic [2:0] {IDLE, REQUEST, RESPONSE, FORMAT, SEND} state_e;
  state_e state;
  tlp_packet_t request_q, formatted;
  cpl_backend_rsp_t response_q;
  txn_kind_e kind;
  logic read_request, supported;
  logic [3:0] byte_enable;
  integer first_byte, last_byte, byte_count;

  assign in_ready = rst_n && (state == IDLE);
  assign backend_req_valid = BACKEND_ENABLE && (state == REQUEST);
  assign backend_rsp_ready = BACKEND_ENABLE && (state == RESPONSE);
  assign cpl_valid = (state == SEND);
  assign kind = decode_tlp_kind(request_q);
  assign read_request = (kind == TXN_MEM_RD) || (kind == TXN_IO_RD) ||
                        (kind == TXN_CFG0_RD) || (kind == TXN_CFG1_RD);
  always_comb begin
    supported = tlp_needs_completion(in_tlp) && in_tlp.address[1:0] == 0 &&
                in_tlp.length_dw != 0 && int'(in_tlp.length_dw) <= MAX_PAYLOAD_DW;
    if (decode_tlp_kind(in_tlp) == TXN_MEM_RD) begin
      if ((int'(in_tlp.address[11:0]) + 4*int'(in_tlp.length_dw)) > 4096) supported = 0;
      if (in_tlp.length_dw > 1 && (in_tlp.first_be == 0 || in_tlp.last_be == 0)) supported = 0;
    end else if (in_tlp.length_dw != 1) supported = 0;
    backend_req = '0;
    backend_req.kind = kind;
    backend_req.tc = request_q.tc;
    backend_req.attr = request_q.attr;
    backend_req.address = request_q.address;
    backend_req.length_dw = request_q.length_dw;
    backend_req.requester_id = request_q.requester_id;
    backend_req.tag = request_q.tag;
    backend_req.first_be = request_q.first_be;
    backend_req.last_be = (request_q.length_dw == 1) ? 4'b0 : request_q.last_be;
    backend_req.payload = request_q.payload;

    // Byte Count describes the span, not the population count of byte enables.
    first_byte = 0;
    last_byte = 0;
    for (int b = 3; b >= 0; b--) if (request_q.first_be[b]) first_byte = b;
    for (int b = 0; b < 4; b++) begin
      if ((request_q.length_dw == 1 ? request_q.first_be[b] : request_q.last_be[b])) last_byte = b;
    end
    byte_count = (request_q.length_dw == 1) ? last_byte-first_byte+1 :
                 4*(int'(request_q.length_dw)-1)+last_byte-first_byte+1;
    formatted = '0;
    formatted.fmt = 3'b000;
    formatted.tlp_type = 5'b01010;
    formatted.tc = request_q.tc;
    formatted.attr = request_q.attr;
    formatted.requester_id = request_q.requester_id;
    formatted.completer_id = COMPLETER_ID;
    formatted.tag = request_q.tag;
    formatted.cpl_status = response_q.status;
    formatted.byte_count = 12'd4;
    byte_enable = '0;
    if (response_q.status == CPL_SC && read_request) begin
      formatted.fmt = 3'b010;
      formatted.length_dw = request_q.length_dw;
      if (kind == TXN_MEM_RD) begin
        formatted.byte_count = 12'(byte_count);
        formatted.lower_address = {request_q.address[6:2], 2'b00} + 7'(first_byte);
      end
      for (int w = 0; w < MAX_PAYLOAD_DW; w++) begin
        byte_enable = (w == 0) ? request_q.first_be :
                      ((w == int'(request_q.length_dw)-1) ? request_q.last_be : 4'hf);
        for (int b = 0; b < 4; b++)
          if (w < int'(request_q.length_dw) && byte_enable[b])
            formatted.payload[32*w+8*b+:8] = response_q.data[32*w+8*b+:8];
      end
    end
  end
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state <= IDLE;
      request_q <= '0;
      response_q <= '0;
      cpl_tlp <= '0;
      error_count <= 0;
    end else begin
      case (state)
        IDLE: if (in_valid && in_ready && tlp_needs_completion(in_tlp)) begin
          // Corrupted/poisoned requests must never reach a side-effecting backend.
          // Discard rather than replying to possibly corrupted requester/tag bits.
          if (in_ecrc_error || in_tlp.poisoned) error_count <= error_count + 1'b1;
          else begin
$display("[%0t] COMPLETER RX: tag=%h fmt=%b type=%b kind=%0d addr=%h len=%0d first_be=%h last_be=%h payload=%h",
         $time,
         in_tlp.tag,
         in_tlp.fmt,
         in_tlp.tlp_type,
         decode_tlp_kind(in_tlp),
         in_tlp.address,
         in_tlp.length_dw,
         in_tlp.first_be,
         in_tlp.last_be,
         in_tlp.payload[31:0]);
            request_q <= in_tlp;
            response_q <= '{status:CPL_UR, data:'0};
            state <= (BACKEND_ENABLE && supported) ? REQUEST : FORMAT;
          end
        end
        REQUEST: if (backend_req_ready) state <= RESPONSE;
        RESPONSE: if (backend_rsp_valid) begin
          response_q <= backend_rsp;
          if (backend_rsp.status != CPL_SC && backend_rsp.status != CPL_UR && backend_rsp.status != CPL_CA) begin
            response_q.status <= CPL_CA;
            error_count <= error_count + 1'b1;
          end
          state <= FORMAT;
        end
        FORMAT: begin cpl_tlp <= formatted; state <= SEND; end
        SEND: if (cpl_ready) state <= IDLE;
        default: state <= IDLE;
      endcase
    end
  end
endmodule
