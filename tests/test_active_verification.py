from pathlib import Path
from types import SimpleNamespace
import json

from mverify.core.project_scanner import scan_project
from mverify.core.strategy_registry import select_strategy
from mverify.core.simulator_backend import (
    classify_log, compile_command, simulation_command, write_filelist, waveform_info,
    discover_tools, run_process, run_compile, verdi_command,
)
import mverify.core.simulator_backend as backend
from mverify.core.uvm_generator import generate_uvm_project
from mverify.core.wrr_model import WeightedRoundRobinModel


def test_wrr_model_fairness_quota_and_stall():
    model = WeightedRoundRobinModel(2, [1, 1])
    observed = []
    for _ in range(4):
        valid, index, onehot = model.clock([True, True], accepted=True)
        assert valid and onehot == 1 << index
        observed.append(index)
    assert observed == [0, 1, 0, 1]
    before = (model.pointer, list(model.remaining))
    model.clock([True, True], accepted=False)
    assert (model.pointer, model.remaining) == before


def test_wrr_zero_weight_and_withdrawal():
    model = WeightedRoundRobinModel(3, [0, 3, 1])
    valid, index, onehot = model.clock([True, True, True], accepted=True)
    assert valid and index == 1 and onehot == 0b010
    assert model.remaining == [0, 2, 1]
    assert model.predict([False, True, False])[:3] == (True, 1, 0b010)


def test_wrr_reset_and_non_power_of_two_pointer_wrap():
    model = WeightedRoundRobinModel(3, [1, 1, 1])
    assert [model.clock([True] * 3, True)[1] for _ in range(6)] == [0, 1, 2, 0, 1, 2]
    model.reset()
    assert model.pointer == 0 and model.remaining == [0, 0, 0]


def test_wrr_weight_changes_apply_at_round_reload():
    model = WeightedRoundRobinModel(2, [1, 1])
    model.clock([True, True], True)
    assert model.remaining == [0, 1]
    model.clock([True, True], True, weights=[3, 2])
    assert model.remaining == [0, 0]
    model.clock([True, True], True, weights=[3, 2])
    assert model.remaining == [2, 2]


def _wrr_report():
    dut_dir = Path(__file__).resolve().parent / "fixtures" / "rtl" / "wrr_contract"
    return scan_project(dut_dir, requested_top="pcie_wrr_arbiter")


def test_strategy_requires_confirmed_wrr_contract():
    report = _wrr_report()
    strategy = select_strategy(report, "pcie_wrr_arbiter")
    assert strategy.active and strategy.confidence == "CONFIRMED"
    assert "grant_accept" in dict(strategy.required_ports)
    generic = select_strategy({"module_details": [{"name": "mystery", "ports": []}]}, "mystery")
    assert not generic.active and generic.confidence == "UNKNOWN"


def test_active_generator_emits_connected_functional_environment(tmp_path):
    report = _wrr_report()
    result = generate_uvm_project(report, tmp_path / "generated", "pcie_wrr_arbiter")
    assert result["mode"] == "active_confirmed_contract"
    root = Path(result["output_dir"])
    manifest = (root / "mverify_generation_manifest.json").read_text()
    generated_pkg = (root / "mverify_wrr_pkg.sv").read_text()
    assert '"mode": "active_confirmed_contract"' in manifest
    for token in ("class wrr_driver", "class wrr_seqr", "class wrr_scoreboard", "class wrr_model",
                  "MVERIFY_MISMATCH", "MVERIFY_FUNCTIONAL_PASS", "covergroup cov"):
        assert token in generated_pkg
    assert (root / "mverify.f").is_file()
    assert "pcie_wrr_arbiter.sv" in (root / "mverify.f").read_text()


def test_active_generator_honors_non_power_of_two_parameters(tmp_path, monkeypatch):
    monkeypatch.setenv("MVERIFY_NUM_TC", "5")
    monkeypatch.setenv("MVERIFY_WEIGHT_W", "4")
    result = generate_uvm_project(_wrr_report(), tmp_path / "wrr5", "pcie_wrr_arbiter")
    root = Path(result["output_dir"])
    manifest = json.loads((root / "mverify_generation_manifest.json").read_text())
    assert manifest["parameters"] == {"NUM_TC": 5, "WEIGHT_W": 4}
    assert "+define+MVERIFY_NUM_TC=5" in (root / "mverify.f").read_text()


def test_simulator_backend_commands_and_evidence(tmp_path):
    flist = write_filelist(tmp_path / "mverify.f", [tmp_path / "dut.sv"], [tmp_path])
    assert "+incdir+" in flist.read_text()
    command = compile_command("vcs", flist, tmp_path / "build", ["-lca"])
    assert command[:4] == ["vcs", "-full64", "-sverilog", "-ntb_opts"]
    assert "-lca" in command
    assert simulation_command("simv", "wrr_test", 42)[1:3] == ["+UVM_TESTNAME=wrr_test", "+ntb_random_seed=42"]
    status, checks = classify_log("UVM_INFO: passed\nMVERIFY_FUNCTIONAL_PASS\nMVERIFY_TEST_COMPLETE", 0)
    assert status == "SIMULATION_PASSED" and checks["completion_marker"]
    status, checks = classify_log("UVM_ERROR : 1\nMVERIFY_TEST_COMPLETE", 0)
    assert status == "SIMULATION_FAILED" and checks["uvm_error"] == 1
    vcd = tmp_path / "valid.vcd"
    vcd.write_text("$date today $end\n$scope module top $end\n$enddefinitions $end\n")
    assert waveform_info(vcd)["valid"]
    assert verdi_command("verdi", vcd, flist)[2] == str(vcd.resolve())


def test_tool_discovery_uses_environment_without_modifying_license(tmp_path):
    vcs = tmp_path / "vcs"; verdi = tmp_path / "verdi"
    vcs.write_text(""); verdi.write_text("")
    tools = discover_tools({"VCS_BIN": str(vcs), "VERDI_BIN": str(verdi),
                            "SNPSLMD_LICENSE_FILE": "27000@license-host", "UVM_HOME": str(tmp_path)})
    assert tools["vcs"].available and tools["vcs"].executable == str(vcs)
    assert tools["verdi"].available and tools["license"].executable == "27000@license-host"
    assert tools["uvm"].available


def test_process_timeout_is_captured(monkeypatch, tmp_path):
    def timeout(*args, **kwargs):
        raise backend.subprocess.TimeoutExpired(args[0], kwargs["timeout"], output=b"partial output")
    monkeypatch.setattr(backend.subprocess, "run", timeout)
    result = run_process(["simv"], tmp_path, tmp_path / "timeout.log", timeout=0.01)
    assert result["timed_out"] and "partial output" in result["output"]
    assert "MVERIFY_PROCESS_TIMEOUT" in (tmp_path / "timeout.log").read_text()


def test_compile_requires_executable_and_records_result(monkeypatch, tmp_path):
    build = tmp_path / "build"
    filelist = write_filelist(tmp_path / "mverify.f", [tmp_path / "dut.sv"])
    def fake_run(args, **kwargs):
        if "-ID" in args:
            return SimpleNamespace(returncode=0, stdout="vcs script version : U-2023.03", stderr="")
        Path(args[args.index("-o") + 1]).write_text("simulator")
        return SimpleNamespace(returncode=0, stdout="compile ok", stderr="")
    monkeypatch.setattr(backend.subprocess, "run", fake_run)
    result = run_compile("vcs", filelist, build)
    assert result["status"] == "COMPILE_PASSED"
    assert result["simulator_version"] == "U-2023.03"
    assert (build / "compile.result.json").is_file()


def test_duplicate_module_definitions_block_filelist(tmp_path):
    first, second = tmp_path / "a.sv", tmp_path / "b.sv"
    first.write_text("module duplicate; endmodule\n")
    second.write_text("module duplicate; endmodule\n")
    try:
        write_filelist(tmp_path / "duplicate.f", [first, second])
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate module definitions must not be silently compiled")

