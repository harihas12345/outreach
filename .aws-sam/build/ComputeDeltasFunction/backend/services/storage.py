from __future__ import annotations

import json
from pathlib import Path
from typing import List
from uuid import uuid4

from ..models import Notification


DB_DIR = Path("db")
DB_FILE = DB_DIR / "notifications.json"


def _ensure_db() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    if not DB_FILE.exists():
        DB_FILE.write_text(json.dumps({"notifications": []}, indent=2))


def load_notifications() -> List[Notification]:
    _ensure_db()
    data = json.loads(DB_FILE.read_text())
    return [Notification(**n) for n in data.get("notifications", [])]


def save_notifications(notifications: List[Notification]) -> None:
    _ensure_db()
    data = {"notifications": [n.model_dump() for n in notifications]}
    DB_FILE.write_text(json.dumps(data, indent=2))


def add_notification(n: Notification) -> Notification:
    notifications = load_notifications()
    notifications.append(n)
    save_notifications(notifications)
    return n


def update_notification_status(notification_id: str, new_status: str) -> Notification:
    notifications = load_notifications()
    updated: Notification | None = None
    for i, n in enumerate(notifications):
        if n.id == notification_id:
            updated = Notification(**{**n.model_dump(), "status": new_status})
            notifications[i] = updated
            break
    if updated is None:
        raise ValueError(f"Notification {notification_id} not found")
    save_notifications(notifications)
    return updated


def create_notification_id() -> str:
    return str(uuid4())

