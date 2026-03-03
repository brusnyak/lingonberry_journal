#!/usr/bin/env python3
"""
Test Trade Visualization with Real EURUSD Data
Fetches yesterday's EURUSD data and visualizes a specific trade
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot.chart_generator import generate_trade_charts
from infra.ctrader_client import CTraderClient

# Output directory
OUTPUT_DIR = Path("data/reports")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def test_eurusd_trade():
    """Test EURUSD trade visualization with real data"""
    print("\n" + "="*60)
    print("📊 EURUSD Trade Visualization Test")
    print("="*60)
    
    # 1. Test cTrader connection
    print("\n1️⃣ Testing cTrader connection...")
    client = CTraderClient()
    if not client.connect():
        print("❌ cTrader connection failed - will use fallback data sources")
    else:
        print("✅ cTrader connected successfully")
        client.disconnect()
    
    # 2. Define your trade
    # Entry: 1.17383, SL: 1.17480, TP: 1.16900
    # Time: 12:45 (assuming today for testing, adjust as needed)
    # Direction: SHORT (TP below entry, SL above entry)
    # Account: 47,746.20, Risk: 0.6%
    
    today = datetime.now(timezone.utc)
    yesterday = today - timedelta(days=1)
    
    # Trade at 12:45 yesterday
    trade_time = yesterday.replace(hour=12, minute=45, second=0, microsecond=0)
    
    trade = {
        "symbol": "EURUSD",
        "asset_type": "forex",
        "direction": "SHORT",  # TP below entry = SHORT
        "entry_price": 1.17383,
        "entry": 1.17383,
        "sl_price": 1.17480,
        "sl": 1.17480,
        "tp_price": 1.16900,
        "tp": 1.16900,
        "ts_open": trade_time.isoformat(),
        "ts_close": None,  # Still open
        "outcome": "OPEN",
        "account_balance": 47746.20,
        "risk_percent": 0.6,
        "notes": "Followed trend down, entered after CHOCH + BOS confirmation",
        "confidence": "HIGH",
    }
    
    # Calculate position size and risk
    sl_pips = abs(trade["entry_price"] - trade["sl_price"]) * 10000  # Forex pips
    risk_amount = trade["account_balance"] * (trade["risk_percent"] / 100)
    
    print(f"\n2️⃣ Trade Details:")
    print(f"   Symbol: {trade['symbol']}")
    print(f"   Direction: {trade['direction']}")
    print(f"   Entry: {trade['entry_price']:.5f}")
    print(f"   Stop Loss: {trade['sl_price']:.5f}")
    print(f"   Take Profit: {trade['tp_price']:.5f}")
    print(f"   Time: {trade_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"   Account: ${trade['account_balance']:,.2f}")
    print(f"   Risk: {trade['risk_percent']}% (${risk_amount:.2f})")
    print(f"   SL Distance: {sl_pips:.1f} pips")
    print(f"   Notes: {trade['notes']}")
    
    # Calculate R:R
    tp_pips = abs(trade["entry_price"] - trade["tp_price"]) * 10000
    rr_ratio = tp_pips / sl_pips if sl_pips > 0 else 0
    print(f"   Risk:Reward: 1:{rr_ratio:.2f}")
    
    # 3. Generate charts
    print(f"\n3️⃣ Generating multi-timeframe charts...")
    print(f"   Fetching EURUSD data from yesterday...")
    
    try:
        chart_paths = generate_trade_charts(
            trade=trade,
            output_dir=str(OUTPUT_DIR),
            context_weeks=1,  # Show 1 week of context
        )
        
        if chart_paths:
            print(f"\n✅ Successfully generated {len(chart_paths)} chart(s):")
            for path in chart_paths:
                print(f"   📈 {Path(path).name}")
        else:
            print("\n⚠️ No charts were generated")
            
    except Exception as e:
        print(f"\n❌ Chart generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 4. Summary
    print("\n" + "="*60)
    print("✅ Test Complete!")
    print("="*60)
    print(f"\nCharts saved to: {OUTPUT_DIR.absolute()}")
    print("\nNext steps:")
    print("  • Review the generated charts")
    print("  • Verify EURUSD data is accurate")
    print("  • Check that trade markers (entry, SL, TP) are correct")
    print("  • Confirm TradingView-style visualization")
    
    return True


if __name__ == "__main__":
    success = test_eurusd_trade()
    sys.exit(0 if success else 1)
