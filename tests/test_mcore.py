import json
from mcore.training.dataset import TrainingDataset
from mcore.core.knowledge import KnowledgeStore

def test_training_requires_consent(tmp_path):
    ds=TrainingDataset(tmp_path/"d.sqlite")
    item=ds.submit("rtl_explanation",{"rtl":"x"},{"answer":"y"},{"validation_status":"EVIDENCE_VALIDATED","evidence_ids":["ev_1"]})
    assert item["status"]=="pending_review"
    try: ds.approve(item["id"],consent=False)
    except ValueError: pass
    else: assert False
    ds.approve(item["id"],consent=True,reviewer="reviewer-a")
    out=tmp_path/"out.jsonl"
    assert ds.export_jsonl(out)==1
    assert json.loads(out.read_text().strip())["target"]["answer"]=="y"

def test_training_requires_validation_and_deduplicates(tmp_path):
    ds=TrainingDataset(tmp_path/"d.sqlite")
    item=ds.submit("rtl_explanation",{"rtl":"x"},{"answer":"y"},{"line":1})
    duplicate=ds.submit("rtl_explanation",{"rtl":"x"},{"answer":"y"},{"line":1})
    assert duplicate["duplicate"] and duplicate["id"]==item["id"]
    try: ds.approve(item["id"],consent=True,reviewer="reviewer-a")
    except ValueError as exc: assert "validated" in str(exc)
    else: assert False

def test_knowledge_store_search(tmp_path):
    store=KnowledgeStore(tmp_path/"k.sqlite")
    store.ingest_text("spec.txt","valid ready handshake protocol","interface")
    assert store.search("handshake")
