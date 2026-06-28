#!/usr/bin/env python3
"""Quick smoke test for infra/ctrader_client.py"""
import sys
sys.path.insert(0, ".")

from infra.ctrader_client import get_ctrader, reset_ctrader

print("=== cTrader Client Smoke Test ===\n")

try:
    ct = get_ctrader()
    print("[OK] Connected and authed")

    # Symbols
    syms = ct.get_symbols()
    print(f"[OK] {len(syms)} symbols loaded")

    crypto = ct.get_crypto_symbols()
    print(f"[OK] {len(crypto)} crypto symbols:")
    for c in crypto:
        print(f"     {c.symbol_name}  (id={c.symbol_id}, enabled={c.enabled})")

    # Symbol resolution
    btc_id = ct.get_symbol_id("BTCUSD")
    print(f"[OK] BTCUSD -> symbol_id={btc_id}")

    # Account info
    info = ct.get_account_info()
    print(f"[OK] Account: balance={info.get('balance')} broker={info.get('broker')}")

    # Positions
    pos = ct.get_positions()
    print(f"[OK] {len(pos)} open positions")
    for p in pos:
        print(f"     #{p.position_id} {p.side} {p.symbol} {p.lots}L @ {p.open_price}")

    print("\n=== ALL OK ===")

except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    reset_ctrader()
