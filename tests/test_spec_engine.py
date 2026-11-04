from pathlib import Path
from mverify.core.spec_engine import extract_candidate_requirements, map_requirements


def test_extracts_normative_candidate_lines():
    text = """Introductory text.
    The receiver shall check the LCRC before accepting a TLP.
    This is explanatory text without a normative keyword.
    The transmitter must retain a packet until it receives an ACK.
    """
    rows = extract_candidate_requirements(text, "test_spec.txt")
    assert len(rows) == 2
    assert rows[0]["requirement_id"] == "REQ-0001"
    assert rows[0]["review_status"] == "needs_review"


def test_maps_structural_evidence_without_claiming_verification():
    reqs = [{"requirement_id":"REQ-1",
             "statement":"The receiver shall check LCRC and sequence number.",
             "category":"data_link_layer", "review_status":"approved"}]
    report = {
        "module_details":[{"name":"pcie_dll_rx","ports":[{"name":"link_rx_valid"}]}],
        "hierarchy":[],
        "architecture_discovery":{"layers":{"data_link_layer":{
            "status":"structural_evidence_found",
            "evidence":["DLL packet type is used","ACK/NAK and replay evidence"]
        }}}
    }
    result = map_requirements(reqs, report)[0]
    assert result["mapping_status"] == "structural_evidence_found"
    assert result["verification_status"] == "not_verified"


def test_unmatched_requirement_stays_unmapped():
    result = map_requirements([{"requirement_id":"REQ-X",
        "statement":"The device shall support an unusual custom feature."}], {})[0]
    assert result["mapping_status"] == "no_matching_structural_evidence"
    assert result["verification_status"] == "not_verified"
