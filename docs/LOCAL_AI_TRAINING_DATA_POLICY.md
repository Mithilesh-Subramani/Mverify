# Mverify AI training data policy

Mverify must distinguish retrieval data from training data.

- Project RTL and specifications are indexed for that project's retrieval context only.
- Project content is not automatically promoted into model training data.
- Save model prompts, responses, evidence references, corrections and validation results as separate records.
- Require explicit engineer approval before an example enters a training dataset.
- Require explicit authorization before using customer-confidential RTL or specifications for any training purpose.
- Keep project/tenant identity and source hashes with every example.
- Keep rejected and unreviewed examples out of training exports.
- Evaluate a fine-tuned model against a fixed benchmark and the original base model before deployment.
