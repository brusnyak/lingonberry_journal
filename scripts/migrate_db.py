#!/usr/bin/env python3
import sqlite3
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot import journal_db

def migrate():
    conn = journal_db.get_connection()
    cursor = conn.cursor()
    
    # 1. Accounts table harmonization
    cursor.execute("PRAGMA table_info(accounts)")
    columns = {row[1] for row in cursor.fetchall()}
    
    # Add missing risk columns
    missing_cols = {
        "max_daily_loss_pct": "REAL DEFAULT 5.0",
        "max_total_loss_pct": "REAL DEFAULT 10.0",
        "profit_target_pct": "REAL DEFAULT 10.0",
        "risk_per_trade_pct": "REAL DEFAULT 1.0",
        "timezone_name": "TEXT DEFAULT 'UTC'"
    }
    
    for col, type_def in missing_cols.items():
        if col not in columns:
            print(f"Adding column {col} to accounts...")
            cursor.execute(f"ALTER TABLE accounts ADD COLUMN {col} {type_def}")
            
    # Handle timezone column name mismatch if 'timezone' exists but 'timezone_name' doesn't
    if 'timezone' in columns and 'timezone_name' not in columns:
        print("Migrating timezone to timezone_name...")
        cursor.execute("UPDATE accounts SET timezone_name = timezone")
        
    # 2. Trades table harmonization
    cursor.execute("PRAGMA table_info(trades)")
    columns = {row[1] for row in cursor.fetchall()}
    
    if "chart_path" not in columns:
        print("Adding chart_path to trades...")
        cursor.execute("ALTER TABLE trades ADD COLUMN chart_path TEXT")
        
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
