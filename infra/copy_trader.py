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

# ── TLAPI instances ───────────────────────────────────────────────────────────


def _create_tlapi(label: str, acc_num: int):
    """Create an independent TLAPI instance for one account."""
    from tradelocker import TLAPI

    active_env = os.getenv("TL_ACTIVE_ENV", "demo").lower()
    suffix = active_env.upper()
    env = os.getenv(f"TL_ENVIRONMENT_{suffix}", "")
    username = os.getenv(f"TL_USERNAME_{suffix}", "")
    password = os.getenv(f"TL_PASSWORD_{suffix}", "")
    server = os.getenv(f"TL_SERVER_{suffix}", "")

    if not all([env, username, password, server]):
        raise RuntimeError(
            f"Missing TL credentials for '{active_env}' environment. "
            f"Set TL_ENVIRONMENT_{suffix}, TL_USERNAME_{suffix}, TL_PASSWORD_{suffix}, "
            f"and TL_SERVER_{suffix} in .env"
        )

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


def _calc_slave_lots(master_lots: float, master_equity: float, slave_equity: float) -> float:
    """Scale master position size by account equity ratio.

    The master's lot size already reflects the intended risk per trade
    (risk_pct of master equity). We replicate the same risk exposure on
    the slave by scaling lots proportionally to the slave's equity.

    Slave lots = master_lots * (slave_equity / master_equity)

    No instrument-specific multipliers needed — works for any asset class.
    """
    if master_equity <= 0 or slave_equity <= 0:
        return LOT_STEP
    ratio = slave_equity / master_equity
    raw = master_lots * ratio
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


def _snapshot_positions(tl, instrument_cache: dict, symbol_cache: dict) -> dict[int, PosSnapshot] | None:
    """Fetch all open positions and return {position_id: PosSnapshot}.

    Returns None if the API call failed (rate-limited). Returns {} if the
    call succeeded but there are no positions. Callers must distinguish these.

    SL/TP comes from the position row directly (TLAPI includes stopLoss/takeProfit
    columns). No separate orders call needed — that halves API requests and avoids
    rate-limit pressure on the demo environment.
    """
    try:
        df = tl.get_all_positions()
    except Exception as exc:
        log.error("get_all_positions failed: %s", exc)
        return None  # None = API error (rate-limited)

    if df is None or (hasattr(df, "empty") and df.empty):
        return {}  # empty dict = success, no positions

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

            # TLAPI includes absolute stopLoss/takeProfit on the position row
            row_sl = float(row.get("stopLoss", 0) or 0)
            sl = row_sl if row_sl > 0 else None
            row_tp = float(row.get("takeProfit", 0) or 0)
            tp = row_tp if row_tp > 0 else None

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

        # Set of (symbol, side) that we've recently ordered to open on slave.
        # Prevents re-opening same position if the link step fails after placing the order.
        self._pending_opens: set[tuple[str, str]] = set()

        # Rate-limit backoff counter: incremented on skipped polls, reset on success
        self._backoff = 0


    def poll(self):
        """One poll cycle: detect opens, closes, modifications.

        Uses get_account_state() as a canary (not rate-limited) to detect new
        positions even when get_all_positions() is rate-limited.
        """
        # ── Check account state first — not rate-limited ──
        m_cnt = s_cnt = 0
        try:
            m_state = self.master.get_account_state()
            s_state = self.slave.get_account_state()
            m_cnt = m_state.get("positionsCount", 0)
            s_cnt = s_state.get("positionsCount", 0)
        except Exception:
            log.warning("Account state fetch failed, skipping poll")
            self._backoff += 1
            return

        new_master = _snapshot_positions(self.master, self._master_inst_cache, self._master_sym_cache)
        new_slave = _snapshot_positions(self.slave, self._slave_inst_cache, self._slave_sym_cache)

        # None = API call failed (rate-limited). Back off, try again later.
        if new_master is None or new_slave is None:
            log.warning("Rate-limited: master=%s slave=%s (positionsCount=%d/%d)",
                        "FAIL" if new_master is None else "ok",
                        "FAIL" if new_slave is None else "ok",
                        m_cnt, s_cnt)
            self._backoff += 1
            return

        # Both snapshots succeeded (may be empty or have data) — proceed

        master_ids = set(new_master.keys())
        prev_master_ids = set(self._master_positions.keys())

        # ── Detect new opens on master ──
        opened = master_ids - prev_master_ids
        for mid in opened:
            pos = new_master[mid]
            log.info("NEW MASTER  #%s  %s %s %.2f lots @ %.5f  SL=%s TP=%s",
                     mid, pos.side.upper(), pos.symbol, pos.qty, pos.avg_price,
                     pos.stop_loss, pos.take_profit)

            # Check 1: skip if we already have a pending open for this symbol+side
            # (link step failed previously, but we already placed the order)
            if (pos.symbol, pos.side) in self._pending_opens:
                log.info("SKIP — pending open exists for %s %s (re-linking instead)",
                         pos.side, pos.symbol)
                self._relink_to_slave(mid, pos.symbol, pos.side, new_slave)
                continue

            # Check 2: don't open if slave already has an unlinked position for this symbol+side.
            # This prevents duplicates when slave snapshot was missing the position on a prior
            # cycle (e.g. due to 429).
            already_on_slave = any(
                spos.side == pos.side and spos.symbol == pos.symbol
                and sid not in self._master_to_slave.values()
                for sid, spos in new_slave.items()
            )
            if already_on_slave:
                log.info("SKIP — slave already has open %s %s (re-linking)",
                         pos.side, pos.symbol)
                self._relink_to_slave(mid, pos.symbol, pos.side, new_slave)
                continue

            self._open_on_slave(pos)

        # ── Detect closes on master ──
        closed = prev_master_ids - master_ids
        for mid in closed:
            closed_pos = self._master_positions.get(mid)
            if closed_pos:
                self._pending_opens.discard((closed_pos.symbol, closed_pos.side))
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

        # ── Resolve pending opens (link after deferred link step) ──
        # Runs every cycle, retrying until the slave position is found.
        if self._pending_opens:
            for mid, mpos in list(self._master_positions.items()):
                key = (mpos.symbol, mpos.side)
                if key in self._pending_opens and mid not in self._master_to_slave:
                    self._relink_to_slave(mid, mpos.symbol, mpos.side, new_slave)

        # ── Update state ──
        self._master_positions = new_master
        self._slave_positions = new_slave
        self._backoff = 0  # successful poll resets rate-limit backoff

    def _relink_to_slave(self, master_id: int, symbol: str, side: str, slave_snapshot: dict):
        """Find a matching unlinked slave position and link it to master."""
        for sid, spos in slave_snapshot.items():
            if (
                spos.symbol == symbol
                and spos.side == side
                and sid not in self._master_to_slave.values()
            ):
                self._master_to_slave[master_id] = sid
                self._slave_sl_tp[sid] = (spos.stop_loss, spos.take_profit)
                self._pending_opens.discard((symbol, side))
                log.info("Re-linked master #%s → slave #%s  %s %s", master_id, sid, side, symbol)
                return
        log.warning("No unlinked slave position found for %s %s to re-link", side, symbol)

    def _open_on_slave(self, master_pos: PosSnapshot):
        """Open a proportionally-sized position on the slave account."""
        # Mark as pending immediately so re-detection won't double-open.
        self._pending_opens.add((master_pos.symbol, master_pos.side))
        try:
            # Get both account equities for proportional sizing
            slave_state = self.slave.get_account_state()
            slave_equity = float(slave_state.get("balance", slave_state.get("equity", 0)))
            if slave_equity <= 0:
                log.error("SLAVE equity is 0, cannot size")
                return

            master_state = self.master.get_account_state()
            master_equity = float(master_state.get("balance", master_state.get("equity", 0)))
            if master_equity <= 0:
                log.error("MASTER equity is 0, cannot size")
                return

            # Scale master lots by equity ratio — same risk exposure on both accounts
            lots = _calc_slave_lots(master_pos.qty, master_equity, slave_equity)

            # Resolve instrument on slave
            iid = _resolve_id(self.slave, master_pos.symbol, self._slave_inst_cache)

            ratio = slave_equity / master_equity if master_equity > 0 else 0
            log.info("OPEN SLAVE  %s %s  lots=%.2f (master %.2f)  equities %.0f→%.0f (%.2fx)",
                     master_pos.side.upper(), master_pos.symbol, lots, master_pos.qty,
                     master_equity, slave_equity, ratio)

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
                log.info("SLAVE order placed  order_id=%s  (link deferred to next poll)", order_id)
            else:
                log.error("SLAVE create_order returned None for %s", master_pos.symbol)

        except Exception as exc:
            log.error("Failed to open on slave: %s", exc, exc_info=True)

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

        # Initial sync: retry until we get a clean snapshot of both accounts.
        # Without this, existing positions look "new" on first successful poll → duplicates.
        # Use get_account_state() first (not rate-limited) to check positionsCount.
        # If both accounts are empty, we're done. If non-empty but get_all_positions
        # is rate-limited (returns {}), back off and retry.
        log.info("Syncing current positions...")
        self._master_positions = {}
        self._slave_positions = {}
        initial_backoff = 0
        while True:
            try:
                m_state = self.master.get_account_state()
                s_state = self.slave.get_account_state()
            except Exception:
                # Account state failed — auth/connectivity issue, retry
                initial_backoff += 1
                delay = min(15 * (2 ** initial_backoff), 300)
                log.warning("Account state fetch failed, retry in %ds...", delay)
                time.sleep(delay)
                continue

            m_cnt = m_state.get("positionsCount", 0)
            s_cnt = s_state.get("positionsCount", 0)

            # Both empty — done
            if m_cnt == 0 and s_cnt == 0:
                log.info("Both accounts have 0 open positions")
                break

            # Positions exist — try to get their details
            mp = _snapshot_positions(self.master, self._master_inst_cache, self._master_sym_cache)
            sp = _snapshot_positions(self.slave, self._slave_inst_cache, self._slave_sym_cache)

            # None = API rate-limited
            if mp is None or sp is None:
                initial_backoff += 1
                delay = min(15 * (2 ** initial_backoff), 300)
                log.warning("Initial sync retry in %ds — rate-limited", delay)
                time.sleep(delay)
                continue

            # Got position details for both accounts
            if len(mp) > 0 and len(sp) > 0:
                self._master_positions = mp
                self._slave_positions = sp
                break

            # Snapshots returned empty despite positionsCount > 0 — race condition
            # (position closed between account state check and positions call), retry.
            initial_backoff += 1
            delay = min(15 * (2 ** initial_backoff), 300)
            log.warning("Initial sync retry in %ds — snapshots empty (master: %d, slave: %d)",
                        delay, m_cnt, s_cnt)
            time.sleep(delay)

        log.info("Master has %d open positions, Slave has %d open positions",
                 len(self._master_positions), len(self._slave_positions))

        # Pre-link existing positions if they match by instrument+side
        self._prelink_existing()

        log.info("Entering poll loop (Ctrl+C to stop)...")
        while True:
            # Exponential backoff: after a rate-limited poll, double the wait up to 5 min
            backoff = POLL_INTERVAL * (2 ** min(self._backoff, 6))  # max 64x
            time.sleep(min(backoff, 300))
            try:
                self.poll()
            except KeyboardInterrupt:
                log.info("Stopped by user")
                break
            except Exception as exc:
                log.error("Poll error: %s", exc, exc_info=True)
            time.sleep(15)

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
