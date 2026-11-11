"""Deterministic trace analysis for event-based DUT progress checks."""
from __future__ import annotations
from typing import Any

def analyse_event_trace(expected_events: list[dict[str,Any]], observed_events: list[dict[str,Any]]):
    """Compare ordered named events. Timing limits apply only when explicitly supplied."""
    results=[]; cursor=0; first=None
    for index,expected in enumerate(expected_events):
        name=expected.get("name")
        found=None
        for j in range(cursor,len(observed_events)):
            if observed_events[j].get("name")==name:
                found=(j,observed_events[j]); break
        if found is None:
            item={"index":index,"event":name,"status":"missing","expected":expected}
            if first is None:first=item
            results.append(item); continue
        j,actual=found; cursor=j+1
        item={"index":index,"event":name,"status":"observed","expected":expected,"actual":actual}
        max_cycles=expected.get("max_cycles_from_previous")
        if max_cycles is not None and index>0:
            prev=results[index-1].get("actual",{})
            if "cycle" in prev and "cycle" in actual:
                delta=actual["cycle"]-prev["cycle"]
                item["latency_cycles"]=delta
                if delta>max_cycles:
                    item["status"]="timing_violation"
                    if first is None:first=item
        results.append(item)
    return {"status":"divergence" if first else "matched","first_divergence":first,
            "events":results,"observed_event_count":len(observed_events),
            "note":"Only supplied event names and explicitly supplied cycle limits are checked. This does not infer protocol timing."}

def summarize_signal_samples(samples: list[dict[str,Any]]):
    """Summarize selected signal observations without claiming protocol semantics."""
    summary={}
    for sample in samples:
        for name,value in sample.get("signals",{}).items():
            item=summary.setdefault(name,{"samples":0,"changes":0,"last":None,"unknown_samples":0})
            item["samples"]+=1
            if isinstance(value,str) and any(ch in value.lower() for ch in "xz"):
                item["unknown_samples"]+=1
            if item["last"] is not None and item["last"]!=value:item["changes"]+=1
            item["last"]=value
    return summary
