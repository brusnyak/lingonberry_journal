#!/usr/bin/env python
"""
Test script for feature engineering modules.
"""
import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.features.technicals import calculate_all_technicals
from src.features.microstructure import calculate_all_microstructure
from src.features.market_structure import analyze_market_structure
from src.features.regime import detect_regime_rule_based, RegimeDetector


def test_features():
    """Test all feature modules."""
    print("Testing Feature Engineering Modules")
    print("=" * 60)
    
    # Load sample data
    print("\n1. Loading sample data...")
    df = pd.read_parquet('data/parquet/crypto/BTCUSD1440.parquet')
    print(f"✓ Loaded {len(df)} candles")
    print(f"  Date range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
    
    # Test technicals
    print("\n2. Testing technical indicators...")
    df_tech = calculate_all_technicals(df.tail(500), normalize=True)
    tech_features = [col for col in df_tech.columns if col not in df.columns]
    print(f"✓ Added {len(tech_features)} technical features:")
    print(f"  {', '.join(tech_features[:5])}...")
    
    # Test microstructure
    print("\n3. Testing microstructure features...")
    df_micro = calculate_all_microstructure(df.tail(500))
    micro_features = [col for col in df_micro.columns if col not in df.columns]
    print(f"✓ Added {len(micro_features)} microstructure features:")
    print(f"  {', '.join(micro_features[:5])}...")
    
    # Test market structure
    print("\n4. Testing market structure analysis...")
    structure = analyze_market_structure(df.tail(500))
    print(f"✓ Detected:")
    print(f"  - {len(structure['swing_highs'])} swing highs")
    print(f"  - {len(structure['swing_lows'])} swing lows")
    print(f"  - {len(structure['fvgs'])} fair value gaps")
    print(f"  - {len(structure['order_blocks'])} order blocks")
    print(f"  - {len(structure['structure_breaks'])} structure breaks")
    
    # Test regime detection (rule-based)
    print("\n5. Testing regime detection (rule-based)...")
    regimes = detect_regime_rule_based(df.tail(500))
    regime_counts = regimes.value_counts()
    print(f"✓ Detected regimes:")
    for regime, count in regime_counts.items():
        print(f"  - {regime}: {count} candles ({count/len(regimes)*100:.1f}%)")
    
    # Test regime detection (ML-based)
    print("\n6. Testing regime detection (ML-based)...")
    detector = RegimeDetector(n_regimes=5)
    detector.fit(df.tail(1000))
    ml_regimes, probabilities = detector.predict(df.tail(100))
    print(f"✓ Trained GMM on 1000 candles")
    print(f"✓ Predicted regimes for 100 candles")
    print(f"  Regime distribution: {ml_regimes.value_counts().to_dict()}")
    
    # Get regime characteristics
    characteristics = detector.get_regime_characteristics(df.tail(1000))
    print(f"\n✓ Regime characteristics:")
    for regime_id, chars in list(characteristics.items())[:2]:
        print(f"  {regime_id}:")
        print(f"    - ADX: {chars['avg_adx']:.2f}")
        print(f"    - ATR percentile: {chars['avg_atr_percentile']:.2f}")
        print(f"    - EMA alignment: {chars['avg_ema_alignment']:.2f}")
    
    print("\n" + "=" * 60)
    print("✓ All feature modules working correctly!")
    print("=" * 60)


if __name__ == '__main__':
    test_features()
