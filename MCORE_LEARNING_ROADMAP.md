# Mcore Learning Roadmap

## Delivered in v0.4.0
- Persistent task/outcome/evidence records.
- Reusable lesson proposals linked to an experience.
- Human review and explicit consent before shared knowledge promotion.
- Evaluation history with conservative metric comparison.

## Not delivered yet
- Automatic capture from VCS/Verdi logs, waveforms or Mverify runs.
- Automatic lesson proposal from every failure or engineer correction.
- Tenant isolation and role-based reviewer identity.
- Semantic/vector retrieval.
- Fine-tuning, model registry, rollback or online model updates.

## Required next milestones
1. Instrument Mverify compile, elaboration, simulation and diagnosis stages. Record tool version, command, exit code, log references and artifact hashes.
2. Link each prediction to later observed outcome. Do not infer a pass from missing errors or incomplete logs.
3. Add a fixed, versioned benchmark corpus with train/validation/holdout separation.
4. Generate lesson candidates from recurring, evidence-backed failures. Require human approval before shared promotion.
5. Add retrieval evaluation (recall@k, precision@k, citation correctness) and reasoning evaluation (requirement accuracy, false claims, diagnosis accuracy).
6. Add offline fine-tuning jobs only after sufficient licensed, consented, high-quality examples exist. Keep the current model as a rollback baseline.
7. Promote a model only when it improves pre-registered holdout metrics without unacceptable regressions. Never train directly from unreviewed customer RTL.

## Patent engineering record
Potential mechanism: evidence-linked engineering experience is converted into scoped, reviewed reusable lessons and evaluated against fixed engineering benchmarks before model or knowledge promotion. This is a novelty hypothesis only. Add prior-art review, inventor contribution and implementation evidence before making any patentability claim.
