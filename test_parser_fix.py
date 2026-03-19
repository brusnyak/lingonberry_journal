import sys
import os
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.raw_trade_import import parse_raw_trades

test_log = """
Currency flag
NAS100
2026/03/19 12:06:38 Market Buy 0.02 24,382.10 
24,312.67
24,862.21 2026/03/19 12:38:29 24,373.90 $0.00 $0.00 -$16.40 -$16.40 7277816997972859414 7277816997857377492 

Currency flag
NAS100
2026/03/19 11:25:38 Stop loss Buy 0.03 24,358.30 
24,324.46
- 2026/03/19 11:25:45 24,320.00 $0.00 $0.00 -$114.90 -$114.90 7277816997972851026 7277816997857376314 

Currency flag
NAS100
2026/03/19 11:20:42 Stop loss Buy 0.03 24,352.10 
24,323.52
24,442.04 2026/03/19 11:25:45 24,319.65 $0.00 $0.00 -$97.35 -$97.35 7277816997972850361 7277816997857376163
"""

print("Running parser test...")
trades = parse_raw_trades(test_log, tz_offset_hours=0)
print(f"Parsed {len(trades)} trades.")

for i, t in enumerate(trades):
    print(f"Trade {i+1}: {t['symbol']} {t['direction']} at {t['entry_price']} | SL: {t['sl']} | TP: {t['tp']} | ID: {t['external_id']}")

if len(trades) == 3:
    print("✅ SUCCESS: All 3 trades parsed correctly.")
else:
    print(f"❌ FAILURE: Parsed {len(trades)} trades, expected 3.")
