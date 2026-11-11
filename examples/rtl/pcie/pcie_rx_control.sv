module pcie_rx_control (
  input  logic                    clk,
  input  logic                    rst_n,
  input  logic                    tlp_valid,
  output logic                    tlp_ready,
  input  pcie_pkg::tlp_packet_t   tlp,
  input  logic                    ecrc_error,
  output logic                    meta_valid,
  input  logic                    meta_ready,
  output pcie_pkg::rx_meta_t      meta
);
  import pcie_pkg::*;

  assign tlp_ready = !meta_valid || meta_ready;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      meta_valid <= 1'b0;
      meta <= '0;
    end else begin
      if (meta_valid && meta_ready)
        meta_valid <= 1'b0;

      if (tlp_valid && tlp_ready) begin
        meta_valid        <= 1'b1;
        meta.kind         <= decode_tlp_kind(tlp);
        meta.tc           <= tlp.tc;
        meta.attr         <= tlp.attr;
        meta.length_dw    <= tlp.length_dw;
        meta.requester_id <= tlp.requester_id;
        meta.completer_id <= tlp.completer_id;
        meta.tag          <= tlp.tag;
        meta.cpl_status   <= tlp.cpl_status;
        meta.byte_count   <= tlp.byte_count;
        meta.lower_address <= tlp.lower_address;
        meta.address      <= tlp.address;
        meta.poisoned     <= tlp.poisoned;
        meta.digest_present <= tlp.digest_present;
        meta.ecrc_error   <= ecrc_error;
      end
    end
  end
endmodule
