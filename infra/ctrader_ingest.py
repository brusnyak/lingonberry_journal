#!/usr/bin/env python3
"""
cTrader Trade Import
Imports trades from cTrader into the journal database
"""
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import journal_db
from bot.session_detector import detect_session
from infra.ctrader_client import create_client


def _pick(source: Dict, *keys, default=None):
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    return default


def _ms_to_iso(value) -> Optional[str]:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc).isoformat()
    except Exception:
        return None


def import_ctrader_trades(
    account_id: int,
    from_ts: Optional[datetime] = None,
    to_ts: Optional[datetime] = None,
) -> Dict[str, int]:
    """Import trades from cTrader"""
    client = create_client()
    
    if not client.connected:
        return {"imported": 0, "skipped": 0, "errors": 0}
    
    try:
        # Get closed positions from cTrader
        positions = client.get_closed_positions(from_ts=from_ts, to_ts=to_ts)
        
        imported = 0
        skipped = 0
        errors = 0
        
        for pos in positions:
            try:
                # Check if already imported
                external_id = str(pos.get("positionId"))
                existing = journal_db.find_trade_by_external_id(external_id, "ctrader")
                
                if existing:
                    skipped += 1
                    continue
                
                # Map cTrader position to journal trade
                side = str(_pick(pos, "tradeSide", "side", default="")).upper()
                direction = "LONG" if side in {"BUY", "LONG"} else "SHORT"
                entry_price = float(_pick(pos, "entryPrice", "openPrice", default=0) or 0)
                exit_price = float(_pick(pos, "closePrice", "exitPrice", default=0) or 0)
                volume = float(_pick(pos, "volume", "quantity", "lotSize", default=0) or 0)
                symbol = pos.get("symbolName", "")
                
                ts_open = _ms_to_iso(_pick(pos, "openTimestamp", "openTime", "openTimestampMs")) or datetime.now(timezone.utc).isoformat()
                ts_close = _ms_to_iso(_pick(pos, "closeTimestamp", "closeTime", "closeTimestampMs")) or datetime.now(timezone.utc).isoformat()
                
                session = detect_session(ts_open)
                
                # Determine asset type
                asset_type = "forex"
                if symbol.upper() in ["NAS100", "US100", "USTEC", "SPX500", "US30"]:
                    asset_type = "index"
                elif symbol.upper() in ["XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD"]:
                    asset_type = "commodity"
                
                # Capture indicators at entry
                timeframe = "M30"  # Default timeframe
                entry_indicators = journal_db.capture_indicators_at_timestamp(
                    symbol=symbol,
                    asset_type=asset_type,
                    timeframe=timeframe,
                    timestamp=ts_open,
                )
                
                # Capture indicators at exit
                exit_indicators = journal_db.capture_indicators_at_timestamp(
                    symbol=symbol,
                    asset_type=asset_type,
                    timeframe=timeframe,
                    timestamp=ts_close,
                )
                
                # Build indicator_data
                indicator_data = {
                    "entry": entry_indicators,
                    "exit": exit_indicators,
                }
                
                # Calculate P&L
                pnl_usd = float(_pick(pos, "grossProfit", default=0) or 0) + float(_pick(pos, "commission", default=0) or 0) + float(_pick(pos, "swap", default=0) or 0)
                pnl_pct = None
                if entry_price:
                    if direction == "LONG":
                        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                    else:
                        pnl_pct = ((entry_price - exit_price) / entry_price) * 100
                
                # Create trade
                trade_id = journal_db.create_trade(
                    account_id=account_id,
                    symbol=symbol,
                    direction=direction,
                    entry_price=entry_price,
                    position_size=volume,
                    ts_open=ts_open,
                    asset_type=asset_type,
                    session=session,
                    timeframe=timeframe,
                    external_id=external_id,
                    provider="ctrader",
                    indicator_data=indicator_data,
                )
                
                # Close trade
                journal_db.close_trade(
                    trade_id=trade_id,
                    exit_price=exit_price,
                    outcome="MANUAL",
                    event_type="ctrader_import",
                    provider="ctrader",
                    payload=pos,
                    ts_close=ts_close,
                    pnl_usd_override=pnl_usd,
                    pnl_pct_override=pnl_pct,
                    exit_indicators=exit_indicators,
                )
                
                imported += 1
                
            except Exception as e:
                print(f"Error importing position {pos.get('positionId')}: {e}")
                import traceback
                traceback.print_exc()
                errors += 1
        
        return {"imported": imported, "skipped": skipped, "errors": errors}
        
    finally:
        client.disconnect()


def sync_open_positions(account_id: int) -> Dict[str, int]:
    """Sync open positions from cTrader"""
    client = create_client()
    
    if not client.connected:
        return {"synced": 0, "errors": 0}
    
    try:
        positions = client.get_open_positions()
        
        synced = 0
        errors = 0
        
        for pos in positions:
            try:
                external_id = str(pos.get("positionId"))
                existing = journal_db.find_trade_by_external_id(external_id, "ctrader")
                
                if existing:
                    # Update SL/TP if changed
                    sl_price = pos.get("stopLoss")
                    tp_price = pos.get("takeProfit")
                    
                    if sl_price != existing.get("sl_price") or tp_price != existing.get("tp_price"):
                        journal_db.update_trade_sl_tp(existing["id"], sl_price, tp_price)
                        synced += 1
                else:
                    # Create new open trade
                    side = str(_pick(pos, "tradeSide", "side", default="")).upper()
                    direction = "LONG" if side in {"BUY", "LONG"} else "SHORT"
                    entry_price = float(_pick(pos, "entryPrice", "openPrice", default=0) or 0)
                    volume = float(_pick(pos, "volume", "quantity", "lotSize", default=0) or 0)
                    ts_open = _ms_to_iso(_pick(pos, "openTimestamp", "openTime", "openTimestampMs")) or datetime.now(timezone.utc).isoformat()
                    session = detect_session(ts_open)
                    
                    journal_db.create_trade(
                        account_id=account_id,
                        symbol=pos.get("symbolName", ""),
                        direction=direction,
                        entry_price=entry_price,
                        position_size=volume,
                        ts_open=ts_open,
                        asset_type="forex",
                        sl_price=_pick(pos, "stopLoss", "sl", "stopLossPrice"),
                        tp_price=_pick(pos, "takeProfit", "tp", "takeProfitPrice"),
                        session=session,
                        external_id=external_id,
                        provider="ctrader",
                    )
                    synced += 1
                    
            except Exception as e:
                print(f"Error syncing position {pos.get('positionId')}: {e}")
                errors += 1
        
        return {"synced": synced, "errors": errors}
        
    finally:
        client.disconnect()


def get_trade_replay_data(
    symbol: str,
    timeframe: str,
    from_ts: str,
    to_ts: str,
) -> List[Dict]:
    """Get historical candle data for trade replay"""
    # Placeholder - implement actual data fetching
    return []
