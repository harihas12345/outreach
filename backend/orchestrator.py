from __future__ import annotations

from typing import Dict, List

from .models import ConversationTurn, Notification, QueueRequest, StudentRecord
from .services import storage
from .services import rules as rules_svc
from .services import messages as messages_svc
from .services import excel_parser
from .services import dynamo


def _last_n_weeks(per_week: Dict[str, List[StudentRecord]], n: int) -> Dict[str, List[StudentRecord]]:
    weeks = sorted(per_week.keys())
    if n <= 0 or n >= len(weeks):
        return per_week
    subset = {w: per_week[w] for w in weeks[-n:]}
    return subset


def _attach_history(latest_by_student: Dict[str, StudentRecord], per_week: Dict[str, List[StudentRecord]]) -> None:
    # Build metrics history for last 3 weeks for each student
    weeks = sorted(per_week.keys())[-3:]
    # Map week -> studentId -> record
    map_by_week: Dict[str, Dict[str, StudentRecord]] = {}
    for w in weeks:
        map_by_week[w] = {r.studentId: r for r in per_week.get(w, [])}
    for student_id, rec in latest_by_student.items():
        history: Dict[str, List[Dict[str, float | str]]] = {}
        for w in weeks:
            r = map_by_week.get(w, {}).get(student_id)
            if not r:
                continue
            for m, v in r.metrics.items():
                history.setdefault(m, []).append({"week": w, "value": float(v)})
        if history:
            rec.metricsHistory = history
        # Attach recent conversations from DynamoDB if available
        rec.recentConversations = dynamo.get_recent_conversations(student_id)


def ingest_and_queue(data_path: str | None, message_all: bool = False) -> List[Notification]:
    # Parse all available weeks
    latest_by_student, per_week = excel_parser.load_weekly_records(data_path)

    if not per_week:
        return []

    # Restrict to last 3 weeks: previous 2 + current
    per_week_3 = _last_n_weeks(per_week, 3)

    # Compute deltas across consecutive weeks and decide flags (extend rules for trends)
    deltas_by_student = rules_svc.compute_deltas(per_week_3)
    trend_flags = rules_svc.decide_flags(latest_by_student, deltas_by_student)

    # Attach metrics history and recent conversation context to records for message drafting
    _attach_history(latest_by_student, per_week_3)

    queued: List[Notification] = []
    for student_id, rec in latest_by_student.items():
        # Only students with Slack IDs are eligible
        if not rec.slackUserId or str(rec.slackUserId).strip() == "":
            continue
        flags = trend_flags.get(student_id, [])
        if not flags and not message_all:
            continue
        # Draft message using LLM/template taking into account history
        msg = messages_svc.draft_message(rec, flags)

        # Persist conversation turn for context next time (optional debug)
        try:
            turn = ConversationTurn(
                studentId=rec.studentId,
                week=rec.week,
                context={k: float(v) for k, v in (rec.metrics or {}).items()},
                flags=flags,
                draftedMessage=msg,
            )
            dynamo.put_conversation_turn(turn.model_dump())
        except Exception as e:
            # keep queueing even if history store fails
            if os.getenv("DDB_DEBUG", "").lower() in {"1", "true", "yes"}:
                try:
                    print(f"[DDB] Orchestrator put turn failed: {e}")
                except Exception:
                    pass

        # Queue notification (dedup handled by API)
        note = storage.add_notification(
            Notification(
                id=storage.create_notification_id(),
                studentId=rec.studentId,
                studentName=rec.studentName,
                slackUserId=rec.slackUserId,
                message=msg,
            )
        )
        queued.append(note)

    return queued


