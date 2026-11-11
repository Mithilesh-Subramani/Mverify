module alu #(
  parameter int WIDTH = 32
) (
  input  logic [WIDTH-1:0] a,
  input  logic [WIDTH-1:0] b,
  input  logic [2:0]       op,
  output logic [WIDTH-1:0] result,
  output logic             zero
);
  always_comb begin
    unique case (op)
      3'd0: result = a + b;
      3'd1: result = a - b;
      3'd2: result = a & b;
      3'd3: result = a | b;
      3'd4: result = a ^ b;
      default: result = '0;
    endcase
    zero = (result == '0);
  end
endmodule
