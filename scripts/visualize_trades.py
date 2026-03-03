#!/usr/bin/env python3
"""
Visualize Trades on Charts
Creates multi-timeframe charts with long/short position markers
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from infra.ctrader_client import CTraderClient

# Output directory
OUTPUT_DIR = Path("data/reports")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def plot_candlestick_chart(
    df: pd.DataFrame,
    trade: dict,
    timeframe: str,
    output_path: Path
):
    """
    Plot premium dark theme candlestick chart with trade markers
    
    Args:
        df: DataFrame with OHLCV data
        trade: Trade dict with entry, exit, SL, TP
        timeframe: Timeframe label (e.g., "4H", "30M", "5M")
        output_path: Where to save the chart
    """
    # Set dark theme
    plt.style.use('dark_background')
    
    fig, ax = plt.subplots(figsize=(18, 10), facecolor='#0a0e27')
    ax.set_facecolor('#0a0e27')
    
    # Plot candlesticks with premium colors
    for idx, row in df.iterrows():
        is_bullish = row['close'] >= row['open']
        candle_color = '#00ff88' if is_bullish else '#ff3366'
        wick_color = '#00ff88' if is_bullish else '#ff3366'
        
        # High-Low wick
        ax.plot([row['time'], row['time']], [row['low'], row['high']], 
               color=wick_color, linewidth=1.2, alpha=0.8, zorder=1)
        
        # Candle body
        body_height = abs(row['close'] - row['open'])
        body_bottom = min(row['open'], row['close'])
        
        if body_height > 0:
            ax.add_patch(Rectangle(
                (mdates.date2num(row['time']), body_bottom),
                0.0004,
                body_height,
                facecolor=candle_color,
                edgecolor=candle_color,
                alpha=0.9,
                zorder=2
            ))
        else:
            # Doji
            ax.plot([row['time'], row['time']], [row['open'], row['open']], 
                   color=candle_color, linewidth=2, alpha=0.9, zorder=2)
    
    # Trade markers
    entry_time = trade['open_time']
    exit_time = trade.get('close_time')
    entry_price = trade['entry_price']
    exit_price = trade.get('exit_price')
    direction = trade['direction']
    pnl = trade.get('pnl', 0)
    
    # Colors based on direction
    if direction == 'LONG':
        entry_color = '#00b8ff'
    else:
        entry_color = '#ff9500'
    
    sl_color = '#ff3366'
    tp_color = '#00ff88'
    
    # Entry line
    ax.axhline(y=entry_price, color=entry_color, linestyle='-', linewidth=2.5, 
              alpha=0.9, zorder=3)
    ax.axvline(x=entry_time, color=entry_color, linestyle=':', linewidth=1.5, 
              alpha=0.4, zorder=1)
    
    # Exit line
    if exit_time and exit_price:
        exit_color = tp_color if pnl > 0 else sl_color
        ax.axhline(y=exit_price, color=exit_color, linestyle='-', linewidth=2.5, 
                  alpha=0.9, zorder=3)
        ax.axvline(x=exit_time, color=exit_color, linestyle=':', linewidth=1.5, 
                  alpha=0.4, zorder=1)
    
    # SL/TP lines
    if trade.get('sl_price'):
        ax.axhline(y=trade['sl_price'], color=sl_color, linestyle='--', 
                  linewidth=2, alpha=0.8, zorder=3)
    
    if trade.get('tp_price'):
        ax.axhline(y=trade['tp_price'], color=tp_color, linestyle='--', 
                  linewidth=2, alpha=0.8, zorder=3)
    
    # Direction badge
    badge_x = entry_time
    badge_y = entry_price
    
    if direction == 'SHORT':
        ax.annotate('', xy=(badge_x, badge_y * 0.9995), xytext=(badge_x, badge_y),
                   arrowprops=dict(arrowstyle='->', color=entry_color, lw=3),
                   zorder=5)
        badge_text = '▼ SHORT'
        badge_y_offset = badge_y * 1.0003
    else:
        ax.annotate('', xy=(badge_x, badge_y * 1.0005), xytext=(badge_x, badge_y),
                   arrowprops=dict(arrowstyle='->', color=entry_color, lw=3),
                   zorder=5)
        badge_text = '▲ LONG'
        badge_y_offset = badge_y * 0.9997
    
    ax.text(badge_x, badge_y_offset, badge_text,
           color='#ffffff', fontsize=13, fontweight='bold',
           horizontalalignment='center',
           bbox=dict(boxstyle='round,pad=0.6', facecolor=entry_color, 
                    edgecolor='#ffffff', linewidth=2, alpha=0.95),
           zorder=6)
    
    # Info panel
    symbol = trade['symbol']
    info_lines = [
        f"{symbol} • {direction} • {timeframe}",
        f"",
        f"Entry: {entry_price:.5f}",
    ]
    
    if exit_price:
        info_lines.append(f"Exit: {exit_price:.5f}")
        info_lines.append(f"P&L: {pnl:.2f}")
    
    info_text = '\n'.join(info_lines)
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
           fontsize=12, verticalalignment='top',
           color='#ffffff', fontweight='bold',
           bbox=dict(boxstyle='round,pad=0.8', facecolor='#1a1f3a', 
                    edgecolor='#3d4466', linewidth=2, alpha=0.95),
           zorder=10)
    
    # Title
    title_text = f"{symbol} • {direction} Position • {timeframe} Chart"
    ax.text(0.5, 1.02, title_text, transform=ax.transAxes,
           fontsize=16, fontweight='bold', color='#ffffff',
           horizontalalignment='center')
    
    # Styling
    ax.set_xlabel('Time', fontsize=12, color='#8892b0', fontweight='bold')
    ax.set_ylabel('Price', fontsize=12, color='#8892b0', fontweight='bold')
    ax.grid(True, alpha=0.1, linestyle='-', linewidth=0.5, color='#3d4466')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    ax.tick_params(colors='#8892b0', labelsize=10)
    
    for spine in ax.spines.values():
        spine.set_edgecolor('#3d4466')
        spine.set_linewidth(1.5)
    
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#0a0e27')
    plt.close()
    
    print(f"  ✅ Saved chart: {output_path.name}")


def visualize_trade(trade_data: dict, client: CTraderClient):
    """
    Create 3-timeframe charts for a trade
    
    Args:
        trade_data: Trade dict from cTrader
        client: Connected cTrader client
    """
    symbol = trade_data['symbolName']
    open_time = pd.to_datetime(trade_data['openTimestamp'], unit='ms')
    close_time = pd.to_datetime(trade_data['closeTimestamp'], unit='ms')
    
    print(f"\n📊 Visualizing trade: {symbol} {trade_data['tradeSide']}")
    print(f"   Opened: {open_time}")
    print(f"   Closed: {close_time}")
    print(f"   P&L: {trade_data.get('grossProfit', 0):.2f}")
    
    # Prepare trade dict
    trade = {
        'symbol': symbol,
        'direction': 'LONG' if trade_data['tradeSide'] == 'BUY' else 'SHORT',
        'entry_price': trade_data['entryPrice'],
        'exit_price': trade_data.get('closePrice'),
        'open_time': open_time,
        'close_time': close_time,
        'pnl': trade_data.get('grossProfit', 0),
        'sl_price': trade_data.get('stopLoss'),
        'tp_price': trade_data.get('takeProfit'),
    }
    
    # Timeframes to generate
    timeframes = [
        ('H4', '4H'),
        ('M30', '30M'),
        ('M5', '5M'),
    ]
    
    # Fetch data for each timeframe
    from_ts = open_time - timedelta(days=7)  # 7 days before trade
    to_ts = close_time + timedelta(hours=12)  # 12 hours after trade
    
    for ct_tf, label in timeframes:
        print(f"\n  Generating {label} chart...")
        
        # Fetch trendbars
        trendbars = client.get_trendbars(
            symbol=symbol,
            timeframe=ct_tf,
            from_ts=from_ts,
            to_ts=to_ts,
            count=1000
        )
        
        if not trendbars:
            print(f"    ⚠️ No data available for {label}")
            continue
        
        # Convert to DataFrame
        df = pd.DataFrame(trendbars)
        df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Create chart
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = OUTPUT_DIR / f"trade_{symbol}_{label}_{timestamp}.png"
        
        plot_candlestick_chart(df, trade, label, output_path)


def main():
    """Main function"""
    print("\n📈 Trade Visualization Tool\n")
    
    # Connect to cTrader
    client = CTraderClient()
    if not client.connect():
        print("❌ Connection failed")
        return
    
    try:
        # Fetch recent trades
        print("Fetching recent trades...")
        to_ts = datetime.now(timezone.utc)
        from_ts = to_ts - timedelta(days=30)
        
        trades = client.get_closed_positions(from_ts=from_ts, to_ts=to_ts, limit=5)
        
        if not trades:
            print("⚠️ No trades found in the last 30 days")
            return
        
        print(f"✅ Found {len(trades)} trade(s)")
        print("\nGenerating charts for the most recent trade...")
        
        # Visualize the most recent trade
        latest_trade = trades[0]
        visualize_trade(latest_trade, client)
        
        print("\n" + "=" * 60)
        print("✅ Visualization complete!")
        print("=" * 60)
        print(f"\nCharts saved to: {OUTPUT_DIR.absolute()}")
        
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
