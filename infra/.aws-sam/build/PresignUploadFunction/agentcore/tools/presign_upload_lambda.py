import json
import os
import time
from typing import Any, Dict


def handler(event, context):
    try:
        import boto3  # type: ignore
    except Exception:
        return {
            "statusCode": 500,
            "headers": {"content-type": "application/json"},
            "body": json.dumps({"error": "boto3 not available"}),
        }

    body = event.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except Exception:
            body = {}
    if not isinstance(body, dict):
        body = {}

    file_name = body.get("fileName") or f"upload-{int(time.time())}.xlsx"
    prefix = body.get("prefix", "")
    bucket = os.environ.get("BUCKET_NAME")
    if not bucket:
        return {
            "statusCode": 500,
            "headers": {"content-type": "application/json"},
            "body": json.dumps({"error": "BUCKET_NAME not configured"}),
        }

    key = f"{prefix}/{file_name}" if prefix else file_name
    s3 = boto3.client("s3")

    conditions = [["starts-with", "$Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]]
    fields = {"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    presigned = s3.generate_presigned_post(
        Bucket=bucket,
        Key=key,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=3600,
    )
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"bucket": bucket, "key": key, "presigned": presigned}),
    }


