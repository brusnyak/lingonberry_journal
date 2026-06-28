#!/usr/bin/env python3
"""cTrader Copy Trader — mirrors manual trades from master to slave account.

Single CtraderClient with both accounts authed. Polls master, mirrors to slave.

Sizing: both accounts use the same risk_pct (default 0.5%). Lot size is calculated
independently per account based on its own equity and stop distance.

Environment variables:
    CTRADER_CLIENT_ID          cTrader app client ID
    CTRADER_SECRET             cTrader app secret
    CTRADER_ACCESS_TOKEN       cTrader OAuth access token
    CTRADER_ACC_NUM_MASTER     Master account ID (BlackBull: 44798689)
    CTRADER_ACC_NUM_SLAVE      Slave account ID (Spotware 100K: 47747211)
    COPY_RISK_PCT              Risk per trade as fraction (default 0.005)
    COPY_POLL_INTERVAL         Seconds between polls (default 3)
    COPY_LOT_STEP              Minimum lot increment (default 0.01)
    COPY_MAX_LOTS              Maximum lots per order (default 20.0)
    COPY_DRY_RUN               "true" → log actions, never place orders
"""
from __future__ import annotations

import logging
import math
import os
import sys
import time
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ctrader-mirror")

# ── Config ────────────────────────────────────────────────────────────────────

RISK_PCT = float(os.getenv("COPY_RISK_PCT", "0.005"))
POLL_INTERVAL = int(os.getenv("COPY_POLL_INTERVAL", "3"))
LOT_STEP = float(os.getenv("COPY_LOT_STEP", "0.01"))
MAX_LOTS = float(os.getenv("COPY_MAX_LOTS", "20.0"))
DRY_RUN = os.getenv("COPY_DRY_RUN", "true").lower() == "true"

MASTER_ACCOUNT_ID = int(os.getenv("CTRADER_ACC_NUM_MASTER", "44798689"))
SLAVE_ACCOUNT_ID = int(os.getenv("CTRADER_ACC_NUM_SLAVE", "47747211"))

_JPY_PAIRS = {"EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "USDJPY", "NZDJPY"}


def _calc_lots(equity: float, stop_distance: float, is_jpy: bool) -> float:
    """Risk-based lot sizing."""
    mult = 1_000 if is_jpy else 100_000
    risk_amt = equity * RISK_PCT
    if stop_distance <= 0:
        return LOT_STEP
    raw = (risk_amt / stop_distance) / mult
    size = round(math.floor(raw / LOT_STEP) * LOT_STEP, 2)
    return max(min(size, MAX_LOTS), LOT_STEP)


@dataclass
class PosSnapshot:
    """Snapshot of a single open position."""
    position_id: int
    symbol: str
    symbol_id: int
    side: str
    qty: float
    avg_price: float
    stop_loss: float | None = None
    take_profit: float | None = None


class CtraderCopyTrader:
    """Polls master account on cTrader and mirrors trades to slave."""

    def __init__(self, client=None):
        if client is not None:
            self.client = client
        else:
            from infra.ctrader_client import CtraderClient
            log.info("Connecting accounts %s (master) and %s (slave)...",
                     MASTER_ACCOUNT_ID, SLAVE_ACCOUNT_ID)
            self.client = CtraderClient(
                account_ids=[MASTER_ACCOUNT_ID, SLAVE_ACCOUNT_ID]
            )
            self.client.connect()

        self._master_positions: dict[int, PosSnapshot] = {}
        self._slave_positions: dict[int, PosSnapshot] = {}
        self._master_to_slave: dict[int, int] = {}
        self._slave_sl_tp: dict[int, tuple[float | None, float | None]] = {}
        # Analytics
        self._poll_count: int = 0
        self._actions: dict[str, int] = {
            "opens": 0, "closes": 0, "modifies": 0, "errors": 0,
        }
        self._heartbeat_interval: int = int(os.getenv("COPY_HEARTBEAT", "20"))

    def _snapshot(self, account_id: int) -> dict[int, PosSnapshot]:
        """Fetch and snapshot all open positions from one account."""
        try:
            positions = self.client.get_positions(account_id=account_id)
        except Exception as exc:
            log.error("get_positions(%s) failed: %s", account_id, exc)
            return {}

        result: dict[int, PosSnapshot] = {}
        for p in positions:
            sym_id = self.client.get_symbol_id(p.symbol, account_id=account_id) or 0
            result[p.position_id] = PosSnapshot(
                position_id=p.position_id,
                symbol=p.symbol,
                symbol_id=sym_id,
                side=p.side,
                qty=p.lots,
                avg_price=p.open_price,
                stop_loss=p.stop_loss,
                take_profit=p.take_profit,
            )
        return result

    def _log_heartbeat(self):
        n_master = len(self._master_positions)
        n_slave = len(self._slave_positions)
        n_linked = len(self._master_to_slave)
        log.info("HEARTBEAT  polls=%d  master=%d  slave=%d  linked=%d  actions=%s",
                 self._poll_count, n_master, n_slave, n_linked, self._actions)

    def poll(self):
        """One poll cycle: detect opens, closes, modifications."""
        self._poll_count += 1
        new_master = self._snapshot(MASTER_ACCOUNT_ID)
        new_slave = self._snapshot(SLAVE_ACCOUNT_ID)

        master_ids = set(new_master.keys())
        prev_master_ids = set(self._master_positions.keys())

        # ── New opens on master ──
        opened = master_ids - prev_master_ids
        for mid in opened:
            pos = new_master[mid]
            log.info("NEW MASTER  #%s  %s %s %.2f lots @ %.5f  SL=%s TP=%s",
                     mid, pos.side.upper(), pos.symbol, pos.qty, pos.avg_price,
                     pos.stop_loss, pos.take_profit)
            self._open_on_slave(pos)

        # ── Closes on master ──
        closed = prev_master_ids - master_ids
        for mid in closed:
            if mid in self._master_to_slave:
                sid = self._master_to_slave.pop(mid)
                log.info("CLOSE MASTER #%s → closing SLAVE #%s", mid, sid)
                self._close_on_slave(sid)
                self._slave_sl_tp.pop(sid, None)
            else:
                log.warning("Master #%s closed but no slave mapping", mid)

        # ── SL/TP modifications on master ──
        for mid in master_ids:
            pos = new_master[mid]
            if mid not in self._master_to_slave:
                continue
            sid = self._master_to_slave[mid]
            if sid not in new_slave:
                log.warning("Slave #%s missing for master #%s", sid, mid)
                continue
            prev = self._master_positions.get(mid)
            if prev is None:
                continue
            sl_changed = pos.stop_loss != prev.stop_loss
            tp_changed = pos.take_profit != prev.take_profit
            if sl_changed or tp_changed:
                log.info("MODIFY MASTER #%s  SL: %s→%s  TP: %s→%s",
                         mid, prev.stop_loss, pos.stop_loss,
                         prev.take_profit, pos.take_profit)
                self._modify_on_slave(sid, pos.stop_loss, pos.take_profit)

        self._master_positions = new_master
        self._slave_positions = new_slave

        # Periodic heartbeat
        if self._poll_count % max(self._heartbeat_interval, 1) == 0:
            self._log_heartbeat()

    def _open_on_slave(self, master_pos: PosSnapshot):
        try:
            info = self.client.get_account_info(account_id=SLAVE_ACCOUNT_ID)
            equity = float(info.get("balance", 0))
            if equity <= 0:
                log.error("SLAVE equity is 0, cannot size")
                return

            if master_pos.stop_loss is not None and master_pos.avg_price > 0:
                stop_distance = abs(master_pos.avg_price - master_pos.stop_loss)
            else:
                stop_distance = master_pos.avg_price * 0.015
                log.warning("No SL on master, using 1.5%% default")

            is_jpy = master_pos.symbol.upper() in _JPY_PAIRS
            lots = _calc_lots(equity, stop_distance, is_jpy)

            log.info("OPEN SLAVE  %s %s  lots=%.2f (master=%.2f)  equity=%.2f",
                     master_pos.side.upper(), master_pos.symbol, lots,
                     master_pos.qty, equity)

            if DRY_RUN:
                log.info("[DRY RUN] would open %s %s %.2f lots",
                         master_pos.side, master_pos.symbol, lots)
                return

            # Phase 1: market order without SL/TP (cTrader rejects SL/TP on MARKET)
            result = self.client.create_order(
                symbol=master_pos.symbol,
                quantity=lots,
                side=master_pos.side,
                account_id=SLAVE_ACCOUNT_ID,
            )
            if not result.order_id:
                log.error("SLAVE order failed: %s", result.message)
                return

            log.info("SLAVE market order placed  id=%s", result.order_id)
            self._actions["opens"] += 1
            time.sleep(1.5)

            # Phase 2: set SL/TP on the new position
            slave_positions = self.client.get_positions(account_id=SLAVE_ACCOUNT_ID)
            new_slave = next((p for p in slave_positions
                              if p.position_id == result.order_id), None)

            if new_slave and (master_pos.stop_loss or master_pos.take_profit):
                sl = master_pos.stop_loss
                tp = master_pos.take_profit
                mod = self.client.modify_sltp(
                    new_slave.position_id,
                    stop_loss=sl,
                    take_profit=tp,
                    account_id=SLAVE_ACCOUNT_ID,
                )
                if mod.status == "modified":
                    log.info("SLAVE SL/TP set  SL=%s TP=%s", sl, tp)
                else:
                    log.warning("SLAVE SL/TP failed: %s", mod.message)

            self._link_slave_position(master_pos, lots)
        except Exception as exc:
            log.error("Failed to open on slave: %s", exc, exc_info=True)

    def _link_slave_position(self, master_pos: PosSnapshot, expected_lots: float):
        try:
            slave_poses = self._snapshot(SLAVE_ACCOUNT_ID)
            for sid, spos in slave_poses.items():
                if (sid not in self._slave_sl_tp and
                    spos.symbol == master_pos.symbol and
                    spos.side == master_pos.side and
                    abs(spos.qty - expected_lots) < expected_lots * 0.1):
                    for mid, pos in self._master_positions.items():
                        if pos.symbol == master_pos.symbol and pos.side == master_pos.side:
                            self._master_to_slave[mid] = sid
                            self._slave_sl_tp[sid] = (spos.stop_loss, spos.take_profit)
                            log.info("Linked master #%s → slave #%s", mid, sid)
                            return
        except Exception as exc:
            log.warning("Could not link slave position: %s", exc)

    def _close_on_slave(self, slave_position_id: int):
        if DRY_RUN:
            log.info("[DRY RUN] would close slave #%s", slave_position_id)
            return
        result = self.client.close_position(
            slave_position_id, account_id=SLAVE_ACCOUNT_ID
        )
        if result.status == "closed":
            log.info("SLAVE position #%s closed", slave_position_id)
            self._actions["closes"] += 1
        else:
            log.warning("SLAVE close #%s failed: %s", slave_position_id, result.message)
            self._actions["errors"] += 1

    def _modify_on_slave(self, slave_id: int, sl: float | None, tp: float | None):
        if DRY_RUN:
            log.info("[DRY RUN] would modify slave #%s  SL=%s TP=%s", slave_id, sl, tp)
            return
        result = self.client.modify_sltp(
            slave_id, stop_loss=sl, take_profit=tp, account_id=SLAVE_ACCOUNT_ID
        )
        if result.status == "modified":
            log.info("SLAVE #%s modified  SL=%s TP=%s", slave_id, sl, tp)
            self._slave_sl_tp[slave_id] = (sl, tp)
            self._actions["modifies"] += 1
        else:
            log.warning("SLAVE #%s modify failed: %s", slave_id, result.message)
            self._actions["errors"] += 1

    def run(self):
        """Main polling loop. Runs forever until interrupted."""
        log.info("cTrader Copy Trader started  risk=%.1f%%  poll=%ds  dry_run=%s",
                 RISK_PCT * 100, POLL_INTERVAL, DRY_RUN)
        log.info("Master: %s  Slave: %s", MASTER_ACCOUNT_ID, SLAVE_ACCOUNT_ID)

        self._master_positions = self._snapshot(MASTER_ACCOUNT_ID)
        self._slave_positions = self._snapshot(SLAVE_ACCOUNT_ID)
        log.info("Master %d positions, Slave %d",
                 len(self._master_positions), len(self._slave_positions))
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
        for mid, mpos in self._master_positions.items():
            if mid in self._master_to_slave:
                continue
            for sid, spos in self._slave_positions.items():
                if sid in self._master_to_slave.values():
                    continue
                if mpos.symbol == spos.symbol and mpos.side == spos.side:
                    self._master_to_slave[mid] = sid
                    self._slave_sl_tp[sid] = (spos.stop_loss, spos.take_profit)
                    log.info("Pre-linked master #%s → slave #%s  %s %s",
                             mid, sid, mpos.side, mpos.symbol)
                    break


def main():
    import argparse
    ap = argparse.ArgumentParser(description="cTrader Copy Trader")
    ap.add_argument("--dry-run", action="store_true", help="Log only, no trades")
    ap.add_argument("--risk", type=float, default=None, help="Risk %% (e.g. 0.005)")
    ap.add_argument("--poll", type=int, default=None, help="Poll interval seconds")
    ap.add_argument("--status", action="store_true", help="Print account status and exit")
    args = ap.parse_args()

    if args.dry_run:
        os.environ["COPY_DRY_RUN"] = "true"
    if args.risk is not None:
        os.environ["COPY_RISK_PCT"] = str(args.risk)
    if args.poll is not None:
        os.environ["COPY_POLL_INTERVAL"] = str(args.poll)

    trader = CtraderCopyTrader()

    if args.status:
        for aid, label in [(MASTER_ACCOUNT_ID, "MASTER"), (SLAVE_ACCOUNT_ID, "SLAVE")]:
            try:
                info = trader.client.get_account_info(account_id=aid)
                print(f"{label} ({aid}): balance={info.get('balance')}  broker={info.get('broker')}")
            except Exception as exc:
                print(f"{label} ({aid}): error: {exc}")
        return

    trader.run()


if __name__ == "__main__":
    main()
