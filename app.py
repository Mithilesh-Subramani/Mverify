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

st.set_page_config(page_title="Mverify", page_icon="🧪", layout="wide")
config = load_config()
configure_logging(config.log_dir)
initialize_database(config.database_path)

st.title("Mverify")
st.caption("Local-first RTL design verification assistant")
st.info("Mverify v0.6 — RTL discovery, evidence-based requirement triage, and UVM skeleton generation.")

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
        st.caption("Structural estimates only. These are not protocol compliance results.")
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
        if mapped:
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
                             "mapping_note": item["mapping_note"]})
            st.download_button(
                "Download requirement evidence matrix (JSON)",
                data=__import__("json").dumps(mapped, indent=2),
                file_name="mverify_requirement_evidence.json",
                mime="application/json",
            )

            st.divider()
            st.subheader("Verification intelligence")
            st.caption("Creates reviewable test-plan proposals from approved requirements and their RTL evidence. It does not generate executable UVM or claim test execution.")
            if st.button("Generate verification plan", type="primary"):
                plan = generate_verification_plan(mapped)
                st.session_state["verification_plan"] = plan
            plan = st.session_state.get("verification_plan", [])
            if plan:
                st.dataframe([{
                    "Requirement": x["requirement_id"],
                    "Suggested layer": x["suggested_category"],
                    "Plan status": x["plan_status"],
                    "Scenarios": len(x["proposed_scenarios"]),
                    "Execution": x["execution_status"],
                } for x in plan], use_container_width=True)
                with st.expander("Detailed verification plan"):
                    for item in plan:
                        st.markdown(f"**{item['requirement_id']} — {item['suggested_category']}**")
                        st.write(item["statement"])
                        st.write("**Decomposition**")
                        st.json(item["decomposition"])
                        st.write("**Proposed scenarios**")
                        st.json(item["proposed_scenarios"])
                st.download_button(
                    "Download verification plan (JSON)",
                    data=__import__("json").dumps(plan, indent=2),
                    file_name="mverify_verification_plan.json",
                    mime="application/json",
                )

            st.divider()
            st.subheader("UVM architecture and source generator")
            st.caption("Generates editable UVM 1.2 skeleton files inside the RTL project in a separate mverify_uvm_generated directory. It does not modify RTL files.")
            selected = report.get("selected_top")
            candidates_top = report.get("top_candidates", [])
            top_options = sorted(set(([selected] if selected else []) + candidates_top))
            if top_options:
                chosen_top = st.selectbox("DUT top module", top_options, index=0)
                output_dir = str(Path(report["project_dir"]) / "mverify_uvm_generated")
                st.code(output_dir)
                if st.button("Generate UVM files in RTL project"):
                    try:
                        result = generate_uvm_project(report, output_dir, chosen_top)
                        st.session_state["uvm_generation"] = result
                        st.success("Generated %s files for %s."%(result["files"],result["top"]))
                    except Exception as exc:
                        st.error("UVM generation failed: %s"%exc)
            else:
                st.warning("No top-level candidate is available. Select or fix the DUT top before generation.")
            generated = st.session_state.get("uvm_generation")
            if generated:
                st.write("Generated directory: `%s`"%generated["output_dir"])
                st.write("Agents: "+", ".join(generated["agents"]))
                st.warning("This is a structural skeleton. Review TODO markers, add DUT instance connections, protocol behavior, config_db setup, scoreboard checks, and compile order before VCS simulation.")

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

    st.download_button(
        "Download scan report (JSON)",
        data=__import__("json").dumps(report, indent=2),
        file_name="mverify_scan_report.json",
        mime="application/json",
    )
