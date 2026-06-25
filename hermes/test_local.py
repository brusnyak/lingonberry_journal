#!/usr/bin/env python3
"""
Test script for Hermes Trading Skills.
Run this locally to verify everything works before deploying to Oracle.
"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_trade_locker_connection():
    """Test TradeLocker connection and data fetching."""
    print("=== Testing TradeLocker Connection ===")
    try:
        from infra.tradelocker_client import get_quote, fetch_historical_bars

        # Test quote
        quote = get_quote("GBPUSD")
        print(f"  GBPUSD quote: bid={quote['bid']}, ask={quote['ask']}, spread={quote['ask'] - quote['bid']:.5f}")

        # Test historical data
        df = fetch_historical_bars("GBPUSD", "M15", limit=10)
        print(f"  GBPUSD M15: {len(df)} bars")
        print(f"  Latest close: {df['close'].iloc[-1]:.5f}")

        print("  ✅ TradeLocker connection OK")
        return True

    except Exception as e:
        print(f"  ❌ TradeLocker error: {e}")
        return False


def test_market_analysis():
    """Test market analysis skill."""
    print("\n=== Testing Market Analysis ===")
    try:
        from hermes.skills.market_analysis import analyze_symbol, format_briefing

        analysis = analyze_symbol("GBPUSD")
        print(f"  GBPUSD analysis:")
        print(f"    Quote: {analysis.get('current_quote', {})}")
        for tf, data in analysis.get("timeframes", {}).items():
            if "error" in data:
                print(f"    {tf}: {data['error']}")
            else:
                print(f"    {tf}: {data.get('trend', '?')} | Range: {data.get('range', {}).get('pips', '?')}p")

        print("  ✅ Market analysis OK")
        return True

    except Exception as e:
        print(f"  ❌ Market analysis error: {e}")
        return False


def test_paper_trade_status():
    """Test paper trade status (read-only, no execution)."""
    print("\n=== Testing Paper Trade Status ===")
    try:
        from hermes.skills.paper_trade import get_status, format_status

        status = get_status(25)
        print(f"  25k Account:")
        print(f"    Balance: ${status['balance'].get('balance', 0):,.2f}")
        print(f"    Equity: ${status['balance'].get('equity', 0):,.2f}")
        print(f"    Open positions: {len(status['open_positions'])}")

        print("  ✅ Paper trade status OK")
        return True

    except Exception as e:
        print(f"  ❌ Paper trade error: {e}")
        return False


def test_daily_briefing():
    """Test daily briefing generation."""
    print("\n=== Testing Daily Briefing ===")
    try:
        from hermes.skills.daily_briefing import morning_briefing

        briefing = morning_briefing()
        print(f"  Briefing length: {len(briefing)} chars")
        print(f"  First 200 chars:")
        print(f"  {briefing[:200]}...")

        print("  ✅ Daily briefing OK")
        return True

    except Exception as e:
        print(f"  ❌ Daily briefing error: {e}")
        return False


def test_trade_review():
    """Test trade review (read-only)."""
    print("\n=== Testing Trade Review ===")
    try:
        from hermes.skills.trade_review import review_recent_trades

        review = review_recent_trades(5)
        print(f"  Review length: {len(review)} chars")
        print(f"  First 200 chars:")
        print(f"  {review[:200]}...")

        print("  ✅ Trade review OK")
        return True

    except Exception as e:
        print(f"  ❌ Trade review error: {e}")
        return False


def main():
    """Run all tests."""
    print("Hermes Trading Skills - Local Test")
    print("=" * 40)

    results = []
    results.append(test_trade_locker_connection())
    results.append(test_market_analysis())
    results.append(test_paper_trade_status())
    results.append(test_daily_briefing())
    results.append(test_trade_review())

    print("\n" + "=" * 40)
    if all(results):
        print("✅ All tests passed!")
        print("\nReady to deploy to Oracle server.")
        print("Run: bash hermes/setup.sh")
    else:
        print("❌ Some tests failed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
