// Registered reflected CRC-32 engine. Each cycle advances at most CHUNK_BITS.
// Constant GF(2) masks form parallel XOR reductions; no full-packet CRC cone.
module pcie_crc32_engine #(
  parameter int MAX_BITS = 512,
  parameter int CHUNK_BITS = 8,
  parameter int COUNT_W = $clog2(MAX_BITS + 1)
) (
  input  logic clk,
  input  logic rst_n,
  input  logic start,
  output logic ready,
  input  logic [MAX_BITS-1:0] data,
  input  logic [COUNT_W-1:0] bit_count,
  output logic result_valid,
  input  logic result_ready,
  output logic [31:0] result
);
  logic busy;
  logic [MAX_BITS-1:0] data_q;
  logic [COUNT_W-1:0] remaining;
  logic [31:0] crc_q, crc_next;
  logic [CHUNK_BITS:0] take;

  // Evaluated at elaboration for each output bit and possible final length.
  function automatic logic [32+CHUNK_BITS-1:0] coefficient_mask(
    input integer output_bit, input integer count
  );
    logic [31:0] basis;
    logic feedback;
    logic [CHUNK_BITS-1:0] input_basis;
    begin
      coefficient_mask = '0;
      for (integer k = 0; k < 32+CHUNK_BITS; k = k+1) begin
        basis = '0;
        input_basis = '0;
        if (k < 32) basis[k] = 1'b1;
        else input_basis[k-32] = 1'b1;
        for (integer j = 0; j < count; j = j+1) begin
          feedback = basis[0] ^ input_basis[j];
          basis = (basis >> 1) ^ (32'hEDB8_8320 & {32{feedback}});
        end
        coefficient_mask[k] = basis[output_bit];
      end
    end
  endfunction

  for (genvar n = 0; n <= CHUNK_BITS; n = n+1) begin : g_length
    if (n == CHUNK_BITS)
      assign take[n] = (remaining >= COUNT_W'(CHUNK_BITS));
    else
      assign take[n] = (remaining == COUNT_W'(n));
  end
  for (genvar b = 0; b < 32; b = b+1) begin : g_output
    logic [CHUNK_BITS:0] terms;
    for (genvar n = 0; n <= CHUNK_BITS; n = n+1) begin : g_tail
      localparam logic [32+CHUNK_BITS-1:0] MASK = coefficient_mask(b, n);
      assign terms[n] = take[n] && (^{data_q[CHUNK_BITS-1:0] & MASK[32+:CHUNK_BITS],
                                     crc_q & MASK[31:0]});
    end
    assign crc_next[b] = |terms;
  end

  assign ready = !busy && !result_valid;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      busy <= 1'b0;
      data_q <= '0;
      remaining <= '0;
      crc_q <= '1;
      result_valid <= 1'b0;
      result <= '0;
    end else begin
      if (result_valid && result_ready) result_valid <= 1'b0;
      if (start && ready) begin
        data_q <= data;
        remaining <= bit_count;
        crc_q <= '1;
        busy <= 1'b1;
      end else if (busy) begin
        crc_q <= crc_next;
        data_q <= data_q >> CHUNK_BITS;
        if (remaining <= COUNT_W'(CHUNK_BITS)) begin
          result <= ~crc_next;
          result_valid <= 1'b1;
          remaining <= '0;
          busy <= 1'b0;
        end else remaining <= remaining - COUNT_W'(CHUNK_BITS);
      end
    end
  end
`ifndef SYNTHESIS
  initial begin
    if (MAX_BITS < CHUNK_BITS || CHUNK_BITS < 1)
      $fatal(1, "Invalid CRC engine parameters");
  end
  always @(posedge clk)
    if (rst_n && start && ready && bit_count > COUNT_W'(MAX_BITS))
      $fatal(1, "CRC input length exceeds MAX_BITS");
`endif
endmodule
