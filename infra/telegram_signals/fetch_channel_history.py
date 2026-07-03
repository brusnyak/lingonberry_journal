"""
Stage 0, step 1: pull the FULL message history of the "just trade it" channel
(not just recent posts) -- read-only, no execution, no posting.

Saves every message (text + downloaded chart images) to disk so the vision
parser and backtest can run against the complete population, not a
highlight-reel sample.

Usage:
    python infra/telegram_signals/fetch_channel_history.py
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
OUT_DIR = ROOT / "data" / "telegram_signals" / "just_trade_it"
IMG_DIR = OUT_DIR / "images"
MSG_LOG = OUT_DIR / "messages.jsonl"

API_ID = int(os.environ["TELETHON_API_ID"])
API_HASH = os.environ["TELETHON_API_HASH"]
SESSION_STRING = os.environ["TELETHON_SESSION_STRING"]
CHANNEL_ID = int(os.environ["TELETHON_JUSTTRADEIT_CHANNEL"])


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()

    entity = await client.get_entity(CHANNEL_ID)
    n = 0
    n_images = 0
    with open(MSG_LOG, "w") as f:
        async for msg in client.iter_messages(entity, reverse=True):
            row = {
                "id": msg.id,
                "date": msg.date.isoformat() if msg.date else None,
                "text": msg.raw_text or "",
                "has_image": bool(msg.photo),
                "image_path": None,
            }
            if msg.photo:
                img_path = IMG_DIR / f"{msg.id}.jpg"
                if not img_path.exists():
                    await client.download_media(msg, file=str(img_path))
                row["image_path"] = str(img_path.relative_to(ROOT))
                n_images += 1
            f.write(json.dumps(row) + "\n")
            n += 1
            if n % 200 == 0:
                print(f"...{n} messages ({n_images} images)")

    print(f"Done. {n} messages, {n_images} images. -> {MSG_LOG}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
