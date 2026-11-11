from mverify.core.sv_frontend import build_design_graph, run_surelog

def test_graph_has_module_port_and_instance_edges():
    report={"module_details":[{"name":"top","source_file":"top.sv","ports":[{"name":"clk","direction":"input","width":"scalar"}]},{"name":"child","source_file":"child.sv","ports":[]}],"hierarchy":[{"parent":"top","child":"child","instance":"u0"}],"semantic_analysis":{"modules":[]}}
    g=build_design_graph(report)
    assert any(e["relation"]=="INSTANTIATES" for e in g["edges"])
    assert any(n["type"]=="port" for n in g["nodes"])

def test_surelog_reports_unavailable_or_blocked_without_crashing(tmp_path):
    r=run_surelog(tmp_path,{"compile_sources":[]})
    assert r["status"] in {"unavailable","blocked_no_filelist_sources"}
