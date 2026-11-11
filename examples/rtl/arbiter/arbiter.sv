module arbiter #(
  parameter int N = 4
) (
  input logic clk, rst_n,
  input logic [N-1:0] request,
  output logic [N-1:0] grant
);
  logic [$clog2(N)-1:0] last_grant;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) last_grant <= '0;
    else if (|request) last_grant <= last_grant + 1'b1;
  end
  always_comb begin
    grant = '0;
    for (int i = 0; i < N; i++) begin
      if (request[(last_grant+i)%N] && grant == '0)
        grant[(last_grant+i)%N] = 1'b1;
    end
  end
endmodule
