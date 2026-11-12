from pathlib import Path
import streamlit as st

from mverify.core.config import load_config
from mverify.core.logging_setup import configure_logging
from mverify.core.project_scanner import scan_project
from mverify.storage.database import initialize_database, save_scan
from mverify.core.spec_engine import extract_spec_text, extract_candidate_requirements, load_requirements_csv, map_requirements
from mverify.core.verification_planner import generate_verification_plan
from mverify.core.requirement_intelligence import apply_auto_triage
from mverify.core.uvm_generator import generate_uvm_project
from mverify.core.design_intelligence import build_dut_model, propose_architectures, generate_intelligence
from mverify.core.mcore_learning_client import record_mcore_experience
from mverify.core.verification_intelligence import (
    build_verification_readiness, capture_project_snapshot, compare_project_snapshots,
    discover_interface_contracts, analyze_handshake_samples, load_signal_csv,
)

st.set_page_config(page_title="Mverify", page_icon="🧪", layout="wide")
config = load_config()
configure_logging(config.log_dir)
initialize_database(config.database_path)

st.title("Mverify")
st.caption("Local-first RTL design verification assistant")
st.info("Mverify v0.16.1 — evidence-grounded RTL analysis, protocol-aware verification planning, and simulation intelligence.")

with st.sidebar:
    st.header("Project")
    project_path = st.text_input("RTL project directory", placeholder="/home/user/rtl_project")
    top_module = st.text_input("Top-level module (optional)", placeholder="dut_top")
    st.caption("Use an absolute path on the machine running Mverify.")

if st.button("Scan RTL project", type="primary", disabled=not project_path.strip()):
    path = Path(project_path).expanduser()
    if not path.exists() or not path.is_dir():
        st.error("The directory does not exist. Check the path.")
    else:
        with st.spinner("Scanning RTL files..."):
            report = scan_project(path, top_module.strip() or None)
            scan_id = save_scan(config.database_path, str(path), report)
        st.success(f"Scan complete. Local scan ID: {scan_id}")
        st.session_state["last_report"] = report

report = st.session_state.get("last_report")
if report:
    st.subheader("Scan summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("RTL files", report["summary"]["rtl_files"])
    c2.metric("Modules found", report["summary"]["modules"])
    c3.metric("Parse warnings", report["summary"]["warnings"])
    if "hierarchy_instances" in report["summary"]:
        st.caption(f"Likely hierarchy instances: {report['summary']['hierarchy_instances']}")

    if report.get("selected_top"):
        st.write(f"**Selected top:** `{report['selected_top']}`")
    elif report.get("top_candidates"):
        st.warning("Top-level module was not selected. Review the candidates below.")

    feature_analysis = report.get("feature_analysis", {})
    st.subheader("DUT feature inventory")
    st.caption("Mverify searches for design functions across the full RTL. It does not require a feature to belong to a named protocol layer.")
    features = feature_analysis.get("features", [])
    if features:
        st.dataframe([{
            "Feature": x["feature"],
            "Status": x["status"],
            "Confidence": x["confidence"],
            "Modules": ", ".join(x["modules_involved"]),
            "Evidence hits": x["evidence_count"],
        } for x in features], use_container_width=True)
        with st.expander("Inspect feature evidence and source modules"):
            for item in features:
                st.markdown(f"**{item['feature']}** — {item['confidence']} confidence")
                for module in item["evidence"]:
                    st.write(f"Module: `{module['module']}` ({module['source_file']})")
                    for evidence in module["evidence"]:
                        st.code(evidence["evidence"])
    else:
        st.warning("No feature patterns were detected. This does not prove that the DUT has no features.")
    st.caption(feature_analysis.get("coverage_note", "Feature analysis is a static first pass."))

    semantic = report.get("semantic_analysis", {})
    if semantic:
        st.subheader("RTL behaviour evidence")
        st.caption("This view extracts candidate writes, reads, continuous assignments and state-machine case blocks. It is not a fully elaborated SystemVerilog data-flow graph.")
        semantic_modules = semantic.get("modules", [])
        s1, s2, s3 = st.columns(3)
        s1.metric("Modules analysed", len(semantic_modules))
        s2.metric("State-machine candidates", sum(len(x.get("state_machine_candidates", [])) for x in semantic_modules))
        s3.metric("Continuous assignments", sum(len(x.get("continuous_assignments", [])) for x in semantic_modules))
        with st.expander("Inspect per-module semantic evidence"):
            for sm in semantic_modules:
                st.markdown(f"**{sm.get('module')}** — `{sm.get('source_file')}`")
                st.write("Procedural blocks:", sm.get("procedural_block_count"))
                st.write("Write candidates:", ", ".join(sm.get("write_candidates", [])[:80]) or "None detected")
                for fsm in sm.get("state_machine_candidates", []):
                    st.write("State selector:", fsm.get("selector"))
                    st.write("Case labels:", ", ".join(fsm.get("case_labels", [])))
                    st.write("Transition targets:", ", ".join(fsm.get("transition_targets", [])))
                if sm.get("continuous_assignments"):
                    st.json(sm["continuous_assignments"])
        for limitation in semantic.get("limitations", []):
            st.caption("Limitation: " + limitation)

    discovery = report.get("architecture_discovery", {})
    if discovery:
        st.subheader("Architecture discovery")
        p = discovery.get("protocol", {})
        r = discovery.get("device_role", {})
        g = discovery.get("generation", {})
        a, b, c = st.columns(3)
        a.metric("Detected protocol", p.get("value", "unknown"))
        b.metric("Device role", r.get("value", "unknown"))
        c.metric("PCIe generation", g.get("value", "unknown"))
        st.caption("Protocol layers are optional context. The feature inventory above is the primary DUT discovery view. Structural estimates are not compliance results.")
        for layer, detail in discovery.get("layers", {}).items():
            with st.expander(f"{layer.replace('_', ' ').title()} — {detail.get('status')}"):
                st.write(f"**Confidence:** {detail.get('confidence')}")
                st.write(detail.get("interpretation"))
                for item in detail.get("evidence", []): st.write(f"- {item}")
        if discovery.get("boundaries"):
            st.subheader("Detected layer boundaries")
            st.dataframe(discovery["boundaries"], use_container_width=True)
        st.subheader("Recommended verification scope")
        st.dataframe(discovery.get("recommended_scope", []), use_container_width=True)
        st.subheader("Discovery limitations")
        for item in discovery.get("limitations", []): st.caption(f"• {item}")
        with st.expander("Protocol and role evidence"):
            st.json({"protocol": p, "device_role": r, "generation": g})

    st.divider()
    st.header("Specification and requirements")
    st.caption("Upload a local specification. Mverify auto-approves only clear, testable requirements with supporting RTL evidence. Other candidates remain in review.")
    spec_file = st.file_uploader("Upload specification", type=["txt", "md", "rst", "csv", "pdf", "docx"], key="spec_upload")
    if spec_file is not None:
        try:
            suffix = Path(spec_file.name).suffix.lower()
            temp_path = Path(config.log_dir).parent / f"mverify_spec_upload{suffix}"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(spec_file.getvalue())
            if suffix == ".csv":
                candidates = load_requirements_csv(temp_path)
            else:
                spec_text = extract_spec_text(temp_path)
                candidates = extract_candidate_requirements(spec_text, spec_file.name)
            # Preserve editable clause metadata for clause-level verification traceability.
            for candidate in candidates:
                candidate.setdefault("clause", "")
            # Auto-triage uses the current RTL scan as evidence. Ambiguous items stay in review.
            premap = map_requirements(candidates, report)
            candidates = apply_auto_triage(candidates, premap)
            st.session_state["spec_candidates"] = candidates
            st.session_state["spec_name"] = spec_file.name
            st.success(f"Extracted and assessed {len(candidates)} candidate requirements from {spec_file.name}.")
            if not candidates:
                st.warning("No normative requirement lines were detected. Use a CSV with requirement_id, statement, category, source columns, or provide a text specification with one requirement per line.")
        except Exception as exc:
            st.error(f"Specification import failed: {exc}")

    candidates = st.session_state.get("spec_candidates", [])
    if candidates:
        st.subheader("Requirement intelligence — automatic triage")
        auto_counts = {}
        for item in candidates: auto_counts[item.get("review_status","needs_review")] = auto_counts.get(item.get("review_status","needs_review"),0)+1
        st.write(" | ".join("%s: %s"%(k,v) for k,v in sorted(auto_counts.items())))
        with st.expander("Why did Mverify make these decisions?"):
            for item in candidates:
                st.write("%s — %s (confidence %.0f%%)"%(item["requirement_id"],item.get("auto_decision"),100*item.get("auto_confidence",0)))
                st.caption(item.get("auto_reason",""))
        st.subheader("Candidate requirements — engineer override available")
        edited = st.data_editor(
            candidates,
            use_container_width=True,
            num_rows="dynamic",
            disabled=["requirement_id", "source", "source_line", "extraction_method"],
            key="requirements_editor",
        )
        if st.button("Map reviewed requirements to RTL", type="primary"):
            approved = []
            for item in edited:
                item = dict(item)
                if item.get("review_status") == "approved":
                    approved.append(item)
            if not approved:
                st.warning("Approve at least one requirement in the Review status column before mapping.")
            else:
                mapped = map_requirements(approved, report)
                st.session_state["mapped_requirements"] = mapped
                st.success(f"Mapped {len(mapped)} approved requirements against the latest RTL scan.")
        mapped = st.session_state.get("mapped_requirements", [])
        if mapped or report:
            st.subheader("Requirement-to-RTL evidence matrix")
            st.dataframe([{
                "ID": x["requirement_id"],
                "Requirement": x["statement"],
                "Review": x.get("review_status"),
                "Mapping": x["mapping_status"],
                "Confidence": x["mapping_confidence"],
                "Verification": x["verification_status"],
            } for x in mapped], use_container_width=True)
            with st.expander("Detailed evidence for each requirement"):
                for item in mapped:
                    st.markdown(f"**{item['requirement_id']} — {item['statement']}**")
                    st.json({"rtl_evidence": item["rtl_evidence"],
                             "layer_evidence": item["layer_evidence"],
                             "feature_evidence": item.get("feature_evidence", []),
                             "semantic_evidence": item.get("semantic_evidence", []),
                             "mapping_note": item["mapping_note"]})
            st.download_button(
                "Download requirement evidence matrix (JSON)",
                data=__import__("json").dumps(mapped, indent=2),
                file_name="mverify_requirement_evidence.json",
                mime="application/json",
            )

            st.divider()
            st.subheader("Verification intelligence")
            st.caption("This analysis uses the current DUT scan and approved requirement-to-RTL evidence. It does not generate a fixed plan when inputs are missing.")
            spec_revision = st.text_input("Applicable PCIe specification revision", key="plan_spec_revision", placeholder="Example: PCI Express Base Specification Revision 4.0")
            use_ollama = st.checkbox("Use local Ollama for design reasoning", value=True, help="Ollama must be running locally. RTL and specification content are not sent to a cloud service.")
            ollama_model = st.text_input("Ollama model", value="qwen2.5-coder:7b", key="intel_ollama_model")
            ollama_url = st.text_input("Ollama URL", value="http://localhost:11434", key="intel_ollama_url")
            if st.button("Analyze this DUT and design its verification strategy", type="primary"):
                with st.spinner("Building DUT model, tracing evidence, and evaluating architecture options..."):
                    enriched = []
                    for item in mapped:
                        row = dict(item); row["spec_revision"] = spec_revision.strip()
                        row["protocol_context"] = "PCIe" if report.get("architecture_discovery", {}).get("protocol", {}).get("value") == "PCIe" else "not established"
                        enriched.append(row)
                    dut_model = build_dut_model(report, enriched, spec_revision)
                    architectures = propose_architectures(dut_model)
                    intelligence = generate_intelligence(dut_model, architectures, enriched, use_ollama, ollama_model.strip(), ollama_url.strip())
                    st.session_state["dut_model"] = dut_model
                    st.session_state["architecture_options"] = architectures
                    st.session_state["verification_intelligence"] = intelligence
                    st.session_state["intelligence_requirements"] = enriched
            intelligence = st.session_state.get("verification_intelligence")
            dut_model = st.session_state.get("dut_model")
            architectures = st.session_state.get("architecture_options", [])
            if intelligence and dut_model:
                st.markdown("#### DUT-specific analysis")
                st.write("**DUT:** `%s` | **Ports:** %s | **Requirements mapped:** %s" % (dut_model['dut_top'], dut_model['port_count'], dut_model['requirement_count']))
                st.write("**Reasoning engine:** %s | **Local model:** %s" % (intelligence['reasoning_engine'], intelligence['model_status']))
                for finding in intelligence.get("dut_specific_findings", []): st.write("- " + finding)
                if intelligence.get("model_error"):
                    st.warning("Ollama analysis was not available: " + intelligence["model_error"])
                if intelligence.get("local_model_analysis"):
                    ai = intelligence["local_model_analysis"]
                    st.markdown("#### Local AI reasoning")
                    st.write(ai.get("summary", ""))
                    for key, title in [("rationale","Architecture rationale"),("dut_specific_test_priorities","DUT-specific test priorities"),("signal_mapping_questions","Signal mapping questions"),("risks","Risks"),("next_actions","Next actions")]:
                        vals=ai.get(key,[])
                        if vals:
                            st.markdown("**%s**"%title)
                            for v in vals: st.write("- "+str(v))
                st.markdown("#### Verification architecture options")
                for opt in architectures:
                    with st.expander(opt['name'] + (" — recommended" if intelligence.get('architecture_recommendation',{}).get('id')==opt['id'] else "")):
                        st.write(opt['when_to_use'])
                        st.write("**Agents**")
                        for agent in opt['agents']: st.write("- `%s` — %s [%s]"%(agent['name'],agent['role'],agent['mode']))
                        st.write("**Advantages:** " + "; ".join(opt['advantages']))
                        st.write("**Risks:** " + "; ".join(opt['risks']))
                st.markdown("#### Select and approve an architecture")
                default_id=intelligence.get('architecture_recommendation',{}).get('id','passive')
                ids=[x['id'] for x in architectures]
                idx=ids.index(default_id) if default_id in ids else 0
                selected_id=st.selectbox("Architecture", ids, index=idx, format_func=lambda x: next(a['name'] for a in architectures if a['id']==x), key="approved_architecture_id")
                selected_arch=next(a for a in architectures if a['id']==selected_id)
                st.write(selected_arch['when_to_use'])
                st.warning("Approval records your architecture choice. Active PCIe drivers are generated only after each pin/interface signal has a confirmed role, direction, clock, reset and handshake model. No serial PHY pins were inferred from a TLP/backend interface.")
                approved=st.checkbox("I reviewed the architecture and approve this topology proposal", key="architecture_approved")
                st.divider()
                st.subheader("UVM architecture and source generator")
                selected = report.get("selected_top")
                candidates_top = report.get("top_candidates", [])
                top_options = sorted(set(([selected] if selected else []) + candidates_top))
                if top_options:
                    chosen_top = st.selectbox("DUT top module", top_options, index=top_options.index(dut_model['dut_top']) if dut_model['dut_top'] in top_options else 0)
                    output_dir = str(Path(report["project_dir"]) / "mverify_uvm_generated")
                    st.code(output_dir)
                    if st.button("Generate approved UVM architecture", disabled=not approved):
                        try:
                            result = generate_uvm_project(report, output_dir, chosen_top, architecture=selected_arch)
                            st.session_state["uvm_generation"] = result
                            learning_result = record_mcore_experience(
                                task_type="uvm_generation",
                                task={
                                    "dut_top": chosen_top,
                                    "project_dir": report.get("project_dir", ""),
                                    "architecture_id": selected_arch.get("id", ""),
                                    "architecture_name": selected_arch.get("name", ""),
                                    "rtl_file_count": report.get("summary", {}).get("rtl_files", 0),
                                    "module_count": report.get("summary", {}).get("modules", 0),
                                },
                                prediction={
                                    "expected_output": "DUT-specific UVM scaffold generated from the selected architecture",
                                    "expected_file_count": result.get("files"),
                                    "expected_agents": result.get("agents", []),
                                },
                                outcome={
                                    "generation_status": "success",
                                    "output_dir": result.get("output_dir", output_dir),
                                    "file_count": result.get("files"),
                                    "agents": result.get("agents", []),
                                },
                                evidence={
                                    "source": "Mverify UVM generator",
                                    "generated_output_dir": result.get("output_dir", output_dir),
                                    "generation_result": result,
                                    "note": "Generation success is not proof of protocol correctness or functional verification.",
                                },
                                project_id=str(report.get("project_dir", "")),
                                notes="Automatically captured after successful UVM generation; no model weights were changed.",
                            )
                            if learning_result.get("recorded"):
                                st.success("Mcore recorded this UVM generation as an engineering experience.")
                            else:
                                st.warning("UVM generation succeeded, but Mcore experience capture failed: " + learning_result.get("error", "unknown error"))
                            st.success("Generated architecture package with %s files."%result["files"])
                        except Exception as exc: st.error("UVM generation failed: %s"%exc)
                generated = st.session_state.get("uvm_generation")
                if generated:
                    st.write("Generated directory: `%s`"%generated["output_dir"])
                    st.write("Agents: "+", ".join(generated["agents"]))
                    st.info("The approved architecture is saved with the generated project. Pin-level active driver generation is a separate stage and requires reviewed signal mappings. This prevents unsafe stimulus on incorrectly classified pins.")
                st.markdown("#### Analysis evidence and limitations")
                with st.expander("Inspect DUT model JSON"):
                    st.json(dut_model)
                with st.expander("Inspect full reasoning result"):
                    st.json(intelligence)
                st.download_button("Download DUT-specific intelligence report", data=__import__("json").dumps(intelligence,indent=2), file_name="mverify_dut_intelligence.json", mime="application/json")

    st.subheader("Top-level candidates")
    st.write(report.get("top_candidates", []))

    st.subheader("Discovered hierarchy")
    hierarchy = report.get("hierarchy", [])
    if hierarchy:
        st.dataframe(hierarchy, use_container_width=True)
    else:
        st.caption("No child-module instances were identified by the structural scan.")

    st.subheader("Discovered modules")
    for module in report.get("module_details", []):
        with st.expander(f"{module['name']} — {module['source_file']}"):
            st.write(f"**Port style:** {module.get('port_style', 'unknown')}")
            st.write(f"**Ports:** {len(module['ports'])}")
            if module["ports"]:
                st.dataframe(module["ports"], use_container_width=True)
            else:
                st.caption("No ports extracted by the current parser.")

    if report.get("warnings"):
        st.subheader("Warnings")
        for warning in report["warnings"]:
            st.warning(warning)

    st.divider()
    st.header("Protocol and runtime verification intelligence")
    st.caption("This layer adds reviewable interface candidates, measured handshake stalls from exported signal samples, and RTL change snapshots. It does not infer legal protocol latency or declare compliance from signal names.")

    readiness = build_verification_readiness(report, st.session_state.get("mapped_requirements", []))
    contracts = readiness.get("interface_contract_candidates", [])
    r1, r2, r3 = st.columns(3)
    r1.metric("Handshake candidates", len(contracts))
    r2.metric("FSM candidates", len(readiness.get("state_machine_candidates", [])))
    r3.metric("Approved requirements", readiness["requirements"]["approved"])

    if contracts:
        st.subheader("Candidate interface contracts")
        st.dataframe([{
            "Interface": x["interface_id"],
            "Valid": f'{x["valid_signal"]} ({x["valid_direction"]})',
            "Ready": f'{x["ready_signal"]} ({x["ready_direction"]})',
            "Quality": x["candidate_quality"],
            "Review required": x["review_required"],
        } for x in contracts], use_container_width=True)
        with st.expander("Inspect interface assumptions and review items"):
            for item in contracts:
                st.markdown(f'**{item["interface_id"]}**')
                st.json({"acceptance_expression_candidate": item["acceptance_expression"],
                         "classification": item["classification"],
                         "not_established": item["not_established"]})
    else:
        st.info("No exact valid/ready naming pairs were detected. This does not prove that the DUT has no handshake interfaces.")

    st.subheader("Handshake stall analysis")
    st.write("Export a CSV from your simulator or waveform tool. Supported formats: wide (`cycle,tx_valid,tx_ready`) or long (`cycle,signal,value`).")
    trace_file = st.file_uploader("Upload signal-sample CSV", type=["csv"], key="mcore_handshake_trace")
    if trace_file is not None:
        try:
            trace_path = Path(config.log_dir) / f"handshake_trace_{Path(trace_file.name).name}"
            trace_bytes = trace_file.getvalue()
            if len(trace_bytes) > 20 * 1024 * 1024:
                raise ValueError("CSV upload exceeds the 20 MB limit.")
            trace_path.write_bytes(trace_bytes)
            samples = load_signal_csv(trace_path)
            contract_ids = [x["interface_id"] for x in contracts]
            if contract_ids:
                selected_contract_id = st.selectbox("Interface to analyse", contract_ids, key="mcore_trace_contract")
                selected_contract = next(x for x in contracts if x["interface_id"] == selected_contract_id)
                if st.button("Analyse handshake stalls"):
                    analysis = analyze_handshake_samples(samples, [selected_contract])
                    st.session_state["mcore_handshake_analysis"] = analysis
            else:
                st.warning("No candidate interface is available for automatic signal pairing. Review signal names and upload a manually mapped trace in a future release.")
        except Exception as exc:
            st.error(f"Could not read signal CSV: {exc}")
    handshake_result = st.session_state.get("mcore_handshake_analysis")
    if handshake_result:
        for item in handshake_result.get("interfaces", []):
            a, b, c, d = st.columns(4)
            a.metric("Accepted cycles", item["accepted_cycles"])
            b.metric("Stalled cycles", item["stalled_cycles"])
            c.metric("Longest stall", item["longest_observed_stall_cycles"])
            d.metric("Unknown samples", item["unknown_or_missing_samples"])
            st.caption(item["interpretation_limit"])
        st.download_button("Download handshake analysis (JSON)", data=__import__("json").dumps(handshake_result, indent=2), file_name="mverify_handshake_analysis.json", mime="application/json")

    st.subheader("RTL change-impact snapshots")
    st.caption("Snapshots hash RTL and build inputs. A file-level diff identifies what changed; run a fresh scan before treating the change as semantic impact.")
    if st.button("Capture snapshot and compare with previous"):
        try:
            snapshot = capture_project_snapshot(Path(report["project_dir"]))
            snapshot_dir = Path(report["project_dir"]) / ".mverify" / "snapshots"
            prior_paths = sorted(snapshot_dir.glob("*.json"))
            prior_paths = [x for x in prior_paths if x.name != Path(snapshot["snapshot_path"]).name]
            st.session_state["mcore_latest_snapshot"] = snapshot
            if prior_paths:
                previous = __import__("json").loads(prior_paths[-1].read_text(encoding="utf-8"))
                diff = compare_project_snapshots(previous, snapshot)
                st.session_state["mcore_snapshot_diff"] = diff
            else:
                st.session_state["mcore_snapshot_diff"] = None
        except Exception as exc:
            st.error(f"Snapshot failed: {exc}")
    latest_snapshot = st.session_state.get("mcore_latest_snapshot")
    if latest_snapshot:
        st.success(f'Snapshot captured: {latest_snapshot["file_count"]} tracked files.')
        st.caption(latest_snapshot["snapshot_path"])
        diff = st.session_state.get("mcore_snapshot_diff")
        if diff is None:
            st.info("This is the first snapshot. Capture another snapshot after an RTL or build-input change to obtain a diff.")
        else:
            st.write(f'Change status: **{diff["status"]}** — {diff["change_count"]} changed files')
            st.json({"added": diff["added"], "removed": diff["removed"], "modified": diff["modified"]})

    with st.expander("Verification readiness gates and limitations"):
        st.json({"readiness_gates": readiness["readiness_gates"], "limitations": readiness["limitations"]})

    st.download_button(
        "Download scan report (JSON)",
        data=__import__("json").dumps(report, indent=2),
        file_name="mverify_scan_report.json",
        mime="application/json",
    )
