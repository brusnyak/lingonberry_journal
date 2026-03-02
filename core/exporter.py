#!/usr/bin/env python3
"""
ML Dataset Exporter
Exports trading data for machine learning analysis
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import journal_db

EXPORT_DIR = Path("data/exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def export_ml_dataset(
    account_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict[str, any]:
    """
    Export trading data as ML dataset
    
    Returns:
        Dictionary with export metadata and file path
    """
    # Get trades
    trades = journal_db.get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    closed_trades = [t for t in trades if t["outcome"] != "OPEN"]
    
    if not closed_trades:
        return {"status": "error", "message": "No closed trades to export"}
    
    # Convert to DataFrame
    df = pd.DataFrame(closed_trades)
    
    # Feature engineering
    df["hour"] = pd.to_datetime(df["ts_open"]).dt.hour
    df["day_of_week"] = pd.to_datetime(df["ts_open"]).dt.dayofweek
    df["is_win"] = (df["pnl_usd"] > 0).astype(int)
    df["has_sl"] = df["sl_price"].notna().astype(int)
    df["has_tp"] = df["tp_price"].notna().astype(int)
    
    # Calculate risk/reward
    df["risk_reward"] = 0.0
    for idx, row in df.iterrows():
        if row["direction"] == "LONG" and row["sl_price"] and row["tp_price"]:
            risk = row["entry_price"] - row["sl_price"]
            reward = row["tp_price"] - row["entry_price"]
            if risk > 0:
                df.at[idx, "risk_reward"] = reward / risk
        elif row["direction"] == "SHORT" and row["sl_price"] and row["tp_price"]:
            risk = row["sl_price"] - row["entry_price"]
            reward = row["entry_price"] - row["tp_price"]
            if risk > 0:
                df.at[idx, "risk_reward"] = reward / risk
    
    # Select features for ML
    feature_columns = [
        "symbol", "direction", "session", "timeframe", "strategy",
        "hour", "day_of_week", "has_sl", "has_tp", "risk_reward",
        "position_size", "pnl_usd", "pnl_pct", "outcome", "is_win"
    ]
    
    ml_df = df[feature_columns].copy()
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ml_dataset_{timestamp}.csv"
    filepath = EXPORT_DIR / filename
    
    # Export to CSV
    ml_df.to_csv(filepath, index=False)
    
    # Generate metadata
    metadata = {
        "status": "success",
        "filepath": str(filepath),
        "filename": filename,
        "total_trades": len(closed_trades),
        "features": feature_columns,
        "date_range": {
            "from": df["ts_open"].min(),
            "to": df["ts_open"].max(),
        },
        "statistics": {
            "win_rate": (df["is_win"].sum() / len(df)) * 100,
            "total_pnl": df["pnl_usd"].sum(),
            "avg_pnl": df["pnl_usd"].mean(),
        },
    }
    
    # Save metadata
    metadata_path = EXPORT_DIR / f"ml_dataset_{timestamp}_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    return metadata


def export_trades_json(
    account_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict[str, any]:
    """Export trades as JSON"""
    trades = journal_db.get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"trades_{timestamp}.json"
    filepath = EXPORT_DIR / filename
    
    with open(filepath, "w") as f:
        json.dump(trades, f, indent=2)
    
    return {
        "status": "success",
        "filepath": str(filepath),
        "filename": filename,
        "total_trades": len(trades),
    }
