"""Best-effort client for recording Mverify outcomes in the local Mcore learning API.

Experience capture is non-blocking: an Mcore outage must not prevent RTL analysis
or UVM generation. This records generation events; it does not claim that generated
UVM is functionally correct or update model weights.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def record_mcore_experience(*, task_type, task, prediction, outcome, evidence,
                            project_id=None, notes=""):
    base_url = os.environ.get("MCORE_API_URL", "http://127.0.0.1:8765").rstrip("/")
    payload = {
        "task_type": task_type,
        "task": task,
        "prediction": prediction,
        "outcome": outcome,
        "evidence": evidence,
        "project_id": project_id,
        "notes": notes,
    }
    request = Request(
        base_url + "/learning/experience",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
            return {"recorded": response.status in (200, 201), "response": body}
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        return {"recorded": False, "error": str(exc)}
