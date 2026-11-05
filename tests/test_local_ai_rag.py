from pathlib import Path

from mverify.core.rag.indexer import _chunks, project_collection_name
from mverify.core.rag.retriever import _terms


def test_project_collection_is_stable_and_isolated():
    assert project_collection_name("customer-a") == project_collection_name("customer-a")
    assert project_collection_name("customer-a") != project_collection_name("customer-b")


def test_chunks_keep_source_line_ranges():
    path = Path("/tmp/design.sv")
    chunks = _chunks(path, Path("/tmp"), "\n".join(f"line_{i}" for i in range(1, 171)), max_lines=80)
    assert len(chunks) == 3
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 80
    assert chunks[1]["start_line"] == 81
    assert chunks[2]["end_line"] == 170
    assert chunks[0]["source_file"] == "design.sv"


def test_lexical_tokens_preserve_rtl_identifiers():
    assert "tx_valid" in _terms("Find tx_valid and pcie_pkg::tlp_t")
    assert "pcie_pkg" in _terms("pcie_pkg::tlp_t")
