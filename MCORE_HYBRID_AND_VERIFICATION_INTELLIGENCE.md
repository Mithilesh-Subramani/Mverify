# Mcore hybrid routing and verification intelligence

## Design principles

1. Deterministic tools own parsing, simulation, assertions, coverage and evidence collection.
2. LLMs assist with planning and diagnosis. They do not establish a pass result.
3. Static RTL inferences remain labelled as candidates until reviewed or confirmed by stronger evidence.
4. Local inference is the default. Cloud inference requires explicit per-request approval.

## New verification intelligence API

`mverify.core.verification_intelligence` provides:

- `discover_interface_contracts(scan_report)`: finds valid/ready port-name pairs with complementary directions. The result is an interface candidate, not a confirmed protocol contract.
- `load_signal_csv(path)`: reads wide (`cycle,valid,ready`) and long (`cycle,signal,value`) CSV exports.
- `analyze_handshake_samples(samples, contracts)`: counts observed accepts, stall cycles, longest contiguous stall and unknown samples. It does not impose a protocol timing limit.
- `capture_project_snapshot(project_dir)`: hashes RTL and selected build inputs into `.mverify/snapshots/`.
- `compare_project_snapshots(previous, current)`: reports added, removed and modified files.
- `build_verification_readiness(scan_report, requirements)`: summarizes structural evidence and review gates.

## Hybrid model routing

`mcore.core.model_router.HybridModelRouter` wraps a local client and an optional OpenAI-compatible cloud client. The router sends requests to local Ollama unless all of the following are true:

- `MCORE_CLOUD_ENABLED=true`.
- Cloud base URL, API key and model are configured.
- The caller sets `cloud_approved=True`.
- The caller sets `data_classification="approved_for_cloud"`.

The Mcore engineering API accepts these two per-request fields. A missing cloud configuration or missing approval uses local Ollama. Cloud request content must be approved by the design owner and the organization's security policy.

## Limitations

- Valid/ready matching is name- and direction-based. It does not prove payload association, clocking, reset, stability or protocol meaning.
- CSV analysis measures supplied samples only. It cannot recover signals that were not exported.
- Snapshot comparison is file-level. It does not yet compute semantic dependency impact or automatically select regression tests.
- Protocol requirements still need an authoritative specification source, revision, engineer review and traceable acceptance criteria.
- No new VCS/Questa/Xcelium simulation claim is made by this release.
