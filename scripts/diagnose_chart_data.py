#!/usr/bin/env python3
"""
Diagnose chart data and visualization issues
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

sys.path.insert(0, str(Path(__file__).parent.parent))

def clear_reports():
    """Clear all PNG files from reports directory"""
    reports_dir = Path("data/reports")
    if reports_dir.exists():
        png_files = list(reports_dir.glob("*.png"))
        for png_file in png_files:
            png_file.unlink()
            print(f"   🗑️  Deleted: {png_file.name}")
        print(f"   ✅ Cleared {len(png_files)} chart(s)")

def load_and_inspect_data(symbol: str, timeframe: str):
    """Load and inspect cached data"""
    data_path = Path(f"data/market_data/{symbol}_{timeframe}.csv")
    
    if not data_path.exists():
        print(f"❌ Data file not found: {data_path}")
        return None
    
    print(f"\n📊 Loading {symbol} {timeframe} data from {data_path}")
    df = pd.read_csv(data_path)
    
    # Parse timestamp
    df['ts'] = pd.to_datetime(df['ts'], utc=True)
    
    print(f"   Rows: {len(df)}")
    print(f"   Columns: {list(df.columns)}")
    print(f"   Date range: {df['ts'].min()} to {df['ts'].max()}")
    print(f"   Price range: {df['low'].min():.5f} to {df['high'].max():.5f}")
    
    print(f"\n   First 3 rows:")
    print(df.head(3).to_string())
    
    print(f"\n   Last 3 rows:")
    print(df.tail(3).to_string())
    
    return df

def plot_raw_data(df: pd.DataFrame, symbol: str, timeframe: str):
    """Plot raw data to diagnose issues"""
    print(f"\n📈 Plotting raw {timeframe} data...")
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), facecolor='#0a0e27')
    
    # Plot 1: Close prices as line
    ax1.set_facecolor('#0a0e27')
    ax1.plot(df['ts'], df['close'], color='#00ff88', linewidth=1.5, label='Close Price')
    ax1.set_title(f'{symbol} {timeframe} - Close Prices', color='#ffffff', fontsize=14)
    ax1.set_ylabel('Price', color='#8892b0')
    ax1.grid(True, alpha=0.2, color='#3d4466')
    ax1.tick_params(colors='#8892b0')
    ax1.legend(facecolor='#1a1f3a', edgecolor='#3d4466', labelcolor='#ffffff')
    
    # Plot 2: OHLC as candlesticks
    ax2.set_facecolor('#0a0e27')
    
    for idx, row in df.iterrows():
        is_bullish = row['close'] >= row['open']
        color = '#00ff88' if is_bullish else '#ff3366'
        
        # Wick
        ax2.plot([row['ts'], row['ts']], [row['low'], row['high']], 
                color=color, linewidth=1, alpha=0.8)
        
        # Body
        body_height = abs(row['close'] - row['open'])
        body_bottom = min(row['open'], row['close'])
        
        if body_height > 0.00001:  # Only draw if there's visible height
            from matplotlib.patches import Rectangle
            # Calculate candle width based on timeframe
            if len(df) > 1:
                time_diff = (df['ts'].iloc[1] - df['ts'].iloc[0]).total_seconds() / 86400
                candle_width = time_diff * 0.6
            else:
                candle_width = 0.001
            
            ax2.add_patch(Rectangle(
                (mdates.date2num(row['ts']) - candle_width/2, body_bottom),
                candle_width,
                body_height,
                facecolor=color,
                edgecolor=color,
                alpha=0.9
            ))
    
    ax2.set_title(f'{symbol} {timeframe} - Candlesticks', color='#ffffff', fontsize=14)
    ax2.set_xlabel('Time', color='#8892b0')
    ax2.set_ylabel('Price', color='#8892b0')
    ax2.grid(True, alpha=0.2, color='#3d4466')
    ax2.tick_params(colors='#8892b0')
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    
    for spine in ax1.spines.values():
        spine.set_edgecolor('#3d4466')
    for spine in ax2.spines.values():
        spine.set_edgecolor('#3d4466')
    
    plt.tight_layout()
    
    output_path = Path(f"data/reports/diagnostic_{symbol}_{timeframe}.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#0a0e27')
    plt.close()
    
    print(f"   ✅ Saved diagnostic chart: {output_path}")
    return output_path

def main():
    """Main diagnostic function"""
    print("\n" + "="*70)
    print("🔍 Chart Data Diagnostic Tool")
    print("="*70)
    
    # Clear old reports
    print("\n🗑️  Clearing old reports...")
    clear_reports()
    
    # Check each timeframe
    timeframes = ['m5', 'm30', 'h4']
    
    for tf in timeframes:
        df = load_and_inspect_data('EURUSD', tf)
        if df is not None:
            plot_raw_data(df, 'EURUSD', tf.upper())
    
    print("\n" + "="*70)
    print("✅ Diagnostic Complete!")
    print("="*70)
    print("\nCheck the diagnostic charts in data/reports/")
    print("These show the raw data to help identify visualization issues.")

if __name__ == "__main__":
    main()
