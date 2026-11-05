# Mcore v0.4.0 — Evidence-Gated Engineering Learning

## Purpose
Add persistent engineering experience, human-reviewed lessons and evaluation history. This is a controlled learning loop. It does not silently train or modify an LLM.

## New API
- `GET /learning/status` — counts and honest learning-mode status.
- `GET /learning/experiences` — recorded engineering outcomes.
- `GET /learning/lessons?status=pending_review` — proposed lessons.
- `POST /learning/experience` — record task, prediction, actual outcome and evidence.
- `POST /learning/lesson/propose` — propose a reusable lesson from a recorded experience.
- `POST /learning/lesson/review` — engineer approves/rejects. Approval requires `consent: true`; approved lessons are added to the knowledge store.
- `POST /learning/evaluation` — store benchmark metrics and compare against a supplied baseline.

## Learning safety
1. Every experience requires evidence.
2. A lesson is not reusable knowledge until a human approves it and gives explicit consent.
3. Project-specific data must remain isolated by `project_id` and must not be promoted to shared knowledge without permission.
4. A stored evaluation is not proof of general improvement. The current comparator only supports explicit, comparable metrics such as pass rate, accuracy, error rate and latency.
5. Model weights are not updated. No autonomous fine-tuning occurs.
6. The system must not convert one DUT-specific workaround into a universal protocol rule without validation.

## Next work
- Add project/tenant access controls and row-level isolation before multi-user deployment.
- Connect VCS/Verdi result parsers to experience recording.
- Add fixed benchmark suites and regression gates.
- Add embedding-based retrieval and source/version metadata.
- Add a reviewed dataset builder and isolated fine-tuning job with before/after benchmark gates, rollback and model registry.
