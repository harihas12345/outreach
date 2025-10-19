from __future__ import annotations

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

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
        from .orchestrator import ingest_and_queue  # type: ignore
    except Exception:
        raise HTTPException(status_code=503, detail="ingest not available in this deployment")
    try:
        return ingest_and_queue(req.dataPath)
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

    team_id = os.getenv("SLACK_TEAM_ID", "")
    override_id = os.getenv("FORCE_SLACK_USER_ID", "").strip()
    target_id = override_id or note.slackUserId
    deep_link = f"slack://user?team={team_id}&id={target_id}"
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

