#!/usr/bin/env python
"""
Test runner for the trading system.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == '__main__':
    print("=" * 60)
    print("TRADING SYSTEM - TEST SUITE")
    print("=" * 60)
    
    # Run data pipeline tests
    print("\n📊 Testing Data Pipeline...")
    print("-" * 60)
    from tests.test_data_pipeline import (
        test_binance_source,
        test_yfinance_source,
        test_data_manager,
        test_cache
    )
    
    try:
        test_binance_source()
        test_yfinance_source()
        test_data_manager()
        test_cache()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
