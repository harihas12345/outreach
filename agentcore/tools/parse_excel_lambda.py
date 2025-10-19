import json
import io
from typing import Any, Dict, List


def _read_excel_bytes(content: bytes) -> List[Dict[str, Any]]:
    import pandas as pd  # type: ignore

    df = pd.read_excel(io.BytesIO(content))
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    if "last_active" not in df.columns:
        df["last_active"] = pd.NaT

    for col in ["student_id", "student_name", "slack_user_id"]:
        if col not in df.columns:
            raise ValueError(f"Missing column {col}")

    id_cols = {"student_id", "student_name", "slack_user_id", "last_active"}
    metric_cols = [c for c in df.columns if c not in id_cols]

    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        metrics = {
            k: float(row[k])
            for k in metric_cols
            if row.get(k) is not None and str(row.get(k)) not in {"nan", "NaT"}
        }
        records.append(
            {
                "studentId": str(row["student_id"]),
                "studentName": str(row["student_name"]),
                "slackUserId": str(row["slack_user_id"]),
                "metrics": metrics,
                "lastActiveIso": str(row["last_active"]) if pd.notna(row["last_active"]) else None,
            }
        )
    return records


def handler(event, context):
    body = event.get("body")
    if isinstance(body, str):
        body = json.loads(body)

    # Expect { bucket, key } to read from S3, or { contentBase64 }
    bucket = None
    key = None
    content_b64 = None
    if isinstance(body, dict):
        bucket = body.get("bucket")
        key = body.get("key")
        content_b64 = body.get("contentBase64")

    try:
        if content_b64:
            import base64

            content = base64.b64decode(content_b64)
            records = _read_excel_bytes(content)
        elif bucket and key:
            import boto3  # type: ignore

            s3 = boto3.client("s3")
            obj = s3.get_object(Bucket=bucket, Key=key)
            content = obj["Body"].read()
            records = _read_excel_bytes(content)
        else:
            raise ValueError("Provide contentBase64 or bucket+key")
    except Exception as e:
        return {
            "statusCode": 400,
            "headers": {"content-type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }

    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"records": records}),
    }


