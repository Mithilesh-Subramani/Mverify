module pcie_tx_data_path #(
  parameter int NUM_TC = pcie_pkg::NUM_TC,
  parameter int QUEUE_DEPTH = 4
) (
  input  logic                       clk,
  input  logic                       rst_n,
  input  logic                       entry_valid,
  output logic                       entry_ready,
  input  pcie_pkg::tx_entry_t        entry,
  input  logic [NUM_TC*8-1:0]        tc_weights,
  output logic                       tlp_valid,
  input  logic                       tlp_ready,
  output pcie_pkg::tlp_packet_t      tlp
);
  import pcie_pkg::*;
  localparam int ENTRY_W = $bits(tx_entry_t);
  localparam int INDEX_W = (NUM_TC > 1) ? $clog2(NUM_TC) : 1;
  localparam int MUX_LEAVES = 1 << $clog2(NUM_TC);

  logic [NUM_TC-1:0] fifo_in_valid;
  logic [NUM_TC-1:0] fifo_in_ready;
  logic [NUM_TC-1:0] fifo_out_valid;
  logic [NUM_TC-1:0] fifo_out_ready;
  logic [ENTRY_W-1:0] fifo_out_data [0:NUM_TC-1];
  logic [NUM_TC-1:0] grant_onehot;
  logic grant_valid;
  logic [INDEX_W-1:0] grant_index;
  logic grant_accept;
  logic slot_ready;
  logic [ENTRY_W-1:0] mux_tree [0:2*MUX_LEAVES-2];
  tx_entry_t selected_entry;
  tlp_packet_t formatted_tlp;
  genvar tc;

  assign entry_ready = (int'(entry.tc) < NUM_TC) ? fifo_in_ready[entry.tc] : 1'b0;

  generate
    for (tc = 0; tc < NUM_TC; tc = tc + 1) begin : g_tc_fifo
      assign fifo_in_valid[tc] = entry_valid && (entry.tc == tc);
      assign fifo_out_ready[tc] = grant_accept && grant_onehot[tc];

      pcie_sync_fifo #(
        .WIDTH (ENTRY_W),
        .DEPTH (QUEUE_DEPTH)
      ) u_fifo (
        .clk       (clk),
        .rst_n     (rst_n),
        .in_valid  (fifo_in_valid[tc]),
        .in_ready  (fifo_in_ready[tc]),
        .in_data   (entry),
        .out_valid (fifo_out_valid[tc]),
        .out_ready (fifo_out_ready[tc]),
        .out_data  (fifo_out_data[tc])
      );
    end
  endgenerate

  pcie_wrr_arbiter #(
    .NUM_TC (NUM_TC),
    .WEIGHT_W (8)
  ) u_wrr (
    .clk          (clk),
    .rst_n        (rst_n),
    .request      (fifo_out_valid),
    .weight_cfg   (tc_weights),
    .grant_valid  (grant_valid),
    .grant_index  (grant_index),
    .grant_onehot (grant_onehot),
    .grant_accept (grant_accept)
  );

  // A balanced one-hot mux avoids encoding the grant and then decoding it in
  // a second wide packet mux. Padding supports non-power-of-two TC counts.
  for (genvar leaf = 0; leaf < MUX_LEAVES; leaf = leaf + 1) begin : g_mux_leaf
    if (leaf < NUM_TC) begin : g_real
      assign mux_tree[MUX_LEAVES-1+leaf] = fifo_out_data[leaf] &
                                         {ENTRY_W{grant_onehot[leaf]}};
    end else begin : g_padding
      assign mux_tree[MUX_LEAVES-1+leaf] = '0;
    end
  end
  for (genvar node = 0; node < MUX_LEAVES-1; node = node + 1) begin : g_mux_node
    assign mux_tree[node] = mux_tree[2*node+1] | mux_tree[2*node+2];
  end
  assign selected_entry = tx_entry_t'(mux_tree[0]);

  always_comb begin
    formatted_tlp = '0;
    formatted_tlp.tc           = selected_entry.tc;
    formatted_tlp.attr         = selected_entry.attr;
    formatted_tlp.length_dw    = selected_entry.length_dw;
    formatted_tlp.requester_id = selected_entry.requester_id;
    formatted_tlp.tag          = selected_entry.tag;
    formatted_tlp.first_be     = selected_entry.first_be;
    formatted_tlp.last_be      = selected_entry.last_be;
    formatted_tlp.address      = selected_entry.address;
    formatted_tlp.payload      = selected_entry.payload;

    case (selected_entry.kind)
      TXN_MEM_RD: begin
        formatted_tlp.fmt = 3'b001;       // 4-DW header, no data
        formatted_tlp.tlp_type = 5'b00000;
      end
      TXN_MEM_WR: begin
        formatted_tlp.fmt = 3'b011;       // 4-DW header, with data
        formatted_tlp.tlp_type = 5'b00000;
      end
      TXN_IO_RD: begin
        formatted_tlp.fmt = 3'b000;
        formatted_tlp.tlp_type = 5'b00010;
      end
      TXN_IO_WR: begin
        formatted_tlp.fmt = 3'b010;
        formatted_tlp.tlp_type = 5'b00010;
      end
      TXN_CFG0_RD: begin
        formatted_tlp.fmt = 3'b000;
        formatted_tlp.tlp_type = 5'b00100;
      end
      TXN_CFG0_WR: begin
        formatted_tlp.fmt = 3'b010;
        formatted_tlp.tlp_type = 5'b00100;
      end
      TXN_CFG1_RD: begin
        formatted_tlp.fmt = 3'b000;
        formatted_tlp.tlp_type = 5'b00101;
      end
      TXN_CFG1_WR: begin
        formatted_tlp.fmt = 3'b010;
        formatted_tlp.tlp_type = 5'b00101;
      end
      TXN_MSG: begin
        formatted_tlp.fmt = 3'b011;
        formatted_tlp.tlp_type = 5'b10000;
      end
      default: begin
        formatted_tlp.fmt = 3'b000;
        formatted_tlp.tlp_type = 5'b11111;
      end
    endcase
  end

  // One elastic packet slot isolates arbitration and formatting from CRC.
  // Quota consumption and FIFO dequeue occur at slot acceptance, independent
  // of subsequent weight changes or downstream backpressure. A simultaneous
  // output transfer and refill sustains one selected packet per clock.
  assign slot_ready = !tlp_valid || tlp_ready;
  assign grant_accept = grant_valid && slot_ready;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      tlp_valid <= 1'b0;
      tlp <= '0;
    end else if (slot_ready) begin
      tlp_valid <= grant_valid;
      if (grant_valid)
        tlp <= formatted_tlp;
    end
  end
endmodule
