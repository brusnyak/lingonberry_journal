#!/usr/bin/env python3
"""
Simple Chart Generator (Fallback)
Generates basic charts without external market data
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timezone
from typing import Dict, List


def generate_simple_trade_chart(trade: Dict, output_path: str) -> bool:
    """Generate a simple trade visualization"""
    try:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        entry_price = trade["entry_price"]
        exit_price = trade.get("exit_price", entry_price)
        sl_price = trade.get("sl_price")
        tp_price = trade.get("tp_price")
        
        # Plot horizontal lines
        ax.axhline(y=entry_price, color='blue', linewidth=2, label=f'Entry: {entry_price}')
        
        if exit_price != entry_price:
            ax.axhline(y=exit_price, color='orange', linewidth=2, label=f'Exit: {exit_price}')
        
        if sl_price:
            ax.axhline(y=sl_price, color='red', linestyle='--', linewidth=1.5, label=f'SL: {sl_price}')
        
        if tp_price:
            ax.axhline(y=tp_price, color='green', linestyle='--', linewidth=1.5, label=f'TP: {tp_price}')
        
        # Set title and labels
        direction = trade["direction"]
        symbol = trade["symbol"]
        pnl = trade.get("pnl_usd", 0)
        pnl_pct = trade.get("pnl_pct", 0)
        
        title = f"{symbol} - {direction}\nP&L: ${pnl:.2f} ({pnl_pct:.2f}%)"
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_ylabel('Price', fontsize=12)
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        return True
        
    except Exception as e:
        print(f"Error generating simple chart: {e}")
        return False


def generate_simple_equity_curve(trades: List[Dict], initial_balance: float, output_path: str) -> bool:
    """Generate a simple equity curve"""
    try:
        closed_trades = [t for t in trades if t["outcome"] != "OPEN"]
        closed_trades = sorted(closed_trades, key=lambda x: x.get("ts_close", ""))
        
        if not closed_trades:
            return False
        
        # Calculate equity
        equity = [initial_balance]
        labels = ["Start"]
        
        balance = initial_balance
        for i, trade in enumerate(closed_trades):
            balance += trade.get("pnl_usd", 0)
            equity.append(balance)
            labels.append(f"T{i+1}")
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(range(len(equity)), equity, marker='o', linewidth=2, color='blue')
        ax.axhline(y=initial_balance, color='gray', linestyle='--', linewidth=1)
        
        ax.set_title('Equity Curve', fontsize=14, fontweight='bold')
        ax.set_xlabel('Trade Number', fontsize=12)
        ax.set_ylabel('Balance', fontsize=12)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        return True
        
    except Exception as e:
        print(f"Error generating simple equity curve: {e}")
        return False
