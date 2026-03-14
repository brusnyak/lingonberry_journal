#!/usr/bin/env python3
"""Trading Journal Telegram Bot."""
import json
import logging
import os
import sys
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import journal_db
from bot.session_detector import detect_session

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:5000/mini")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_JOURNAL") or os.getenv("TELEGRAM_JOURAL")
AUTH_ID = int(os.getenv("TELEGRAM_JOURNAL_CHAT", "0") or "0")


def _api_base() -> str:
    base = WEBAPP_URL.rstrip("/")
    if base.endswith("/mini"):
        base = base[:-5]
    return base

JOURNAL_STEPS = [
    "symbol",
    "direction",
    "entry_price",
    "sl_price",
    "tp_price",
    "entry_time",
    "notes",
    "mood",
    "market_condition",
    "lot_size",
]


def is_authorized(update: Update) -> bool:
    if AUTH_ID <= 0:
        return True
    user_id = update.effective_user.id if update.effective_user else 0
    chat_id = update.effective_chat.id if update.effective_chat else 0
    return AUTH_ID in (user_id, chat_id)


def _normalize_direction(value: str) -> Optional[str]:
    text = value.strip().lower()
    if text in {"long", "buy", "l"}:
        return "LONG"
    if text in {"short", "sell", "s"}:
        return "SHORT"
    return None


def _parse_float(value: str) -> Optional[float]:
    try:
        return float(value.strip().replace(",", "."))
    except ValueError:
        return None


def _current_account() -> Optional[Dict[str, Any]]:
    accounts = journal_db.get_accounts()
    return accounts[0] if accounts else None


def _journal_prompt(step: str, data: Dict[str, Any]) -> str:
    if step == "symbol":
        return "💱 Asset symbol? (e.g. EURUSD, GBPJPY, BTCUSDT)"
    if step == "direction":
        return "🧭 Direction? (long/short)"
    if step == "entry_price":
        return "💰 Entry price?"
    if step == "sl_price":
        return "🛑 Stop Loss price?"
    if step == "tp_price":
        return "🎯 Take Profit price?"
    if step == "entry_time":
        return "⏰ Entry time? (`now` or `HH:MM` UTC)"
    if step == "notes":
        rr = None
        if data.get("entry_price") and data.get("sl_price") and data.get("tp_price"):
            risk = abs(data["entry_price"] - data["sl_price"])
            reward = abs(data["tp_price"] - data["entry_price"])
            rr = round(reward / risk, 2) if risk > 0 else None
        rr_line = f"📐 RR Ratio: 1:{rr}\n\n" if rr else ""
        return rr_line + "📝 Setup notes/tags? (`skip` to omit)"
    if step == "mood":
        return "🧠 Mental state before entry? (`skip` to omit)"
    if step == "market_condition":
        return "🌦 Market condition? (`trending/ranging/volatile` or `skip`)"
    if step == "lot_size":
        return "📦 Lot size used? (`skip` to use 1.0)"
    return ""


async def _start_journal_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["journal"] = {"step_idx": 0, "data": {"asset_type": "forex"}}
    await update.message.reply_text("📝 New trade journal started.\n\n" + _journal_prompt("symbol", {}))


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return

    account = _current_account()
    balance = "N/A"
    if account:
        stats = journal_db.get_stats(account_id=account["id"])
        balance = f"{account['currency']} {stats['balance']:.2f}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Open Dashboard", web_app=WebAppInfo(url=WEBAPP_URL.rstrip('/') + '/mini'))],
    ])
    await update.message.reply_text(
        "👋 Welcome back!\n\n"
        f"💼 {account['name'] if account else 'No account'} | Balance: {balance}\n\n"
        "Commands:\n"
        "/journal — Log a new trade\n"
        "/open — View open trades\n"
        "/stats — View performance stats\n"
        "/report — Open Dashboard\n"
        "/mini — Setup Mini App Button\n"
        "/import — Paste trade logs\n"
        "/cancel — Cancel current journal flow",
        reply_markup=keyboard,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    await update.message.reply_text(
        "Commands:\n"
        "/journal, /open, /close, /stats, /report, /weekly, /import, /cancel"
    )


async def import_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return

    raw_text = ""
    if update.message and update.message.text:
        parts = update.message.text.split(None, 1)
        if len(parts) > 1:
            raw_text = parts[1]

    if not raw_text and update.message and update.message.reply_to_message:
        raw_text = update.message.reply_to_message.text or ""

    if not raw_text.strip():
        await update.message.reply_text(
            "Paste your trade log after the command, or reply to a message with /import.\n\n"
            "Example:\n"
            "/import <paste logs>"
        )
        return

    account = _current_account()
    if not account:
        await update.message.reply_text("❌ No account found to import into.")
        return

    payload = {
        "text": raw_text,
        "account_id": account["id"],
        "timezone_offset_hours": 2,
        "timeframe": "M30",
    }

    url = f"{_api_base()}/api/trades/import_raw?account_id={account['id']}"
    req = urlrequest.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlrequest.urlopen(req, timeout=25) as resp:
            body = resp.read().decode("utf-8")
        data = json.loads(body) if body else {}
        imported = data.get("imported_count", 0)
        skipped = data.get("skipped", 0)
        await update.message.reply_text(
            f"✅ Imported {imported} trades into {account['name']}.\n"
            f"Skipped: {skipped}"
        )
    except HTTPError as exc:
        details = exc.read().decode("utf-8") if exc.fp else ""
        await update.message.reply_text(f"❌ Import failed: {exc.code}\n{details}")
    except URLError as exc:
        await update.message.reply_text(f"❌ Import failed: {exc}")


async def journal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    await _start_journal_flow(update, context)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("journal", None)
    await update.message.reply_text("🛑 Journal flow cancelled.")


async def _finalize_trade(update: Update, context: ContextTypes.DEFAULT_TYPE, data: Dict[str, Any]) -> None:
    account = _current_account()
    if not account:
        await update.message.reply_text("❌ No account found. Create one from the dashboard first.")
        return

    ts_open = data["ts_open"]
    session = detect_session(ts_open)
    notes = data.get("notes")
    if data.get("mood"):
        notes = (notes + " | " if notes else "") + f"mood:{data['mood']}"
    if data.get("market_condition"):
        notes = (notes + " | " if notes else "") + f"market:{data['market_condition']}"

    # Save trade immediately
    trade_id = journal_db.create_trade(
        account_id=account["id"],
        symbol=data["symbol"],
        direction=data["direction"],
        entry_price=data["entry_price"],
        position_size=data.get("lot_size", 1.0),
        ts_open=ts_open,
        asset_type="forex",
        sl_price=data["sl_price"],
        tp_price=data["tp_price"],
        session=session,
        notes=notes,
        provider="manual_bot",
    )

    rr = 0.0
    risk = abs(data["entry_price"] - data["sl_price"])
    reward = abs(data["tp_price"] - data["entry_price"])
    if risk > 0:
        rr = reward / risk

    summary = (
        f"✅ Trade #{trade_id} logged!\n\n"
        f"{data['symbol']} — {data['direction']}\n"
        f"Entry: {data['entry_price']} | SL: {data['sl_price']} | TP: {data['tp_price']}\n"
        f"RR: 1:{rr:.2f}\n"
        f"Lot: {data.get('lot_size', 1.0)}\n\n"
        f"📊 Generating charts in background..."
    )

    await update.message.reply_text(summary)

    # Generate charts asynchronously (non-blocking)
    trade = journal_db.get_trade(trade_id)
    if trade:
        try:
            from bot.chart_generator import generate_trade_charts

            chart_paths = generate_trade_charts(
                trade, output_dir="data/reports", context_weeks=1, timeframe=trade.get("timeframe")
            )
            if chart_paths:
                journal_db.set_trade_chart_paths(trade_id, chart_paths)
                
                # Send chart images
                for path in chart_paths[:3]:
                    try:
                        with open(path, 'rb') as photo:
                            await update.message.reply_photo(photo=photo, caption=os.path.basename(path))
                    except Exception as e:
                        logger.warning(f"Failed to send chart {path}: {e}")
        except Exception as exc:
            logger.warning("Chart generation failed: %s", exc)
            await update.message.reply_text(f"⚠️ Charts could not be generated: {exc}")


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    flow = context.user_data.get("journal")
    if not flow:
        return

    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    step_idx = flow.get("step_idx", 0)
    data = flow.get("data", {})

    if step_idx >= len(JOURNAL_STEPS):
        context.user_data.pop("journal", None)
        return

    step = JOURNAL_STEPS[step_idx]

    if step == "symbol":
        data[step] = text.upper().replace(" ", "")
    elif step == "direction":
        direction = _normalize_direction(text)
        if not direction:
            await update.message.reply_text("Type `long` or `short`.")
            return
        data[step] = direction
    elif step in {"entry_price", "sl_price", "tp_price", "lot_size"}:
        if text.lower() == "skip" and step == "lot_size":
            data[step] = 1.0
        else:
            number = _parse_float(text)
            if number is None:
                await update.message.reply_text("Please send a valid number.")
                return
            data[step] = number
    elif step == "entry_time":
        now = datetime.now(timezone.utc)
        if text.lower() == "now":
            data["ts_open"] = now.isoformat()
        else:
            try:
                hh, mm = text.split(":")
                dt = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
                data["ts_open"] = dt.isoformat()
            except Exception:
                await update.message.reply_text("Use `now` or `HH:MM`.")
                return
    else:
        data[step] = None if text.lower() == "skip" else text

    flow["step_idx"] = step_idx + 1
    flow["data"] = data

    if flow["step_idx"] >= len(JOURNAL_STEPS):
        context.user_data.pop("journal", None)
        await update.message.reply_text("⏳ Generating charts & saving trade...")
        try:
            await _finalize_trade(update, context, data)
        except Exception as exc:
            logger.exception("Failed to save trade")
            await update.message.reply_text(f"❌ Failed to save trade: {exc}")
        return

    next_step = JOURNAL_STEPS[flow["step_idx"]]
    await update.message.reply_text(_journal_prompt(next_step, data))


def _webapp_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Open Journal Dashboard", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    
    # Use the configured WEBAPP_URL
    url = WEBAPP_URL.rstrip('/')
    await update.message.reply_text(
        "📊 Trading Dashboard\n\n"
        f"Open in your browser:\n{url}\n\n"
        "Or use the 'Open Dashboard' button below.",
        reply_markup=_webapp_keyboard()
    )


async def mini_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    keyboard = [[{"text": "📱 Open Mini App", "web_app": {"url": WEBAPP_URL}}]]
    await update.message.reply_text(
        "Tap to open mini app:",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=False),
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    try:
        journal_db.init_db()
        account = _current_account()
        if not account:
            await update.message.reply_text("No trading accounts found. Create one in dashboard.")
            return
        stats = journal_db.get_stats(account_id=account["id"])
        await update.message.reply_text(
            "📊 Trading Statistics\n\n"
            f"Account: {account['name']}\n"
            f"Total Trades: {stats['total_trades']}\n"
            f"Win Rate: {stats['win_rate']:.1f}%\n"
            f"Balance: {stats['balance']:.2f} {account['currency']}\n"
            f"Total P&L: {stats['total_pnl_usd']:.2f} {account['currency']}\n"
            f"Profit Factor: {stats['profit_factor']:.2f}\n"
            f"Max DD: {stats['max_drawdown_pct']:.2f}%"
        )
    except Exception as exc:
        logger.exception("Error fetching stats")
        await update.message.reply_text(f"❌ Error fetching statistics: {exc}")


async def open_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return

    try:
        open_trades = journal_db.get_open_trades(account_id=_current_account()["id"] if _current_account() else None)
        if not open_trades:
            await update.message.reply_text("📭 No open positions.")
            return

        response = "📈 Open Positions:\n\n"
        for trade in open_trades:
            direction = str(trade.get("direction", "")).upper()
            direction_emoji = "🟢" if direction == "LONG" else "🔴"
            response += (
                f"{direction_emoji} {trade['symbol']} {direction}\n"
                f"  Entry: {trade.get('entry_price')}\n"
                f"  Size: {trade.get('position_size') or '-'}\n"
                f"  SL: {trade.get('sl_price') or '-'}\n"
                f"  TP: {trade.get('tp_price') or '-'}\n"
                f"  Opened: {str(trade.get('ts_open', ''))[:16]}\n\n"
            )
        await update.message.reply_text(response)
    except Exception as exc:
        logger.exception("Error fetching open trades")
        await update.message.reply_text(f"❌ Error fetching open positions: {exc}")


async def close_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    await update.message.reply_text("Use API/manual close from dashboard for now: POST /api/trades/{id}/close")


async def weekly_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return

    try:
        account = _current_account()
        if not account:
            await update.message.reply_text("No trading accounts found.")
            return

        now = datetime.now(timezone.utc)
        week_start = (now - timedelta(days=now.weekday())).date().isoformat()
        review = journal_db.get_weekly_review(account_id=account["id"], week_start=week_start)
        stats = journal_db.get_stats(account_id=account["id"], from_ts=week_start)

        response = (
            f"📅 Weekly Review\nWeek of {week_start}\n\n"
            f"Trades: {stats['total_trades']}\n"
            f"Win Rate: {stats['win_rate']:.1f}%\n"
            f"P&L: {stats['total_pnl_usd']:.2f}\n\n"
        )
        if review.get("summary"):
            response += f"Summary:\n{review['summary']}\n"
        await update.message.reply_text(response)
    except Exception as exc:
        logger.exception("Error fetching weekly review")
        await update.message.reply_text(f"❌ Error fetching weekly review: {exc}")


async def daily_reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle daily reminder Yes/No button responses"""
    query = update.callback_query
    await query.answer()
    
    if not is_authorized(update):
        await query.edit_message_text("⛔ You are not authorized to use this bot.")
        return
    
    callback_data = query.data
    
    if callback_data == "daily_reminder:yes":
        await query.edit_message_text(
            "✅ Great! Let's log your trades.\n\n"
            "Use /journal to start logging a trade, or /open to see open positions."
        )
    elif callback_data == "daily_reminder:no":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Review Market", callback_data="daily_reminder:review")],
            [InlineKeyboardButton("👋 See You Tomorrow", callback_data="daily_reminder:goodbye")]
        ])
        await query.edit_message_text(
            "No trades today - that's okay!\n\n"
            "What would you like to do?",
            reply_markup=keyboard
        )
    elif callback_data == "daily_reminder:review":
        await query.edit_message_text(
            "📈 Market Review\n\n"
            "Use /stats to see your performance, or /weekly for weekly review.\n"
            "You can also open the dashboard with /report"
        )
    elif callback_data == "daily_reminder:goodbye":
        await query.edit_message_text(
            "👋 See you tomorrow! Trade safe."
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Update %s caused error %s", update, context.error)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_JOURNAL (or TELEGRAM_JOURAL) environment variable not set")
        sys.exit(1)

    journal_db.init_db()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("journal", journal_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("mini", mini_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("open", open_command))
    application.add_handler(CommandHandler("close", close_command))
    application.add_handler(CommandHandler("weekly", weekly_command))
    application.add_handler(CommandHandler("import", import_command))
    application.add_handler(CallbackQueryHandler(daily_reminder_callback, pattern="^daily_reminder:"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    application.add_error_handler(error_handler)

    async def _post_init(app) -> None:
        """Register command hints with Telegram after bot starts."""
        from telegram import BotCommand
        await app.bot.set_my_commands([
            BotCommand("start",   "Welcome message & dashboard"),
            BotCommand("journal", "Log a new trade"),
            BotCommand("stats",   "View performance statistics"),
            BotCommand("open",    "See open positions"),
            BotCommand("close",   "Close an open trade"),
            BotCommand("report",  "Open the trading dashboard"),
            BotCommand("mini",    "Add Mini App button to keyboard"),
            BotCommand("weekly",  "Weekly performance review"),
            BotCommand("cancel",  "Cancel current journal flow"),
        ])
        logger.info("Bot commands registered with Telegram.")

    application.post_init = _post_init

    logger.info("Starting Trading Journal Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
