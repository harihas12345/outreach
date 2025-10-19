from __future__ import annotations

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from dotenv import load_dotenv

from .models import (
    DecisionRequest,
    DecisionResponse,
    HealthResponse,
    IngestRequest,
    Notification,
    QueueRequest,
)
from .orchestrator import ingest_and_queue
from .services import storage


load_dotenv()
app = FastAPI(title="Local Progress Notifier", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/ingest", response_model=List[Notification])
def ingest(req: IngestRequest) -> List[Notification]:
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
    deep_link = f"slack://user?team={team_id}&id={note.slackUserId}"
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


@app.post("/queue", response_model=Notification)
def queue(req: QueueRequest) -> Notification:
    n = Notification(
        id=storage.create_notification_id(),
        studentId=req.studentId,
        studentName=req.studentName,
        slackUserId=req.slackUserId,
        message=req.message,
    )
    storage.add_notification(n)
    return n

