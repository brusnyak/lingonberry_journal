#!/usr/bin/env python3
"""Test script to verify trade logging functionality"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bot import journal_db

def test_manual_trade():
    """Test adding a manual trade"""
    print("Testing manual trade logging...")
    
    # Initialize database
    journal_db.init_db()
    
    # Get or create test account
    accounts = journal_db.get_accounts()
    if not accounts:
        print("Creating test account...")
        account_id = journal_db.create_account(
            name="Test Account",
            currency="USD",
            initial_balance=10000.0
        )
    else:
        account_id = accounts[0]["id"]
    
    print(f"Using account_id: {account_id}")
    
    # Test data
    ts_open = datetime.now(timezone.utc).isoformat()
    ts_close = datetime.now(timezone.utc).isoformat()
    
    try:
        trade_id = journal_db.add_manual_trade(
            account_id=account_id,
            symbol="EURUSD",
            direction="LONG",
            entry_price=1.08500,
            exit_price=1.08700,
            sl_price=1.08300,
            tp_price=1.08700,
            ts_open=ts_open,
            ts_close=ts_close,
            lots=0.1,
            notes="Test trade",
            outcome="TP",
            indicator_data={"test": "data"}
        )
        
        print(f"✓ Trade created successfully! ID: {trade_id}")
        
        # Verify trade was saved
        trade = journal_db.get_trade(trade_id)
        if trade:
            print(f"✓ Trade retrieved: {trade['symbol']} {trade['direction']}")
            print(f"  Entry: {trade['entry']}, Exit: {trade['exit_price']}")
            print(f"  P&L: {trade['pnl_usd']:.2f} USD ({trade['pnl_pct']:.2f}%)")
        else:
            print("✗ Failed to retrieve trade")
            return False
        
        # Test drawing save
        print("\nTesting drawing save...")
        drawing_data = {
            "type": "trendline",
            "points": [
                {"time": 1234567890, "price": 1.08500},
                {"time": 1234567900, "price": 1.08600}
            ],
            "style": {"color": "#00ff00", "width": 2}
        }
        
        import json
        drawing_id = journal_db.save_drawing(
            trade_id=trade_id,
            drawing_type="trendline",
            drawing_data=json.dumps(drawing_data),
            account_id=account_id,
            symbol="EURUSD",
            timeframe="H1"
        )
        
        print(f"✓ Drawing saved successfully! ID: {drawing_id}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_manual_trade()
    sys.exit(0 if success else 1)
