module pcie_sync_fifo #(
  parameter int WIDTH = 32,
  parameter int DEPTH = 4
) (
  input  logic             clk,
  input  logic             rst_n,
  input  logic             in_valid,
  output logic             in_ready,
  input  logic [WIDTH-1:0] in_data,
  output logic             out_valid,
  input  logic             out_ready,
  output logic [WIDTH-1:0] out_data
);
  localparam int PTR_W   = (DEPTH <= 1) ? 1 : $clog2(DEPTH);
  localparam int COUNT_W = $clog2(DEPTH + 1);

  logic [WIDTH-1:0] mem [0:DEPTH-1];
  logic [PTR_W-1:0] rd_ptr;
  logic [PTR_W-1:0] wr_ptr;
  logic [COUNT_W-1:0] count;
  logic push;
  logic pop;

  assign in_ready = (count < DEPTH);
  assign out_valid = (count != 0);
  assign out_data = mem[rd_ptr];
  assign push = in_valid && in_ready;
  assign pop = out_valid && out_ready;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      rd_ptr <= '0;
      wr_ptr <= '0;
      count  <= '0;
  foreach(mem[i]) begin     //mem initialization for each address was made since values were assigned as X after reset instead of 0
      mem[i] <='0 ;
end
    end else begin
      if (push) begin
        mem[wr_ptr] <= in_data;
        if (wr_ptr == DEPTH-1)
          wr_ptr <= '0;
        else
          wr_ptr <= wr_ptr + 1'b1;
      end

      if (pop) begin
        if (rd_ptr == DEPTH-1)
          rd_ptr <= '0;
        else
          rd_ptr <= rd_ptr + 1'b1;
      end

      case ({push, pop})
        2'b10: count <= count + 1'b1;
        2'b01: count <= count - 1'b1;
        default: count <= count;
      endcase
    end
  end
endmodule
