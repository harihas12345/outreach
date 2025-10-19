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
from tkinter import messagebox


API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "15"))
TYPE_DELAY_SECONDS = float(os.getenv("TYPE_DELAY_SECONDS", "2.0"))


def fetch_pending() -> List[dict]:
    try:
        r = requests.get(f"{API_BASE}/notifications", params={"status": "pending"}, timeout=10)
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


def open_and_type(deep_link: str, message: str, notification_id: str) -> None:
    try:
        pyperclip.copy(message)
        webbrowser.open(deep_link)
        time.sleep(TYPE_DELAY_SECONDS)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.2)
        pyautogui.press("enter")
        mark_sent(notification_id)
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
        self.build_header()
        threading.Thread(target=self.poll_loop, daemon=True).start()

    def build_header(self) -> None:
        hdr = tk.Label(self.list_frame, text="Pending Notifications", font=("Segoe UI", 12, "bold"))
        hdr.pack(pady=6)

    def refresh_list(self, notes: List[dict]) -> None:
        for child in list(self.list_frame.pack_slaves())[1:]:
            child.destroy()
        for n in notes:
            frame = tk.Frame(self.list_frame, relief=tk.GROOVE, borderwidth=1)
            frame.pack(fill=tk.X, padx=8, pady=6)
            title = tk.Label(frame, text=f"{n['studentName']} ({n['slackUserId']})", font=("Segoe UI", 10, "bold"))
            title.pack(anchor="w", padx=6, pady=2)
            msg = tk.Label(frame, text=n["message"], wraplength=480, justify=tk.LEFT)
            msg.pack(anchor="w", padx=6)
            btns = tk.Frame(frame)
            btns.pack(anchor="e", pady=4)
            approve = tk.Button(btns, text="Approve and Send", command=partial(self.on_decide, n["id"], True))
            deny = tk.Button(btns, text="Deny", command=partial(self.on_decide, n["id"], False))
            approve.pack(side=tk.LEFT, padx=4)
            deny.pack(side=tk.LEFT, padx=4)

    def on_decide(self, notification_id: str, approve: bool) -> None:
        try:
            res = post_decision(notification_id, "approve" if approve else "deny")
            if not approve:
                messagebox.showinfo("Denied", "Notification denied.")
                return
            if res.get("action") == "open_slack":
                deep = res.get("deepLink", "")
                msg = res.get("message", "")
                threading.Thread(target=open_and_type, args=(deep, msg, notification_id), daemon=True).start()
                messagebox.showinfo("Sending", "Opening Slack and sending message...")
            else:
                messagebox.showwarning("No Action", "No action returned from server.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def poll_loop(self) -> None:
        while True:
            notes = fetch_pending()
            self.root.after(0, lambda n=notes: self.refresh_list(n))
            time.sleep(POLL_SECONDS)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    NotifierApp().run()

