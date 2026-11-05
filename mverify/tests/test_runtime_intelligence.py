from mverify.core.runtime_intelligence import analyse_event_trace, summarize_signal_samples

def test_event_trace_finds_first_missing_event():
    r=analyse_event_trace([{"name":"request"},{"name":"crc_done"},{"name":"tx"}], [{"name":"request","cycle":1},{"name":"crc_done","cycle":4}])
    assert r["status"]=="divergence"
    assert r["first_divergence"]["event"]=="tx"

def test_event_trace_only_checks_explicit_latency_limit():
    r=analyse_event_trace([{"name":"a"},{"name":"b","max_cycles_from_previous":2}], [{"name":"a","cycle":1},{"name":"b","cycle":5}])
    assert r["events"][1]["status"]=="timing_violation"

def test_signal_summary_counts_changes_and_unknowns():
    r=summarize_signal_samples([{"signals":{"ready":"0"}},{"signals":{"ready":"1"}},{"signals":{"ready":"x"}}])
    assert r["ready"]["changes"]==2 and r["ready"]["unknown_samples"]==1
