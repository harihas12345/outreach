from __future__ import annotations

import os
from typing import List

from ..models import StudentRecord


def draft_message_template(student: StudentRecord, flags: List[str]) -> str:
    reasons = ", ".join([f for f in flags if f])
    # Include compact 3-week summary when present
    hist_parts: List[str] = []
    history = getattr(student, "metricsHistory", None) or {}
    for metric, pts in history.items():
        if len(pts) >= 3:
            hist_parts.append(f"{metric}: {pts[-3]['value']}→{pts[-2]['value']}→{pts[-1]['value']}")
    hist = "; ".join(hist_parts[:3])  # keep short
    recent_conv = getattr(student, "recentConversations", None) or []
    recent_hint = f" Recent notes: {recent_conv[0]['message']}" if recent_conv and recent_conv[0].get('message') else ""
    if reasons:
        base = (
            f"Hi {student.studentName}, I noticed this week ({reasons}). "
            f"I'm here to help—what feels unclear or blocked?"
        )
    else:
        base = (
            f"Hi {student.studentName}, great job staying engaged this week. "
            f"Would you like a quick check-in or tips to keep the momentum?"
        )
    if hist:
        base += f" Recent trend — {hist}."
    base += recent_hint
    return base


def draft_message_with_bedrock(student: StudentRecord, flags: List[str]) -> str:
    try:
        import boto3  # type: ignore
    except Exception:
        return draft_message_template(student, flags)

    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0")
    br = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    # Build concise history context
    history = getattr(student, "metricsHistory", None) or {}
    hist_lines: List[str] = []
    for metric, pts in history.items():
        if len(pts) >= 3:
            hist_lines.append(f"- {metric}: {pts[-3]['value']} -> {pts[-2]['value']} -> {pts[-1]['value']}")
    conv_lines: List[str] = []
    for c in (getattr(student, "recentConversations", None) or [])[:3]:
        msg = c.get("message") or ""
        if msg:
            conv_lines.append(f"- {c.get('timestampIso','')}: {msg}")
    prompt = (
        "You are an empathetic instructor. Draft a concise, supportive Slack DM (<= 3 sentences) "
        "to a learner based on the following context. Avoid shaming; be specific, offer help, and keep a warm tone.\n\n"
        f"Learner: {student.studentName}\n"
        f"Signals: {', '.join(flags)}\n"
        f"Latest metrics: {student.metrics}\n"
        f"3-week trends:\n" + ("\n".join(hist_lines) if hist_lines else "- None") + "\n"
        f"Recent conversation snippets (most recent first):\n" + ("\n".join(conv_lines) if conv_lines else "- None") + "\n"
    )
    resp = br.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        inferenceConfig={"maxTokens": 300, "temperature": 0.3},
    )
    try:
        return resp["output"]["message"]["content"][0]["text"]
    except Exception:
        return draft_message_template(student, flags)


def draft_message(student: StudentRecord, flags: List[str]) -> str:
    # Prefer Agent Lambda if configured; else Bedrock direct; else template
    agent_lambda = os.getenv("AGENT_DRAFT_MESSAGE_LAMBDA_ARN")
    if agent_lambda:
        try:
            import boto3  # type: ignore
            import json as _json  # local alias to avoid shadowing
            client = boto3.client("lambda", region_name=os.getenv("AWS_REGION", "us-east-1"))
            payload = {
                "student": student.model_dump(),
                "flags": flags,
            }
            resp = client.invoke(
                FunctionName=agent_lambda,
                InvocationType="RequestResponse",
                # The Lambda expects event.body which may be a JSON string; send properly serialized JSON
                Payload=_json.dumps({"body": _json.dumps(payload)}).encode("utf-8"),
            )
            raw = resp["Payload"].read().decode("utf-8")
            body = _json.loads(raw).get("body")
            if isinstance(body, str):
                body = _json.loads(body)
            msg = body.get("message")
            if msg:
                return msg
        except Exception:
            pass

    # Default to using Bedrock unless explicitly disabled
    use_bedrock = os.getenv("USE_BEDROCK", "true").lower() in {"1", "true", "yes"}
    if use_bedrock:
        return draft_message_with_bedrock(student, flags)
    return draft_message_template(student, flags)

