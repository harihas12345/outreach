from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from .models import Notification
from .services import excel_parser, rules, messages, storage


def _is_same_day(iso_a: str, iso_b: str) -> bool:
    try:
        a = datetime.fromisoformat(iso_a).date()
        b = datetime.fromisoformat(iso_b).date()
        return a == b
    except Exception:
        return False


def _dedupe_existing(existing: List[Notification], candidate: Notification) -> bool:
    for n in existing:
        if (
            n.studentId == candidate.studentId
            and _is_same_day(n.createdAtIso, candidate.createdAtIso)
            and n.status in {"pending", "approved"}
        ):
            if n.message.strip() == candidate.message.strip():
                return True
    return False


def ingest_and_queue(data_dir: str | None) -> List[Notification]:
    latest_by_student, per_week = excel_parser.load_weekly_records(data_dir)
    if not latest_by_student:
        return []

    deltas_by_student = rules.compute_deltas(per_week)
    flags_by_student = rules.decide_flags(latest_by_student, deltas_by_student)

    queued: List[Notification] = []
    existing = storage.load_notifications()

    for student_id, flags in flags_by_student.items():
        student = latest_by_student[student_id]
        msg = messages.draft_message(student, flags)
        n = Notification(
            id=storage.create_notification_id(),
            studentId=student.studentId,
            studentName=student.studentName,
            slackUserId=student.slackUserId,
            message=msg,
        )
        if _dedupe_existing(existing, n):
            continue
        storage.add_notification(n)
        queued.append(n)
        existing.append(n)

    return queued

