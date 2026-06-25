"""
Debug Order Block detection to understand why OBs = 0.
"""
import sys
sys.path.append('backend')

import pandas as pd
from src.features.market_structure import detect_swings, detect_order_blocks

def load_data(limit: int = 5000) -> pd.DataFrame:
    """Load BTC data."""
    filepath = 'data/charts/crypto/BTCUSD15.csv'
    df = pd.read_csv(filepath, sep='\s+', header=None,
                    names=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime')
    if limit and len(df) > limit:
        df = df.iloc[-limit:]
    return df

def debug_ob_detection():
    """Debug OB detection step by step."""
    print("="*60)
    print("DEBUGGING ORDER BLOCK DETECTION")
    print("="*60)
    
    df = load_data(1000)  # Smaller dataset for debugging
    
    # Detect swings
    swing_highs, swing_lows = detect_swings(df['high'], df['low'], period=5)
    print(f"\nSwing Highs: {len(swing_highs)}")
    print(f"Swing Lows: {len(swing_lows)}")
    
    # Check volume
    avg_vol = df['volume'].rolling(20).mean()
    is_high_vol = df['volume'] > (avg_vol * 1.2)
    print(f"\nHigh volume bars (>1.2x avg): {is_high_vol.sum()} / {len(df)}")
    print(f"Percentage: {(is_high_vol.sum() / len(df)) * 100:.1f}%")
    
    # Try with volume filter
    print("\n--- WITH Volume Filter (1.2x) ---")
    obs_with_filter = detect_order_blocks(df, swing_highs, swing_lows, 
                                         volume_filter=True, volume_threshold=1.2)
    print(f"Order Blocks: {len(obs_with_filter)}")
    
    # Try without volume filter
    print("\n--- WITHOUT Volume Filter ---")
    obs_no_filter = detect_order_blocks(df, swing_highs, swing_lows, 
                                       volume_filter=False)
    print(f"Order Blocks: {len(obs_no_filter)}")
    
    # Try with lower threshold
    print("\n--- WITH Lower Threshold (1.0x) ---")
    obs_lower = detect_order_blocks(df, swing_highs, swing_lows, 
                                    volume_filter=True, volume_threshold=1.0)
    print(f"Order Blocks: {len(obs_lower)}")
    
    # Manual check: Find structure breaks
    print("\n--- Manual Structure Break Check ---")
    bullish_breaks = 0
    bearish_breaks = 0
    
    for swing in swing_highs[:10]:  # Check first 10
        for j in range(swing.index + 1, min(swing.index + 20, len(df))):
            if df['close'].iloc[j] > swing.price:
                bullish_breaks += 1
                print(f"Bullish break at index {j}, swing at {swing.index}")
                
                # Look for OB candle
                for k in range(j-1, max(j-20, 0), -1):
                    if df['close'].iloc[k] < df['open'].iloc[k]:  # Bearish
                        vol_ratio = df['volume'].iloc[k] / avg_vol.iloc[k] if avg_vol.iloc[k] > 0 else 0
                        print(f"  Found bearish candle at {k}, vol ratio: {vol_ratio:.2f}")
                        break
                break
    
    print(f"\nBullish breaks found: {bullish_breaks}")
    
    return obs_no_filter

if __name__ == "__main__":
    obs = debug_ob_detection()
    
    if obs:
        print(f"\n--- Sample Order Blocks ---")
        for ob in obs[:5]:
            print(f"{ob.type}: {ob.bottom:.2f} - {ob.top:.2f} @ {ob.time}, vol={ob.volume:.0f}")
