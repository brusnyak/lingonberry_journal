#!/usr/bin/env python3
"""
Visualize EURUSD trade with real data
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the clean chart generator
from scripts.create_eurusd_trade_chart import (
    clear_reports, plot_trade_chart, get_symbol_config,
    calculate_pips, format_price
)

import pandas as pd

def main():
    """Main function"""
    print("\n" + "="*70)
    print("📊 EURUSD Trade Visualization with Real Data")
    print("="*70)
    
    # Clear old reports
    print("\n🗑️  Clearing old reports...")
    clear_reports()
    
    # Load real data
    data_path = Path("data/market_data/EURUSD_5m_real.csv")
    
    if not data_path.exists():
        print(f"\n❌ Data file not found: {data_path}")
        print("   Run: python scripts/fetch_forex_data.py first")
        return False
    
    print(f"\n📂 Loading data from: {data_path}")
    df = pd.read_csv(data_path)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    
    print(f"   Loaded {len(df)} candles")
    print(f"   Time range: {df['time'].min()} to {df['time'].max()}")
    print(f"   Price range: {df['low'].min():.5f} to {df['high'].max():.5f}")
    
    # Trade details
    symbol = 'EURUSD'
    direction = 'SHORT'
    entry_price = 1.17383
    sl_price = 1.17480
    tp_price = 1.16900
    
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    entry_time = yesterday.replace(hour=12, minute=45, second=0, microsecond=0)
    
    # Calculate metrics
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
    print(f"   Entry Time: {entry_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"   Account: ${account_balance:,.2f}")
    print(f"   Risk: {risk_percent}% (${risk_amount:.2f})")
    
    # Generate chart
    print(f"\n📈 Generating chart...")
    
    output_dir = Path("data/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = output_dir / f"trade_{symbol}_{direction}_5M_REAL_{timestamp}.png"
    
    plot_trade_chart(
        df=df,
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        sl_price=sl_price,
        tp_price=tp_price,
        entry_time=entry_time,
        timeframe="5M",
        output_path=output_path
    )
    
    print("\n" + "="*70)
    print("✅ Complete!")
    print("="*70)
    print(f"\nChart saved to: {output_path.absolute()}")
    print("\nThis chart uses real market data structure with:")
    print("  ✓ Correct price precision (5 decimals)")
    print("  ✓ Accurate pip calculations")
    print("  ✓ Realistic price movement")
    print("  ✓ TradingView-style visualization")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
