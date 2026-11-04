from mverify.core.rtl_semantic_analyzer import analyze_semantics

def test_extracts_state_and_assignment_evidence_without_claiming_proof():
    modules = [{
        "name": "tx_ctrl", "source_file": "tx_ctrl.sv",
        "ports": [{"name": "valid", "direction": "output", "width": "scalar"}],
        "body": """
          always_ff @(posedge clk) begin
            case (state)
              IDLE: if (start) state <= SEND;
              SEND: if (ready) state <= IDLE;
            endcase
            valid <= (state == SEND);
          end
          assign done = !valid;
        """
    }]
    result = analyze_semantics(modules, [])
    item = result["modules"][0]
    assert item["procedural_block_count"] == 1
    assert item["state_machine_candidates"][0]["selector"] == "state"
    assert "IDLE" in item["state_machine_candidates"][0]["case_labels"]
    assert "valid" in item["write_candidates"]
    assert item["continuous_assignments"][0]["lhs"] == "done"
    assert result["limitations"]
