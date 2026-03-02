#!/usr/bin/env python3
"""
SL/TP Poller Job
Monitors open trades and automatically closes them when SL/TP is hit
"""
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import journal_db
from infra.market_data import get_current_price


class SLTPPoller:
    """SL/TP monitoring and auto-close"""
    
    def __init__(self):
        self.check_interval = 60  # seconds
    
    def check_trade(self, trade: Dict) -> Optional[Dict]:
        """
        Check if trade should be closed based on current price
        
        Returns:
            Closed trade dict if closed, None otherwise
        """
        symbol = trade["symbol"]
        asset_type = trade.get("asset_type", "forex")
        
        # Get current price
        current_price = get_current_price(symbol, asset_type)
        
        if current_price is None:
            return None
        
        direction = trade["direction"]
        sl_price = trade.get("sl_price")
        tp_price = trade.get("tp_price")
        
        should_close = False
        outcome = None
        
        if direction == "LONG":
            # Check SL
            if sl_price and current_price <= sl_price:
                should_close = True
                outcome = "SL"
                exit_price = sl_price
            # Check TP
            elif tp_price and current_price >= tp_price:
                should_close = True
                outcome = "TP"
                exit_price = tp_price
        
        elif direction == "SHORT":
            # Check SL
            if sl_price and current_price >= sl_price:
                should_close = True
                outcome = "SL"
                exit_price = sl_price
            # Check TP
            elif tp_price and current_price <= tp_price:
                should_close = True
                outcome = "TP"
                exit_price = tp_price
        
        if should_close:
            print(f"Closing trade {trade['id']}: {symbol} {direction} - {outcome} hit")
            
            closed_trade = journal_db.close_trade(
                trade_id=trade["id"],
                exit_price=exit_price,
                outcome=outcome,
                event_type="sltp_auto_close",
                provider="sltp_poller",
                payload={
                    "current_price": current_price,
                    "trigger": outcome,
                },
            )
            
            return closed_trade
        
        return None
    
    def run_once(self, account_id: Optional[int] = None) -> List[Dict]:
        """
        Run one check cycle
        
        Args:
            account_id: Optional account ID to filter trades
        
        Returns:
            List of closed trades
        """
        print(f"[{datetime.now()}] Running SL/TP check...")
        
        # Get open trades
        open_trades = journal_db.get_open_trades(account_id=account_id)
        
        if not open_trades:
            print("No open trades to check")
            return []
        
        print(f"Checking {len(open_trades)} open trades...")
        
        closed_trades = []
        
        for trade in open_trades:
            # Only check trades with SL or TP set
            if not trade.get("sl_price") and not trade.get("tp_price"):
                continue
            
            try:
                closed_trade = self.check_trade(trade)
                if closed_trade:
                    closed_trades.append(closed_trade)
            except Exception as e:
                print(f"Error checking trade {trade['id']}: {e}")
        
        print(f"Closed {len(closed_trades)} trades")
        
        return closed_trades
    
    def run_continuous(self, account_id: Optional[int] = None):
        """
        Run continuous monitoring
        
        Args:
            account_id: Optional account ID to filter trades
        """
        print(f"Starting continuous SL/TP monitoring (interval: {self.check_interval}s)")
        
        while True:
            try:
                self.run_once(account_id=account_id)
            except Exception as e:
                print(f"Error in SL/TP check: {e}")
            
            time.sleep(self.check_interval)


if __name__ == "__main__":
    poller = SLTPPoller()
    
    account_id = int(os.getenv("JOURNAL_ACCOUNT_ID", "1")) if os.getenv("JOURNAL_ACCOUNT_ID") else None
    
    if len(sys.argv) > 1 and sys.argv[1] == "continuous":
        poller.run_continuous(account_id=account_id)
    else:
        result = poller.run_once(account_id=account_id)
        print(f"Closed {len(result)} trades")
