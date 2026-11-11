package pcie_pkg;
  parameter int NUM_TC         = 8;
  parameter int MAX_PAYLOAD_DW = 8;
  parameter int PAYLOAD_W      = MAX_PAYLOAD_DW * 32;

  // Memory-mapped request address:
  //   [63:60] transaction opcode
  //   [59:57] traffic class
  //   [56:0]  PCIe target address / message-specific value
  typedef enum logic [3:0] {
    MAP_MEM_RD  = 4'h0,
    MAP_MEM_WR  = 4'h1,
    MAP_IO_RD   = 4'h2,
    MAP_IO_WR   = 4'h3,
    MAP_CFG0_RD = 4'h4,
    MAP_CFG0_WR = 4'h5,
    MAP_CFG1_RD = 4'h6,
    MAP_CFG1_WR = 4'h7,
    MAP_MSG     = 4'h8
  } map_opcode_e;

  typedef enum logic [3:0] {
    TXN_MEM_RD  = 4'd0,
    TXN_MEM_WR  = 4'd1,
    TXN_IO_RD   = 4'd2,
    TXN_IO_WR   = 4'd3,
    TXN_CFG0_RD = 4'd4,
    TXN_CFG0_WR = 4'd5,
    TXN_CFG1_RD = 4'd6,
    TXN_CFG1_WR = 4'd7,
    TXN_MSG     = 4'd8,
    TXN_CPL     = 4'd9,
    TXN_CPLD    = 4'd10,
    TXN_UNKNOWN = 4'd15
  } txn_kind_e;

  typedef struct packed {
    txn_kind_e          kind;
    logic [2:0]         tc;
    logic [2:0]         attr;
    logic [9:0]         length_dw;
    logic [15:0]        requester_id;
    logic [7:0]         tag;
    logic [3:0]         first_be;
    logic [3:0]         last_be;
    logic [63:0]        address;
    logic [PAYLOAD_W-1:0] payload;
  } tx_entry_t;

  // One outstanding completer-backend operation. The response belongs to the
  // last accepted request; SC for a write means its enabled bytes are committed.
  typedef tx_entry_t cpl_backend_req_t;
  localparam logic [2:0] CPL_SC = 3'b000, CPL_UR = 3'b001, CPL_CA = 3'b100;
  typedef struct packed {
    logic [2:0] status;
    logic [PAYLOAD_W-1:0] data;
  } cpl_backend_rsp_t;

  // This is the controller's internal packetized TLP representation. A PHY
  // adapter may serialize this structure into the PCIe wire header format.
  typedef struct packed {
    logic [2:0]         fmt;
    logic [4:0]         tlp_type;
    logic [2:0]         tc;
    logic [2:0]         attr;
    logic               poisoned;
    logic               digest_present;
    logic [9:0]         length_dw;
    logic [15:0]        requester_id;
    logic [15:0]        completer_id;
    logic [7:0]         tag;
    logic [3:0]         first_be;
    logic [3:0]         last_be;
    logic [2:0]         cpl_status;
    logic [11:0]        byte_count;
    logic [6:0]         lower_address;
    logic [63:0]        address;
    logic [PAYLOAD_W-1:0] payload;
    // Transaction-layer end-to-end CRC. This is the final DWORD of a TLP
    // whenever digest_present (the PCIe TD indication) is asserted.
    logic [31:0]        ecrc;
  } tlp_packet_t;

  // Header image covered by the internal transaction-layer ECRC model.
  // The payload is processed separately so only length_dw valid DWORDs are
  // included, and the ECRC DWORD itself is never part of its own calculation.
  typedef struct packed {
    logic [2:0]  fmt;
    logic [4:0]  tlp_type;
    logic [2:0]  tc;
    logic [2:0]  attr;
    logic        poisoned;
    logic        digest_present;
    logic [9:0]  length_dw;
    logic [15:0] requester_id;
    logic [15:0] completer_id;
    logic [7:0]  tag;
    logic [3:0]  first_be;
    logic [3:0]  last_be;
    logic [2:0]  cpl_status;
    logic [11:0] byte_count;
    logic [6:0]  lower_address;
    logic [63:0] address;
  } tlp_ecrc_header_t;

  typedef struct packed {
    logic [11:0] seq;
    tlp_packet_t tlp;
    logic [31:0] lcrc;
  } dll_packet_t;

  // Unscaled, non-FLIT flow control on VC0. This decoded DLLP sideband is
  // protected/serialized by the link adapter, just like the ACK/NAK sideband.
  typedef enum logic [1:0] {FC_POSTED, FC_NON_POSTED, FC_COMPLETION, FC_INVALID} fc_class_e;
  typedef enum logic [1:0] {FC_INIT1, FC_INIT2, FC_UPDATE, FC_RESERVED} fc_kind_e;
  typedef struct packed {
    fc_kind_e kind;
    fc_class_e credit_class;
    logic [2:0] vc;
    logic [7:0] header_limit;
    logic [11:0] data_limit;
  } fc_dllp_t;
  typedef struct packed {
    logic [2:0][7:0] header;
    logic [2:0][11:0] data;
  } fc_credits_t;

  typedef struct packed {
    txn_kind_e   kind;
    logic [2:0]  tc;
    logic [2:0]  attr;
    logic [9:0]  length_dw;
    logic [15:0] requester_id;
    logic [15:0] completer_id;
    logic [7:0]  tag;
    logic [2:0]  cpl_status;
    logic [11:0] byte_count;
    logic [6:0] lower_address;
    logic [63:0] address;
    logic        poisoned;
    logic        digest_present;
    logic        ecrc_error;
  } rx_meta_t;

  function automatic logic txn_has_data(input txn_kind_e kind);
    case (kind)
      TXN_MEM_WR, TXN_IO_WR, TXN_CFG0_WR, TXN_CFG1_WR,
      TXN_MSG, TXN_CPLD: txn_has_data = 1'b1;
      default:            txn_has_data = 1'b0;
    endcase
  endfunction

  function automatic txn_kind_e decode_tlp_kind(input tlp_packet_t tlp);
    case ({tlp.fmt, tlp.tlp_type})
      {3'b000, 5'b00000},
      {3'b001, 5'b00000}: decode_tlp_kind = TXN_MEM_RD;
      {3'b010, 5'b00000},
      {3'b011, 5'b00000}: decode_tlp_kind = TXN_MEM_WR;
      {3'b000, 5'b00010}: decode_tlp_kind = TXN_IO_RD;
      {3'b010, 5'b00010}: decode_tlp_kind = TXN_IO_WR;
      {3'b000, 5'b00100}: decode_tlp_kind = TXN_CFG0_RD;
      {3'b010, 5'b00100}: decode_tlp_kind = TXN_CFG0_WR;
      {3'b000, 5'b00101}: decode_tlp_kind = TXN_CFG1_RD;
      {3'b010, 5'b00101}: decode_tlp_kind = TXN_CFG1_WR;
      {3'b001, 5'b10000},
      {3'b011, 5'b10000}: decode_tlp_kind = TXN_MSG;
      {3'b000, 5'b01010}: decode_tlp_kind = TXN_CPL;
      {3'b010, 5'b01010}: decode_tlp_kind = TXN_CPLD;
      default:            decode_tlp_kind = TXN_UNKNOWN;
    endcase
  endfunction

  function automatic fc_class_e tlp_fc_class(input tlp_packet_t packet);
    case (decode_tlp_kind(packet))
      TXN_MEM_WR, TXN_MSG: tlp_fc_class = FC_POSTED;
      TXN_MEM_RD, TXN_IO_RD, TXN_IO_WR, TXN_CFG0_RD, TXN_CFG0_WR,
      TXN_CFG1_RD, TXN_CFG1_WR: tlp_fc_class = FC_NON_POSTED;
      TXN_CPL, TXN_CPLD: tlp_fc_class = FC_COMPLETION;
      default: tlp_fc_class = FC_INVALID;
    endcase
  endfunction

  function automatic logic tlp_needs_completion(input tlp_packet_t packet);
    return tlp_fc_class(packet) == FC_NON_POSTED;
  endfunction

  function automatic logic fc_has_credit(input tlp_packet_t packet, input fc_credits_t available);
    fc_class_e cl;
    cl = tlp_fc_class(packet);
    if (!tlp_fc_supported(packet)) return 1'b0;
    return (available.header[cl] != 0) && (available.data[cl] >= tlp_fc_data_cost(packet));
  endfunction

  // A data credit covers four DWORDs. ECRC is covered by the header credit,
  // not the data-credit charge. Read request length does not consume data.
  function automatic logic [11:0] tlp_fc_data_cost(input tlp_packet_t packet);
    if (packet.fmt[1])
      tlp_fc_data_cost = ({2'b00, packet.length_dw} + 12'd3) >> 2;
    else
      tlp_fc_data_cost = 12'd0;
  endfunction

  function automatic logic tlp_fc_supported(input tlp_packet_t packet);
    tlp_fc_supported = (tlp_fc_class(packet) != FC_INVALID) &&
      (!packet.fmt[1] || ((packet.length_dw != 0) &&
                         (int'(packet.length_dw) <= MAX_PAYLOAD_DW)));
  endfunction

  function automatic logic [31:0] crc32_bit(
    input logic [31:0] crc_in,
    input logic        data_bit
  );
    logic feedback;
    begin
      feedback = crc_in[0] ^ data_bit;
      crc32_bit = crc_in >> 1;
      if (feedback)
        crc32_bit = crc32_bit ^ 32'hEDB8_8320;
    end
  endfunction

  // Transaction-layer end-to-end CRC over the internal TLP representation.
  // The digest DWORD is excluded. Only valid payload DWORDs are covered. The
  // TD indication is forced to one, and the mutable poisoned indication is
  // normalized to one so setting EP in transit does not invalidate the ECRC.
  // A wire-format adapter must still implement PCIe byte/bit ordering and any
  // additional generation-specific invariant-field rules.
  function automatic logic [31:0] calculate_ecrc(input tlp_packet_t tlp);
    localparam int HEADER_BITS = $bits(tlp_ecrc_header_t);
    tlp_ecrc_header_t header;
    logic [HEADER_BITS-1:0] flat_header;
    logic [31:0] crc;
    integer i;
    begin
      header = '0;
      header.fmt            = tlp.fmt;
      header.tlp_type       = tlp.tlp_type;
      header.tc             = tlp.tc;
      header.attr           = tlp.attr;
      header.poisoned       = 1'b1;
      header.digest_present = 1'b1;
      header.length_dw      = tlp.length_dw;
      header.requester_id   = tlp.requester_id;
      header.completer_id   = tlp.completer_id;
      header.tag            = tlp.tag;
      header.first_be       = tlp.first_be;
      header.last_be        = tlp.last_be;
      header.cpl_status     = tlp.cpl_status;
      header.byte_count     = tlp.byte_count;
      header.lower_address  = tlp.lower_address;
      header.address        = tlp.address;
      flat_header = header;

      crc = 32'hFFFF_FFFF;
      for (i = 0; i < HEADER_BITS; i = i + 1)
        crc = crc32_bit(crc, flat_header[i]);

      for (i = 0; i < PAYLOAD_W; i = i + 1) begin
        if (tlp.fmt[1] && (i < (tlp.length_dw * 32)))
          crc = crc32_bit(crc, tlp.payload[i]);
      end

      calculate_ecrc = ~crc;
    end
  endfunction

  // Data-link CRC-32 over the internal packet representation. It covers the
  // sequence number and complete TLP, including an ECRC DWORD when present.
  // The PHY adapter is responsible for exact lane/byte ordering on-wire.
  function automatic logic [31:0] calculate_lcrc(
    input logic [11:0] seq,
    input tlp_packet_t tlp
  );
    localparam int TLP_BITS = $bits(tlp_packet_t);
    logic [TLP_BITS-1:0] flat_tlp;
    logic [31:0] crc;
    integer i;
    begin
      flat_tlp = tlp;
      crc = 32'hFFFF_FFFF;
      for (i = 0; i < 12; i = i + 1)
        crc = crc32_bit(crc, seq[i]);
      for (i = 0; i < TLP_BITS; i = i + 1)
        crc = crc32_bit(crc, flat_tlp[i]);
      calculate_lcrc = ~crc;
    end
  endfunction
endpackage
