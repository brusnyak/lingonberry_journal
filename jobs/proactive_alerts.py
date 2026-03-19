#!/usr/bin/env python3
"""
Proactive Alerts Job
Monitors account for:
- 50% Daily Loss Limit breach
- 4-day Inactivity
"""
import os
import sys
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from bot import journal_db
from telegram import Bot

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("proactive_alerts")

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_JOURNAL") or os.getenv("TELEGRAM_JOURAL")
CHAT_ID = int(os.getenv("TELEGRAM_JOURNAL_CHAT", "0") or "0")
CACHE_FILE = os.path.join("data", "cache", "alerts_sent.json")

def load_cache() -> Dict[str, Any]:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache: Dict[str, Any]):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

async def send_alert(message: str):
    if not TELEGRAM_BOT_TOKEN or CHAT_ID <= 0:
        logger.error("Telegram credentials missing")
        return
    
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message)
        logger.info(f"Alert sent: {message[:50]}...")
    except Exception as e:
        logger.error(f"Failed to send telegram message: {e}")

async def check_alerts():
    logger.info("Checking for proactive alerts...")
    accounts = journal_db.get_accounts()
    cache = load_cache()
    today = datetime.now(timezone.utc).date().isoformat()
    
    if "daily_loss" not in cache: cache["daily_loss"] = {}
    if "inactivity" not in cache: cache["inactivity"] = {}

    for account in accounts:
        account_id = account["id"]
        account_name = account["name"]
        
        # 1. Check Daily Loss Limit (50%)
        trades = journal_db.get_all_trades(account_id=account_id)
        loss_state = journal_db.get_daily_loss_state(account, trades)
        current = loss_state.get("current")
        
        if current:
            loss_pct = 0
            if current["daily_loss_limit"] > 0:
                loss_pct = (current["worst_drawdown_usd"] / current["daily_loss_limit"]) * 100
            
            if loss_pct >= 50:
                cache_key = f"{account_id}_{today}"
                if cache["daily_loss"].get(cache_key) != "SENT":
                    alert_msg = (
                        f"⚠️ RISK ALERT: {account_name}\n"
                        f"You have reached {loss_pct:.1f}% of your daily loss limit!\n"
                        f"Current drawdown: ${current['worst_drawdown_usd']:.2f}\n"
                        f"Limit: ${current['daily_loss_limit']:.2f}\n"
                        f"Remaining: ${current['remaining_usd']:.2f}"
                    )
                    await send_alert(alert_msg)
                    cache["daily_loss"][cache_key] = "SENT"

        # 2. Check Inactivity (> 4 days)
        last_trade = trades[0] if trades else None
        if last_trade:
            # Use ts_open as string manually if _parse_timestamp not available here
            ts_str = last_trade.get("ts_open") or last_trade.get("created_at")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                wait_days = (datetime.now(timezone.utc) - ts).days
                if wait_days >= 4:
                    cache_key = f"{account_id}"
                    last_alert_date = cache["inactivity"].get(cache_key)
                    if last_alert_date != today:
                        alert_msg = (
                            f"🚷 INACTIVITY ALERT: {account_name}\n"
                            f"You haven't logged a trade in {wait_days} days. "
                            "Consistency is key! Is everything okay?"
                        )
                        await send_alert(alert_msg)
                        cache["inactivity"][cache_key] = today
            except:
                logger.error(f"Failed to parse timestamp for account {account_id}")

    save_cache(cache)

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_alerts())
