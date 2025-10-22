from __future__ import annotations

import os
import threading
import time
import webbrowser
from functools import partial
from typing import Any, List

import pyautogui
import pyperclip
import requests
import tkinter as tk
from urllib.parse import urlparse, parse_qs
from typing import Optional


API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "15"))
TYPE_DELAY_SECONDS = float(os.getenv("TYPE_DELAY_SECONDS", "10.0"))
SEND_COMBO = os.getenv("SLACK_SEND_COMBO", "auto").lower()  # auto | enter | ctrl-enter
NEXT_AFTER_SEND_USER_ID = os.getenv("NEXT_FORCE_SLACK_USER_ID", "U09HM80SE8M").strip()
NEXT_AFTER_SEND_MESSAGE = os.getenv(
    "NEXT_AFTER_SEND_MESSAGE",
    "Hi there! Quick follow-up to ensure everything is on track.",
)

# Internal send tracking to avoid infinite re-queueing
FOLLOWUP_QUEUED = False
LAST_SENT_USER_ID: Optional[str] = None
AUTO_SEND_APPROVED = os.getenv("AUTO_SEND_APPROVED", "true").lower() in {"1", "true", "yes"}
PROCESSED_APPROVED: set[str] = set()


def fetch_pending() -> List[dict]:
    try:
        r = requests.get(f"{API_BASE}/notifications", params={"status": "pending"}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def fetch_approved() -> List[dict]:
    try:
        r = requests.get(f"{API_BASE}/notifications", params={"status": "approved"}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def post_decision(notification_id: str, decision: str) -> dict:
    r = requests.post(f"{API_BASE}/decision", json={"notificationId": notification_id, "decision": decision}, timeout=10)
    r.raise_for_status()
    return r.json()


def mark_sent(notification_id: str) -> None:
    try:
        requests.post(f"{API_BASE}/mark-sent", json={"notificationId": notification_id, "decision": "approve"}, timeout=10)
    except Exception:
        pass


def mark_failed(notification_id: str) -> None:
    try:
        requests.post(f"{API_BASE}/mark-failed", json={"notificationId": notification_id, "decision": "approve"}, timeout=10)
    except Exception:
        pass


def queue_followup(user_id: str, message: str) -> None:
    try:
        payload = {
            "studentId": user_id,
            "studentName": "Follow-up",
            "slackUserId": user_id,
            "message": message,
        }
        requests.post(f"{API_BASE}/queue", json=payload, timeout=10)
    except Exception:
        pass


def open_and_type(deep_link: str, message: str, notification_id: str, override_user_id: Optional[str] = None) -> None:
    try:
        # Extract target user ID from deep link first (allow override)
        try:
            qs = parse_qs(urlparse(deep_link).query)
            user_id = (qs.get("id") or [None])[0]
        except Exception:
            user_id = None
        if override_user_id:
            user_id = override_user_id

        # Open Slack
        webbrowser.open(deep_link)
        time.sleep(TYPE_DELAY_SECONDS)
        if user_id:
            # Open new message composer, paste full Slack user ID, then Enter to resolve
            pyautogui.hotkey("ctrl", "n")
            time.sleep(0.8)
            pyperclip.copy(user_id)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.3)
            pyautogui.press("enter")  # resolve to DM
            time.sleep(0.6)
            pyautogui.press("tab")    # move focus from To to message box
            time.sleep(0.3)

        # Paste the prepared message and send
        pyperclip.copy(message)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.2)
        # Send
        if SEND_COMBO == "ctrl-enter":
            pyautogui.hotkey("ctrl", "enter")
        elif SEND_COMBO == "enter":
            pyautogui.press("enter")
        else:  # auto
            # Try Ctrl+Enter, then Enter as fallback
            pyautogui.hotkey("ctrl", "enter")
            time.sleep(0.25)
            pyautogui.press("enter")
        mark_sent(notification_id)
        # Automatically queue next follow-up item once, and only if distinct target
        global FOLLOWUP_QUEUED, LAST_SENT_USER_ID
        LAST_SENT_USER_ID = user_id
        if NEXT_AFTER_SEND_USER_ID and not FOLLOWUP_QUEUED and NEXT_AFTER_SEND_USER_ID != (LAST_SENT_USER_ID or ""):
            queue_followup(NEXT_AFTER_SEND_USER_ID, NEXT_AFTER_SEND_MESSAGE)
            FOLLOWUP_QUEUED = True
    except Exception:
        mark_failed(notification_id)


class NotifierApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Slack Approvals")
        self.root.geometry("520x300")
        self.root.attributes("-topmost", True)
        self.list_frame = tk.Frame(self.root)
        self.list_frame.pack(fill=tk.BOTH, expand=True)
        self.items: List[str] = []
        self.hidden_ids = set()
        self.build_header()
        threading.Thread(target=self.poll_loop, daemon=True).start()

    def build_header(self) -> None:
        self.header = tk.Label(self.list_frame, text="Pending Notifications", font=("Segoe UI", 12, "bold"))
        self.header.pack(pady=6)

    def refresh_list(self, notes: List[dict]) -> None:
        # Clear dynamic rows but keep the header
        for child in self.list_frame.winfo_children():
            if getattr(self, "header", None) is not None and child is self.header:
                continue
            child.destroy()
        # Filter out hidden/in-flight notifications locally so the user doesn't double-approve
        notes = [n for n in notes if n.get("id") not in self.hidden_ids]
        if not notes:
            empty = tk.Label(self.list_frame, text="No pending items.", fg="#666")
            empty.pack(pady=8)
            return
        for n in notes:
            frame = tk.Frame(self.list_frame, relief=tk.GROOVE, borderwidth=1)
            frame.pack(fill=tk.X, padx=8, pady=6)
            title = tk.Label(frame, text=f"{n['studentName']} ({n['slackUserId']})", font=("Segoe UI", 10, "bold"))
            title.pack(anchor="w", padx=6, pady=2)
            msg = tk.Label(frame, text=n["message"], wraplength=480, justify=tk.LEFT)
            msg.pack(anchor="w", padx=6)
            btns = tk.Frame(frame)
            btns.pack(anchor="e", pady=4)
            approve = tk.Button(btns, text="Approve and Send", command=partial(self.on_decide, n["id"], True, n.get("slackUserId")))
            deny = tk.Button(btns, text="Deny", command=partial(self.on_decide, n["id"], False))
            approve.pack(side=tk.LEFT, padx=4)
            deny.pack(side=tk.LEFT, padx=4)

    def on_decide(self, notification_id: str, approve: bool, target_user_id: Optional[str] = None) -> None:
        try:
            res = post_decision(notification_id, "approve" if approve else "deny")
            if not approve:
                return
            if res.get("action") == "open_slack":
                deep = res.get("deepLink", "")
                msg = res.get("message", "")
                # compute target user id (prefer per-item slackUserId, then FORCE, then deep link)
                target_id = (target_user_id or os.getenv("FORCE_SLACK_USER_ID", "").strip())
                if not target_id:
                    try:
                        target_id = (parse_qs(urlparse(deep).query).get("id") or [""])[0]
                    except Exception:
                        target_id = ""
                # hide item immediately to avoid double-approval
                self.hidden_ids.add(notification_id)
                self.refresh_list(fetch_pending())
                threading.Thread(target=open_and_type, args=(deep, msg, notification_id, target_id), daemon=True).start()
            else:
                pass
        except Exception as e:
            pass

    def poll_loop(self) -> None:
        while True:
            notes = fetch_pending()
            self.root.after(0, lambda n=notes: self.refresh_list(n))
            # Background: auto-send items that were approved outside this app (e.g., via web UI)
            if AUTO_SEND_APPROVED:
                try:
                    approved = fetch_approved()
                    for n in approved:
                        nid = n.get("id")
                        if not nid or nid in PROCESSED_APPROVED or nid in self.hidden_ids:
                            continue
                        # Reuse decision endpoint to obtain deep link and message
                        try:
                            res = post_decision(nid, "approve")
                            if res.get("action") == "open_slack":
                                deep = res.get("deepLink", "")
                                msg = res.get("message", n.get("message", ""))
                                target_id = n.get("slackUserId") or os.getenv("FORCE_SLACK_USER_ID", "").strip()
                                PROCESSED_APPROVED.add(nid)
                                threading.Thread(target=open_and_type, args=(deep, msg, nid, target_id), daemon=True).start()
                        except Exception:
                            PROCESSED_APPROVED.add(nid)
                            continue
                except Exception:
                    pass
            time.sleep(POLL_SECONDS)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    NotifierApp().run()

