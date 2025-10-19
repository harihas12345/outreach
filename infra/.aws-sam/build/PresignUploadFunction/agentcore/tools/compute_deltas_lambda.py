import json
from typing import Dict, List, Any


def _compute_deltas(prev: Dict[str, Dict[str, Any]], curr: Dict[str, Dict[str, Any]]):
    deltas: Dict[str, List[Dict[str, Any]]] = {}
    for student_id, c in curr.items():
        p = prev.get(student_id)
        if not p:
            continue
        for metric, cval in c.get("metrics", {}).items():
            pval = p.get("metrics", {}).get(metric)
            if pval is None:
                continue
            change = float(cval) - float(pval)
            deltas.setdefault(student_id, []).append(
                {
                    "studentId": student_id,
                    "metric": metric,
                    "change": change,
                    "previous": float(pval),
                    "current": float(cval),
                }
            )
    return deltas


def handler(event, context):
    body = event.get("body")
    if isinstance(body, str):
        body = json.loads(body)
    prev = body.get("previousByStudent", {}) if isinstance(body, dict) else {}
    curr = body.get("currentByStudent", {}) if isinstance(body, dict) else {}
    deltas = _compute_deltas(prev, curr)
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"deltasByStudent": deltas}),
    }


