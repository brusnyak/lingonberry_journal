#!/usr/bin/env python3
import os
import sys
import sqlite3
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from bot import journal_db

def backfill():
    print("Starting chart path backfill...")
    conn = journal_db.get_connection()
    cursor = conn.cursor()
    
    # Get all trades without chart_path
    cursor.execute("SELECT id, symbol, direction, ts_open FROM trades WHERE chart_path IS NULL OR chart_path = ''")
    trades = cursor.fetchall()
    
    print(f"Found {len(trades)} trades to process.")
    
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reports")
    if not os.path.exists(reports_dir):
        print(f"Reports directory not found: {reports_dir}")
        return

    files = os.listdir(reports_dir)
    
    updated_count = 0
    for t in trades:
        trade_id, symbol, direction, ts_open = t
        
        # Try to find matching files
        # Filename format: trade_EURUSD_SHORT_M30_20260303_202908.png
        # We search for trade_{symbol}_{direction}_{any}_{date}_
        
        # Extract date from ts_open (e.g. 2026-02-28T11:49:13 -> 20260228)
        try:
            dt = datetime.fromisoformat(ts_open.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y%m%d")
        except:
            continue
            
        matches = []
        pattern = f"trade_{symbol.upper()}_{direction.upper()}"
        for f in files:
            if f.startswith(pattern) and date_str in f:
                matches.append(f)
        
        if matches:
            chart_path = ",".join(matches)
            cursor.execute("UPDATE trades SET chart_path = ? WHERE id = ?", (chart_path, trade_id))
            updated_count += 1
            print(f"Updated trade {trade_id} ({symbol}) with {len(matches)} charts.")
            
    conn.commit()
    conn.close()
    print(f"Backfill complete. Updated {updated_count} trades.")

if __name__ == "__main__":
    backfill()
