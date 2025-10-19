from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class StudentRecord(BaseModel):
    studentId: str
    studentName: str
    slackUserId: str
    week: str
    metrics: Dict[str, float] = Field(default_factory=dict)
    lastActiveIso: Optional[str] = None


class Delta(BaseModel):
    studentId: str
    metric: str
    change: float
    previous: Optional[float] = None
    current: Optional[float] = None


class Notification(BaseModel):
    id: str
    studentId: str
    studentName: str
    slackUserId: str
    message: str
    createdAtIso: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "pending"  # pending | approved | denied | sent | failed


class DecisionRequest(BaseModel):
    notificationId: str
    decision: str  # approve | deny


class DecisionResponse(BaseModel):
    action: str  # open_slack | none
    deepLink: Optional[str] = None
    message: Optional[str] = None


class IngestRequest(BaseModel):
    dataPath: Optional[str] = None  # directory path with .xlsx files


class HealthResponse(BaseModel):
    status: str


class QueueRequest(BaseModel):
    studentId: str
    studentName: str
    slackUserId: str
    message: str

