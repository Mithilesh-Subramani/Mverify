from mcore.core.knowledge import KnowledgeStore


def test_project_scoping_prevents_cross_project_retrieval(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3")
    store.ingest_text("pcie.sv", "PCIe replay buffer and TLP credit control", "rtl", "project-pcie")
    store.ingest_text("alu.sv", "ALU add subtract logic and overflow flag", "rtl", "project-alu")

    alu = store.search("what are the risks? ALU add subtract overflow", project_id="project-alu")
    assert alu
    assert all(x["project_id"] == "project-alu" for x in alu)
    assert all("pcie" not in x["source"].lower() for x in alu)

    pcie = store.search("replay buffer TLP credit", project_id="project-pcie")
    assert pcie
    assert all(x["project_id"] == "project-pcie" for x in pcie)


def test_project_reindex_clears_stale_chunks(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3")
    store.ingest_text("old.sv", "old module stale signal", "rtl", "same-project")
    result = store.clear_project("same-project")
    assert result["deleted_chunks"] == 1
    store.ingest_text("new.sv", "new module current signal", "rtl", "same-project")
    found = store.search("current signal", project_id="same-project")
    assert found and all(x["source"] == "new.sv" for x in found)


def test_hybrid_embedding_score_is_used_when_embedder_available(tmp_path):
    def embed(text):
        return [1.0, 0.0] if ("adder" in text.lower() or "arithmetic" in text.lower() or "sum" in text.lower()) else [0.0, 1.0]
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3", embedder=embed)
    store.ingest_text("alu.sv", "combinational adder and arithmetic logic", "rtl", "alu")
    found = store.search("sum arithmetic", project_id="alu")
    assert found
    assert found[0]["semantic_score"] > 0.9
