from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from ..models import Delta, StudentRecord


def compute_deltas(per_week: Dict[str, List[StudentRecord]]) -> Dict[str, List[Delta]]:
    # For each student, compute week-over-week changes for numeric metrics
    deltas_by_student: Dict[str, List[Delta]] = {}
    weeks = sorted(per_week.keys())
    for i in range(1, len(weeks)):
        prev_week = weeks[i - 1]
        curr_week = weeks[i]
        prev_map = {r.studentId: r for r in per_week[prev_week]}
        curr_map = {r.studentId: r for r in per_week[curr_week]}
        for student_id, curr in curr_map.items():
            prev = prev_map.get(student_id)
            if not prev:
                continue
            for metric, curr_val in curr.metrics.items():
                prev_val = prev.metrics.get(metric)
                if prev_val is None:
                    continue
                change = float(curr_val) - float(prev_val)
                deltas_by_student.setdefault(student_id, []).append(
                    Delta(
                        studentId=student_id,
                        metric=metric,
                        change=change,
                        previous=float(prev_val),
                        current=float(curr_val),
                    )
                )
    return deltas_by_student


def decide_flags(
    latest_by_student: Dict[str, StudentRecord],
    deltas_by_student: Dict[str, List[Delta]],
) -> Dict[str, List[str]]:
    # Produce simple human-readable flags per student
    flags: Dict[str, List[str]] = {}
    now = datetime.utcnow()
    for student_id, rec in latest_by_student.items():
        student_flags: List[str] = []

        # Inactivity rule
        if rec.lastActiveIso:
            try:
                last = datetime.fromisoformat(rec.lastActiveIso)
                if now - last > timedelta(days=7):
                    student_flags.append("inactivity_over_7_days")
            except Exception:
                pass
        else:
            student_flags.append("no_last_active_recorded")

        # Negative momentum rule: any metric drop >= 5
        for d in deltas_by_student.get(student_id, []):
            if d.change <= -5.0:
                student_flags.append(f"drop_{d.metric}_{d.previous}_to_{d.current}")

        if student_flags:
            flags[student_id] = student_flags

    return flags

