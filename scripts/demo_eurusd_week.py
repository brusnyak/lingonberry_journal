#!/usr/bin/env python3
"""
Demo: Fetch EURUSD data for previous week and visualize one day
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.ctrader_client import CTraderClient
from bot.tradingview_chart import create_tradingview_chart, save_chart


def fetch_eurusd_week():
    """Fetch EURUSD data for the previous week"""
    print("=" * 60)
    print("EURUSD Weekly Data Fetch Demo")
    print("=" * 60)
    
    # Calculate date range (previous week until today)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=7)
    
    print(f"\n📅 Date Range:")
    print(f"   Start: {start_date.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"   End:   {end_date.strftime('%Y-%m-%d %H:%M UTC')}")
    
    # Connect to cTrader
    print(f"\n🔌 Connecting to cTrader API...")
    client = CTraderClient()
    
    if not client.connect():
        print("❌ Failed to connect to cTrader API")
        return None
    
    print("✅ Connected successfully!")
    
    # Fetch H1 data for the week
    print(f"\n📊 Fetching EURUSD H1 data...")
    bars = client.get_trendbars(
        symbol='EURUSD',
        timeframe='H1',
        from_ts=start_date,
        to_ts=end_date,
        count=200
    )
    
    client.disconnect()
    
    if not bars:
        print("❌ No data received")
        return None
    
    print(f"✅ Fetched {len(bars)} hourly bars")
    
    # Convert to DataFrame
    df = pd.DataFrame(bars)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volume']]
    
    # Save to market_data folder with proper structure
    output_dir = Path('data/market_data/forex/EURUSD')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = output_dir / 'h1.csv'
    df.to_csv(csv_path, index=False)
    print(f"\n💾 Saved to: {csv_path}")
    
    # Show summary
    print(f"\n📈 Data Summary:")
    print(f"   Bars: {len(df)}")
    print(f"   First: {df['datetime'].iloc[0]}")
    print(f"   Last:  {df['datetime'].iloc[-1]}")
    print(f"   Open:  {df['open'].iloc[0]:.5f}")
    print(f"   Close: {df['close'].iloc[-1]:.5f}")
    print(f"   High:  {df['high'].max():.5f}")
    print(f"   Low:   {df['low'].min():.5f}")
    
    return df


def visualize_single_day(df, day_offset=0):
    """
    Visualize a single day from the data
    
    Args:
        df: DataFrame with EURUSD data
        day_offset: 0 = today, 1 = yesterday, 2 = 2 days ago, etc.
    """
    print(f"\n" + "=" * 60)
    print(f"Visualizing Day (offset: {day_offset})")
    print("=" * 60)
    
    # Get target date
    target_date = datetime.now(timezone.utc).date() - timedelta(days=day_offset)
    
    # Filter data for that day
    df['date'] = df['datetime'].dt.date
    day_data = df[df['date'] == target_date].copy()
    
    if day_data.empty:
        print(f"❌ No data for {target_date}")
        return None
    
    print(f"\n📅 Date: {target_date}")
    print(f"📊 Bars: {len(day_data)}")
    print(f"📈 Range: {day_data['low'].min():.5f} - {day_data['high'].max():.5f}")
    
    # Create TradingView-style chart
    fig = create_tradingview_chart(
        df=day_data,
        title=f'EURUSD - {target_date} (H1 Timeframe)',
        show_volume=True,
        figsize=(16, 9)
    )
    
    # Save chart
    output_dir = Path('data/reports')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    chart_path = output_dir / f'eurusd_{target_date}_h1.png'
    save_chart(fig, str(chart_path), dpi=150)
    print(f"\n💾 Chart saved to: {chart_path}")
    
    return chart_path


def main():
    """Main execution"""
    # Step 1: Fetch week of data
    df = fetch_eurusd_week()
    
    if df is None:
        print("\n❌ Failed to fetch data")
        return
    
    # Step 2: Visualize yesterday (most likely to have complete data)
    print("\n" + "=" * 60)
    print("Creating visualization...")
    print("=" * 60)
    
    # Try yesterday first, then today, then 2 days ago
    for offset in [1, 0, 2, 3]:
        chart_path = visualize_single_day(df, day_offset=offset)
        if chart_path:
            break
    
    print("\n" + "=" * 60)
    print("✅ Demo Complete!")
    print("=" * 60)
    print(f"\nFiles created:")
    print(f"  - CSV: data/market_data/forex/EURUSD/h1.csv")
    print(f"  - Chart: data/reports/eurusd_*_h1.png")


if __name__ == '__main__':
    main()
