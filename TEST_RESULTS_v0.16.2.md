# Mverify 0.16.2 validation record

Environment used for package validation: Python 3.13.

- `python -m compileall -q app.py mcore mverify` — passed.
- `python -m pytest -q` — 77 passed.
- New tests cover valid/ready candidate discovery, measured handshake stalls, wide/long CSV ingestion, project snapshot diffs, readiness labels, and explicit cloud-routing policy.

Not executed in this packaging environment:
- Streamlit GUI launch (Streamlit is an optional dependency and was not installed in the packaging environment).
- Ollama model inference.
- Synopsys VCS/Verdi, Siemens Questa, or Cadence Xcelium compile/simulation.
- Formal verification or PCIe compliance testing.

Passing Python tests do not establish RTL functional correctness or protocol compliance.
