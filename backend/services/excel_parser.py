from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from ..models import StudentRecord


REQUIRED_COLUMNS = {"student_id", "student_name", "slack_user_id"}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {c: c.strip().lower().replace(" ", "_") for c in df.columns}
    df = df.rename(columns=mapping)
    return df


def _extract_metrics(df: pd.DataFrame) -> pd.DataFrame:
    # Treat any numeric columns other than identifiers as metrics
    metric_cols = [
        c
        for c in df.columns
        if c not in ["student_id", "student_name", "slack_user_id", "last_active"]
    ]
    return df[["student_id", "student_name", "slack_user_id", "last_active", *metric_cols]]


def load_weekly_records(data_dir: str | None) -> Tuple[Dict[str, StudentRecord], Dict[str, List[StudentRecord]]]:
    base = Path(data_dir or "data")
    # Accept either a directory (containing weekly .xlsx) or a single .xlsx file
    files: List[Path]
    if base.is_file() and base.suffix.lower() == ".xlsx":
        files = [base]
    else:
        base.mkdir(parents=True, exist_ok=True)
        files = sorted(base.glob("*.xlsx"))
    if not files:
        return {}, {}

    per_week: Dict[str, List[StudentRecord]] = {}
    for f in files:
        week = f.stem  # use filename (without extension) as the week key
        df = pd.read_excel(f)
        df = _normalize_columns(df)
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"File {f.name} missing columns: {sorted(missing)}")
        if "last_active" not in df.columns:
            df["last_active"] = pd.NaT
        df = _extract_metrics(df)
        records: List[StudentRecord] = []
        for _, row in df.iterrows():
            metrics = {
                k: float(row[k])
                for k in df.columns
                if k not in ["student_id", "student_name", "slack_user_id", "last_active"]
                and pd.notna(row[k])
            }
            rec = StudentRecord(
                studentId=str(row["student_id"]),
                studentName=str(row["student_name"]),
                slackUserId=str(row["slack_user_id"]),
                week=week,
                metrics=metrics,
                lastActiveIso=str(row["last_active"]) if pd.notna(row["last_active"]) else None,
            )
            records.append(rec)
        per_week[week] = records

    # latest per-student
    latest_by_student: Dict[str, StudentRecord] = {}
    for week in sorted(per_week.keys()):
        for rec in per_week[week]:
            latest_by_student[rec.studentId] = rec

    return latest_by_student, per_week


