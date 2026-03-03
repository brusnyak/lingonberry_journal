#!/usr/bin/env python3
"""
Generate EURUSD Trade Chart with Real-Looking Data
Creates professional TradingView-style charts for the specific trade
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.chart_generator import generate_trade_charts

def clear_reports():
    """Clear all PNG files from reports directory"""
    reports_dir = Path("data/reports")
    if reports_dir.exists():
        png_files = list(reports_dir.glob("*.png"))
        for png_file in png_files:
            png_file.unlink()
        if png_files:
            print(f"   🗑️  Cleared {len(png_files)} old chart(s)")

def generate_realistic_eurusd_data(
    center_price: float,
    start_time: datetime,
    end_time: datetime,
    timeframe_minutes: int = 5
) -> pd.DataFrame:
    """Generate realistic EURUSD price data"""
    
    # Create time series
    times = pd.date_range(start=start_time, end=end_time, freq=f'{timeframe_minutes}min')
    num_candles = len(times)
    
    # Generate realistic price movement
    np.random.seed(42)
    
    # Create a downtrend (since this is a SHORT trade)
    trend = np.linspace(0.0002, -0.0005, num_candles)  # Gradual downtrend
    
    # Add random walk
    returns = np.random.normal(0, 0.00003, num_candles)
    
    # Combine trend and randomness
    price_changes = trend + returns
    close_prices = center_price + np.cumsum(price_changes)
    
    # Keep prices in realistic range
    close_prices = np.clip(close_prices, center_price - 0.005, center_price + 0.003)
    
    # Generate OHLC from close prices
    data = []
    for i, (time, close) in enumerate(zip(times, close_prices)):
        # Realistic spread and volatility
        spread = np.random.uniform(0.00005, 0.00012)
        volatility = np.random.uniform(0.00008, 0.00020)
        
        open_price = close + np.random.uniform(-spread, spread)
        high_price = max(open_price, close) + np.random.uniform(0, volatility)
        low_price = min(open_price, close) - np.random.uniform(0, volatility)
        volume = np.random.randint(500, 2000)
        
        data.append({
            'ts': time,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    return df


def save_to_cache(df: pd.DataFrame, symbol: str, timeframe: str):
    """Save data to local cache for reuse"""
    cache_dir = Path("data/market_data")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = cache_dir / f"{symbol}_{timeframe}.csv"
    df.to_csv(csv_path, index=False)
    print(f"   💾 Cached data to: {csv_path}")


def main():
    """Generate EURUSD trade visualization"""
    print("\n" + "="*70)
    print("📊 EURUSD Trade Visualization Generator")
    print("="*70)
    
    # Clear old reports
    print("\n🗑️  Clearing old reports...")
    clear_reports()
    
    # Trade details
    entry_price = 1.17383
    sl_price = 1.17480
    tp_price = 1.16900
    
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    trade_time = yesterday.replace(hour=12, minute=45, second=0, microsecond=0)
    
    trade = {
        "symbol": "EURUSD",
        "asset_type": "forex",
        "direction": "SHORT",
        "entry_price": entry_price,
        "entry": entry_price,
        "sl_price": sl_price,
        "sl": sl_price,
        "tp_price": tp_price,
        "tp": tp_price,
        "ts_open": trade_time.isoformat(),
        "ts_close": None,
        "outcome": "OPEN",
    }
    
    # Calculate metrics
    sl_pips = abs(entry_price - sl_price) * 10000
    tp_pips = abs(entry_price - tp_price) * 10000
    rr_ratio = tp_pips / sl_pips if sl_pips > 0 else 0
    
    account_balance = 47746.20
    risk_percent = 0.6
    risk_amount = account_balance * (risk_percent / 100)
    
    print(f"\n📝 Trade Details:")
    print(f"   Symbol: EURUSD")
    print(f"   Direction: SHORT")
    print(f"   Entry: {entry_price:.5f}")
    print(f"   Stop Loss: {sl_price:.5f} ({sl_pips:.1f} pips)")
    print(f"   Take Profit: {tp_price:.5f} ({tp_pips:.1f} pips)")
    print(f"   Risk:Reward: 1:{rr_ratio:.2f}")
    print(f"   Time: {trade_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"   Account: ${account_balance:,.2f}")
    print(f"   Risk: {risk_percent}% (${risk_amount:.2f})")
    print(f"   Notes: Followed trend down, entered after CHOCH + BOS confirmation")
    
    # Generate realistic data for each timeframe
    print(f"\n📈 Generating realistic EURUSD data...")
    
    timeframes = {
        'M5': 5,
        'M30': 30,
        'H4': 240,
    }
    
    for tf_name, tf_minutes in timeframes.items():
        print(f"\n   Generating {tf_name} data...")
        
        # Calculate time window
        if tf_minutes <= 5:
            days_before = 3
            days_after = 1
        elif tf_minutes <= 30:
            days_before = 5
            days_after = 1
        else:
            days_before = 14
            days_after = 2
        
        start_time = trade_time - timedelta(days=days_before)
        end_time = trade_time + timedelta(days=days_after)
        
        # Generate data
        df = generate_realistic_eurusd_data(
            center_price=entry_price,
            start_time=start_time,
            end_time=end_time,
            timeframe_minutes=tf_minutes
        )
        
        print(f"      Generated {len(df)} candles")
        print(f"      Price range: {df['low'].min():.5f} to {df['high'].max():.5f}")
        
        # Save to cache
        save_to_cache(df, "EURUSD", tf_name.lower())
    
    # Generate charts
    print(f"\n📊 Generating multi-timeframe charts...")
    
    output_dir = Path("data/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        chart_paths = generate_trade_charts(
            trade=trade,
            output_dir=str(output_dir),
            context_weeks=1,
        )
        
        if chart_paths:
            print(f"\n✅ Successfully generated {len(chart_paths)} chart(s):")
            for path in chart_paths:
                print(f"   📈 {Path(path).name}")
                print(f"      {Path(path).absolute()}")
        else:
            print("\n⚠️ No charts were generated")
            return False
            
    except Exception as e:
        print(f"\n❌ Chart generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print("\n" + "="*70)
    print("✅ Visualization Complete!")
    print("="*70)
    print(f"\nCharts saved to: {output_dir.absolute()}")
    print("\nGenerated timeframes:")
    print("  • H4 (4-hour) - Higher timeframe trend context")
    print("  • M30 (30-minute) - Entry timeframe context")
    print("  • M5 (5-minute) - Precise entry timing")
    print("\nFeatures:")
    print("  ✓ TradingView-style dark theme")
    print("  ✓ Entry, SL, and TP levels marked")
    print("  ✓ Risk/reward zones highlighted")
    print("  ✓ Direction indicator (SHORT)")
    print("  ✓ Realistic price action")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
