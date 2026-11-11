from mcore.core.knowledge import KnowledgeStore
from mcore.training.dataset import TrainingDataset

def test_knowledge_ingest_chunks_and_searches(tmp_path):
    k=KnowledgeStore(tmp_path/"k.sqlite")
    r=k.ingest_text("spec.pdf", "PCIe replay buffer credit management\n\nCRC integrity check", "pcie")
    assert r["chunks"] >= 1
    assert k.search("replay buffer")[0]["topic"] == "pcie"
    again=k.ingest_text("spec.pdf", "PCIe replay buffer credit management\n\nCRC integrity check", "pcie")
    assert again["inserted"] == 0

def test_training_review_reject_and_list(tmp_path):
    d=TrainingDataset(tmp_path/"t.sqlite")
    x=d.submit("rtl", {"a":1}, {"b":2}, {"source":"fixture.sv","validation_status":"ENGINEERING_REVIEW_REQUIRED"})
    assert d.list(status="pending_review")[0]["id"] == x["id"]
    d.reject(x["id"], "bad example")
    assert d.get(x["id"])["status"] == "rejected"
