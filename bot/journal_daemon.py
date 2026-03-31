#!/usr/bin/env python3
"""Trading Journal Telegram Bot."""
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import journal_db
from bot.session_detector import detect_session
from core.raw_trade_import import parse_raw_trades

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:5000/mini")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_JOURNAL") or os.getenv("TELEGRAM_JOURAL")
AUTH_ID = int(os.getenv("TELEGRAM_JOURNAL_CHAT", "0") or "0")


def _webapp_full_url() -> str:
    """Return the full URL to the Web App (Mini App)."""
    url = WEBAPP_URL.strip("/")
    if not url.startswith("http"):
        # Assume https for production domains, http for localhost/internal IPs
        if any(x in url for x in ["localhost", "127.0.0.1", "10.", "192."]):
            url = "http://" + url
        else:
            url = "https://" + url
    
    if not url.endswith("/mini"):
        url += "/mini"
    return url

def _api_base() -> str:
    """Return the base URL for API calls (without /mini)."""
    url = _webapp_full_url()
    if url.endswith("/mini"):
        return url[:-5]
    return url

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


def _get_selected_account_ids(context: Optional[ContextTypes.DEFAULT_TYPE] = None) -> list[int]:
    """Get IDs of currently selected accounts for the bot."""
    if context and "selected_account_ids" in context.user_data:
        s_ids = [aid for aid in context.user_data["selected_account_ids"] if journal_db.get_account(aid)]
        if s_ids:
            context.user_data["selected_account_ids"] = s_ids
            return s_ids
            
    accounts = journal_db.get_accounts()
    if not accounts:
        return []
        
    # Default to the first account if none selected
    return [accounts[0]["id"]]

def _current_account(context: Optional[ContextTypes.DEFAULT_TYPE] = None) -> Optional[Dict[str, Any]]:
    """Legacy helper for single-account operations. Returns the first selected account."""
    ids = _get_selected_account_ids(context)
    if not ids:
        return None
    return journal_db.get_account(ids[0])


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

    ids = _get_selected_account_ids(context)
    active_names = []
    total_balance = 0.0
    currency = "USD"
    
    for aid in ids:
        acc = journal_db.get_account(aid)
        if acc:
            active_names.append(acc["name"])
            stats = journal_db.get_stats(account_id=aid)
            total_balance += stats["balance"]
            currency = acc["currency"]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Open Dashboard", web_app=WebAppInfo(url=_webapp_full_url()))],
        [InlineKeyboardButton("🔄 Switch / Select Accounts", callback_data="select_accounts:init")],
    ])
    await update.message.reply_text(
        "👋 Welcome back!\n\n"
        f"💼 {', '.join(active_names) if active_names else 'No account selected'}\n"
        f"💰 Total Balance: {currency} {total_balance:.2f}\n\n"
        "Commands:\n"
        "/journal — Log a new trade\n"
        "/stats — View performance stats\n"
        "/report — Open Dashboard\n"
        "/mini — Setup Mini App Button\n"
        "/dump — Paste trade logs (Prop/Platform)\n"
        "/select — Select active accounts\n"
        "/cancel — Cancel current journal flow",
        reply_markup=keyboard,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    await update.message.reply_text(
        "Commands:\n"
        "/journal, /stats, /report, /weekly, /dump, /cancel"
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
        context.user_data["awaiting_import"] = True
        await update.message.reply_text(
            "📥 Import mode enabled.\n\n"
            "Paste the raw trade export in your next message.\n"
            "You can also reply to an export message with /dump.\n\n"
            "Use /cancel to leave import mode."
        )
        return

    await _process_import(update, context, raw_text)


async def _process_import(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text: str) -> None:
    context.user_data.pop("awaiting_import", None)

    account_ids = _get_selected_account_ids(context)
    if not account_ids:
        await update.message.reply_text("❌ No account found to import into.")
        return

    try:
        account_ids = [aid for aid in account_ids if journal_db.get_account(aid)]
        if not account_ids:
            await update.message.reply_text("❌ No valid selected account found for import.")
            return

        trades = parse_raw_trades(raw_text, tz_offset_hours=2)
        if not trades:
            await update.message.reply_text("❌ No trades parsed from input.")
            return

        imported = 0
        skipped = 0
        existed = 0
        for aid in account_ids:
            for trade in trades:
                try:
                    trade_id = journal_db.create_trade(
                        account_id=aid,
                        symbol=trade["symbol"],
                        direction=trade["direction"],
                        entry_price=trade["entry_price"],
                        position_size=trade.get("lots", 0.1),
                        ts_open=trade["ts_open"],
                        sl_price=trade.get("sl"),
                        tp_price=trade.get("tp"),
                        timeframe="M30",
                        notes=trade.get("notes"),
                        external_id=trade.get("external_id"),
                        provider="import_bot",
                    )

                    if trade_id is None:
                        existed += 1
                        continue

                    journal_db.close_trade(
                        trade_id=trade_id,
                        exit_price=trade["exit_price"],
                        outcome=trade.get("outcome", "MANUAL"),
                        event_type="import",
                        provider="import_bot",
                        payload=trade,
                        ts_close=trade.get("ts_close"),
                        pnl_usd_override=trade.get("pnl_usd"),
                    )
                    imported += 1
                except Exception:
                    logger.exception("Failed to import raw trade for account %s", aid)
                    skipped += 1

        account_names = [journal_db.get_account(aid)["name"] for aid in account_ids if journal_db.get_account(aid)]
        
        msg = f"✅ Processed {len(account_ids)} accounts: {', '.join(account_names)}\n\n"
        msg += f"📥 Imported: {imported}\n"
        if existed > 0:
            msg += f"🔁 Already existed: {existed}\n"
        msg += f"⏭️ Skipped (errors): {skipped}"
        
        await update.message.reply_text(msg)
    except Exception as exc:
        logger.exception("Unexpected local error during import")
        await update.message.reply_text(f"❌ An unexpected error occurred: {exc}")


async def journal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    await _start_journal_flow(update, context)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("journal", None)
    context.user_data.pop("awaiting_import", None)
    await update.message.reply_text("🛑 Current flow cancelled.")


async def _finalize_trade(update: Update, context: ContextTypes.DEFAULT_TYPE, data: Dict[str, Any]) -> None:
    account = _current_account(context)
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

    # Chart generation removed as per user request
    pass


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("awaiting_import"):
        if not update.message or not update.message.text:
            return
        await _process_import(update, context, update.message.text)
        return

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
        account = _current_account(context)
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
        current_account = _current_account(context)
        open_trades = journal_db.get_open_trades(account_id=current_account["id"] if current_account else None)
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
        account = _current_account(context)
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
    elif callback_data == "select_accounts:init":
        await _send_account_selection(update, context, is_edit=True)
    elif callback_data.startswith("select_acc:"):
        await _handle_account_selection_callback(update, context)

async def select_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return
    await _send_account_selection(update, context)

async def _send_account_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, is_edit: bool = False):
    accounts = journal_db.get_accounts()
    if not accounts:
        msg = "No accounts found."
        if is_edit: await update.callback_query.edit_message_text(msg)
        else: await update.message.reply_text(msg)
        return

    selected_ids = _get_selected_account_ids(context)
    buttons = []
    for acc in accounts:
        is_selected = acc["id"] in selected_ids
        status = "✅ " if is_selected else ""
        buttons.append([InlineKeyboardButton(f"{status}{acc['name']} ({acc['currency']})", callback_data=f"select_acc:{acc['id']}")])
    
    buttons.append([InlineKeyboardButton("Done", callback_data="select_acc:done")])
    
    msg = "Select accounts for trade logging (multiple allowed for /dump):"
    reply_markup = InlineKeyboardMarkup(buttons)
    
    if is_edit:
        await update.callback_query.edit_message_text(msg, reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, reply_markup=reply_markup)

async def _handle_account_selection_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    action = query.data.split(":")[1]
    if action == "done":
        ids = _get_selected_account_ids(context)
        names = [journal_db.get_account(aid)["name"] for aid in ids]
        await query.edit_message_text(f"✅ Accounts updated: {', '.join(names)}")
        return
        
    acc_id = int(action)
    selected_ids = list(_get_selected_account_ids(context))
    if acc_id in selected_ids:
        if len(selected_ids) > 1:
            selected_ids.remove(acc_id)
    else:
        selected_ids.append(acc_id)
        
    context.user_data["selected_account_ids"] = selected_ids
    await _send_account_selection(update, context, is_edit=True)


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
    application.add_handler(CommandHandler("dump", import_command))
    application.add_handler(CommandHandler("import", import_command)) 
    application.add_handler(CommandHandler("select", select_command))
    application.add_handler(CallbackQueryHandler(daily_reminder_callback, pattern="^(daily_reminder:|select_accounts:|select_acc:)"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    application.add_error_handler(error_handler)

    async def _post_init(app) -> None:
        """Register command hints and menu button with Telegram after bot starts."""
        from telegram import BotCommand, MenuButtonWebApp
        
        # Register commands
        await app.bot.set_my_commands([
            BotCommand("start",   "Welcome message & dashboard"),
            BotCommand("journal", "Log a new trade"),
            BotCommand("stats",   "View performance statistics"),
            BotCommand("report",  "Open the trading dashboard"),
            BotCommand("mini",    "Add Mini App button to keyboard"),
            BotCommand("dump",    "Import raw trade logs"),
            BotCommand("select",  "Select active accounts"),
            BotCommand("weekly",  "Weekly performance review"),
            BotCommand("cancel",  "Cancel current journal flow"),
        ])
        
        # Set persistent menu button to open Web App
        try:
            await app.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="📊 Dashboard", web_app=WebAppInfo(url=_webapp_full_url()))
            )
            logger.info(f"Bot menu button set to {_webapp_full_url()}")
        except Exception as e:
            logger.warning(f"Failed to set menu button: {e}")
            
        logger.info("Bot commands registered with Telegram.")

    application.post_init = _post_init

    logger.info("Starting Trading Journal Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
