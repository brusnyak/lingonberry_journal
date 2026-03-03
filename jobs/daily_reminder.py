#!/usr/bin/env python3
"""
Daily Trading Reminder
Sends a notification at 7pm UTC Mon-Fri asking if trades were made today
"""
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram import Bot

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_JOURNAL") or os.getenv("TELEGRAM_JOURAL")
CHAT_ID = int(os.getenv("TELEGRAM_JOURNAL_CHAT", "0") or "0")


async def send_daily_reminder():
    """Send daily trading reminder with Yes/No buttons"""
    if not TELEGRAM_BOT_TOKEN or CHAT_ID <= 0:
        logger.error("Missing TELEGRAM_JOURNAL or TELEGRAM_JOURNAL_CHAT in .env")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    now = datetime.now(timezone.utc)
    day_name = now.strftime("%A")
    
    # Skip weekends
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        logger.info(f"Skipping reminder on {day_name}")
        return
    
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data="daily_reminder:yes"),
            InlineKeyboardButton("❌ No", callback_data="daily_reminder:no")
        ]
    ])
    
    message = (
        f"📊 Daily Trading Check - {day_name}\n\n"
        "Did you take any trades today?"
    )
    
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            reply_markup=keyboard
        )
        logger.info(f"Daily reminder sent successfully to chat {CHAT_ID}")
    except Exception as e:
        logger.error(f"Failed to send daily reminder: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(send_daily_reminder())
