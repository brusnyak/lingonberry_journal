#!/usr/bin/env python3
"""
Chart Generator with Market Data
Generates trading charts with technical indicators
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from infra.market_data import load_ohlcv_with_cache, get_timeframe_for_asset


def generate_trade_chart(
    trade: Dict,
    output_path: str,
    context_weeks: int = 1,
    timeframe: Optional[str] = None,
) -> bool:
    """Generate a chart for a trade with market data"""
    try:
        if timeframe is None:
            timeframe = trade.get("timeframe") or get_timeframe_for_asset(trade.get("asset_type", "forex"))
        
        # Calculate time window
        ts_open = datetime.fromisoformat(trade["ts_open"].replace("Z", "+00:00"))
        ts_close = datetime.fromisoformat(trade["ts_close"].replace("Z", "+00:00")) if trade.get("ts_close") else datetime.now(timezone.utc)
        
        start = ts_open - timedelta(weeks=context_weeks)
        end = ts_close + timedelta(days=1)
        
        # Load market data
        df = load_ohlcv_with_cache(
            symbol=trade["symbol"],
            asset_type=trade.get("asset_type", "forex"),
            timeframe=timeframe,
            start=start,
            end=end,
        )
        
        if df.empty:
            return False
        
        # Create figure
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Plot candlesticks
        for idx, row in df.iterrows():
            color = 'green' if row['close'] >= row['open'] else 'red'
            ax.plot([row['ts'], row['ts']], [row['low'], row['high']], color=color, linewidth=0.5)
            ax.add_patch(Rectangle(
                (mdates.date2num(row['ts']), min(row['open'], row['close'])),
                0.0003,
                abs(row['close'] - row['open']),
                facecolor=color,
                edgecolor=color
            ))
        
        # Mark entry and exit
        entry_price = trade["entry_price"]
        ax.axhline(y=entry_price, color='blue', linestyle='--', linewidth=1, label=f'Entry: {entry_price}')
        ax.axvline(x=ts_open, color='blue', linestyle='--', linewidth=1, alpha=0.5)
        
        if trade.get("exit_price"):
            exit_price = trade["exit_price"]
            ax.axhline(y=exit_price, color='orange', linestyle='--', linewidth=1, label=f'Exit: {exit_price}')
            ax.axvline(x=ts_close, color='orange', linestyle='--', linewidth=1, alpha=0.5)
        
        # Mark SL/TP
        if trade.get("sl_price"):
            ax.axhline(y=trade["sl_price"], color='red', linestyle=':', linewidth=1, label=f'SL: {trade["sl_price"]}')
        
        if trade.get("tp_price"):
            ax.axhline(y=trade["tp_price"], color='green', linestyle=':', linewidth=1, label=f'TP: {trade["tp_price"]}')
        
        # Formatting
        ax.set_title(f"{trade['symbol']} - {trade['direction']} - {timeframe}", fontsize=14, fontweight='bold')
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Price', fontsize=12)
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return True
        
    except Exception as e:
        print(f"Error generating chart: {e}")
        return False


def generate_equity_curve(
    trades: List[Dict],
    initial_balance: float,
    output_path: str,
) -> bool:
    """Generate equity curve chart"""
    try:
        if not trades:
            return False
        
        closed_trades = [t for t in trades if t["outcome"] != "OPEN" and t.get("ts_close")]
        closed_trades = sorted(closed_trades, key=lambda x: x["ts_close"])
        
        if not closed_trades:
            return False
        
        # Calculate equity curve
        equity = [initial_balance]
        timestamps = [datetime.fromisoformat(closed_trades[0]["ts_close"].replace("Z", "+00:00"))]
        
        balance = initial_balance
        for trade in closed_trades:
            balance += trade.get("pnl_usd", 0)
            equity.append(balance)
            timestamps.append(datetime.fromisoformat(trade["ts_close"].replace("Z", "+00:00")))
        
        # Create figure
        fig, ax = plt.subplots(figsize=(14, 6))
        
        ax.plot(timestamps, equity, linewidth=2, color='blue', label='Equity')
        ax.axhline(y=initial_balance, color='gray', linestyle='--', linewidth=1, label='Initial Balance')
        
        # Fill area
        ax.fill_between(timestamps, equity, initial_balance, where=[e >= initial_balance for e in equity], 
                        color='green', alpha=0.2, label='Profit')
        ax.fill_between(timestamps, equity, initial_balance, where=[e < initial_balance for e in equity], 
                        color='red', alpha=0.2, label='Loss')
        
        ax.set_title('Equity Curve', fontsize=14, fontweight='bold')
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Balance', fontsize=12)
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return True
        
    except Exception as e:
        print(f"Error generating equity curve: {e}")
        return False
