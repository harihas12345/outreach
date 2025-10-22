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
    # Last 3 weeks metrics history: metric -> list of {week, value}
    metricsHistory: Optional[Dict[str, List[Dict[str, float | str]]]] = None
    # Recent conversation snippets for context (most recent first)
    recentConversations: Optional[List[Dict[str, str]]] = None


class Delta(BaseModel):
    studentId: str
    metric: str
    change: float
    previous: float
    current: float


class Notification(BaseModel):
    id: str
    studentId: str
    studentName: str
    slackUserId: str
    message: str
    createdAtIso: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "pending"  # pending | approved | denied | sent | failed


class IngestRequest(BaseModel):
    dataPath: Optional[str] = None
    messageAll: bool = False


class HealthResponse(BaseModel):
    status: str


class QueueRequest(BaseModel):
    studentId: str
    studentName: str
    slackUserId: str
    message: str


class DecisionRequest(BaseModel):
    notificationId: str
    decision: str  # approve | deny


class DecisionResponse(BaseModel):
    action: str  # open_slack | sent | none
    deepLink: Optional[str] = None
    message: Optional[str] = None
    webDmUrl: Optional[str] = None


class EditMessageRequest(BaseModel):
    notificationId: str
    message: str


class ConversationTurn(BaseModel):
    studentId: str
    week: Optional[str] = None
    timestampIso: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    context: Dict[str, float] = Field(default_factory=dict)
    flags: List[str] = Field(default_factory=list)
    draftedMessage: Optional[str] = None
    sentMessage: Optional[str] = None


