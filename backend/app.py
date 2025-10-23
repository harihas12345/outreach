from __future__ import annotations

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import requests

from .models import (
    DecisionRequest,
    DecisionResponse,
    HealthResponse,
    IngestRequest,
    Notification,
    QueueRequest,
    EditMessageRequest,
)
from .services import storage
from .orchestrator import ingest_and_queue


load_dotenv()
app = FastAPI(title="Local Progress Notifier", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _same_calendar_day(iso_a: str, iso_b: str) -> bool:
    try:
        from datetime import datetime

        return datetime.fromisoformat(iso_a).date() == datetime.fromisoformat(iso_b).date()
    except Exception:
        return False


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/ingest", response_model=List[Notification])
def ingest(req: IngestRequest) -> List[Notification]:
    # Import lazily so production (without pandas) can still run
    try:
        return ingest_and_queue(req.dataPath, message_all=req.messageAll)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/ingest-upload", response_model=List[Notification])
def ingest_upload(file: UploadFile = File(...), messageAll: bool = Form(False)) -> List[Notification]:
    # Save uploaded file to a temp path and run ingest on it
    try:
        import shutil
        from pathlib import Path
        # Persist uploads into the data/ directory using the original filename so history can accumulate across weeks
        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)
        target_name = file.filename or "upload.xlsx"
        # Sanitize simple cases
        target_name = target_name.replace("..", "_").replace("/", "_")
        dest = data_dir / target_name
        with file.file as src, open(dest, "wb") as dst:
            shutil.copyfileobj(src, dst)
        # Build notifications using the entire data directory to include prior weeks
        return ingest_and_queue(str(data_dir), message_all=bool(messageAll))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/notifications", response_model=List[Notification])
def get_notifications(status: Optional[str] = Query(default=None)) -> List[Notification]:
    notes = storage.load_notifications()
    if status:
        notes = [n for n in notes if n.status == status]
    return notes


@app.post("/decision", response_model=DecisionResponse)
def decision(req: DecisionRequest) -> DecisionResponse:
    if req.decision not in {"approve", "deny"}:
        raise HTTPException(status_code=400, detail="decision must be approve|deny")

    try:
        note = storage.update_notification_status(req.notificationId, "approved" if req.decision == "approve" else "denied")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if req.decision == "deny":
        return DecisionResponse(action="none")

    team_id = os.getenv("SLACK_TEAM_ID", "T0HQD7V5M")
    override_id = os.getenv("FORCE_SLACK_USER_ID", "").strip()
    target_id = override_id or note.slackUserId
    deep_link = f"slack://user?team={team_id}&id={target_id}"

    # If a Slack bot token is configured, send directly via Web API or provide precise Web DM URL
    bot_token = os.getenv("SLACK_BOT_TOKEN", "").strip()
    if bot_token and target_id:
        try:
            headers = {"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json; charset=utf-8"}
            # Open (or get) a DM channel with the target user
            r_open = requests.post(
                "https://slack.com/api/conversations.open",
                headers=headers,
                json={"users": target_id},
                timeout=10,
            )
            data_open = r_open.json()
            if data_open.get("ok"):
                channel_id = data_open["channel"]["id"]
                web_dm_url = f"https://app.slack.com/client/{team_id}/{channel_id}?aci_user={target_id}"
                r_msg = requests.post(
                    "https://slack.com/api/chat.postMessage",
                    headers=headers,
                    json={"channel": channel_id, "text": note.message},
                    timeout=10,
                )
                data_msg = r_msg.json()
                if data_msg.get("ok"):
                    storage.update_notification_status(req.notificationId, "sent")
                    return DecisionResponse(action="sent", message=note.message, webDmUrl=web_dm_url)
                # If sending fails, still return the precise Web DM URL for manual send
                return DecisionResponse(action="open_slack", deepLink=deep_link, message=note.message, webDmUrl=web_dm_url)
        except Exception:
            # Fall back to deeplink if API send fails
            pass

    return DecisionResponse(action="open_slack", deepLink=deep_link, message=note.message)


@app.post("/mark-sent")
def mark_sent(req: DecisionRequest) -> dict:
    try:
        storage.update_notification_status(req.notificationId, "sent")
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/mark-failed")
def mark_failed(req: DecisionRequest) -> dict:
    try:
        storage.update_notification_status(req.notificationId, "failed")
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/edit-message", response_model=Notification)
def edit_message(req: EditMessageRequest) -> Notification:
    # Update message content while preserving other fields
    notes = storage.load_notifications()
    for i, n in enumerate(notes):
        if n.id == req.notificationId:
            updated = Notification(**{**n.model_dump(), "message": req.message})
            notes[i] = updated
            storage.save_notifications(notes)
            return updated
    raise HTTPException(status_code=404, detail="Notification not found")


@app.post("/queue", response_model=Notification)
def queue(req: QueueRequest) -> Notification:
    # Deduplicate: same student/message on same day while pending/approved
    existing = storage.load_notifications()
    now_n = Notification(
        id=storage.create_notification_id(),
        studentId=req.studentId,
        studentName=req.studentName,
        slackUserId=req.slackUserId,
        message=req.message,
    )
    for n in existing:
        if (
            n.studentId == now_n.studentId
            and n.message.strip() == now_n.message.strip()
            and n.status in {"pending", "approved"}
            and _same_calendar_day(n.createdAtIso, now_n.createdAtIso)
        ):
            return n
    storage.add_notification(now_n)
    return now_n

