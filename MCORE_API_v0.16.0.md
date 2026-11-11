# Mcore API 0.16.0

Mcore is an independently launched local service. Default base URL is `http://127.0.0.1:8765/api/v1`; legacy unprefixed paths remain accepted. Requests and responses are JSON. Requests are size-limited, assigned request IDs in logs, and bound to loopback. There is no command execution or remote job API.

## Core endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service, configuration and API health metadata |
| GET | `/models` | Configured Ollama model/embedding status; no silent fallback |
| POST | `/reason/engineering` | Evidence-bounded, project-scoped engineering reasoning |
| POST | `/reason/evaluate` | Validate claim evidence against supplied project evidence |
| POST | `/knowledge/ingest` | Add text to one project namespace with source metadata |
| POST | `/knowledge/search` | Search only the provided `project_id` namespace |
| POST | `/knowledge/project/status` | Get counts/status for a project namespace |
| POST | `/knowledge/project/clear` | Remove indexed content for the named project |
| POST | `/evaluation/retrieval` | Compute retrieval metrics from supplied cases |
| POST | `/training/submit` | Submit evidence-bearing example for review |
| POST | `/training/approve` | Approve a validated/negative example with consent and reviewer |
| POST | `/training/export` | Export approved records under `MCORE_HOME/training_exports` |

### Reasoning request

```json
{
  "task": "Identify reset-related risks and propose checks",
  "project_id": "stable-project-id",
  "project_context": {"dut_top": "example_top"},
  "rtl_evidence": {"ports": []},
  "spec_evidence": [],
  "tool_evidence": {},
  "model": "qwen2.5-coder:14b"
}
```

Reasoning results include schema validation, claim-validation status, evidence references, project scope and retrieval metadata. An unavailable model returns a service error; Mcore does not claim unavailable model output or choose another model silently. Evidence validation is not proof of semantic correctness.

## Configuration

See `.env.example` and `mcore/config.py`. The defaults are loopback-only. Do not expose Mcore or Ollama on a public interface. `MCORE_HOME` is the private persistent data directory. Migrations back up databases before schema changes. The API is an engineering-local API, not an authenticated network service; access should remain host-local and protected by OS account controls.
