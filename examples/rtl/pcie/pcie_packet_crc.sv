// CRC adapter for the existing internal packet format. Captures the complete
// packet at acceptance; its input-to-CRC path always crosses engine registers.
module pcie_packet_crc #(
  parameter bit LINK_CRC = 1'b0
) (
  input logic clk,
  input logic rst_n,
  input logic in_valid,
  output logic in_ready,
  input pcie_pkg::tlp_packet_t in_tlp,
  input logic [11:0] in_seq,
  output logic out_valid,
  input logic out_ready,
  output logic [31:0] out_crc
);
  import pcie_pkg::*;
  localparam int HEADER_BITS = $bits(tlp_ecrc_header_t);
  localparam int BITS = LINK_CRC ? (12+$bits(tlp_packet_t)) : (HEADER_BITS+PAYLOAD_W);
  localparam int COUNT_W = $clog2(BITS+1);
  logic [BITS-1:0] image;
  logic [COUNT_W-1:0] count;
  if (LINK_CRC) begin : g_link
    // Existing reference consumes sequence first, then LSB-first packed TLP.
    assign image = {in_tlp, in_seq};
    assign count = COUNT_W'(BITS);
  end else begin : g_end_to_end
    tlp_ecrc_header_t header;
    always_comb begin
      header.fmt = in_tlp.fmt;
      header.tlp_type = in_tlp.tlp_type;
      header.tc = in_tlp.tc;
      header.attr = in_tlp.attr;
      header.poisoned = 1'b1;
      header.digest_present = 1'b1;
      header.length_dw = in_tlp.length_dw;
      header.requester_id = in_tlp.requester_id;
      header.completer_id = in_tlp.completer_id;
      header.tag = in_tlp.tag;
      header.first_be = in_tlp.first_be;
      header.last_be = in_tlp.last_be;
      header.cpl_status = in_tlp.cpl_status;
      header.byte_count = in_tlp.byte_count;
      header.lower_address = in_tlp.lower_address;
      header.address = in_tlp.address;
      image = {in_tlp.payload, header};
      count = COUNT_W'(HEADER_BITS);
      if (in_tlp.fmt[1]) begin
        // Preserve the reference model's clamp to available payload storage.
        if (in_tlp.length_dw >= 10'(MAX_PAYLOAD_DW)) count = COUNT_W'(BITS);
        else count = COUNT_W'(HEADER_BITS) + (COUNT_W'(in_tlp.length_dw) << 5);
      end
    end
  end
  pcie_crc32_engine #(.MAX_BITS(BITS), .CHUNK_BITS(8)) u_crc (
    .clk(clk), .rst_n(rst_n), .start(in_valid), .ready(in_ready),
    .data(image), .bit_count(count), .result_valid(out_valid),
    .result_ready(out_ready), .result(out_crc)
  );
endmodule
