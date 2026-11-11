# Mverify 0.12.2

## Desktop specification workflow
- Specification import now runs automatic requirement triage against the current RTL scan.
- Clear, testable normative requirements with supporting structural evidence are marked approved for verification planning.
- Ambiguous or unsupported candidates remain in manual review. Rejected headings and process text remain rejected.
- Engineers can edit `review_status` in the review data and rerun mapping.
- Approval is a traceability/planning decision. It is not proof of RTL compliance or simulation success.

## Mcore presentation
- Ask Mcore output is rendered as readable engineering sections instead of raw JSON.
- RAG search results show source, topic, score and evidence text.
- Ask Mcore continues to retrieve indexed evidence automatically through the Mcore API and selected local Ollama model.
- Search RAG remains a retrieval-only diagnostic.

## Validation
- Python unit tests cover readable Mcore response formatting.
- No simulator compile or RTL functional pass is claimed.
