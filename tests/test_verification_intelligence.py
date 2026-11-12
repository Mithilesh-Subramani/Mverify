import json
from pathlib import Path

from mverify.core.verification_intelligence import (
    analyze_handshake_samples,
    build_verification_readiness,
    capture_project_snapshot,
    compare_project_snapshots,
    discover_interface_contracts,
    load_signal_csv,
)


def _report():
    return {
        "project_dir": "/tmp/demo",
        "selected_top": "pcie_link",
        "module_details": [{
            "name": "pcie_link",
            "ports": [
                {"name": "tx_valid", "direction": "output", "width": "1"},
                {"name": "tx_ready", "direction": "input", "width": "1"},
                {"name": "rx_valid", "direction": "input", "width": "1"},
                {"name": "rx_ready", "direction": "output", "width": "1"},
            ],
        }],
        "semantic_analysis": {"modules": [{"module": "pcie_link", "state_machine_candidates": [
            {"selector": "state", "case_labels": ["IDLE", "SEND"]}
        ]}]},
    }


def test_discovers_direction_complementary_handshake_candidates():
    found = discover_interface_contracts(_report())
    assert len(found) == 2
    tx = next(x for x in found if x["interface_id"].endswith("tx"))
    assert tx["candidate_quality"] == "direction_complementary_candidate"
    assert tx["review_required"] is True


def test_measures_accepts_and_stall_bursts_without_assuming_latency():
    contract = discover_interface_contracts(_report())
    samples = [
        {"cycle": 1, "signals": {"tx_valid": "1", "tx_ready": "0"}},
        {"cycle": 2, "signals": {"tx_valid": "1", "tx_ready": "0"}},
        {"cycle": 3, "signals": {"tx_valid": "1", "tx_ready": "1"}},
        {"cycle": 4, "signals": {"tx_valid": "0", "tx_ready": "1"}},
    ]
    result = analyze_handshake_samples(samples, [x for x in contract if x["interface_id"].endswith("tx")])
    item = result["interfaces"][0]
    assert item["accepted_cycles"] == 1
    assert item["stalled_cycles"] == 2
    assert item["longest_observed_stall_cycles"] == 2
    assert "No maximum legal latency" in item["interpretation_limit"]


def test_loads_wide_and_long_csv(tmp_path):
    wide = tmp_path / "wide.csv"
    wide.write_text("cycle,tx_valid,tx_ready\n1,1,0\n2,1,1\n", encoding="utf-8")
    assert len(load_signal_csv(wide)) == 2
    long = tmp_path / "long.csv"
    long.write_text("cycle,signal,value\n1,tx_valid,1\n1,tx_ready,0\n", encoding="utf-8")
    assert load_signal_csv(long)[0]["signals"] == {"tx_valid": "1", "tx_ready": "0"}


def test_snapshot_detects_added_removed_and_modified_files(tmp_path):
    (tmp_path / "rtl").mkdir()
    (tmp_path / "rtl" / "a.sv").write_text("module a; endmodule")
    (tmp_path / "rtl" / "b.sv").write_text("module b; endmodule")
    first = capture_project_snapshot(tmp_path)
    (tmp_path / "rtl" / "a.sv").write_text("module a; logic x; endmodule")
    (tmp_path / "rtl" / "b.sv").unlink()
    (tmp_path / "rtl" / "c.sv").write_text("module c; endmodule")
    second = capture_project_snapshot(tmp_path)
    diff = compare_project_snapshots(first, second)
    assert diff["modified"] == ["rtl/a.sv"]
    assert diff["removed"] == ["rtl/b.sv"]
    assert diff["added"] == ["rtl/c.sv"]
    assert Path(second["snapshot_path"]).exists()


def test_readiness_report_labels_static_candidates_not_compliance():
    result = build_verification_readiness(_report(), [{"review_status": "needs_review"}])
    assert result["requirements"]["needs_review"] == 1
    assert result["readiness_gates"]["protocol_compliance"] == "not_established"
