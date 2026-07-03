"""
One-time Telethon login, step 1 of 2: request a login code.

Read-only session — we never post to the channel, only read its history.
Run once. Sends a login code to your Telegram app (or SMS). Saves
phone_code_hash + a temp session file so step 2 can complete the login.

Usage:
    python infra/telegram_signals/login_step1_request_code.py
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
TMP_STATE = ROOT / "infra" / "telegram_signals" / ".login_state.json"

API_ID = int(os.environ["TELETHON_API_ID"])
API_HASH = os.environ["TELETHON_API_HASH"]
PHONE = os.environ["TELETHON_PHONE"]


async def main() -> None:
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    sent = await client.send_code_request(PHONE)
    TMP_STATE.write_text(json.dumps({
        "session_string": client.session.save(),
        "phone_code_hash": sent.phone_code_hash,
    }))
    print(f"Code sent to {PHONE}. Check your Telegram app (or SMS).")
    print("Run login_step2_complete.py <CODE> next.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
