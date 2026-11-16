#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Send report.md to the «مخزن عمومی آرفیس» Telegram topic via the bot API.

The bot token comes from the TELEGRAM_BOT_TOKEN repository secret.
Chat id and topic (thread) id below are public routing ids, not credentials.
If the token is not set, this step skips quietly so data collection still works.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

CHAT_ID = "-1003993019712"  # forum group «دست راستم»
THREAD_ID = 74              # topic «مخزن عمومی آرفیس»
LIMIT = 3900                # Telegram message limit is 4096; keep a margin


def send(token, text):
    data = json.dumps({
        "chat_id": CHAT_ID,
        "message_thread_id": THREAD_ID,
        "text": text,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def chunks(text):
    out, cur = [], ""
    for line in text.splitlines():
        if len(cur) + len(line) + 1 > LIMIT:
            out.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        out.append(cur)
    return out


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("TELEGRAM_BOT_TOKEN not set; skipping Telegram send")
        return
    text = Path("report.md").read_text(encoding="utf-8")
    for c in chunks(text):
        res = send(token, c)
        if not res.get("ok"):
            print("telegram send failed:", res)
            sys.exit(1)
    print("report sent to Telegram topic")


if __name__ == "__main__":
    main()
