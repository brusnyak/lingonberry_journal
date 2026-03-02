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
                direction = "LONG" if pos.get("tradeSide") == "BUY" else "SHORT"
                entry_price = pos.get("entryPrice", 0)
                exit_price = pos.get("closePrice", 0)
                volume = pos.get("volume", 0)
                
                ts_open = datetime.fromtimestamp(pos.get("openTimestamp", 0) / 1000, tz=timezone.utc).isoformat()
                ts_close = datetime.fromtimestamp(pos.get("closeTimestamp", 0) / 1000, tz=timezone.utc).isoformat()
                
                session = detect_session(ts_open)
                
                # Calculate P&L
                pnl_usd = pos.get("grossProfit", 0) + pos.get("commission", 0) + pos.get("swap", 0)
                
                # Create trade
                trade_id = journal_db.create_trade(
                    account_id=account_id,
                    symbol=pos.get("symbolName", ""),
                    direction=direction,
                    entry_price=entry_price,
                    position_size=volume,
                    ts_open=ts_open,
                    asset_type="forex",
                    session=session,
                    external_id=external_id,
                    provider="ctrader",
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
                )
                
                imported += 1
                
            except Exception as e:
                print(f"Error importing position {pos.get('positionId')}: {e}")
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
                    direction = "LONG" if pos.get("tradeSide") == "BUY" else "SHORT"
                    entry_price = pos.get("entryPrice", 0)
                    volume = pos.get("volume", 0)
                    ts_open = datetime.fromtimestamp(pos.get("openTimestamp", 0) / 1000, tz=timezone.utc).isoformat()
                    session = detect_session(ts_open)
                    
                    journal_db.create_trade(
                        account_id=account_id,
                        symbol=pos.get("symbolName", ""),
                        direction=direction,
                        entry_price=entry_price,
                        position_size=volume,
                        ts_open=ts_open,
                        asset_type="forex",
                        sl_price=pos.get("stopLoss"),
                        tp_price=pos.get("takeProfit"),
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
