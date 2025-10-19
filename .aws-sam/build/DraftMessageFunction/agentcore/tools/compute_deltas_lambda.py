import json


def handler(event, context):
    body = event.get("body")
    if isinstance(body, str):
        body = json.loads(body)
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"ok": True, "note": "compute_deltas stub"}),
    }

