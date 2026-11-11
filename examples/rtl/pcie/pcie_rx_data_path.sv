module pcie_rx_data_path (
  input  logic                         clk,
  input  logic                         rst_n,
  input  logic                         tlp_valid,
  output logic                         tlp_ready,
  input  pcie_pkg::tlp_packet_t        tlp,
  output logic                         data_valid,
  input  logic                         data_ready,
  output logic [pcie_pkg::PAYLOAD_W-1:0] data,
  output logic                         data_present
);
  import pcie_pkg::*;

  assign tlp_ready = !data_valid || data_ready;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      data_valid   <= 1'b0;
      data         <= '0;
      data_present <= 1'b0;
    end else begin
      if (data_valid && data_ready)
        data_valid <= 1'b0;

      if (tlp_valid && tlp_ready) begin
        data_valid   <= 1'b1;
        data         <= tlp.payload;
        data_present <= tlp.fmt[1];
      end
    end
  end
endmodule
