module pcie_tx_control #(
  parameter int MAX_PAYLOAD_DW = pcie_pkg::MAX_PAYLOAD_DW
) (
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

  output logic                         entry_valid,
  input  logic                         entry_ready,
  output pcie_pkg::tx_entry_t          entry,

  output logic                         reject_valid,
  output logic [2:0]                   reject_reason
);
  import pcie_pkg::*;

  txn_kind_e decoded_kind;
  logic [2:0] decoded_tc;
  logic [63:0] decoded_address;
  logic decoded_valid;
  logic length_valid;
  logic fixed_length_valid;
  logic aligned;
  logic legal;

  pcie_addr_decoder u_addr_decoder (
    .map_addr       (req_map_addr),
    .kind           (decoded_kind),
    .traffic_class  (decoded_tc),
    .target_address (decoded_address),
    .decode_valid   (decoded_valid)
  );

  always_comb begin
    length_valid = (req_length_dw != 0) &&
                   (req_length_dw <= MAX_PAYLOAD_DW);
    aligned = (decoded_address[1:0] == 2'b00);

    case (decoded_kind)
      TXN_IO_RD, TXN_IO_WR,
      TXN_CFG0_RD, TXN_CFG0_WR,
      TXN_CFG1_RD, TXN_CFG1_WR:
        fixed_length_valid = (req_length_dw == 1);
      default:
        fixed_length_valid = 1'b1;
    endcase

    legal = decoded_valid && length_valid && aligned && fixed_length_valid;

    entry = '0;
    entry.kind         = decoded_kind;
    entry.tc           = decoded_tc;
    entry.attr         = req_attr;
    entry.length_dw    = req_length_dw;
    entry.requester_id = req_requester_id;
    entry.tag          = req_tag;
    entry.first_be     = req_first_be;
    entry.last_be      = req_last_be;
    entry.address      = decoded_address;
    entry.payload      = req_payload;

    entry_valid = req_valid && legal;
    req_ready = legal ? entry_ready : 1'b1;
    reject_valid = req_valid && req_ready && !legal;

    if (!decoded_valid)
      reject_reason = 3'd1;
    else if (!length_valid)
      reject_reason = 3'd2;
    else if (!aligned)
      reject_reason = 3'd3;
    else if (!fixed_length_valid)
      reject_reason = 3'd4;
    else
      reject_reason = 3'd0;
  end
endmodule
