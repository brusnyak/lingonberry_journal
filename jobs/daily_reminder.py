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
    """Send daily trading reminder with performance summary"""
    if not TELEGRAM_BOT_TOKEN or CHAT_ID <= 0:
        logger.error("Missing TELEGRAM_JOURNAL or TELEGRAM_JOURNAL_CHAT in .env")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    from bot import journal_db
    account_id = int(os.getenv("JOURNAL_ACCOUNT_ID", "1"))
    account = journal_db.get_account(account_id)
    stats = journal_db.get_stats(account_id=account_id)
    
    now = datetime.now(timezone.utc)
    day_name = now.strftime("%A")
    
    # Skip weekends
    if now.weekday() >= 5:
        logger.info(f"Skipping reminder on {day_name}")
        return

    # Check if trades were taken today
    trades_today = stats.get("total_trades_today", 0) # I need to check if get_stats has this
    # Actually, get_stats has 'daily_pnl'.
    
    from bot.journal_db import get_all_trades, get_daily_loss_state
    all_trades = get_all_trades(account_id=account_id)
    today_iso = now.date().isoformat()
    today_trades = [t for t in all_trades if (t.get("ts_open") or "").startswith(today_iso)]
    
    if not today_trades:
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
    else:
        loss_state = get_daily_loss_state(account, all_trades)
        current = loss_state.get("current", {})
        
        symbols = ", ".join(list(set([t["symbol"] for t in today_trades])))
        pnl_usd = sum(float(t.get("pnl_usd") or 0) for t in today_trades)
        pnl_pct = (pnl_usd / float(account["initial_balance"])) * 100
        
        # Risk calculation (sum of SL risk if SL exists)
        total_risk_usd = 0
        for t in today_trades:
            entry = float(t.get("entry_price") or 0)
            sl = float(t.get("sl_price") or 0)
            size = float(t.get("position_size") or 0)
            if entry > 0 and sl > 0:
                risk = abs(entry - sl) / entry * size
                total_risk_usd += risk
        
        risk_pct = (total_risk_usd / float(account["initial_balance"])) * 100
        remaining_goal = float(account.get("profit_target_pct") or 0) - stats.get("growth_pct", 0)

        message = (
            f"🏁 EOD PERFORMANCE REPORT - {day_name}\n\n"
            f"💰 Today's PnL: ${pnl_usd:+.2f} ({pnl_pct:+.2f}%)\n"
            f"📊 Trades: {len(today_trades)} ({symbols})\n"
            f"📉 Daily Loss: ${current.get('worst_drawdown_usd', 0):.2f} / ${current.get('daily_loss_limit', 0):.2f}\n"
            f"🔥 Risk Exposure: {risk_pct:.2f}% of capital\n"
            f"🎯 Goal Remaining: {max(0, remaining_goal):.2f}%\n"
            f"💎 Max Drawdown: {stats.get('max_drawdown_pct', 0):.2f}%\n\n"
            "Great work today! Keep the discipline."
        )
        keyboard = None

    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            reply_markup=keyboard,
            parse_mode=None
        )
        logger.info(f"Daily report/reminder sent successfully to chat {CHAT_ID}")
    except Exception as e:
        logger.error(f"Failed to send daily report: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(send_daily_reminder())
