#!/usr/bin/env python3
"""Copy Trader — mirrors manual trades from master (25K) to slave (100K) on TradeLocker.

Polls the master account every POLL_INTERVAL seconds. When a new position opens,
a proportionally-sized position opens on the slave. When master closes or modifies
SL/TP, the slave follows.

Sizing: both accounts use the same risk_pct (default 0.5%). Lot size is calculated
independently per account based on its own equity and stop distance.

Environment variables (all prefixed COPY_ or reusing TL_):
    TL_ENVIRONMENT_LIVE   TradeLocker live URL
    TL_USERNAME_LIVE      Email
    TL_PASSWORD_LIVE      Password
    TL_SERVER_LIVE        Server (GFTTL)
    TL_ACC_NUM_MASTER     Master account number (25K: 2165806)
    TL_ACC_NUM_SLAVE      Slave account number (100K: 2165807)

    COPY_RISK_PCT         Risk per trade as fraction (default 0.005 = 0.5%)
    COPY_POLL_INTERVAL    Seconds between polls (default 3)
    COPY_LOT_STEP         Minimum lot increment (default 0.01)
    COPY_MAX_LOTS         Maximum lots per order (default 20.0)
    COPY_DRY_RUN          "true" → log actions, never place orders
"""
from __future__ import annotations

import logging
import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("copy-trader")

# ── Config ────────────────────────────────────────────────────────────────────

RISK_PCT = float(os.getenv("COPY_RISK_PCT", "0.005"))
POLL_INTERVAL = int(os.getenv("COPY_POLL_INTERVAL", "3"))
LOT_STEP = float(os.getenv("COPY_LOT_STEP", "0.01"))
MAX_LOTS = float(os.getenv("COPY_MAX_LOTS", "20.0"))
DRY_RUN = os.getenv("COPY_DRY_RUN", "false").lower() == "true"

# JPY pairs: 1 pip = 0.01 price, contract multiplier = 1_000 (not 100_000)
_JPY_PAIRS = {"EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "USDJPY", "NZDJPY"}

# ── TLAPI instances ───────────────────────────────────────────────────────────


def _create_tlapi(label: str, acc_num: int):
    """Create an independent TLAPI instance for one account."""
    from tradelocker import TLAPI

    env = os.getenv("TL_ENVIRONMENT_LIVE", "https://live.tradelocker.com")
    username = os.getenv("TL_USERNAME_LIVE", "")
    password = os.getenv("TL_PASSWORD_LIVE", "")
    server = os.getenv("TL_SERVER_LIVE", "GFTTL")

    if not all([username, password, server]):
        raise RuntimeError(f"Missing TL credentials for {label}")

    tl = TLAPI(
        environment=env,
        username=username,
        password=password,
        server=server,
        account_id=acc_num,
        log_level="warning",
    )
    log.info("Connected %s  account_id=%s", label, acc_num)
    return tl


# ── Instrument resolution ─────────────────────────────────────────────────────


def _resolve_id(tl, symbol: str, cache: dict) -> int:
    """Resolve symbol to TradeLocker instrument ID (with cache)."""
    clean = symbol.upper()
    if not clean.endswith(".X"):
        clean += ".X"
    if clean not in cache:
        cache[clean] = tl.get_instrument_id_from_symbol_name(clean)
    return cache[clean]


# ── Lot sizing ────────────────────────────────────────────────────────────────


def _calc_lots(equity: float, stop_distance: float, is_jpy: bool) -> float:
    """Risk-based lot sizing. Same logic as mean_reversion_bot."""
    mult = 1_000 if is_jpy else 100_000
    risk_amt = equity * RISK_PCT
    if stop_distance <= 0:
        return LOT_STEP
    raw = (risk_amt / stop_distance) / mult
    size = round(math.floor(raw / LOT_STEP) * LOT_STEP, 2)
    return max(min(size, MAX_LOTS), LOT_STEP)


# ── Position state ────────────────────────────────────────────────────────────


@dataclass
class PosSnapshot:
    """Snapshot of a single open position."""
    position_id: int
    instrument_id: int
    symbol: str
    side: str  # "buy" or "sell"
    qty: float
    avg_price: float
    stop_loss: float | None = None
    take_profit: float | None = None


def _snapshot_positions(tl, instrument_cache: dict, symbol_cache: dict) -> dict[int, PosSnapshot]:
    """Fetch all open positions and return {position_id: PosSnapshot}."""
    try:
        df = tl.get_all_positions()
    except Exception as exc:
        log.error("get_all_positions failed: %s", exc)
        return {}

    if df is None or (hasattr(df, "empty") and df.empty):
        return {}

    # Fetch orders to get SL/TP prices (positions only have stopLossId/takeProfitId)
    sl_tp_by_position: dict[int, dict[str, float | None]] = {}
    try:
        orders_df = tl.get_all_orders()
        if orders_df is not None and hasattr(orders_df, "columns"):
            for _, o in orders_df.iterrows():
                pid = int(o.get("positionId", 0))
                if pid == 0:
                    continue
                if pid not in sl_tp_by_position:
                    sl_tp_by_position[pid] = {"sl": None, "tp": None}
                otype = str(o.get("type", "")).lower()
                if otype == "stop":
                    sp = float(o.get("stopPrice", 0))
                    if sp > 0:
                        sl_tp_by_position[pid]["sl"] = sp
                elif otype == "limit":
                    p = float(o.get("price", 0))
                    if p > 0:
                        sl_tp_by_position[pid]["tp"] = p
    except Exception as exc:
        log.warning("Failed to fetch orders for SL/TP resolution: %s", exc)

    result: dict[int, PosSnapshot] = {}
    for _, row in df.iterrows():
        try:
            pid = int(row.get("id", 0))
            if pid == 0:
                continue

            iid = int(row.get("tradableInstrumentId", 0))

            # Resolve symbol name from instrument ID (cached)
            if iid not in symbol_cache:
                try:
                    symbol_cache[iid] = tl.get_symbol_name_from_instrument_id(iid).replace(".X", "")
                except Exception:
                    symbol_cache[iid] = f"INST_{iid}"

            symbol = symbol_cache[iid]
            side = str(row.get("side", "")).lower()
            qty = float(row.get("qty", 0))
            avg_price = float(row.get("avgPrice", 0))

            # SL/TP prices come from the orders table (positions only have stopLossId/takeProfitId)
            sl_tp = sl_tp_by_position.get(pid, {"sl": None, "tp": None})
            sl = sl_tp["sl"]
            tp = sl_tp["tp"]

            result[pid] = PosSnapshot(
                position_id=pid,
                instrument_id=iid,
                symbol=symbol,
                side=side,
                qty=qty,
                avg_price=avg_price,
                stop_loss=sl,
                take_profit=tp,
            )
        except Exception as exc:
            log.warning("Failed to parse position row: %s", exc)
            continue

    return result


# ── CopyTrader ────────────────────────────────────────────────────────────────


class CopyTrader:
    """Polls master account and mirrors trades to slave account."""

    def __init__(self):
        master_num = int(os.getenv("TL_ACC_NUM_MASTER", "2165806"))
        slave_num = int(os.getenv("TL_ACC_NUM_SLAVE", "2165807"))

        self.master = _create_tlapi("MASTER", master_num)
        self.slave = _create_tlapi("SLAVE", slave_num)

        # Per-instance caches (instruments resolve to different IDs per account session)
        self._master_inst_cache: dict[str, int] = {}
        self._slave_inst_cache: dict[str, int] = {}
        self._master_sym_cache: dict[int, str] = {}
        self._slave_sym_cache: dict[int, str] = {}

        # State tracking
        self._master_positions: dict[int, PosSnapshot] = {}
        self._slave_positions: dict[int, PosSnapshot] = {}

        # Mapping: master_position_id → slave_position_id
        self._master_to_slave: dict[int, int] = {}

        # Track SL/TP we've set on slave to detect master modifications
        self._slave_sl_tp: dict[int, tuple[float | None, float | None]] = {}

    def poll(self):
        """One poll cycle: detect opens, closes, modifications."""
        new_master = _snapshot_positions(self.master, self._master_inst_cache, self._master_sym_cache)
        new_slave = _snapshot_positions(self.slave, self._slave_inst_cache, self._slave_sym_cache)

        master_ids = set(new_master.keys())
        prev_master_ids = set(self._master_positions.keys())

        # ── Detect new opens on master ──
        opened = master_ids - prev_master_ids
        for mid in opened:
            pos = new_master[mid]
            log.info("NEW MASTER  #%s  %s %s %.2f lots @ %.5f  SL=%s TP=%s",
                     mid, pos.side.upper(), pos.symbol, pos.qty, pos.avg_price,
                     pos.stop_loss, pos.take_profit)
            self._open_on_slave(pos)

        # ── Detect closes on master ──
        closed = prev_master_ids - master_ids
        for mid in closed:
            if mid in self._master_to_slave:
                sid = self._master_to_slave.pop(mid)
                log.info("CLOSE MASTER #%s → closing SLAVE #%s", mid, sid)
                self._close_on_slave(sid)
                self._slave_sl_tp.pop(sid, None)
            else:
                log.warning("Master position #%s closed but no slave mapping found", mid)

        # ── Detect SL/TP modifications on master ──
        for mid in master_ids:
            pos = new_master[mid]
            if mid not in self._master_to_slave:
                continue  # new position, handled above
            sid = self._master_to_slave[mid]
            if sid not in new_slave:
                log.warning("Slave position #%s missing for master #%s", sid, mid)
                continue

            prev = self._master_positions.get(mid)
            if prev is None:
                continue

            sl_changed = pos.stop_loss != prev.stop_loss
            tp_changed = pos.take_profit != prev.take_profit

            if sl_changed or tp_changed:
                log.info("MODIFY MASTER #%s  SL: %s→%s  TP: %s→%s",
                         mid, prev.stop_loss, pos.stop_loss, prev.take_profit, pos.take_profit)
                self._modify_on_slave(sid, pos.stop_loss, pos.take_profit)

        # ── Update state ──
        self._master_positions = new_master
        self._slave_positions = new_slave

    def _open_on_slave(self, master_pos: PosSnapshot):
        """Open a proportionally-sized position on the slave account."""
        try:
            # Get slave equity
            state = self.slave.get_account_state()
            equity = float(state.get("balance", state.get("equity", 0)))
            if equity <= 0:
                log.error("SLAVE equity is 0, cannot size")
                return

            # Calculate stop distance from master position
            if master_pos.stop_loss is not None and master_pos.avg_price > 0:
                stop_distance = abs(master_pos.avg_price - master_pos.stop_loss)
            else:
                # No SL on master — use a default 1.5% stop distance
                stop_distance = master_pos.avg_price * 0.015
                log.warning("No SL on master, using default 1.5%% stop distance (%.5f)", stop_distance)

            is_jpy = master_pos.symbol.upper().replace(".X", "") in _JPY_PAIRS
            lots = _calc_lots(equity, stop_distance, is_jpy)

            # Resolve instrument on slave
            iid = _resolve_id(self.slave, master_pos.symbol, self._slave_inst_cache)

            log.info("OPEN SLAVE  %s %s  lots=%.2f (master had %.2f)  equity=%.2f  risk=%.1f%%",
                     master_pos.side.upper(), master_pos.symbol, lots, master_pos.qty,
                     equity, RISK_PCT * 100)

            if DRY_RUN:
                log.info("[DRY RUN] would open %s %s %.2f lots", master_pos.side, master_pos.symbol, lots)
                return

            order_id = self.slave.create_order(
                instrument_id=iid,
                quantity=lots,
                side=master_pos.side,
                type_="market",
                stop_loss=master_pos.stop_loss,
                stop_loss_type="absolute" if master_pos.stop_loss else None,
                take_profit=master_pos.take_profit,
                take_profit_type="absolute" if master_pos.take_profit else None,
            )

            if order_id:
                log.info("SLAVE order placed  order_id=%s", order_id)
                # Wait briefly for fill, then find the new position
                time.sleep(1)
                self._link_slave_position(master_pos, lots)
            else:
                log.error("SLAVE create_order returned None for %s", master_pos.symbol)

        except Exception as exc:
            log.error("Failed to open on slave: %s", exc, exc_info=True)

    def _link_slave_position(self, master_pos: PosSnapshot, expected_lots: float):
        """After opening, find the new slave position and create mapping."""
        try:
            slave_poses = _snapshot_positions(self.slave, self._slave_inst_cache, self._slave_sym_cache)
            for sid, spos in slave_poses.items():
                if (
                    sid not in self._slave_sl_tp.values()
                    and spos.instrument_id == _resolve_id(self.slave, master_pos.symbol, self._slave_inst_cache)
                    and spos.side == master_pos.side
                    and abs(spos.qty - expected_lots) < expected_lots * 0.1
                ):
                    # Found it
                    master_id = None
                    for mid, pos in self._master_positions.items():
                        if pos.instrument_id == master_pos.instrument_id and pos.side == master_pos.side:
                            master_id = mid
                            break
                    if master_id is not None:
                        self._master_to_slave[master_id] = sid
                        self._slave_sl_tp[sid] = (spos.stop_loss, spos.take_profit)
                        log.info("Linked master #%s → slave #%s", master_id, sid)
                    break
        except Exception as exc:
            log.warning("Could not link slave position: %s", exc)

    def _close_on_slave(self, slave_position_id: int):
        """Close a position on the slave account."""
        if DRY_RUN:
            log.info("[DRY RUN] would close slave position #%s", slave_position_id)
            return
        try:
            ok = self.slave.close_position(position_id=slave_position_id)
            if ok:
                log.info("SLAVE position #%s closed", slave_position_id)
            else:
                log.warning("SLAVE close_position returned False for #%s", slave_position_id)
        except Exception as exc:
            log.error("Failed to close slave #%s: %s", slave_position_id, exc)

    def _modify_on_slave(self, slave_position_id: int, sl: float | None, tp: float | None):
        """Modify SL/TP on slave to match master."""
        if DRY_RUN:
            log.info("[DRY RUN] would modify slave #%s  SL=%s TP=%s", slave_position_id, sl, tp)
            return
        try:
            params: dict[str, Any] = {}
            if sl is not None:
                params["stopLoss"] = sl
                params["stopLossType"] = "absolute"
            if tp is not None:
                params["takeProfit"] = tp
                params["takeProfitType"] = "absolute"

            if not params:
                return

            ok = self.slave.modify_position(slave_position_id, params)
            if ok:
                log.info("SLAVE #%s modified  SL=%s TP=%s", slave_position_id, sl, tp)
                self._slave_sl_tp[slave_position_id] = (sl, tp)
            else:
                log.warning("SLAVE modify_position returned False for #%s", slave_position_id)
        except Exception as exc:
            log.error("Failed to modify slave #%s: %s", slave_position_id, exc)

    def run(self):
        """Main polling loop. Runs forever until interrupted."""
        log.info("Copy Trader started  risk=%.1f%%  poll=%ds  dry_run=%s",
                 RISK_PCT * 100, POLL_INTERVAL, DRY_RUN)
        log.info("Master account: %s  Slave account: %s",
                 os.getenv("TL_ACC_NUM_MASTER", "2165806"),
                 os.getenv("TL_ACC_NUM_SLAVE", "2165807"))

        # Initial sync: snapshot current state without acting on it
        log.info("Syncing current positions...")
        self._master_positions = _snapshot_positions(
            self.master, self._master_inst_cache, self._master_sym_cache)
        self._slave_positions = _snapshot_positions(
            self.slave, self._slave_inst_cache, self._slave_sym_cache)

        log.info("Master has %d open positions, Slave has %d open positions",
                 len(self._master_positions), len(self._slave_positions))

        # Pre-link existing positions if they match by instrument+side
        self._prelink_existing()

        log.info("Entering poll loop (Ctrl+C to stop)...")
        while True:
            time.sleep(POLL_INTERVAL)
            try:
                self.poll()
            except KeyboardInterrupt:
                log.info("Stopped by user")
                break
            except Exception as exc:
                log.error("Poll error: %s", exc, exc_info=True)
                time.sleep(5)

    def _prelink_existing(self):
        """Link master↔slave positions that already exist on startup."""
        for mid, mpos in self._master_positions.items():
            if mid in self._master_to_slave:
                continue
            for sid, spos in self._slave_positions.items():
                if sid in self._master_to_slave.values():
                    continue
                if (
                    mpos.instrument_id == spos.instrument_id
                    or mpos.symbol == spos.symbol
                ) and mpos.side == spos.side:
                    self._master_to_slave[mid] = sid
                    self._slave_sl_tp[sid] = (spos.stop_loss, spos.take_profit)
                    log.info("Pre-linked master #%s → slave #%s  %s %s", mid, sid, mpos.side, mpos.symbol)
                    break


# ── CLI ───────────────────────────────────────────────────────────────────────


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Copy Trader — mirror master→slave on TradeLocker")
    ap.add_argument("--dry-run", action="store_true", help="Log actions without placing orders")
    ap.add_argument("--risk", type=float, default=None, help="Override risk %% (e.g. 0.005 for 0.5%%)")
    ap.add_argument("--poll", type=int, default=None, help="Override poll interval in seconds")
    ap.add_argument("--status", action="store_true", help="Print account status and exit")
    args = ap.parse_args()

    if args.dry_run:
        os.environ["COPY_DRY_RUN"] = "true"
    if args.risk is not None:
        os.environ["COPY_RISK_PCT"] = str(args.risk)
    if args.poll is not None:
        os.environ["COPY_POLL_INTERVAL"] = str(args.poll)

    trader = CopyTrader()

    if args.status:
        for label, tl in [("MASTER", trader.master), ("SLAVE", trader.slave)]:
            try:
                state = tl.get_account_state()
                print(f"{label}: balance={state.get('balance', '?')}  "
                      f"equity={state.get('projectedBalance', state.get('equity', '?'))}  "
                      f"positions={state.get('positionsCount', '?')}")
            except Exception as exc:
                print(f"{label}: error fetching state: {exc}")
        return

    trader.run()


if __name__ == "__main__":
    main()
