#!/usr/bin/env python3
"""
Monte Carlo Simulation
Simulates trading outcomes based on historical performance
"""
import json
import random
import sys
import os
from typing import Dict, List, Optional

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot import journal_db


def run_monte_carlo_simulation(
    account_id: int,
    num_simulations: int = 1000,
    num_trades: int = 100,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
) -> Dict:
    """
    Run Monte Carlo simulation on trading performance
    
    Args:
        account_id: Trading account ID
        num_simulations: Number of simulation runs
        num_trades: Number of trades per simulation
        from_ts: Start timestamp for historical data
        to_ts: End timestamp for historical data
    
    Returns:
        Dictionary with simulation results
    """
    # Get historical trades
    trades = journal_db.get_all_trades(account_id=account_id, from_ts=from_ts, to_ts=to_ts)
    closed_trades = [t for t in trades if t["outcome"] != "OPEN"]
    
    if not closed_trades:
        return {
            "status": "error",
            "message": "No closed trades for simulation",
        }
    
    # Extract P&L percentages
    pnl_pcts = [t.get("pnl_pct", 0) for t in closed_trades]
    
    if not pnl_pcts:
        return {
            "status": "error",
            "message": "No P&L data available",
        }
    
    # Get account info
    account = journal_db.get_account(account_id)
    initial_balance = account["initial_balance"]
    
    # Run simulations
    final_balances = []
    max_drawdowns = []
    
    for _ in range(num_simulations):
        balance = initial_balance
        peak = initial_balance
        max_dd = 0
        
        for _ in range(num_trades):
            # Randomly sample from historical P&L distribution
            pnl_pct = random.choice(pnl_pcts)
            
            # Apply P&L to balance
            balance += balance * (pnl_pct / 100)
            
            # Track drawdown
            if balance > peak:
                peak = balance
            
            dd = ((peak - balance) / peak) * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        final_balances.append(balance)
        max_drawdowns.append(max_dd)
    
    # Calculate statistics
    final_balances = np.array(final_balances)
    max_drawdowns = np.array(max_drawdowns)
    
    results = {
        "status": "success",
        "num_simulations": num_simulations,
        "num_trades": num_trades,
        "initial_balance": initial_balance,
        "final_balance": {
            "mean": float(np.mean(final_balances)),
            "median": float(np.median(final_balances)),
            "std": float(np.std(final_balances)),
            "min": float(np.min(final_balances)),
            "max": float(np.max(final_balances)),
            "percentile_5": float(np.percentile(final_balances, 5)),
            "percentile_25": float(np.percentile(final_balances, 25)),
            "percentile_75": float(np.percentile(final_balances, 75)),
            "percentile_95": float(np.percentile(final_balances, 95)),
        },
        "max_drawdown": {
            "mean": float(np.mean(max_drawdowns)),
            "median": float(np.median(max_drawdowns)),
            "std": float(np.std(max_drawdowns)),
            "min": float(np.min(max_drawdowns)),
            "max": float(np.max(max_drawdowns)),
            "percentile_95": float(np.percentile(max_drawdowns, 95)),
        },
        "probability_of_profit": float(np.sum(final_balances > initial_balance) / num_simulations * 100),
        "probability_of_ruin": float(np.sum(final_balances < initial_balance * 0.5) / num_simulations * 100),
    }
    
    # Save to database
    journal_db.save_monte_carlo_run(
        account_id=account_id,
        num_simulations=num_simulations,
        num_trades=num_trades,
        initial_balance=initial_balance,
        results=json.dumps(results),
    )
    
    return results


def get_risk_of_ruin(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    risk_per_trade_pct: float,
    num_trades: int = 100,
) -> float:
    """
    Calculate risk of ruin
    
    Args:
        win_rate: Win rate as percentage (0-100)
        avg_win: Average win amount
        avg_loss: Average loss amount
        risk_per_trade_pct: Risk per trade as percentage
        num_trades: Number of trades to simulate
    
    Returns:
        Risk of ruin as percentage
    """
    if avg_loss == 0:
        return 0.0
    
    # Calculate win/loss ratio
    win_loss_ratio = avg_win / abs(avg_loss)
    
    # Calculate probability of ruin using simplified formula
    p_win = win_rate / 100
    p_loss = 1 - p_win
    
    if win_loss_ratio >= 1:
        # Favorable odds
        risk_of_ruin = (p_loss / p_win) ** (100 / risk_per_trade_pct)
    else:
        # Unfavorable odds
        risk_of_ruin = 1.0
    
    return min(risk_of_ruin * 100, 100.0)
