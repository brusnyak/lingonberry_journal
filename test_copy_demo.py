#!/usr/bin/env python3
"""Quick copy test on DEMO — watches master (2165806), mirrors to slave (2165807)."""
import math, os, sys, time
from dotenv import load_dotenv
load_dotenv()
from tradelocker import TLAPI

# ── Config ────────────────────────────────────────────────────────────
MASTER_ACC = 2165806
SLAVE_ACC = 2165807
RISK_PCT = 0.005       # 0.5%
POLL_INTERVAL = 3
LOT_STEP = 0.01
MAX_LOTS = 20.0
DRY_RUN = False        # Set True to log without placing orders

JPY_PAIRS = {"EURJPY","GBPJPY","AUDJPY","CADJPY","CHFJPY","USDJPY","NZDJPY"}

# ── Connection ────────────────────────────────────────────────────────
env = os.getenv("TL_ENVIRONMENT_DEMO")
user = os.getenv("TL_USERNAME_DEMO")
pw = os.getenv("TL_PASSWORD_DEMO")
srv = os.getenv("TL_SERVER_DEMO")

master = TLAPI(environment=env, username=user, password=pw, server=srv,
               account_id=MASTER_ACC, log_level="warning")
slave  = TLAPI(environment=env, username=user, password=pw, server=srv,
               account_id=SLAVE_ACC, log_level="warning")

print(f"Master ({MASTER_ACC}): balance={master.get_account_state().get('balance')}")
print(f"Slave  ({SLAVE_ACC}): balance={slave.get_account_state().get('balance')}")

# ── Helpers ───────────────────────────────────────────────────────────
def resolve(tl, symbol):
    clean = symbol.upper()
    if not clean.endswith(".X"): clean += ".X"
    return tl.get_instrument_id_from_symbol_name(clean)

def calc_lots(equity, stop_distance, is_jpy):
    mult = 1_000 if is_jpy else 100_000
    risk_amt = equity * RISK_PCT
    if stop_distance <= 0: return LOT_STEP
    raw = (risk_amt / stop_distance) / mult
    size = round(math.floor(raw / LOT_STEP) * LOT_STEP, 2)
    return max(min(size, MAX_LOTS), LOT_STEP)

def get_positions(tl):
    """Return {position_id: dict} of open positions with SL/TP prices from orders."""
    df = tl.get_all_positions()
    if df is None or (hasattr(df, "empty") and df.empty):
        return {}

    # Fetch orders to get SL/TP prices (positions only have stopLossId/takeProfitId)
    orders_df = tl.get_all_orders()
    sl_tp_by_position = {}  # positionId → {sl, tp}
    if orders_df is not None and hasattr(orders_df, "columns"):
        for _, o in orders_df.iterrows():
            pid = int(o.get("positionId", 0))
            if pid == 0: continue
            if pid not in sl_tp_by_position:
                sl_tp_by_position[pid] = {"sl": None, "tp": None}
            otype = str(o.get("type", "")).lower()
            # For a long position: SL is a sell-stop (stopPrice=sl), TP is a sell-limit (price=tp)
            # For a short position: SL is a buy-stop (stopPrice=sl), TP is a buy-limit (price=tp)
            if otype == "stop":
                sp = float(o.get("stopPrice", 0))
                if sp > 0:
                    sl_tp_by_position[pid]["sl"] = sp
            elif otype == "limit":
                p = float(o.get("price", 0))
                if p > 0:
                    sl_tp_by_position[pid]["tp"] = p

    result = {}
    for _, row in df.iterrows():
        pid = int(row.get("id", 0))
        if pid == 0: continue
        iid = int(row.get("tradableInstrumentId", 0))
        try:
            sym = tl.get_symbol_name_from_instrument_id(iid).replace(".X", "")
        except:
            sym = f"INST_{iid}"

        sl_tp = sl_tp_by_position.get(pid, {"sl": None, "tp": None})

        result[pid] = {
            "id": pid, "iid": iid, "symbol": sym,
            "side": str(row.get("side", "")).lower(),
            "qty": float(row.get("qty", 0)),
            "avg": float(row.get("avgPrice", 0)),
            "sl": sl_tp["sl"],
            "tp": sl_tp["tp"],
        }
    return result

# ── State ─────────────────────────────────────────────────────────────
prev_master = get_positions(master)
prev_slave  = get_positions(slave)
print(f"Master positions: {len(prev_master)}  Slave positions: {len(prev_slave)}")

# Pre-link matching positions (by instrument+side)
master_to_slave = {}
for mid, mp in prev_master.items():
    for sid, sp in prev_slave.items():
        if mp["symbol"] == sp["symbol"] and mp["side"] == sp["side"] and mp["qty"] == sp["qty"]:
            master_to_slave[mid] = sid
            print(f"Pre-linked master #{mid} → slave #{sid}  {mp['side']} {mp['symbol']}")
            break

# ── Poll loop ─────────────────────────────────────────────────────────
print(f"\nPolling every {POLL_INTERVAL}s. Open a trade on the 24K account (2165806). Ctrl+C to stop.\n")

while True:
    time.sleep(POLL_INTERVAL)
    try:
        cur_master = get_positions(master)
        cur_slave  = get_positions(slave)

        master_ids = set(cur_master.keys())
        prev_ids = set(prev_master.keys())

        # New position on master → open on slave
        new_ids = master_ids - prev_ids
        for mid in new_ids:
            mp = cur_master[mid]
            print(f"\n>>> NEW on master: #{mid} {mp['side'].upper()} {mp['symbol']} {mp['qty']} lots @ {mp['avg']}")

            # Size for slave
            state = slave.get_account_state()
            equity = float(state.get("balance", state.get("equity", 0)))
            if mp["sl"]:
                stop_dist = abs(mp["avg"] - mp["sl"])
            else:
                stop_dist = mp["avg"] * 0.015
            is_jpy = mp["symbol"].upper().replace(".X","") in JPY_PAIRS
            lots = calc_lots(equity, stop_dist, is_jpy)
            iid = resolve(slave, mp["symbol"])

            print(f"  Sizing: slave_equity={equity:.2f} stop_dist={stop_dist:.5f} lots={lots:.2f}")

            if DRY_RUN:
                print(f"  [DRY RUN] Would open {mp['side'].upper()} {mp['symbol']} {lots} lots")
            else:
                try:
                    oid = slave.create_order(
                        instrument_id=iid, quantity=lots, side=mp["side"],
                        type_="market",
                        stop_loss=mp["sl"], stop_loss_type="absolute" if mp["sl"] else None,
                        take_profit=mp["tp"], take_profit_type="absolute" if mp["tp"] else None,
                    )
                    if oid:
                        print(f"  >>> ORDER PLACED: id={oid}")
                        # Link
                        time.sleep(1.5)
                        new_slave = get_positions(slave)
                        for sid, sp in new_slave.items():
                            if sp["symbol"] == mp["symbol"] and sp["side"] == mp["side"]:
                                master_to_slave[mid] = sid
                                print(f"  Linked master #{mid} → slave #{sid}")
                                break
                    else:
                        print(f"  FAILED: create_order returned None")
                except Exception as e:
                    print(f"  ERROR placing order: {e}")

        # Position closed on master → close on slave
        closed = prev_ids - master_ids
        for mid in closed:
            if mid in master_to_slave:
                sid = master_to_slave.pop(mid)
                print(f"\n<<< CLOSE on master #{mid} → closing slave #{sid}")
                if not DRY_RUN:
                    try:
                        slave.close_position(position_id=sid)
                        print(f"  Slave #{sid} closed")
                    except Exception as e:
                        print(f"  Error closing slave #{sid}: {e}")
            else:
                print(f"\n<<< CLOSE on master #{mid} (no slave mapping)")

        # SL/TP modification
        for mid in master_ids:
            if mid not in master_to_slave: continue
            sid = master_to_slave[mid]
            mp = cur_master[mid]
            pp = prev_master.get(mid)
            if pp is None: continue
            if mp["sl"] != pp["sl"] or mp["tp"] != pp["tp"]:
                print(f"\n<<< MODIFY master #{mid} SL:{pp['sl']}→{mp['sl']} TP:{pp['tp']}→{mp['tp']} → slave #{sid}")
                if not DRY_RUN:
                    try:
                        params = {}
                        if mp["sl"] is not None:
                            params["stopLoss"] = mp["sl"]
                            params["stopLossType"] = "absolute"
                        if mp["tp"] is not None:
                            params["takeProfit"] = mp["tp"]
                            params["takeProfitType"] = "absolute"
                        if params:
                            slave.modify_position(sid, params)
                            print(f"  Slave #{sid} modified")
                    except Exception as e:
                        print(f"  Error modifying slave #{sid}: {e}")

        prev_master = cur_master
        prev_slave  = cur_slave

    except KeyboardInterrupt:
        print("\nStopped.")
        break
    except Exception as e:
        print(f"Poll error: {e}", file=sys.stderr)
        time.sleep(5)
