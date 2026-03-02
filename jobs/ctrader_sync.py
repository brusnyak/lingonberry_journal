#!/usr/bin/env python3
"""
cTrader Auto-Sync Job
Automatically syncs trades from cTrader at regular intervals
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import journal_db
from infra.ctrader_ingest import import_ctrader_trades, sync_open_positions

STATE_FILE = Path("data/.ctrader_sync_state.txt")


def load_last_sync_time() -> datetime:
    """Load last sync timestamp from state file"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                ts_str = f.read().strip()
                return datetime.fromisoformat(ts_str)
        except Exception:
            pass
    
    # Default to 7 days ago
    return datetime.now(timezone.utc) - timedelta(days=7)


def save_sync_time(ts: datetime) -> None:
    """Save sync timestamp to state file"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        f.write(ts.isoformat())


def run_sync_job(account_id: int) -> dict:
    """
    Run cTrader sync job
    
    Args:
        account_id: Journal account ID to sync to
    
    Returns:
        Dictionary with sync results
    """
    print(f"[{datetime.now()}] Starting cTrader sync job...")
    
    # Load last sync time
    last_sync = load_last_sync_time()
    now = datetime.now(timezone.utc)
    
    print(f"Last sync: {last_sync}")
    print(f"Syncing from {last_sync} to {now}")
    
    # Import closed trades
    import_result = import_ctrader_trades(
        account_id=account_id,
        from_ts=last_sync,
        to_ts=now,
    )
    
    print(f"Import result: {import_result}")
    
    # Sync open positions
    sync_result = sync_open_positions(account_id=account_id)
    
    print(f"Sync result: {sync_result}")
    
    # Save sync time
    save_sync_time(now)
    
    result = {
        "timestamp": now.isoformat(),
        "last_sync": last_sync.isoformat(),
        "imported": import_result,
        "synced": sync_result,
    }
    
    print(f"[{datetime.now()}] Sync job completed")
    
    return result


def run_continuous_sync(account_id: int, interval_seconds: int = 300):
    """
    Run continuous sync job
    
    Args:
        account_id: Journal account ID
        interval_seconds: Sync interval in seconds (default: 5 minutes)
    """
    print(f"Starting continuous cTrader sync (interval: {interval_seconds}s)")
    
    while True:
        try:
            run_sync_job(account_id)
        except Exception as e:
            print(f"Error in sync job: {e}")
        
        print(f"Sleeping for {interval_seconds} seconds...")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    # Get account ID from environment or command line
    account_id = int(os.getenv("JOURNAL_ACCOUNT_ID", "1"))
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "once":
            # Run once
            result = run_sync_job(account_id)
            print(f"Result: {result}")
        elif sys.argv[1] == "continuous":
            # Run continuously
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
            run_continuous_sync(account_id, interval)
    else:
        # Default: run once
        result = run_sync_job(account_id)
        print(f"Result: {result}")
