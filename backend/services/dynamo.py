from __future__ import annotations

import os
from typing import Dict, List, Any
from decimal import Decimal


_DDB_DEBUG = os.getenv("DDB_DEBUG", "").lower() in {"1", "true", "yes"}


def _dbg(msg: str) -> None:
    if _DDB_DEBUG:
        try:
            print(f"[DDB] {msg}")
        except Exception:
            pass


def _get_ddb():
    try:
        import boto3  # type: ignore
        return boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    except Exception as e:
        _dbg(f"boto3 dynamodb init failed: {e}")
        return None


def _get_table():
    table_name = os.getenv("DDB_TABLE_NAME", "aci_conversations").strip()
    if not table_name:
        _dbg("DDB_TABLE_NAME not set; skipping DynamoDB")
        return None
    ddb = _get_ddb()
    if not ddb:
        _dbg("No DynamoDB resource; check AWS credentials/region")
        return None
    try:
        table = ddb.Table(table_name)
        # Touch the table to verify; may raise if not exists
        _ = table.table_status  # type: ignore[attr-defined]
        _dbg(f"Using table {table_name}")
        return table
    except Exception as e:
        _dbg(f"Describe table failed for {table_name}: {e}")
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
            _dbg(f"Created table {table_name}")
            return table
        except Exception as ce:
            _dbg(f"Create table failed for {table_name}: {ce}")
            return None


def put_conversation_turn(turn: Dict) -> None:
    table = _get_table()
    if not table:
        _dbg("Skip put_conversation_turn: table unavailable")
        return

    def _coerce_for_ddb(value: Any) -> Any:
        if isinstance(value, float):
            # Convert floats to Decimal for DynamoDB
            return Decimal(str(value))
        if isinstance(value, dict):
            return {k: _coerce_for_ddb(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_coerce_for_ddb(v) for v in value]
        if isinstance(value, tuple):
            return tuple(_coerce_for_ddb(v) for v in value)
        return value

    item = _coerce_for_ddb({k: v for k, v in turn.items() if v is not None})
    try:
        table.put_item(Item=item)  # type: ignore[attr-defined]
        _dbg(f"Put item ok for studentId={item.get('studentId')} ts={item.get('timestampIso')}")
    except Exception as e:
        # Silent no-op if write fails in local/dev (with optional debug)
        _dbg(f"Put item failed: {e}")


def get_recent_conversations(student_id: str, limit: int = 5) -> List[Dict]:
    table = _get_table()
    if not table:
        _dbg("Skip get_recent_conversations: table unavailable")
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
        _dbg(f"Fetched {len(out)} items for studentId={student_id}")
        return out
    except Exception as e:
        _dbg(f"Query failed for studentId={student_id}: {e}")
        return []



