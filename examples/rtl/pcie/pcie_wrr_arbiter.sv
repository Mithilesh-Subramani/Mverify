module pcie_wrr_arbiter #(
  parameter int NUM_TC = 8,
  parameter int WEIGHT_W = 8
) (
  input  logic                         clk,
  input  logic                         rst_n,
  input  logic [NUM_TC-1:0]            request,
  input  logic [NUM_TC*WEIGHT_W-1:0]   weight_cfg,
  output logic                         grant_valid,
  output logic [((NUM_TC > 1) ? $clog2(NUM_TC) : 1)-1:0] grant_index,
  output logic [NUM_TC-1:0]            grant_onehot,
  input  logic                         grant_accept
);
  localparam int INDEX_W = (NUM_TC > 1) ? $clog2(NUM_TC) : 1;
  localparam int PREFIX_LEVELS = $clog2(NUM_TC);

  logic [WEIGHT_W-1:0] remaining [0:NUM_TC-1];
  logic [INDEX_W-1:0] rr_pointer;
  logic reload_round;
  logic [NUM_TC-1:0] active;
  logic [NUM_TC-1:0] eligible;
  logic [NUM_TC-1:0] round_mask;
  logic [NUM_TC-1:0] after_pointer;
  logic [NUM_TC-1:0] priority_mask;
  logic [NUM_TC-1:0] prefix_or [0:PREFIX_LEVELS];

  // Interleaved weighted round-robin: each active TC receives one grant per
  // pass while it has quota. When all requesting TCs exhaust their quotas,
  // the next weighted round is loaded from weight_cfg. All eligibility tests
  // are local to a TC; there are no serial, dynamically indexed searches.
  for (genvar tc = 0; tc < NUM_TC; tc = tc + 1) begin : g_eligibility
    assign active[tc] = request[tc] &&
                       (weight_cfg[tc*WEIGHT_W +: WEIGHT_W] != '0);
    assign eligible[tc] = active[tc] && (remaining[tc] != '0);
    if (tc == (1 << INDEX_W)-1) begin : g_last_encoding
      assign after_pointer[tc] = round_mask[tc];
    end else begin : g_pointer_mask
      assign after_pointer[tc] = round_mask[tc] &&
                                 (INDEX_W'(tc) >= rr_pointer);
    end

    // A selected TC consumes quota only when its packet is accepted. Local
    // one-hot updates also avoid a wide selected-weight/read-modify-write mux.
    always_ff @(posedge clk or negedge rst_n) begin
      if (!rst_n)
        remaining[tc] <= '0;
      else if (grant_valid && grant_accept) begin
        if (reload_round)
          remaining[tc] <= weight_cfg[tc*WEIGHT_W +: WEIGHT_W] -
                           WEIGHT_W'(grant_onehot[tc]);
        else if (grant_onehot[tc])
          remaining[tc] <= remaining[tc] - 1'b1;
      end
    end
  end

  assign reload_round = !(|eligible);
  assign round_mask = reload_round ? active : eligible;
  // Prefer candidates at/above the pointer; wrap only if that set is empty.
  assign priority_mask = (|after_pointer) ? after_pointer : round_mask;
  assign grant_valid = |priority_mask;

  // Parallel prefix OR yields a first-set-bit selector with logarithmic
  // logical depth, including non-power-of-two NUM_TC values.
  assign prefix_or[0] = priority_mask;
  for (genvar level = 0; level < PREFIX_LEVELS; level = level + 1) begin : g_prefix
    for (genvar tc = 0; tc < NUM_TC; tc = tc + 1) begin : g_tc
      if (tc >= (1 << level)) begin : g_merge
        assign prefix_or[level+1][tc] = prefix_or[level][tc] |
                                        prefix_or[level][tc-(1 << level)];
      end else begin : g_copy
        assign prefix_or[level+1][tc] = prefix_or[level][tc];
      end
    end
  end

  assign grant_onehot[0] = priority_mask[0];
  for (genvar tc = 1; tc < NUM_TC; tc = tc + 1) begin : g_onehot
    assign grant_onehot[tc] = priority_mask[tc] &&
                             !prefix_or[PREFIX_LEVELS][tc-1];
  end
  for (genvar bit_idx = 0; bit_idx < INDEX_W; bit_idx = bit_idx + 1) begin : g_encode
    wire [NUM_TC-1:0] index_bits;
    for (genvar tc = 0; tc < NUM_TC; tc = tc + 1) begin : g_tc
      assign index_bits[tc] = grant_onehot[tc] && ((tc & (1 << bit_idx)) != 0);
    end
    assign grant_index[bit_idx] = |index_bits;
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      rr_pointer <= '0;
    else if (grant_valid && grant_accept) begin
      if (grant_index == INDEX_W'(NUM_TC-1))
        rr_pointer <= '0;
      else
        rr_pointer <= grant_index + 1'b1;
    end
  end
endmodule
