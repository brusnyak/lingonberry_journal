#!/usr/bin/env python3
"""
Test EURUSD Trade Visualization with Real Market Data
Fetches real EURUSD data from yesterday and visualizes the specific trade
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.chart_generator import generate_trade_charts

def main():
    """Test EURUSD trade visualization with real data"""
    print("\n" + "="*70)
    print("📊 EURUSD Trade Visualization - Real Market Data")
    print("="*70)
    
    # Your trade details
    # Entry: 1.17383, SL: 1.17480, TP: 1.16900
    # Time: Yesterday 12:45 UTC
    # Direction: SHORT (TP below entry, SL above entry)
    # Account: $47,746.20, Risk: 0.6%
    # Notes: Followed trend down, entered after CHOCH + BOS confirmation
    
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    trade_time = yesterday.replace(hour=12, minute=45, second=0, microsecond=0)
    
    trade = {
        "symbol": "EURUSD",
        "asset_type": "forex",
        "direction": "SHORT",
        "entry_price": 1.17383,
        "entry": 1.17383,
        "sl_price": 1.17480,
        "sl": 1.17480,
        "tp_price": 1.16900,
        "tp": 1.16900,
        "ts_open": trade_time.isoformat(),
        "ts_close": None,  # Still open
        "outcome": "OPEN",
    }
    
    # Calculate trade metrics
    sl_pips = abs(trade["entry_price"] - trade["sl_price"]) * 10000
    tp_pips = abs(trade["entry_price"] - trade["tp_price"]) * 10000
    rr_ratio = tp_pips / sl_pips if sl_pips > 0 else 0
    
    account_balance = 47746.20
    risk_percent = 0.6
    risk_amount = account_balance * (risk_percent / 100)
    
    print(f"\n📝 Trade Details:")
    print(f"   Symbol: {trade['symbol']}")
    print(f"   Direction: {trade['direction']}")
    print(f"   Entry: {trade['entry_price']:.5f}")
    print(f"   Stop Loss: {trade['sl_price']:.5f} ({sl_pips:.1f} pips)")
    print(f"   Take Profit: {trade['tp_price']:.5f} ({tp_pips:.1f} pips)")
    print(f"   Risk:Reward: 1:{rr_ratio:.2f}")
    print(f"   Time: {trade_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"   Account: ${account_balance:,.2f}")
    print(f"   Risk: {risk_percent}% (${risk_amount:.2f})")
    print(f"   Confidence: HIGH")
    print(f"   Notes: Followed trend down, entered after CHOCH + BOS confirmation")
    
    # Generate charts
    print(f"\n📈 Generating multi-timeframe charts...")
    print(f"   Fetching real EURUSD data from market...")
    
    output_dir = Path("data/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        chart_paths = generate_trade_charts(
            trade=trade,
            output_dir=str(output_dir),
            context_weeks=1,  # Show 1 week of context before trade
        )
        
        if chart_paths:
            print(f"\n✅ Successfully generated {len(chart_paths)} chart(s):")
            for path in chart_paths:
                print(f"   📈 {Path(path).name}")
                print(f"      {Path(path).absolute()}")
        else:
            print("\n⚠️ No charts were generated - check for errors above")
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
    print("\nNext steps:")
    print("  • Review the generated charts")
    print("  • Verify EURUSD data matches market conditions")
    print("  • Check that trade markers (entry, SL, TP) are correctly positioned")
    print("  • Confirm TradingView-style dark theme visualization")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
