from desktop_app import format_mcore_response


def test_formats_engineering_result_as_readable_sections():
    payload = {
        "result": {
            "design_understanding": ["Top module is a packet controller."],
            "confirmed_facts": ["A FIFO module is instantiated."],
            "inferences": ["The FIFO may buffer transmit traffic."],
            "assumptions": [],
            "unknowns": ["Runtime backpressure behavior is unknown."],
            "requirement_analysis": [],
            "verification_strategy": {"agents": ["passive monitor"]},
            "risks": [], "validation_plan": [], "questions_for_engineer": [],
            "confidence": {"overall": 0.72, "basis": "Static RTL evidence"},
        },
        "retrieved_sources": [{"source": "rtl/top.sv", "topic": "rtl", "score": 2}],
    }
    rendered = format_mcore_response(payload)
    assert "MCORE ENGINEERING ANALYSIS" in rendered
    assert "Top module is a packet controller." in rendered
    assert "Runtime backpressure behavior is unknown." in rendered
    assert '"result"' not in rendered


def test_formats_rag_results_with_source_and_content():
    payload = {"results": [{"source": "rtl/fifo.sv", "topic": "rtl_source",
                            "score": 3, "content": "module fifo; endmodule"}]}
    rendered = format_mcore_response(payload)
    assert "RAG RETRIEVAL RESULTS" in rendered
    assert "rtl/fifo.sv" in rendered
    assert "module fifo; endmodule" in rendered
