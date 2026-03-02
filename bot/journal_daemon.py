#!/usr/bin/env python3
"""
Trading Journal Telegram Bot
Handles /journal and /mini commands with WebApp integration
"""
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Load environment variables
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import journal_db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

WEBAPP_URL = "https://brusnyak.github.io/lingonberry_journal"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_JOURAL")  # Note: typo in env var name
AUTHORIZED_USER_IDS = [int(os.getenv("TELEGRAM_JOURNAL_CHAT", "0"))]  # Use chat ID as authorized user


def is_authorized(user_id: int) -> bool:
    """Check if user is authorized to use the bot"""
    if not AUTHORIZED_USER_IDS:
        return True
    return user_id in AUTHORIZED_USER_IDS


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    user = update.effective_user
    if not is_authorized(user.id):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    
    welcome_text = (
        f"👋 Welcome {user.first_name}!\n\n"
        "🎯 Trading Journal Bot\n\n"
        "Commands:\n"
        "/journal - View full journal dashboard\n"
        "/mini - Quick access to mini app\n"
        "/stats - View trading statistics\n"
        "/open - Show open positions\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    
    help_text = (
        "📚 *Trading Journal Bot Help*\n\n"
        "*Commands:*\n"
        "/start - Start the bot\n"
        "/journal - Open full journal dashboard\n"
        "/mini - Quick access mini app (button)\n"
        "/stats - View your trading statistics\n"
        "/open - Show open positions\n"
        "/closed - Show recent closed trades\n"
        "/weekly - Weekly performance review\n"
        "/help - Show this help message\n\n"
        "*Features:*\n"
        "• Real-time trade tracking\n"
        "• Performance analytics\n"
        "• Risk management monitoring\n"
        "• Weekly reviews\n"
        "• Monte Carlo simulations\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def journal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /journal command - opens full webapp"""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Open Journal", web_app=WebAppInfo(url=WEBAPP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 *Trading Journal Dashboard*\n\n"
        "Click the button below to open your full trading journal:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def mini_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /mini command - shows BUTTON with WebApp (NOT a link)"""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    
    # Create a keyboard button with WebApp
    keyboard = [
        [{"text": "📱 Open Mini App", "web_app": {"url": WEBAPP_URL}}]
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    await update.message.reply_text(
        "📱 *Mini Trading Journal*\n\n"
        "Tap the button below to access your mini journal app:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command - show trading statistics"""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    
    try:
        journal_db.init_db()
        accounts = journal_db.get_accounts()
        
        if not accounts:
            await update.message.reply_text("No trading accounts found. Please create an account first.")
            return
        
        account = accounts[0]
        stats = journal_db.get_stats(account_id=account["id"])
        
        stats_text = (
            f"📊 *Trading Statistics*\n\n"
            f"*Account:* {account['name']}\n"
            f"*Currency:* {account['currency']}\n\n"
            f"*Performance:*\n"
            f"• Total Trades: {stats['total_trades']}\n"
            f"• Win Rate: {stats['win_rate']:.1f}%\n"
            f"• Total P&L: {stats['total_pnl_usd']:.2f} {account['currency']}\n"
            f"• Average Win: {stats['avg_win_usd']:.2f} {account['currency']}\n"
            f"• Average Loss: {stats['avg_loss_usd']:.2f} {account['currency']}\n"
            f"• Profit Factor: {stats['profit_factor']:.2f}\n\n"
            f"*Risk Metrics:*\n"
            f"• Max Drawdown: {stats['max_drawdown_pct']:.2f}%\n"
            f"• Sharpe Ratio: {stats.get('sharpe_ratio', 0):.2f}\n"
            f"• Risk/Reward: {stats.get('avg_rr', 0):.2f}\n"
        )
        
        await update.message.reply_text(stats_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        await update.message.reply_text(f"❌ Error fetching statistics: {str(e)}")


async def open_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /open command - show open positions"""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    
    try:
        journal_db.init_db()
        open_trades = journal_db.get_open_trades()
        
        if not open_trades:
            await update.message.reply_text("📭 No open positions.")
            return
        
        response = "📈 *Open Positions:*\n\n"
        
        for trade in open_trades:
            direction_emoji = "🟢" if trade["direction"] == "LONG" else "🔴"
            pnl = trade.get("unrealized_pnl_usd", 0)
            pnl_emoji = "💰" if pnl >= 0 else "📉"
            
            response += (
                f"{direction_emoji} *{trade['symbol']}* {trade['direction']}\n"
                f"  Entry: {trade['entry_price']:.5f}\n"
                f"  Size: {trade['position_size']}\n"
                f"  SL: {trade.get('sl_price', 'N/A')}\n"
                f"  TP: {trade.get('tp_price', 'N/A')}\n"
                f"  {pnl_emoji} P&L: {pnl:.2f}\n"
                f"  Opened: {trade['ts_open'][:16]}\n\n"
            )
        
        await update.message.reply_text(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error fetching open trades: {e}")
        await update.message.reply_text(f"❌ Error fetching open positions: {str(e)}")


async def closed_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /closed command - show recent closed trades"""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    
    try:
        journal_db.init_db()
        all_trades = journal_db.get_all_trades()
        closed_trades = [t for t in all_trades if t["outcome"] != "OPEN"]
        closed_trades = sorted(closed_trades, key=lambda x: x.get("ts_close", ""), reverse=True)[:10]
        
        if not closed_trades:
            await update.message.reply_text("📭 No closed trades found.")
            return
        
        response = "📊 *Recent Closed Trades:*\n\n"
        
        for trade in closed_trades:
            pnl = trade.get("pnl_usd", 0)
            pnl_emoji = "✅" if pnl >= 0 else "❌"
            direction_emoji = "🟢" if trade["direction"] == "LONG" else "🔴"
            
            response += (
                f"{pnl_emoji} {direction_emoji} *{trade['symbol']}*\n"
                f"  P&L: {pnl:.2f} ({trade.get('pnl_pct', 0):.2f}%)\n"
                f"  Outcome: {trade['outcome']}\n"
                f"  Closed: {trade.get('ts_close', 'N/A')[:16]}\n\n"
            )
        
        await update.message.reply_text(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error fetching closed trades: {e}")
        await update.message.reply_text(f"❌ Error fetching closed trades: {str(e)}")


async def weekly_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /weekly command - show weekly review"""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    
    try:
        journal_db.init_db()
        accounts = journal_db.get_accounts()
        
        if not accounts:
            await update.message.reply_text("No trading accounts found.")
            return
        
        account_id = accounts[0]["id"]
        now = datetime.now(timezone.utc)
        week_start = (now - datetime.timedelta(days=now.weekday())).date().isoformat()
        
        review = journal_db.get_weekly_review(account_id=account_id, week_start=week_start)
        stats = journal_db.get_stats(account_id=account_id, from_ts=week_start)
        
        response = (
            f"📅 *Weekly Review*\n"
            f"Week of {week_start}\n\n"
            f"*Performance:*\n"
            f"• Trades: {stats['total_trades']}\n"
            f"• Win Rate: {stats['win_rate']:.1f}%\n"
            f"• P&L: {stats['total_pnl_usd']:.2f}\n\n"
        )
        
        if review.get("summary"):
            response += f"*Summary:*\n{review['summary']}\n\n"
        
        if review.get("key_wins"):
            response += f"*Key Wins:*\n{review['key_wins']}\n\n"
        
        if review.get("key_mistakes"):
            response += f"*Key Mistakes:*\n{review['key_mistakes']}\n\n"
        
        if review.get("next_week_focus"):
            response += f"*Next Week Focus:*\n{review['next_week_focus']}\n"
        
        await update.message.reply_text(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error fetching weekly review: {e}")
        await update.message.reply_text(f"❌ Error fetching weekly review: {str(e)}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred while processing your request. Please try again later."
        )


def main() -> None:
    """Start the bot"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
        sys.exit(1)
    
    # Initialize database
    journal_db.init_db()
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("journal", journal_command))
    application.add_handler(CommandHandler("mini", mini_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("open", open_command))
    application.add_handler(CommandHandler("closed", closed_command))
    application.add_handler(CommandHandler("weekly", weekly_command))
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Starting Trading Journal Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
