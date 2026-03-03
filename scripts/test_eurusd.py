#!/usr/bin/env python3
"""
Test EURUSD data fetch and mock trade visualization
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle

sys.path.insert(0, str(Path(__file__).parent.parent))


def generate_eurusd_data():
    """Generate realistic EURUSD 5-minute data for testing"""
    print("📊 Generating EURUSD 5-minute data...")
    
    # Generate data around the entry price 1.17385
    base_price = 1.17385
    
    # Generate 7 days of 5-minute candles
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=7)
    
    # Create time series (5-minute intervals)
    times = pd.date_range(start=start_time, end=end_time, freq='5min')
    
    num_candles = len(times)
    
    # Random walk for close prices around base_price
    np.random.seed(42)
    returns = np.random.normal(0, 0.00005, num_candles)  # Smaller movements
    close_prices = base_price + np.cumsum(returns)
    
    # Keep prices in realistic range around entry
    close_prices = np.clip(close_prices, base_price - 0.003, base_price + 0.003)
    
    # Generate OHLC from close prices
    data = []
    for i, (time, close) in enumerate(zip(times, close_prices)):
        # Add some randomness to OHLC
        spread = np.random.uniform(0.00005, 0.00015)
        open_price = close + np.random.uniform(-spread, spread)
        high_price = max(open_price, close) + np.random.uniform(0, spread)
        low_price = min(open_price, close) - np.random.uniform(0, spread)
        volume = np.random.randint(100, 1000)
        
        data.append({
            'time': time,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    
    print(f"✅ Generated {len(df)} candles")
    print(f"   Date range: {df['time'].min()} to {df['time'].max()}")
    print(f"   Price range: {df['low'].min():.5f} to {df['high'].max():.5f}")
    print(f"   Latest price: {df['close'].iloc[-1]:.5f}")
    
    # Save to CSV
    output_dir = Path("data/market_data")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = output_dir / "EURUSD_5m.csv"
    df.to_csv(csv_path, index=False)
    print(f"✅ Saved to: {csv_path}")
    
    return df


def plot_mock_trade(df, trade):
    """Plot mock trade on premium dark theme chart"""
    print(f"\n📈 Generating premium dark theme chart...")
    
    # Set dark theme
    plt.style.use('dark_background')
    
    fig, ax = plt.subplots(figsize=(18, 10), facecolor='#0a0e27')
    ax.set_facecolor('#0a0e27')
    
    # Filter data around trade time (show 4 hours before and 2 hours after)
    entry_time = trade['entry_time']
    start_window = entry_time - timedelta(hours=4)
    end_window = entry_time + timedelta(hours=2)
    
    df_window = df[(df['time'] >= start_window) & (df['time'] <= end_window)].copy()
    
    if df_window.empty:
        # If no data in window, use last 100 candles
        df_window = df.tail(100).copy()
    
    print(f"   Showing {len(df_window)} candles around trade time")
    
    # Plot candlesticks with premium colors
    for idx, row in df_window.iterrows():
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
            # Doji - draw a line
            ax.plot([row['time'], row['time']], [row['open'], row['open']], 
                   color=candle_color, linewidth=2, alpha=0.9, zorder=2)
    
    # Trade visualization
    entry_price = trade['entry_price']
    sl_price = trade['sl_price']
    tp_price = trade['tp_price']
    direction = trade['direction']
    
    # Calculate metrics - pip calculation for EURUSD
    # Counting each 0.00001 movement as 1 pip (pipette level)
    pips_to_tp = abs(entry_price - tp_price) * 100000
    pips_to_sl = abs(sl_price - entry_price) * 100000
    rr_ratio = pips_to_tp / pips_to_sl if pips_to_sl > 0 else 0
    
    # Entry zone with fill
    if direction == 'SHORT':
        # For SHORT: SL above, TP below
        entry_color = '#ff9500'
        sl_color = '#ff3366'
        tp_color = '#00ff88'
        
        # Fill risk zone (entry to SL) in red
        ax.fill_between(df_window['time'], entry_price, sl_price, 
                        color=sl_color, alpha=0.08, zorder=0)
        
        # Fill reward zone (entry to TP) in green
        ax.fill_between(df_window['time'], entry_price, tp_price, 
                        color=tp_color, alpha=0.08, zorder=0)
    else:
        # For LONG: SL below, TP above
        entry_color = '#00b8ff'
        sl_color = '#ff3366'
        tp_color = '#00ff88'
        
        # Fill risk zone (SL to entry) in red
        ax.fill_between(df_window['time'], sl_price, entry_price, 
                        color=sl_color, alpha=0.08, zorder=0)
        
        # Fill reward zone (entry to TP) in green
        ax.fill_between(df_window['time'], entry_price, tp_price, 
                        color=tp_color, alpha=0.08, zorder=0)
    
    # Entry line
    ax.axhline(y=entry_price, color=entry_color, linestyle='-', linewidth=2.5, 
              alpha=0.9, zorder=3)
    
    # SL line
    ax.axhline(y=sl_price, color=sl_color, linestyle='--', linewidth=2, 
              alpha=0.8, zorder=3)
    
    # TP line
    ax.axhline(y=tp_price, color=tp_color, linestyle='--', linewidth=2, 
              alpha=0.8, zorder=3)
    
    # Entry time vertical line
    ax.axvline(x=entry_time, color=entry_color, linestyle=':', linewidth=1.5, 
              alpha=0.4, zorder=1)
    
    # Labels on the right side with proper price formatting
    y_range = df_window['high'].max() - df_window['low'].min()
    x_max = df_window['time'].max()
    
    # Entry label - positioned to the right
    ax.text(1.01, entry_price, f'ENTRY {entry_price:.5f}', 
           transform=ax.get_yaxis_transform(),
           color=entry_color, fontsize=11, fontweight='bold',
           verticalalignment='center', horizontalalignment='left',
           bbox=dict(boxstyle='round,pad=0.5', facecolor='#0a0e27', 
                    edgecolor=entry_color, linewidth=2, alpha=0.95))
    
    # SL label - positioned to the right
    ax.text(1.01, sl_price, f'SL {sl_price:.5f}\n-{pips_to_sl:.0f} pips', 
           transform=ax.get_yaxis_transform(),
           color=sl_color, fontsize=10, fontweight='bold',
           verticalalignment='center', horizontalalignment='left',
           bbox=dict(boxstyle='round,pad=0.4', facecolor='#0a0e27', 
                    edgecolor=sl_color, linewidth=1.5, alpha=0.95))
    
    # TP label - positioned to the right
    ax.text(1.01, tp_price, f'TP {tp_price:.5f}\n+{pips_to_tp:.0f} pips', 
           transform=ax.get_yaxis_transform(),
           color=tp_color, fontsize=10, fontweight='bold',
           verticalalignment='center', horizontalalignment='left',
           bbox=dict(boxstyle='round,pad=0.4', facecolor='#0a0e27', 
                    edgecolor=tp_color, linewidth=1.5, alpha=0.95))
    
    # Direction badge at entry point
    badge_x = entry_time
    badge_y = entry_price
    
    if direction == 'SHORT':
        # For SHORT: place badge above entry, arrow points down
        badge_y_text = entry_price * 1.00015  # Slightly above
        ax.annotate('', xy=(badge_x, entry_price * 0.99985), xytext=(badge_x, entry_price),
                   arrowprops=dict(arrowstyle='->', color=entry_color, lw=4),
                   zorder=5)
        badge_text = '▼ SHORT'
    else:
        # For LONG: place badge below entry, arrow points up
        badge_y_text = entry_price * 0.99985  # Slightly below
        ax.annotate('', xy=(badge_x, entry_price * 1.00015), xytext=(badge_x, entry_price),
                   arrowprops=dict(arrowstyle='->', color=entry_color, lw=4),
                   zorder=5)
        badge_text = '▲ LONG'
    
    ax.text(badge_x, badge_y_text, badge_text,
           color='#ffffff', fontsize=14, fontweight='bold',
           horizontalalignment='center', verticalalignment='center',
           bbox=dict(boxstyle='round,pad=0.7', facecolor=entry_color, 
                    edgecolor='#ffffff', linewidth=2.5, alpha=0.95),
           zorder=6)
    
    # Info panel (top left)
    info_lines = [
        f"{'EURUSD'} • {direction} • 5M",
        f"",
        f"Risk/Reward: 1:{rr_ratio:.2f}",
        f"Risk: {pips_to_sl:.0f} pips",
        f"Reward: {pips_to_tp:.0f} pips",
    ]
    
    info_text = '\n'.join(info_lines)
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
           fontsize=12, verticalalignment='top',
           color='#ffffff', fontweight='bold',
           bbox=dict(boxstyle='round,pad=0.8', facecolor='#1a1f3a', 
                    edgecolor='#3d4466', linewidth=2, alpha=0.95),
           zorder=10)
    
    # Title
    title_text = f"EURUSD • {direction} Position • 5-Minute Chart"
    ax.text(0.5, 1.02, title_text, transform=ax.transAxes,
           fontsize=16, fontweight='bold', color='#ffffff',
           horizontalalignment='center')
    
    # Styling
    ax.set_xlabel('Time', fontsize=13, color='#8892b0', fontweight='bold', labelpad=10)
    ax.set_ylabel('Price', fontsize=13, color='#8892b0', fontweight='bold', labelpad=10)
    
    # Format y-axis to show 5 decimal places with proper spacing
    from matplotlib.ticker import FuncFormatter
    def price_formatter(x, p):
        return f'{x:.5f}'
    ax.yaxis.set_major_formatter(FuncFormatter(price_formatter))
    
    # Move y-axis to right side
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    
    # Set y-axis limits to show the trade range properly
    y_min = min(tp_price, df_window['low'].min()) * 0.9999
    y_max = max(sl_price, df_window['high'].max()) * 1.0001
    ax.set_ylim(y_min, y_max)
    
    ax.grid(True, alpha=0.1, linestyle='-', linewidth=0.5, color='#3d4466')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.tick_params(colors='#8892b0', labelsize=11, width=1.5, length=6)
    
    # Spine colors
    for spine in ax.spines.values():
        spine.set_edgecolor('#3d4466')
        spine.set_linewidth(1.5)
    
    plt.xticks(rotation=0)
    plt.tight_layout()
    
    # Save chart
    output_dir = Path("data/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    chart_path = output_dir / f"trade_EURUSD_{direction}_5M_{timestamp}.png"
    plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='#0a0e27')
    plt.close()
    
    print(f"✅ Premium dark theme chart saved: {chart_path}")
    return chart_path


def main():
    """Main test function"""
    print("=" * 60)
    print("EURUSD Data Fetch & Mock Trade Test")
    print("=" * 60)
    
    # Generate EURUSD data
    df = generate_eurusd_data()
    if df is None:
        return
    
    # Mock trade: Today 11:45, SELL EURUSD at 1.17385, SL 1.17485, TP 1.16800
    # Use today's date with 11:45 time
    today = datetime.now(timezone.utc).replace(hour=11, minute=45, second=0, microsecond=0)
    
    trade = {
        'symbol': 'EURUSD',
        'direction': 'SHORT',
        'entry_time': today,
        'entry_price': 1.17385,
        'sl_price': 1.17485,
        'tp_price': 1.16800,
    }
    
    print(f"\n📝 Mock Trade:")
    print(f"   Symbol: {trade['symbol']}")
    print(f"   Direction: {trade['direction']}")
    print(f"   Entry: {trade['entry_price']:.5f}")
    print(f"   SL: {trade['sl_price']:.5f}")
    print(f"   TP: {trade['tp_price']:.5f}")
    
    # Generate chart
    chart_path = plot_mock_trade(df, trade)
    
    print("\n" + "=" * 60)
    print("✅ Test Complete!")
    print("=" * 60)
    print(f"\nData saved to: data/market_data/EURUSD_5m.csv")
    print(f"Chart saved to: {chart_path}")


if __name__ == "__main__":
    main()
