# Known limitations — Mverify 0.16.0

- No RHEL deployment or remote integration has been performed from this development checkout. The RHEL validation report must be generated on the engineering host; this package makes no remote success claim.
- The lightweight RTL parser and UDM are structural aids, not a full language front end, elaborator, simulator, or proof engine. Parameter expressions and behavior are not comprehensively evaluated.
- Evidence ID and metadata checks can detect missing, foreign-project, or some conflicting claims; they cannot determine that an engineering conclusion is semantically correct. Human review remains required.
- Project-isolated RAG limits cross-project retrieval. Embedding availability, lexical fallback, source freshness and metrics are reported, but retrieval relevance is not guaranteed.
- Generated UVM is an engineering scaffold. Actual simulation requires a locally available compatible VCS/UVM setup and reviewed project-specific strategy. GUI Verdi availability, licenses, wave opening, functional correctness and coverage closure are not guaranteed by the Python suite.
- VCS, Verdi, Ollama and proprietary design results are host-specific. The provided validation script does not send source to Windows or any external service and does not accept arbitrary shell commands.
