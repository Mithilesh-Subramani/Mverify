from mverify.core.verification_planner import (
    classify_requirement, decompose_requirement, generate_verification_plan
)


def test_classifies_dll_requirement():
    req = {"statement": "The receiver shall check LCRC and replay after NAK."}
    assert classify_requirement(req)["suggested_category"] == "data_link_layer"


def test_engineer_category_overrides_keyword_guess():
    req = {"statement": "The transmitter shall send a TLP.", "category": "physical_layer"}
    out = classify_requirement(req)
    assert out["suggested_category"] == "physical_layer"
    assert out["classification_reason"] == "Engineer-provided category"


def test_negative_requirement_is_explicit():
    req = {"statement": "The receiver shall not accept a packet with invalid LCRC."}
    out = decompose_requirement(req)
    assert out["negative_requirement"] is True
    assert "must not occur" in out["expected_result"]


def test_plan_does_not_claim_execution():
    req = {"requirement_id":"REQ-1",
           "statement":"The receiver shall check LCRC before accepting a TLP.",
           "review_status":"approved",
           "mapping_status":"structural_evidence_found",
           "rtl_evidence":[{"module":"pcie_dll_rx"}]}
    plan = generate_verification_plan([req])[0]
    assert plan["execution_status"] == "not_generated_or_run"
    assert plan["verification_status"] == "not_verified"
    assert plan["proposed_scenarios"]


def test_plan_is_anchored_to_specification_and_not_layer_guess():
    req = {
        "requirement_id": "REQ-PCIe-01",
        "statement": "The receiver shall not accept a packet with an invalid LCRC.",
        "source": "PCIe_specification.pdf",
        "clause": "3.x.y",
        "spec_revision": "project-specified revision",
        "review_status": "approved",
        "mapping_status": "structural_evidence_found",
        "rtl_evidence": [{"module": "rx_crc_check"}],
        "feature_evidence": [{"feature": "Integrity checking"}],
    }
    plan = generate_verification_plan([req])[0]
    assert plan["specification_basis"]["source"] == "PCIe_specification.pdf"
    assert plan["specification_basis"]["clause_or_section"] == "3.x.y"
    assert plan["specification_basis"]["revision"] == "project-specified revision"
    assert plan["proposed_scenarios"][0]["scenario_type"] == "negative_case"
    assert plan["verification_status"] == "not_verified"
    assert "suggested_category" not in plan
