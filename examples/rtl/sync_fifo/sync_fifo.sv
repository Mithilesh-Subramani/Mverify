module sync_fifo #(
  parameter int WIDTH = 32,
  parameter int DEPTH = 8
) (
  input logic clk, rst_n,
  input logic wr_valid,
  output logic wr_ready,
  input logic [WIDTH-1:0] wr_data,
  output logic rd_valid,
  input logic rd_ready,
  output logic [WIDTH-1:0] rd_data
);
  logic [WIDTH-1:0] mem [0:DEPTH-1];
  logic [$clog2(DEPTH):0] count;
  logic [$clog2(DEPTH)-1:0] wr_ptr, rd_ptr;
  assign wr_ready = (count < DEPTH);
  assign rd_valid = (count != 0);
  assign rd_data = mem[rd_ptr];
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin count <= '0; wr_ptr <= '0; rd_ptr <= '0; end
    else begin
      if (wr_valid && wr_ready) begin mem[wr_ptr] <= wr_data; wr_ptr <= wr_ptr + 1'b1; end
      if (rd_valid && rd_ready) rd_ptr <= rd_ptr + 1'b1;
      case ({wr_valid && wr_ready, rd_valid && rd_ready})
        2'b10: count <= count + 1'b1;
        2'b01: count <= count - 1'b1;
        default: count <= count;
      endcase
    end
  end
endmodule
