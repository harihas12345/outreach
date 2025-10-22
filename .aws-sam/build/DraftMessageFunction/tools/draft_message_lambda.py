import json
import os
from typing import Any, Dict, List


def _template(student: Dict[str, Any], flags: List[str]) -> str:
    reasons = ", ".join(flags)
    return (
        f"Hi {student['studentName']}, I noticed a few signals this week ({reasons}). "
        f"How are you feeling about the material? Anything I can clarify or help with?"
    )


def _draft_with_bedrock(student: Dict[str, Any], flags: List[str]) -> str:
    try:
        import boto3  # type: ignore
    except Exception:
        return _template(student, flags)
    model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
    region = os.getenv("AWS_REGION", "us-east-1")
    br = boto3.client("bedrock-runtime", region_name=region)
    prompt = (
        "You are an empathetic instructor. Draft a concise, supportive Slack DM (<= 3 sentences) "
        "to a learner based on the following context. Avoid shaming; be specific, offer help, and keep a warm tone.\n\n"
        f"Learner: {student['studentName']}\n"
        f"Signals: {', '.join(flags)}\n"
        f"Metrics: {student.get('metrics', {})}\n"
    )
    resp = br.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 300, "temperature": 0.3},
    )
    try:
        return resp["output"]["message"]["content"][0]["text"]
    except Exception:
        return _template(student, flags)


def handler(event, context):
    body = event.get("body")
    if isinstance(body, str):
        body = json.loads(body)
    student = body.get("student")
    flags = body.get("flags", [])
    use_bedrock = os.getenv("USE_BEDROCK", "true").lower() in {"1", "true", "yes"}
    msg = _draft_with_bedrock(student, flags) if use_bedrock else _template(student, flags)
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"message": msg}),
    }



