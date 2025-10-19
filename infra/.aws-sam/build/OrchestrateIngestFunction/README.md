Local Slack Notifier MVP

Run locally without AWS or Agent Core. Parses Excel files, decides who to notify, drafts messages, serves a small API, and a Windows notifier approves/denies and auto-sends via Slack.

Setup

1. Python 3.10+
2. Install deps:
   pip install -r requirements.txt
3. Create folders:
   mkdir data
   # put weekly Excel files into ./data (e.g., 2025-10-01.xlsx, 2025-10-08.xlsx)
4. Optional env (in .env or system env):
   - SLACK_TEAM_ID: your Slack team ID for deep links
   - USE_BEDROCK=true to use Bedrock for message drafting (needs AWS creds)

Run API

uvicorn backend.app:app --reload

Trigger ingest

POST http://127.0.0.1:8000/ingest with JSON {"dataPath":"data"}

Run notifier (Windows)

python notifier/windows_notifier.py

Notes

- Excel columns required: student_id, student_name, slack_user_id. Any other numeric columns are treated as metrics; optional last_active column (ISO). 
- Dedupe: skips same student/message on same day.
- Approve opens Slack DM, auto-pastes message, and presses Enter.


