#!/usr/bin/env python3
"""
Create EURUSD Trade Chart - Clean Implementation
Proper precision, pip calculations, and visualization
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle

# Symbol precision and pip configuration
SYMBOL_CONFIG = {
    'EURUSD': {'decimals': 5, 'pip_position': 4, 'pip_value': 0.0001},
    'GBPUSD': {'decimals': 5, 'pip_position': 4, 'pip_value': 0.0001},
    'USDJPY': {'decimals': 3, 'pip_position': 2, 'pip_value': 0.01},
    'EURJPY': {'decimals': 3, 'pip_position': 2, 'pip_value': 0.01},
    'XAUUSD': {'decimals': 2, 'pip_position': 2, 'pip_value': 0.01},  # Gold
    'NAS100': {'decimals': 1, 'pip_position': 1, 'pip_value': 0.1},   # Nasdaq
}

def get_symbol_config(symbol: str) -> dict:
    """Get configuration for a symbol"""
    symbol = symbol.upper().replace('/', '')
    return SYMBOL_CONFIG.get(symbol, {'decimals': 5, 'pip_position': 4, 'pip_value': 0.0001})

def calculate_pips(price1: float, price2: float, symbol: str) -> float:
    """Calculate pip difference between two prices"""
    config = get_symbol_config(symbol)
    pip_value = config['pip_value']
    return abs(price1 - price2) / pip_value

def format_price(price: float, symbol: str) -> str:
    """Format price with correct decimal places"""
    config = get_symbol_config(symbol)
    decimals = config['decimals']
    return f"{price:.{decimals}f}"

def clear_reports():
    """Clear all PNG files from reports directory"""
    reports_dir = Path("data/reports")
    if reports_dir.exists():
        png_files = list(reports_dir.glob("*.png"))
        for png_file in png_files:
            png_file.unlink()
        if png_files:
            print(f"   🗑️  Cleared {len(png_files)} old chart(s)")

def generate_realistic_price_data(
    symbol: str,
    center_price: float,
    start_time: datetime,
    end_time: datetime,
    timeframe_minutes: int = 5,
    trend_direction: str = 'down'
) -> pd.DataFrame:
    """
    Generate realistic price data with proper precision
    
    Args:
        symbol: Trading symbol (e.g., 'EURUSD')
        center_price: Center price for generation
        start_time: Start datetime
        end_time: End datetime
        timeframe_minutes: Candle timeframe in minutes
        trend_direction: 'up', 'down', or 'sideways'
    """
    config = get_symbol_config(symbol)
    pip_value = config['pip_value']
    
    # Create time series
    times = pd.date_range(start=start_time, end=end_time, freq=f'{timeframe_minutes}min')
    num_candles = len(times)
    
    np.random.seed(42)
    
    # Create trend based on direction
    if trend_direction == 'down':
        trend = np.linspace(2 * pip_value, -5 * pip_value, num_candles)
    elif trend_direction == 'up':
        trend = np.linspace(-2 * pip_value, 5 * pip_value, num_candles)
    else:  # sideways
        trend = np.zeros(num_candles)
    
    # Add realistic random walk (scaled to pip value)
    volatility = pip_value * 0.3
    returns = np.random.normal(0, volatility, num_candles)
    
    # Combine trend and randomness
    price_changes = trend + returns
    close_prices = center_price + np.cumsum(price_changes)
    
    # Keep prices in realistic range
    max_move = 50 * pip_value  # 50 pips max move
    close_prices = np.clip(close_prices, center_price - max_move, center_price + max_move)
    
    # Generate OHLC from close prices
    data = []
    for i, (time, close) in enumerate(zip(times, close_prices)):
        # Realistic spread and candle range (in pips)
        spread = pip_value * np.random.uniform(0.5, 1.2)
        candle_range = pip_value * np.random.uniform(0.8, 2.0)
        
        open_price = close + np.random.uniform(-spread, spread)
        high_price = max(open_price, close) + np.random.uniform(0, candle_range)
        low_price = min(open_price, close) - np.random.uniform(0, candle_range)
        volume = np.random.randint(500, 2000)
        
        data.append({
            'time': time,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    
    # Round to proper precision
    decimals = config['decimals']
    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].round(decimals)
    
    return df

def plot_trade_chart(
    df: pd.DataFrame,
    symbol: str,
    direction: str,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    entry_time: datetime,
    timeframe: str,
    output_path: Path
):
    """
    Plot professional TradingView-style chart with trade overlay
    """
    config = get_symbol_config(symbol)
    
    # Calculate metrics
    sl_pips = calculate_pips(entry_price, sl_price, symbol)
    tp_pips = calculate_pips(entry_price, tp_price, symbol)
    rr_ratio = tp_pips / sl_pips if sl_pips > 0 else 0
    
    # Set dark theme
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(18, 10), facecolor='#0a0e27')
    ax.set_facecolor('#0a0e27')
    
    # Calculate candle width
    if len(df) > 1:
        time_diff = (df['time'].iloc[1] - df['time'].iloc[0]).total_seconds() / 86400
        candle_width = time_diff * 0.6
    else:
        candle_width = 0.001
    
    # Plot candlesticks
    for idx, row in df.iterrows():
        is_bullish = row['close'] >= row['open']
        candle_color = '#00ff88' if is_bullish else '#ff3366'
        
        # High-Low wick
        ax.plot([row['time'], row['time']], [row['low'], row['high']], 
               color=candle_color, linewidth=1.2, alpha=0.8, zorder=1)
        
        # Candle body
        body_height = abs(row['close'] - row['open'])
        body_bottom = min(row['open'], row['close'])
        
        if body_height > config['pip_value'] * 0.01:  # Only draw if visible
            ax.add_patch(Rectangle(
                (mdates.date2num(row['time']) - candle_width/2, body_bottom),
                candle_width,
                body_height,
                facecolor=candle_color,
                edgecolor=candle_color,
                alpha=0.9,
                zorder=2
            ))
        else:
            # Doji - draw horizontal line
            ax.plot([mdates.date2num(row['time']) - candle_width/2, 
                    mdates.date2num(row['time']) + candle_width/2], 
                   [row['open'], row['open']], 
                   color=candle_color, linewidth=2, alpha=0.9, zorder=2)
    
    # Trade overlay
    is_long = direction.upper() == 'LONG'
    entry_color = '#00b8ff' if is_long else '#ff9500'
    sl_color = '#ff3366'
    tp_color = '#00ff88'
    
    # Fill risk/reward zones
    ax.fill_between(df['time'], entry_price, sl_price, 
                    color=sl_color, alpha=0.08, zorder=0)
    ax.fill_between(df['time'], entry_price, tp_price, 
                    color=tp_color, alpha=0.08, zorder=0)
    
    # Price levels
    ax.axhline(y=entry_price, color=entry_color, linestyle='-', linewidth=2.5, 
              alpha=0.9, zorder=3, label=f'Entry {format_price(entry_price, symbol)}')
    ax.axhline(y=sl_price, color=sl_color, linestyle='--', linewidth=2, 
              alpha=0.8, zorder=3, label=f'SL {format_price(sl_price, symbol)} (-{sl_pips:.1f} pips)')
    ax.axhline(y=tp_price, color=tp_color, linestyle='--', linewidth=2, 
              alpha=0.8, zorder=3, label=f'TP {format_price(tp_price, symbol)} (+{tp_pips:.1f} pips)')
    
    # Entry time vertical line
    ax.axvline(x=entry_time, color=entry_color, linestyle=':', linewidth=1.5, 
              alpha=0.4, zorder=1)
    
    # Direction badge
    if direction.upper() == 'SHORT':
        badge_text = '▼ SHORT'
        badge_y = entry_price * 1.00015
        ax.annotate('', xy=(entry_time, entry_price * 0.99985), 
                   xytext=(entry_time, entry_price),
                   arrowprops=dict(arrowstyle='->', color=entry_color, lw=4),
                   zorder=5)
    else:
        badge_text = '▲ LONG'
        badge_y = entry_price * 0.99985
        ax.annotate('', xy=(entry_time, entry_price * 1.00015), 
                   xytext=(entry_time, entry_price),
                   arrowprops=dict(arrowstyle='->', color=entry_color, lw=4),
                   zorder=5)
    
    ax.text(entry_time, badge_y, badge_text,
           color='#ffffff', fontsize=14, fontweight='bold',
           horizontalalignment='center', verticalalignment='center',
           bbox=dict(boxstyle='round,pad=0.7', facecolor=entry_color, 
                    edgecolor='#ffffff', linewidth=2.5, alpha=0.95),
           zorder=6)
    
    # Info panel
    info_lines = [
        f"{symbol} • {direction.upper()} • {timeframe}",
        f"",
        f"Risk/Reward: 1:{rr_ratio:.2f}",
        f"Risk: {sl_pips:.1f} pips",
        f"Reward: {tp_pips:.1f} pips",
    ]
    
    info_text = '\n'.join(info_lines)
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
           fontsize=12, verticalalignment='top',
           color='#ffffff', fontweight='bold',
           bbox=dict(boxstyle='round,pad=0.8', facecolor='#1a1f3a', 
                    edgecolor='#3d4466', linewidth=2, alpha=0.95),
           zorder=10)
    
    # Title
    title_text = f"{symbol} • {direction.upper()} Position • {timeframe} Chart"
    ax.text(0.5, 1.02, title_text, transform=ax.transAxes,
           fontsize=16, fontweight='bold', color='#ffffff',
           horizontalalignment='center')
    
    # Styling
    ax.set_xlabel('Time', fontsize=13, color='#8892b0', fontweight='bold', labelpad=10)
    ax.set_ylabel('Price', fontsize=13, color='#8892b0', fontweight='bold', labelpad=10)
    
    # Format y-axis with proper precision
    from matplotlib.ticker import FuncFormatter
    def price_formatter(x, p):
        return format_price(x, symbol)
    ax.yaxis.set_major_formatter(FuncFormatter(price_formatter))
    
    ax.grid(True, alpha=0.1, linestyle='-', linewidth=0.5, color='#3d4466')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    ax.tick_params(colors='#8892b0', labelsize=11, width=1.5, length=6)
    
    # Legend
    ax.legend(loc='upper left', frameon=True, facecolor='#0b1220', 
             edgecolor='#334155', labelcolor='#e2e8f0', fontsize=10)
    
    for spine in ax.spines.values():
        spine.set_edgecolor('#3d4466')
        spine.set_linewidth(1.5)
    
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#0a0e27')
    plt.close()
    
    print(f"   ✅ Saved: {output_path.name}")

def main():
    """Main function"""
    print("\n" + "="*70)
    print("📊 EURUSD Trade Chart Generator - Clean Implementation")
    print("="*70)
    
    # Clear old reports
    print("\n🗑️  Clearing old reports...")
    clear_reports()
    
    # Trade details
    symbol = 'EURUSD'
    direction = 'SHORT'
    entry_price = 1.17383
    sl_price = 1.17480
    tp_price = 1.16900
    
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    entry_time = yesterday.replace(hour=12, minute=45, second=0, microsecond=0)
    
    # Calculate metrics
    config = get_symbol_config(symbol)
    sl_pips = calculate_pips(entry_price, sl_price, symbol)
    tp_pips = calculate_pips(entry_price, tp_price, symbol)
    rr_ratio = tp_pips / sl_pips if sl_pips > 0 else 0
    
    account_balance = 47746.20
    risk_percent = 0.6
    risk_amount = account_balance * (risk_percent / 100)
    
    print(f"\n📝 Trade Details:")
    print(f"   Symbol: {symbol}")
    print(f"   Direction: {direction}")
    print(f"   Entry: {format_price(entry_price, symbol)}")
    print(f"   Stop Loss: {format_price(sl_price, symbol)} ({sl_pips:.1f} pips)")
    print(f"   Take Profit: {format_price(tp_price, symbol)} ({tp_pips:.1f} pips)")
    print(f"   Risk:Reward: 1:{rr_ratio:.2f}")
    print(f"   Time: {entry_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"   Account: ${account_balance:,.2f}")
    print(f"   Risk: {risk_percent}% (${risk_amount:.2f})")
    print(f"   Notes: Followed trend down, entered after CHOCH + BOS confirmation")
    
    # Generate data and charts for multiple timeframes
    timeframes = [
        ('H4', 240, 14, 2),   # 4-hour, 14 days before, 2 days after
        ('M30', 30, 5, 1),    # 30-min, 5 days before, 1 day after
        ('M5', 5, 3, 1),      # 5-min, 3 days before, 1 day after
    ]
    
    output_dir = Path("data/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📈 Generating charts...")
    
    for tf_name, tf_minutes, days_before, days_after in timeframes:
        print(f"\n   {tf_name} timeframe:")
        
        # Calculate time window
        start_time = entry_time - timedelta(days=days_before)
        end_time = entry_time + timedelta(days=days_after)
        
        # Generate data
        df = generate_realistic_price_data(
            symbol=symbol,
            center_price=entry_price,
            start_time=start_time,
            end_time=end_time,
            timeframe_minutes=tf_minutes,
            trend_direction='down'  # SHORT trade
        )
        
        print(f"      Generated {len(df)} candles")
        print(f"      Price range: {format_price(df['low'].min(), symbol)} to {format_price(df['high'].max(), symbol)}")
        
        # Generate chart
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = output_dir / f"trade_{symbol}_{direction}_{tf_name}_{timestamp}.png"
        
        plot_trade_chart(
            df=df,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            entry_time=entry_time,
            timeframe=tf_name,
            output_path=output_path
        )
    
    print("\n" + "="*70)
    print("✅ Complete!")
    print("="*70)
    print(f"\nCharts saved to: {output_dir.absolute()}")
    print("\nFeatures:")
    print("  ✓ Correct price precision (5 decimals for EURUSD)")
    print("  ✓ Accurate pip calculations")
    print("  ✓ TradingView-style dark theme")
    print("  ✓ Risk/reward zones highlighted")
    print("  ✓ Multi-timeframe analysis")

if __name__ == "__main__":
    main()
