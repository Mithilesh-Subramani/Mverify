module pcie_addr_decoder (
  input  logic [63:0]             map_addr,
  output pcie_pkg::txn_kind_e     kind,
  output logic [2:0]              traffic_class,
  output logic [63:0]             target_address,
  output logic                    decode_valid
);
  import pcie_pkg::*;

  always_comb begin
    traffic_class = map_addr[59:57];
    target_address = {7'b0, map_addr[56:0]};
    decode_valid = 1'b1;

    case (map_addr[63:60])
      MAP_MEM_RD:  kind = TXN_MEM_RD;
      MAP_MEM_WR:  kind = TXN_MEM_WR;
      MAP_IO_RD:   kind = TXN_IO_RD;
      MAP_IO_WR:   kind = TXN_IO_WR;
      MAP_CFG0_RD: kind = TXN_CFG0_RD;
      MAP_CFG0_WR: kind = TXN_CFG0_WR;
      MAP_CFG1_RD: kind = TXN_CFG1_RD;
      MAP_CFG1_WR: kind = TXN_CFG1_WR;
      MAP_MSG:     kind = TXN_MSG;
      default: begin
        kind = TXN_UNKNOWN;
        decode_valid = 1'b0;
      end
    endcase
  end
endmodule
