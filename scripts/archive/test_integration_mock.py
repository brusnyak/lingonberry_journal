#!/usr/bin/env python3
"""
Mock Integration Test
Tests the integration without real cTrader credentials
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        from infra.ctrader_client import CTraderClient
        print("  ✅ ctrader_client")
        
        from infra.ctrader_ingest import import_ctrader_trades
        print("  ✅ ctrader_ingest")
        
        from infra.market_data import load_ohlcv_with_cache
        print("  ✅ market_data")
        
        from bot.chart_generator import generate_trade_chart
        print("  ✅ chart_generator")
        
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False


def test_client_creation():
    """Test client can be created"""
    print("\nTesting client creation...")
    
    try:
        from infra.ctrader_client import CTraderClient
        
        client = CTraderClient(
            client_id="test",
            client_secret="test",
            access_token="test",
            account_id="test"
        )
        
        print("  ✅ Client created")
        return True
    except Exception as e:
        print(f"  ❌ Client creation failed: {e}")
        return False


def test_data_structures():
    """Test data structure handling"""
    print("\nTesting data structures...")
    
    try:
        import pandas as pd
        
        # Mock trade data
        trade_data = {
            'dealId': [1, 2, 3],
            'symbolName': ['GBPJPY', 'EURUSD', 'GBPJPY'],
            'tradeSide': ['BUY', 'SELL', 'BUY'],
            'volume': [50000, 100000, 50000],
            'entryPrice': [191.50, 1.0850, 191.60],
            'closePrice': [192.00, 1.0800, 191.40],
            'grossProfit': [250.00, 500.00, -100.00],
        }
        
        df = pd.DataFrame(trade_data)
        df['direction'] = df['tradeSide'].apply(lambda x: 'LONG' if x == 'BUY' else 'SHORT')
        
        print(f"  ✅ Created DataFrame with {len(df)} trades")
        print(f"  ✅ Calculated directions: {df['direction'].tolist()}")
        
        # Test CSV export
        from pathlib import Path
        test_dir = Path("data/exports")
        test_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = test_dir / "test_mock.csv"
        df.to_csv(csv_path, index=False)
        print(f"  ✅ Exported to CSV: {csv_path}")
        
        # Test Parquet export (optional)
        try:
            parquet_path = test_dir / "test_mock.parquet"
            df.to_parquet(parquet_path, index=False)
            print(f"  ✅ Exported to Parquet: {parquet_path}")
            parquet_path.unlink()
        except Exception as e:
            print(f"  ⚠️ Parquet export skipped (optional): {e}")
        
        # Clean up
        csv_path.unlink()
        
        return True
    except Exception as e:
        print(f"  ❌ Data structure test failed: {e}")
        return False


def test_chart_generation():
    """Test chart generation with mock data"""
    print("\nTesting chart generation...")
    
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        import pandas as pd
        from datetime import datetime, timedelta
        from pathlib import Path
        
        # Create mock OHLCV data
        dates = pd.date_range(start='2026-03-01', periods=100, freq='5min')
        df = pd.DataFrame({
            'time': dates,
            'open': [191.50 + i * 0.01 for i in range(100)],
            'high': [191.55 + i * 0.01 for i in range(100)],
            'low': [191.45 + i * 0.01 for i in range(100)],
            'close': [191.52 + i * 0.01 for i in range(100)],
            'volume': [1000 + i * 10 for i in range(100)],
        })
        
        # Create simple chart
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df['time'], df['close'], label='Close Price')
        ax.axhline(y=191.50, color='blue', linestyle='--', label='Entry')
        ax.axhline(y=192.00, color='green', linestyle='--', label='Exit')
        ax.set_title('Mock Trade Chart')
        ax.set_xlabel('Time')
        ax.set_ylabel('Price')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Save chart
        test_dir = Path("data/reports")
        test_dir.mkdir(parents=True, exist_ok=True)
        
        chart_path = test_dir / "test_mock_chart.png"
        plt.savefig(chart_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        print(f"  ✅ Generated chart: {chart_path}")
        
        # Clean up
        chart_path.unlink()
        
        return True
    except Exception as e:
        print(f"  ❌ Chart generation failed: {e}")
        return False


def main():
    """Run all mock tests"""
    print("=" * 60)
    print("Mock Integration Test (No Credentials Required)")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_client_creation,
        test_data_structures,
        test_chart_generation,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All mock tests passed!")
        print("=" * 60)
        print("\nYour environment is ready for cTrader integration.")
        print("Next steps:")
        print("  1. Get cTrader API credentials (see QUICKSTART_CTRADER.md)")
        print("  2. Add credentials to .env")
        print("  3. Run: make ctrader-test")
    else:
        print("❌ Some tests failed")
        print("=" * 60)
        print("\nPlease check your Python environment and dependencies.")
        print("Try: pip install -r requirements.txt")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
