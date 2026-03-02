#!/usr/bin/env python3
"""
Pine Script Webhook Bridge
Processes webhooks from TradingView Pine Script alerts
"""
import json
import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import journal_db
from bot.session_detector import detect_session


def process_pine_payload(payload: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
    """
    Process Pine Script webhook payload
    
    Expected payload format:
    {
        "action": "open" | "close" | "update",
        "account_id": int,
        "symbol": str,
        "direction": "LONG" | "SHORT",
        "entry_price": float,
        "position_size": float,
        "sl_price": float (optional),
        "tp_price": float (optional),
        "exit_price": float (for close),
        "outcome": str (for close),
        "timestamp": str (ISO format),
        "strategy": str (optional),
        "timeframe": str (optional),
        "notes": str (optional)
    }
    """
    # Check idempotency
    if not journal_db.record_pine_webhook(idempotency_key, json.dumps(payload)):
        return {"status": "duplicate", "message": "Webhook already processed"}
    
    action = payload.get("action")
    
    if action == "open":
        return _handle_open_trade(payload)
    elif action == "close":
        return _handle_close_trade(payload)
    elif action == "update":
        return _handle_update_trade(payload)
    else:
        return {"status": "error", "message": f"Unknown action: {action}"}


def _handle_open_trade(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle open trade webhook"""
    try:
        account_id = int(payload["account_id"])
        symbol = payload["symbol"]
        direction = payload["direction"]
        entry_price = float(payload["entry_price"])
        position_size = float(payload["position_size"])
        ts_open = payload.get("timestamp") or datetime.now(timezone.utc).isoformat()
        
        # Detect session
        session = detect_session(ts_open)
        
        # Create trade
        trade_id = journal_db.create_trade(
            account_id=account_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            position_size=position_size,
            ts_open=ts_open,
            asset_type=payload.get("asset_type", "forex"),
            sl_price=payload.get("sl_price"),
            tp_price=payload.get("tp_price"),
            session=session,
            timeframe=payload.get("timeframe"),
            strategy=payload.get("strategy"),
            notes=payload.get("notes"),
            provider="pine",
        )
        
        return {
            "status": "success",
            "action": "open",
            "trade_id": trade_id,
            "message": f"Trade opened: {symbol} {direction}",
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _handle_close_trade(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle close trade webhook"""
    try:
        account_id = int(payload["account_id"])
        symbol = payload["symbol"]
        exit_price = float(payload["exit_price"])
        outcome = payload.get("outcome", "MANUAL")
        ts_close = payload.get("timestamp") or datetime.now(timezone.utc).isoformat()
        
        # Find open trade
        trade = journal_db.find_open_trade_by_symbol(account_id, symbol)
        
        if not trade:
            return {
                "status": "error",
                "message": f"No open trade found for {symbol}",
            }
        
        # Close trade
        closed_trade = journal_db.close_trade(
            trade_id=trade["id"],
            exit_price=exit_price,
            outcome=outcome,
            event_type="pine_close",
            provider="pine",
            payload=payload,
            ts_close=ts_close,
        )
        
        return {
            "status": "success",
            "action": "close",
            "trade_id": trade["id"],
            "pnl_usd": closed_trade.get("pnl_usd"),
            "pnl_pct": closed_trade.get("pnl_pct"),
            "message": f"Trade closed: {symbol}",
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _handle_update_trade(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle update trade webhook (e.g., SL/TP modification)"""
    try:
        account_id = int(payload["account_id"])
        symbol = payload["symbol"]
        
        # Find open trade
        trade = journal_db.find_open_trade_by_symbol(account_id, symbol)
        
        if not trade:
            return {
                "status": "error",
                "message": f"No open trade found for {symbol}",
            }
        
        # Update SL/TP
        sl_price = payload.get("sl_price")
        tp_price = payload.get("tp_price")
        
        journal_db.update_trade_sl_tp(trade["id"], sl_price, tp_price)
        
        return {
            "status": "success",
            "action": "update",
            "trade_id": trade["id"],
            "message": f"Trade updated: {symbol}",
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
