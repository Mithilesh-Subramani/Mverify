from mverify.core.requirement_intelligence import assess_requirement, apply_auto_triage

def test_rejects_document_heading():
    result = assess_requirement({"statement": "13. Open items required for a controlled baseline"})
    assert result["decision"] == "rejected"

def test_auto_approves_testable_requirement_with_rtl_evidence():
    req = {"statement": "The DUT shall hold valid stable while ready is low."}
    mapping = {"rtl_evidence": [{"module": "dut", "matched_terms": ["valid", "ready"]}], "layer_evidence": []}
    assert assess_requirement(req, mapping)["decision"] == "auto_approved"

def test_missing_evidence_stays_review():
    req = {"statement": "The DUT shall assert reset for the specified reset duration."}
    assert assess_requirement(req, {})["decision"] == "needs_review"

def test_triage_preserves_rationale():
    rows = apply_auto_triage([{"requirement_id":"REQ-1","statement":"The DUT shall hold valid stable while ready is low."}],
                             [{"requirement_id":"REQ-1","rtl_evidence":[{"module":"dut"}],"layer_evidence":[]}])
    assert rows[0]["review_status"] == "approved"
    assert rows[0]["auto_reason"]
