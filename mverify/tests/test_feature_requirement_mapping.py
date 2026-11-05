from mverify.core.spec_engine import map_requirements


def test_requirement_mapping_includes_feature_evidence():
    scan = {
        "module_details": [{"name": "arbiter", "ports": [{"name": "grant"}]}],
        "hierarchy": [],
        "architecture_discovery": {"layers": {}},
        "feature_analysis": {"features": [{
            "feature_id": "arbitration",
            "feature": "Arbitration or scheduling",
            "confidence": "high",
            "modules_involved": ["arbiter"],
        }]},
    }
    result = map_requirements([{
        "requirement_id": "REQ-1",
        "statement": "The arbiter shall select one request using priority scheduling.",
        "category": "unclassified",
    }], scan)[0]
    assert result["feature_evidence"]
    assert result["feature_evidence"][0]["feature_id"] == "arbitration"
