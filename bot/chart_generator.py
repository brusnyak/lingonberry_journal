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


def _trade_value(trade: Dict, primary: str, fallback: str):
    value = trade.get(primary)
    if value is None:
        value = trade.get(fallback)
    return value


def _to_utc_dt(value: Optional[str]) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _candle_width_days(df: pd.DataFrame) -> float:
    if len(df) < 2:
        return 0.001
    deltas = df["ts"].sort_values().diff().dropna().dt.total_seconds()
    if deltas.empty:
        return 0.001
    median_seconds = float(deltas.median())
    # 65% of interval to keep small gap between candles
    width_days = (median_seconds * 0.65) / 86400.0
    # Ensure minimum visible width
    return max(width_days, 0.0001)


def _plot_trade_overlay(ax, trade: Dict, ts_open: datetime, ts_close: datetime) -> None:
    entry_price = float(_trade_value(trade, "entry_price", "entry") or 0)
    sl_price = _trade_value(trade, "sl_price", "sl")
    tp_price = _trade_value(trade, "tp_price", "tp")
    exit_price = trade.get("exit_price")
    direction = str(trade.get("direction", "")).upper()
    is_long = direction == "LONG"
    entry_color = "#10b981" if is_long else "#f97316"

    ax.axhline(y=entry_price, color=entry_color, linestyle="-", linewidth=1.8, alpha=0.95, label=f"Entry {entry_price:.5f}")
    ax.axvline(x=ts_open, color=entry_color, linestyle="--", linewidth=1.0, alpha=0.45)

    # TradingView-like position boxes
    end_x = ts_close if ts_close > ts_open else ts_open + timedelta(hours=1)
    x0 = mdates.date2num(ts_open)
    width = max(1e-6, mdates.date2num(end_x) - x0)
    if sl_price is not None:
        loss_bottom = min(entry_price, float(sl_price))
        loss_height = abs(entry_price - float(sl_price))
        if loss_height > 0:
            ax.add_patch(Rectangle((x0, loss_bottom), width, loss_height, facecolor="#ef4444", edgecolor="none", alpha=0.14))
        ax.axhline(y=float(sl_price), color="#ef4444", linestyle="--", linewidth=1.2, alpha=0.9, label=f"SL {float(sl_price):.5f}")
    if tp_price is not None:
        reward_bottom = min(entry_price, float(tp_price))
        reward_height = abs(entry_price - float(tp_price))
        if reward_height > 0:
            ax.add_patch(Rectangle((x0, reward_bottom), width, reward_height, facecolor="#22c55e", edgecolor="none", alpha=0.14))
        ax.axhline(y=float(tp_price), color="#22c55e", linestyle="--", linewidth=1.2, alpha=0.9, label=f"TP {float(tp_price):.5f}")

    if exit_price is not None:
        exit_color = "#22c55e" if (float(exit_price) >= entry_price if is_long else float(exit_price) <= entry_price) else "#ef4444"
        ax.axhline(y=float(exit_price), color=exit_color, linestyle=":", linewidth=1.3, alpha=0.95, label=f"Exit {float(exit_price):.5f}")
        ax.axvline(x=ts_close, color=exit_color, linestyle=":", linewidth=1.0, alpha=0.4)

    marker = "^" if is_long else "v"
    ax.scatter([ts_open], [entry_price], marker=marker, s=90, color=entry_color, edgecolor="white", linewidth=0.6, zorder=5)
    if exit_price is not None:
        ax.scatter([ts_close], [float(exit_price)], marker="o", s=45, color="#f8fafc", edgecolor="#0f172a", linewidth=0.8, zorder=5)


def _render_chart(df: pd.DataFrame, trade: Dict, timeframe: str, output_path: str) -> bool:
    """Render TradingView-style chart with position boxes"""
    if df.empty:
        return False
    
    from bot.tradingview_chart import create_tradingview_chart, save_chart
    
    # Prepare data
    df_chart = df.copy()
    df_chart = df_chart.rename(columns={'ts': 'datetime'})
    
    # Get trade details
    direction = str(trade.get("direction", "")).upper()
    entry_price = float(trade.get("entry_price") or trade.get("entry") or 0)
    sl_price = trade.get("sl_price") or trade.get("sl")
    tp_price = trade.get("tp_price") or trade.get("tp")
    exit_price = trade.get("exit_price")
    symbol = trade.get("symbol", "UNKNOWN")
    
    # Create chart
    fig = create_tradingview_chart(
        df=df_chart,
        title=f'{symbol} - {direction} - {timeframe}',
        show_volume=False,
        figsize=(16, 9),
        entry_price=entry_price,
        exit_price=exit_price,
        sl_price=float(sl_price) if sl_price else None,
        tp_price=float(tp_price) if tp_price else None,
        direction=direction.lower()
    )
    
    # Save
    save_chart(fig, output_path, dpi=150)
    return True


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
        ts_open = _to_utc_dt(trade.get("ts_open"))
        ts_close = _to_utc_dt(trade.get("ts_close")) if trade.get("ts_close") else datetime.now(timezone.utc)
        start = ts_open - timedelta(weeks=context_weeks)
        end = ts_close + timedelta(days=1)
        df = load_ohlcv_with_cache(
            symbol=trade["symbol"],
            asset_type=trade.get("asset_type", "forex"),
            timeframe=timeframe,
            start=start,
            end=end,
        )
        return _render_chart(df=df, trade=trade, timeframe=timeframe, output_path=output_path)
        
    except Exception as e:
        print(f"Error generating chart: {e}")
        return False


def generate_trade_charts(
    trade: Dict,
    output_dir: str,
    context_weeks: int = 1,
    timeframe: Optional[str] = None,
) -> List[str]:
    """Generate 3 timeframe charts (TradingView-like overlay style)."""
    os.makedirs(output_dir, exist_ok=True)
    direction = str(trade.get("direction", "")).upper() or "TRADE"
    symbol = trade.get("symbol", "UNKNOWN")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if timeframe:
        timeframes = [timeframe]
    else:
        timeframes = ["H4", "M30", "M5"]

    paths: List[str] = []
    for tf in timeframes:
        chart_name = f"trade_{symbol}_{direction}_{tf}_{ts}.png"
        chart_path = os.path.join(output_dir, chart_name)
        ok = generate_trade_chart(trade=trade, output_path=chart_path, context_weeks=context_weeks, timeframe=tf)
        if ok:
            paths.append(chart_path)
    return paths


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
