// TX credit-control path. Credits are reserved ONCE when a new TLP enters
// the DLL replay buffer. Replay/ACK/NAK never change these consumed counters.
module pcie_fc_tx (
  input logic clk, rst_n,
  input logic fc_valid,
  output logic fc_ready,
  input pcie_pkg::fc_dllp_t fc_packet,
  input logic peer_tlp_seen,
  input logic local_initialized,
  input pcie_pkg::tlp_packet_t tlp,
  input logic consume,
  output logic permit,
  output logic init1_done, init2_done,
  output pcie_pkg::fc_credits_t available,
  output logic protocol_error
);
  import pcie_pkg::*;
  fc_credits_t limit_q, consumed_q;
  logic [2:0] initialized_class, infinite_header, infinite_data;
  fc_class_e selected_class;
  logic [11:0] cost;
  logic [7:0] header_advance, header_window;
  logic [11:0] data_advance, data_window;
  logic update_ok;

  assign fc_ready = rst_n;
  assign init1_done = &initialized_class;
  assign selected_class = tlp_fc_class(tlp);
  assign cost = tlp_fc_data_cost(tlp);
  always_comb begin
    for (int c = 0; c < 3; c++) begin
      available.header[c] = infinite_header[c] ? 8'hff :
                            limit_q.header[c] - consumed_q.header[c];
      available.data[c] = infinite_data[c] ? 12'hfff :
                          limit_q.data[c] - consumed_q.data[c];
    end
    permit = 1'b0;
    if (rst_n && local_initialized && init1_done && init2_done && tlp_fc_supported(tlp))
      permit = (available.header[selected_class] != 0) &&
               (available.data[selected_class] >= cost);

    header_advance = '0;
    data_advance = '0;
    header_window = '0;
    data_window = '0;
    update_ok = 1'b0;
    if (fc_packet.credit_class != FC_INVALID) begin
      header_advance = fc_packet.header_limit - limit_q.header[fc_packet.credit_class];
      data_advance = fc_packet.data_limit - limit_q.data[fc_packet.credit_class];
      header_window = fc_packet.header_limit - consumed_q.header[fc_packet.credit_class];
      data_window = fc_packet.data_limit - consumed_q.data[fc_packet.credit_class];
      // Modulo comparisons are unambiguous only within a half-counter window.
      // A zero UPDATE is an ordinary wrapped limit, NOT infinite credit.
      update_ok = (infinite_header[fc_packet.credit_class] ? (fc_packet.header_limit == 0) :
                   (!header_advance[7] && !header_window[7])) &&
                  (infinite_data[fc_packet.credit_class] ? (fc_packet.data_limit == 0) :
                   (!data_advance[11] && !data_window[11]));
    end
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      limit_q <= '0;
      consumed_q <= '0;
      initialized_class <= '0;
      infinite_header <= '0;
      infinite_data <= '0;
      init2_done <= 1'b0;
      protocol_error <= 1'b0;
    end else begin
      if (init1_done && peer_tlp_seen) init2_done <= 1'b1;
      if (consume) begin
        if (permit) begin
          if (!infinite_header[selected_class])
            consumed_q.header[selected_class] <= consumed_q.header[selected_class] + 8'd1;
          if (!infinite_data[selected_class])
            consumed_q.data[selected_class] <= consumed_q.data[selected_class] + cost;
        end else protocol_error <= 1'b1;
      end
      if (fc_valid && fc_ready) begin
        if ((fc_packet.vc != 0) || (fc_packet.credit_class == FC_INVALID) ||
            (fc_packet.kind == FC_RESERVED)) begin
          protocol_error <= 1'b1; // Ignore unsupported/invalid DLLPs atomically.
        end else if (fc_packet.kind == FC_UPDATE) begin
          if (init1_done && update_ok) begin
            limit_q.header[fc_packet.credit_class] <= fc_packet.header_limit;
            limit_q.data[fc_packet.credit_class] <= fc_packet.data_limit;
            init2_done <= 1'b1; // An UpdateFC also proves the peer reached FC_INIT2.
          end else protocol_error <= 1'b1;
        end else begin
          // Capture the first InitFC1 OR InitFC2 for each class. Later InitFC
          // messages do not replenish credits or reset the consumed counters.
          if (!initialized_class[fc_packet.credit_class]) begin
            if (fc_packet.header_limit[7] || fc_packet.data_limit[11]) begin
              protocol_error <= 1'b1;
            end else begin
              limit_q.header[fc_packet.credit_class] <= fc_packet.header_limit;
              limit_q.data[fc_packet.credit_class] <= fc_packet.data_limit;
              infinite_header[fc_packet.credit_class] <= (fc_packet.header_limit == 0);
              infinite_data[fc_packet.credit_class] <= (fc_packet.data_limit == 0);
              initialized_class[fc_packet.credit_class] <= 1'b1;
            end
          end
          if ((fc_packet.kind == FC_INIT2) && init1_done) init2_done <= 1'b1;
        end
      end
    end
  end
endmodule
