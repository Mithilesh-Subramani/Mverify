"""Mverify local Ollama + project-scoped RAG workspace."""
from pathlib import Path
import streamlit as st

from mverify.core.ai.ollama_client import OllamaClient, OllamaError
from mverify.core.rag.indexer import ProjectIndexer
from mverify.core.rag.retriever import ProjectRetriever

st.set_page_config(page_title="Mverify Local AI", page_icon="🧠", layout="wide")
st.title("Local AI + Project RAG")
st.caption("Local Ollama inference. Project-scoped retrieval. No cloud model API.")

report = st.session_state.get("last_report", {})
default_path = report.get("project_dir", "")
project_path = st.text_input("RTL/specification project directory", value=default_path,
                             placeholder="/path/to/your/rtl_project")
project_id = str(Path(project_path).expanduser().resolve()) if project_path.strip() else ""

with st.sidebar:
    st.subheader("Local model settings")
    chat_model = st.text_input("Chat model", value="qwen3-coder:30b")
    embedding_model = st.text_input("Embedding model", value="nomic-embed-text")
    qdrant_path = st.text_input("Local Qdrant data directory",
                                value=str(Path.home() / ".mverify" / "qdrant"))
    ollama_url = st.text_input("Ollama URL", value="http://127.0.0.1:11434")
    context_limit = st.number_input("Retrieved chunks", min_value=2, max_value=20, value=8)

ollama = OllamaClient(base_url=ollama_url, chat_model=chat_model,
                      embedding_model=embedding_model)

if not project_path.strip():
    st.info("Enter a project directory. Mverify will index its RTL and text-based specification files.")
    st.stop()

root = Path(project_path).expanduser()
if not root.is_dir():
    st.error("The project directory does not exist.")
    st.stop()

left, right = st.columns([1, 2])
with left:
    st.markdown("### Knowledge index")
    st.write("Project ID:", project_id)
    if st.button("Index / refresh this project", type="primary"):
        try:
            with st.spinner("Reading project files and creating local embeddings..."):
                indexer = ProjectIndexer(qdrant_path, ollama)
                result = indexer.index_project(project_id, root)
                indexer.client.close()
            st.session_state["rag_index_result"] = result
            st.success("Project index updated.")
        except Exception as exc:
            st.error(f"Indexing failed: {exc}")
    if st.session_state.get("rag_index_result"):
        st.json(st.session_state["rag_index_result"])
    st.caption("Indexing reads files. It does not modify RTL source files.")

with right:
    st.markdown("### Ask about this DUT")
    question = st.text_area(
        "Question",
        placeholder="Example: Trace the request backpressure path. Which modules and signals control it?",
        height=100,
    )
    if st.button("Retrieve evidence and ask local AI", type="primary", disabled=not question.strip()):
        try:
            with st.spinner("Retrieving project evidence and querying local Ollama..."):
                retriever = ProjectRetriever(qdrant_path, ollama)
                hits = retriever.search(project_id, question, limit=int(context_limit))
                retriever.client.close()
                if not hits:
                    st.warning("No indexed evidence was found. Index this project first.")
                else:
                    evidence = "\n\n".join(
                        f"[{i}] {hit['source_file']}:{hit['start_line']}-{hit['end_line']} "
                        f"(score={hit['score']:.3f})\n{hit['text']}"
                        for i, hit in enumerate(hits, start=1)
                    )
                    system_prompt = (
                        "You are Mverify, a local RTL and verification assistant. "
                        "Use only the supplied project evidence for claims about this DUT. "
                        "Separate observed facts, inferences, assumptions and unknowns. "
                        "Do not invent signal behavior, protocol rules, timing values or hierarchy. "
                        "Cite evidence using [1], [2], etc. If evidence is insufficient, say what is missing. "
                        "Never claim that the DUT passes verification without compiler and simulation evidence."
                    )
                    answer = ollama.chat([
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Question:\n{question}\n\nRetrieved project evidence:\n{evidence}"},
                    ])
                    st.session_state["rag_last_answer"] = answer
                    st.session_state["rag_last_hits"] = hits
        except OllamaError as exc:
            st.error(f"Local Ollama error: {exc}")
        except Exception as exc:
            st.error(f"RAG query failed: {exc}")

if st.session_state.get("rag_last_answer"):
    st.markdown("### Local AI response")
    st.markdown(st.session_state["rag_last_answer"])
    with st.expander("Inspect retrieved source evidence"):
        for i, hit in enumerate(st.session_state.get("rag_last_hits", []), start=1):
            st.markdown(f"**[{i}] {hit['source_file']}:{hit['start_line']}-{hit['end_line']}**")
            st.caption(f"Dense: {hit['dense_score']:.3f} · Lexical: {hit['lexical_score']:.3f}")
            st.code(hit["text"])
