from __future__ import annotations

import os
from typing import Dict, List


def _get_ddb():
    try:
        import boto3  # type: ignore
        return boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    except Exception:
        return None


def _get_table():
    table_name = os.getenv("DDB_TABLE_NAME", "aci_conversations").strip()
    if not table_name:
        return None
    ddb = _get_ddb()
    if not ddb:
        return None
    try:
        table = ddb.Table(table_name)
        # Touch the table to verify; may raise if not exists
        _ = table.table_status  # type: ignore[attr-defined]
        return table
    except Exception:
        # Try to create the table if permissions allow
        try:
            table = ddb.create_table(
                TableName=table_name,
                KeySchema=[
                    {"AttributeName": "studentId", "KeyType": "HASH"},
                    {"AttributeName": "timestampIso", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "studentId", "AttributeType": "S"},
                    {"AttributeName": "timestampIso", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            # Wait until active
            table.wait_until_exists()
            return table
        except Exception:
            return None


def put_conversation_turn(turn: Dict) -> None:
    table = _get_table()
    if not table:
        return
    item = {k: v for k, v in turn.items() if v is not None}
    try:
        table.put_item(Item=item)  # type: ignore[attr-defined]
    except Exception:
        # Silent no-op if write fails in local/dev
        pass


def get_recent_conversations(student_id: str, limit: int = 5) -> List[Dict]:
    table = _get_table()
    if not table:
        return []
    try:
        resp = table.query(  # type: ignore[attr-defined]
            KeyConditionExpression="#s = :sid",
            ExpressionAttributeNames={"#s": "studentId"},
            ExpressionAttributeValues={":sid": student_id},
            ScanIndexForward=False,
            Limit=limit,
        )
        items = resp.get("Items", [])
        # Normalize to minimal dicts for LLM context
        out: List[Dict] = []
        for it in items:
            out.append(
                {
                    "timestampIso": str(it.get("timestampIso", "")),
                    "week": str(it.get("week", "")),
                    "flags": ",".join(it.get("flags", [])) if isinstance(it.get("flags"), list) else str(it.get("flags", "")),
                    "message": str(it.get("draftedMessage") or it.get("sentMessage") or ""),
                }
            )
        return out
    except Exception:
        return []


