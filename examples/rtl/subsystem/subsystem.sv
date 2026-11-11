module register_bank(input logic clk, rst_n, input logic wr_en, input logic [7:0] wr_data, output logic [7:0] rd_data);
  logic [7:0] reg0;
  always_ff @(posedge clk or negedge rst_n)
    if (!rst_n) reg0 <= '0;
    else if (wr_en) reg0 <= wr_data;
  assign rd_data = reg0;
endmodule
module subsystem(input logic clk, rst_n, input logic wr_en, input logic [7:0] wr_data, output logic [7:0] rd_data);
  register_bank u_regs(.clk(clk), .rst_n(rst_n), .wr_en(wr_en), .wr_data(wr_data), .rd_data(rd_data));
endmodule
