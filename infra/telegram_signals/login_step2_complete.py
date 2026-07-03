"""
One-time Telethon login, step 2 of 2: complete login with the code you received.

Usage:
    python infra/telegram_signals/login_step2_complete.py <CODE> [2FA_PASSWORD]

Writes the resulting session string directly into .env (TELETHON_SESSION_STRING)
-- it is never printed to stdout. The session string is bearer-equivalent to
your Telegram login (no 2FA needed to reuse it), so it must not pass through
chat/terminal output that gets logged or shared. Deletes the temp login state
either way.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
TMP_STATE = ROOT / "infra" / "telegram_signals" / ".login_state.json"
ENV_FILE = ROOT / ".env"


def _write_session_to_env(session_string: str) -> None:
    text = ENV_FILE.read_text()
    pattern = re.compile(r"^TELETHON_SESSION_STRING=.*$", re.MULTILINE)
    replacement = f"TELETHON_SESSION_STRING={session_string}"
    if pattern.search(text):
        text = pattern.sub(replacement, text)
    else:
        text += f"\n{replacement}\n"
    ENV_FILE.write_text(text)

API_ID = int(os.environ["TELETHON_API_ID"])
API_HASH = os.environ["TELETHON_API_HASH"]
PHONE = os.environ["TELETHON_PHONE"]


async def main(code: str, password: str | None) -> None:
    state = json.loads(TMP_STATE.read_text())
    client = TelegramClient(StringSession(state["session_string"]), API_ID, API_HASH)
    await client.connect()
    try:
        await client.sign_in(PHONE, code, phone_code_hash=state["phone_code_hash"])
    except SessionPasswordNeededError:
        if not password:
            print("Account has 2FA enabled. Re-run with the password as the 2nd argument.")
            await client.disconnect()
            return
        await client.sign_in(password=password)

    me = await client.get_me()
    _write_session_to_env(client.session.save())
    print(f"Logged in as: {me.first_name} (@{me.username})")
    print("Session string written to .env (not printed).")
    await client.disconnect()
    TMP_STATE.unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python login_step2_complete.py <CODE> [2FA_PASSWORD]")
        sys.exit(1)
    code_arg = sys.argv[1]
    pw_arg = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(main(code_arg, pw_arg))
