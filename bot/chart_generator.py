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
    if df.empty:
        return False
    ts_open = _to_utc_dt(trade.get("ts_open"))
    ts_close = _to_utc_dt(trade.get("ts_close")) if trade.get("ts_close") else datetime.now(timezone.utc)
    direction = str(trade.get("direction", "")).upper()

    fig, ax = plt.subplots(figsize=(16, 8), facecolor="#0b1220")
    ax.set_facecolor("#0f172a")
    candle_width = _candle_width_days(df)

    for _, row in df.iterrows():
        bullish = row["close"] >= row["open"]
        color = "#22c55e" if bullish else "#ef4444"
        ax.plot([row["ts"], row["ts"]], [row["low"], row["high"]], color=color, linewidth=0.8, alpha=0.85, zorder=1)
        body_bottom = min(row["open"], row["close"])
        body_height = max(abs(row["close"] - row["open"]), 1e-8)
        ax.add_patch(
            Rectangle(
                (mdates.date2num(row["ts"]) - candle_width / 2.0, body_bottom),
                candle_width,
                body_height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.5,
                alpha=0.95,
                zorder=2,
            )
        )

    _plot_trade_overlay(ax, trade, ts_open=ts_open, ts_close=ts_close)
    ax.set_title(
        f"{trade.get('symbol', 'UNKNOWN')} - {direction} - {timeframe}",
        fontsize=14,
        color="#e2e8f0",
        fontweight="bold",
    )
    ax.set_xlabel("Time", color="#94a3b8")
    ax.set_ylabel("Price", color="#94a3b8")
    ax.grid(True, alpha=0.18, color="#334155")
    ax.tick_params(colors="#94a3b8", labelsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))

    handles, labels = ax.get_legend_handles_labels()
    dedup = {}
    for h, l in zip(handles, labels):
        dedup[l] = h
    if dedup:
        ax.legend(
            dedup.values(),
            dedup.keys(),
            loc="upper left",
            frameon=True,
            facecolor="#0b1220",
            edgecolor="#334155",
            labelcolor="#e2e8f0",
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="#0b1220")
    plt.close()
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
