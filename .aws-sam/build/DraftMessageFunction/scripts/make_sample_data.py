import os
import datetime as dt

import pandas as pd


def main() -> None:
    os.makedirs("data", exist_ok=True)
    now = dt.datetime.utcnow()
    fmt = lambda d: d.isoformat()

    df1 = pd.DataFrame(
        [
            {
                "student_id": "A1",
                "student_name": "Alice",
                "slack_user_id": "UAAAA1",
                "last_active": fmt(now - dt.timedelta(days=10)),
                "quiz_score": 80,
                "assignments_completed": 3,
            },
            {
                "student_id": "B2",
                "student_name": "Bob",
                "slack_user_id": "UBBBB2",
                "last_active": fmt(now - dt.timedelta(days=2)),
                "quiz_score": 92,
                "assignments_completed": 4,
            },
        ]
    )
    df1.to_excel("data/2025-10-01.xlsx", index=False)

    df2 = pd.DataFrame(
        [
            {
                "student_id": "A1",
                "student_name": "Alice",
                "slack_user_id": "UAAAA1",
                "last_active": fmt(now - dt.timedelta(days=9)),
                "quiz_score": 72,
                "assignments_completed": 3,
            },
            {
                "student_id": "B2",
                "student_name": "Bob",
                "slack_user_id": "UBBBB2",
                "last_active": fmt(now - dt.timedelta(days=1)),
                "quiz_score": 94,
                "assignments_completed": 5,
            },
        ]
    )
    df2.to_excel("data/2025-10-08.xlsx", index=False)


if __name__ == "__main__":
    main()


