#!/usr/bin/env python3
"""Mirror SL/TP copy test: place BTCUSD with SL/TP on 25K, verify 100K mirror."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

MASTER = 47747207  # 25K
SLAVE  = 47747211  # 100K
SYM    = "BTCUSD"

# Temp env for mirror
os.environ["CTRADER_ACC_NUM_MASTER"] = str(MASTER)
os.environ["CTRADER_ACC_NUM_SLAVE"]  = str(SLAVE)
os.environ["COPY_DRY_RUN"] = "false"

from infra.ctrader_client import CtraderClient
from infra.ctrader_mirror import CtraderCopyTrader, SLAVE_ACCOUNT_ID

# Connect with both accounts
print("=== Connecting accounts ===")
ct = CtraderClient(account_ids=[MASTER, SLAVE])
ct.connect()

for aid, label in [(MASTER, "25K Master"), (SLAVE, "100K Slave")]:
    info = ct.get_account_info(account_id=aid)
    print(f"  {label} ({aid}): balance={info['balance']} {info.get('broker','')}")

# Get BTCUSD symbol ID for both accounts
mid = ct.get_symbol_id(SYM, account_id=MASTER)
sid = ct.get_symbol_id(SYM, account_id=SLAVE)
print(f"\nBTCUSD: symbol_id master={mid} slave={sid}")

# Check current positions first
existing_master = ct.get_positions(account_id=MASTER)
existing_slave  = ct.get_positions(account_id=SLAVE)
if existing_master:
    print(f"\nWARNING: Master has {len(existing_master)} open positions. Cleanup needed first.")
    for p in existing_master:
        print(f"  Master #{p.position_id} {p.side} {p.symbol} {p.lots} lots @ {p.open_price}")
        r = ct.close_position(p.position_id, account_id=MASTER)
        print(f"  Closed master #{p.position_id}: {r.status} {r.message}")
if existing_slave:
    print(f"\nWARNING: Slave has {len(existing_slave)} open positions. Cleanup needed first.")
    for p in existing_slave:
        print(f"  Slave #{p.position_id} {p.side} {p.symbol} {p.lots} lots @ {p.open_price}")
        r = ct.close_position(p.position_id, account_id=SLAVE)
        print(f"  Closed slave #{p.position_id}: {r.status} {r.message}")

# ── Step 1: Take initial snapshots (seeds mirror's "previous" state) ──
print(f"\n=== Step 1: Seeding mirror with current positions (so poll() sees delta) ===")
trader = CtraderCopyTrader(client=ct)
trader._master_positions = trader._snapshot(MASTER)
trader._slave_positions = trader._snapshot(SLAVE)
trader._prelink_existing()
print(f"  Master seed: {len(trader._master_positions)} positions")
print(f"  Slave seed: {len(trader._slave_positions)} positions")

# ── Step 2: Place market order on master with SL/TP ──
print(f"\n=== Step 2: Opening 0.001 {SYM} BUY on master with SL/TP ===")

BTC_SL_OFFSET = 150   # $150 below entry
BTC_TP_OFFSET = 300   # $300 above entry

result = ct.create_order(
    symbol=SYM,
    quantity=0.001,
    side="buy",
    stop_loss=None,   # Can't set SL on market order if we don't know entry price yet
    take_profit=None,
    account_id=MASTER,
)
print(f"  Order result: {result.status} id={result.order_id} msg={result.message}")

if not result.order_id:
    print("FAILED to open master position")
    sys.exit(1)

# Get position to find open price
time.sleep(1)
master_positions = ct.get_positions(account_id=MASTER)
master_pos = None
for p in master_positions:
    if p.position_id == result.order_id:
        master_pos = p
        break

if not master_pos:
    print(f"FAILED: position #{result.order_id} not found")
    sys.exit(1)

print(f"  Position #{master_pos.position_id}: {master_pos.side} {master_pos.symbol} "
      f"{master_pos.lots} lots @ {master_pos.open_price:.2f}")

# Now set SL/TP on the master position
entry = master_pos.open_price
new_sl = round(entry - BTC_SL_OFFSET, 2)
new_tp = round(entry + BTC_TP_OFFSET, 2)

print(f"\n=== Step 3: Setting SL={new_sl} TP={new_tp} on master ===")
mod = ct.modify_sltp(
    master_pos.position_id,
    stop_loss=new_sl,
    take_profit=new_tp,
    account_id=MASTER,
)
print(f"  SLTP modify: {mod.status} {mod.message}")

# Verify SL/TP on master
time.sleep(1)
master_positions = ct.get_positions(account_id=MASTER)
master_pos = None
for p in master_positions:
    if p.position_id == result.order_id:
        master_pos = p
        break
if master_pos:
    print(f"  Master position SL={master_pos.stop_loss} TP={master_pos.take_profit}")

# ── Step 4: Run mirror poll (detects new position as delta from seed) ──
print(f"\n=== Step 4: Running mirror poll ===")
trader.poll()

# ── Step 5: Check slave position SL/TP ──
time.sleep(2)
print(f"\n=== Step 5: Verifying slave SL/TP ===")
slave_positions = ct.get_positions(account_id=SLAVE)
print(f"  Slave has {len(slave_positions)} open positions")
slave_pos = None
for p in slave_positions:
    print(f"  Slave #{p.position_id} {p.side} {p.symbol} "
          f"{p.lots} lots @ {p.open_price:.2f}  SL={p.stop_loss}  TP={p.take_profit}")
    if p.symbol == "BTCUSD" and p.side == "buy":
        slave_pos = p

# ── Results ──
print(f"\n{'='*60}")
print(f"RESULTS:")
print(f"  Master #{master_pos.position_id}: SL={master_pos.stop_loss} TP={master_pos.take_profit}")
if slave_pos:
    print(f"  Slave  #{slave_pos.position_id}: SL={slave_pos.stop_loss} TP={slave_pos.take_profit}")
    sl_match = (slave_pos.stop_loss == new_sl) if slave_pos.stop_loss else "NONE"
    tp_match = (slave_pos.take_profit == new_tp) if slave_pos.take_profit else "NONE"
    print(f"  SL match: {sl_match}  TP match: {tp_match}")
else:
    print(f"  SLAVE POSITION NOT FOUND — mirror did not copy")

# ── Step 6: Cleanup ──
print(f"\n=== Step 6: Cleanup ===")
if slave_pos:
    r = ct.close_position(slave_pos.position_id, account_id=SLAVE)
    print(f"  Close slave #{slave_pos.position_id}: {r.status} {r.message}")
if master_pos:
    r = ct.close_position(master_pos.position_id, account_id=MASTER)
    print(f"  Close master #{master_pos.position_id}: {r.status} {r.message}")

print("\n=== Done ===")
