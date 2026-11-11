# Mverify 0.16.0 release notes

- Restructured engineering reasoning around a project-scoped evidence context with stable evidence identifiers, bounded inputs, source provenance and claim validation.
- Made Mcore API, Ollama endpoint, reasoning model, embedding model, request size, timeouts and context limits environment-configurable. Mcore binds to loopback only and does not silently switch models.
- Added versioned API routing compatibility, request IDs, request-size checks, startup migrations and model/embedding health reporting.
- Added project metadata and provenance to retrieval, retrieval metrics, validated same-project experience retrieval, and explicit human reviewer/consent gates for training data.
- Added UDM source provenance, parameter defaults and additional structural candidates.
- Routed desktop DUT intelligence through Mcore while retaining deterministic DUT model and architecture output when Mcore is unavailable.
- Added fixed-action RHEL validation with JSON reports, logs, project allowlists, action timeouts and explicit approval flags for private RTL and VCS.
- Added only synthetic test fixtures. No proprietary RTL is included.
