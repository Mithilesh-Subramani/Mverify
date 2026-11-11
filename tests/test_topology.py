from mverify.core.topology import build_topology

def test_topology_reports_declared_ports_and_honest_connectivity_status():
    report = {"selected_top": "top", "module_details": [{"name": "top", "source_file": "top.sv", "ports": [{"name": "valid", "direction": "input", "width": "[0:0]"}]}], "hierarchy": [], "design_graph": {"nodes": [], "edges": []}}
    result = build_topology(report)
    assert result["top"] == "top"
    assert result["ports"][0]["name"] == "valid"
    assert result["connectivity_status"] == "hierarchy_candidates_only"
