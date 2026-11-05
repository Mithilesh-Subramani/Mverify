# Mcore v0.2.0 — architecture and flow

## Independent service
Mcore is a separate local Python package and HTTP service. Mverify is its first client. Mcore stores its knowledge and training records under `~/.mcore` by default.

## Implemented components
- Ollama adapter for local teacher-model inference.
- Knowledge ingestion with paragraph chunking, content provenance and duplicate suppression.
- Lexical retrieval ranked by query-term frequency.
- Retrieval-augmented reasoning endpoint. Retrieved source names and topics are returned with the answer.
- Training candidate queue with pending, training-ready and rejected states.
- Explicit data-use consent gate before training-ready status.
- JSONL export for approved records.
- Optional QLoRA/SFT starter script. Training dependencies are separate and not installed by the normal Mcore service.
- Mverify controls to inspect the queue, approve with explicit consent, or reject a record.

## Runtime data flow
1. Mverify submits a DUT/specification task to Mcore.
2. Mcore retrieves matching knowledge chunks.
3. Mcore sends the prompt plus retrieved context to Qwen through Ollama.
4. Mcore returns the candidate response and retrieved-source metadata.
5. Mverify presents it as advisory output. It is not treated as verified behaviour.
6. Mverify can submit an example to Mcore. It starts as `pending_review`.
7. An engineer inspects and approves or rejects it. Approval requires explicit data-use consent.
8. Approved examples can be exported to JSONL.
9. An engineer can run the optional fine-tuning script on a compatible Hugging Face model.
10. The resulting adapter must pass a held-out benchmark and regression suite before deployment.

## What Qwen does
Qwen is the initial teacher model. It can assist with explanations and candidate examples. Inference is not training. Qwen does not automatically transfer its weights to Mcore. The optional fine-tuning script updates a compatible base model using the approved dataset.

## Limits
- Retrieval is lexical, not embedding/vector retrieval.
- No automatic document PDF/DOCX ingestion UI is included; text ingestion is available through the API.
- The fine-tuning script is an experimental starter, not a distributed trainer or automatic model registry.
- No proprietary foundation model has been trained in this release.
- Do not use confidential customer RTL for training without documented permission.
