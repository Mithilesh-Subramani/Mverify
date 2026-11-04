from pathlib import Path
import streamlit as st

from mverify.core.config import load_config
from mverify.core.logging_setup import configure_logging
from mverify.core.project_scanner import scan_project
from mverify.storage.database import initialize_database, save_scan

st.set_page_config(page_title="Mverify", page_icon="🧪", layout="wide")
config = load_config()
configure_logging(config.log_dir)
initialize_database(config.database_path)

st.title("Mverify")
st.caption("Local-first RTL design verification assistant")
st.info("Milestone 0.1 — foundation and RTL project discovery. Protocol verification is not enabled yet.")

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
