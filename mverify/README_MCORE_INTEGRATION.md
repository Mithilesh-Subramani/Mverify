# Mverify + Mcore integration

Mverify connects to Mcore through its local HTTP API. Mcore is a separate Python service.

## Start Mcore

```bash
cd Mverify_Mcore_Unified/Mcore
./run_mcore.sh
```

Default API: `http://127.0.0.1:8765`.

## Start Qwen (optional teacher model)

```bash
ollama serve
ollama pull qwen2.5-coder:7b
```

Qwen is used for inference and candidate generation. It does not train itself or update Mcore model weights.

## Start Mverify

```bash
cd Mverify_v0.10.0_Mcore_Integrated/Mverify
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python desktop_app.py
```

Open **Mcore AI Core** and check the connection. Use **Refresh training queue**, enter an example ID, and approve only after confirming data-use permission. Rejection is also available in the tab.

## Export approved dataset

Use the Mcore API:

```bash
curl -X POST http://127.0.0.1:8765/training/export \\
  -H 'Content-Type: application/json' \\
  -d '{"path":"/path/to/mcore-approved.jsonl"}'
```

## Optional fine-tuning experiment

Install the separate training dependencies:

```bash
cd ../Mcore
python -m pip install -r training/requirements-finetune.txt
python training/finetune_lora.py --base-model <compatible-HF-model> --dataset /path/to/mcore-approved.jsonl --output ./adapters/mcore-lora-v1
```

Use a model supported by your installed Transformers/PEFT/bitsandbytes stack and hardware. Evaluate the adapter before deployment. This is an opt-in QLoRA/SFT starter, not a production training orchestrator.

## Tests

```bash
cd ../Mverify
PYTHONPATH=.:../Mcore python -m pytest -q
```
