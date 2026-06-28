#!/usr/bin/env python3
"""
Position Manager — structure-based trailing SL and news-aware partial closes.

Decoupled from the copy trader. Works with any CtraderClient.

Phases:
  Phase 1 (this file): trail SL to breakeven + structure levels after price
    moves far enough in our favor.
  Phase 2 (TODO): news-aware partial closes — only when in profit, no rigid stops.

Strategy:
  ┌───────────────┬─────────────────────────────────────────────────────┐
  │ Price Action  │ Action                                              │
  ├───────────────┼─────────────────────────────────────────────────────┤
  │ Hits 0.5×risk │ Wait — too early                                    │
  │ Hits 1.0×risk │ Move SL to entry + 1 spread (breakeven)             │
  │ Hits 1.5×risk │ Look for nearest swing point as trailing SL         │
  │ Hits 2.0×risk │ Tighten to nearest structure level (higher TF)      │
  │ News window   │ Phase 2: close 50% if in profit, no new entries     │
  └───────────────┴─────────────────────────────────────────────────────┘

Usage:
    # Standalone
    from infra.position_manager import PositionManager
    pm = PositionManager(client=ct)
    pm.run()

    # Or import existing client
    from infra.ctrader_client import CtraderClient
    ct = CtraderClient(account_ids=[44798689, 47747211])
    ct.connect()
    pm = PositionManager(client=ct, account_ids=[44798689, 47747211])
    pm.run()

    # With a TradeLocker client (future):
    # pm = PositionManager(client=tradelocker_client, account_ids=[...])
"""
from __future__ import annotations

import logging
import math
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

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
log = logging.getLogger("position-mgr")

# ── Config ────────────────────────────────────────────────────────────────────

POLL_INTERVAL = int(os.getenv("PM_POLL_INTERVAL", "5"))
BE_MULTIPLE = float(os.getenv("PM_BE_MULTIPLE", "1.0"))       # R倍数 at which SL→BE
TRAIL_MULTIPLE = float(os.getenv("PM_TRAIL_MULTIPLE", "1.5"))  # R倍数 to trail via swing points
TIGHTEN_MULTIPLE = float(os.getenv("PM_TIGHTEN_MULTIPLE", "2.0"))  # R倍数 to tighten to higher-TF structure
NEWS_PARTIAL_PCT = float(os.getenv("PM_NEWS_PARTIAL_PCT", "0.5"))   # Fraction to close during news
SPREAD_BUFFER_MULT = float(os.getenv("PM_SPREAD_BUFFER", "0.3"))    # Buffer above BE in R units
DRY_RUN = os.getenv("PM_DRY_RUN", "true").lower() == "true"

# Swing point trailing config
SWING_PERIOD = int(os.getenv("PM_SWING_PERIOD", "2"))         # 2 = M5
SWING_LENGTH = int(os.getenv("PM_SWING_LENGTH", "3"))         # 3-bar pivot (~15 min on M5)
SWING_BUFFER_PCT = float(os.getenv("PM_SWING_BUFFER", "0.1"))  # 10% of R as buffer below swing
OHLC_COUNT = int(os.getenv("PM_OHLC_COUNT", "100"))           # bars to fetch
OHLC_CACHE_SEC = int(os.getenv("PM_OHLC_CACHE_SEC", "30"))    # re-fetch OHLC every N seconds


@dataclass
class ManagedPosition:
    """Tracking state for a single managed position."""
    position_id: int
    account_id: int
    symbol: str
    side: str
    entry_price: float
    volume_cents: int
    initial_risk_r: float          # R in price units (entry−SL or SL−entry)
    current_sl: float | None = None
    be_set: bool = False           # SL moved to breakeven
    trailing: bool = False         # SL following structure
    last_action: str = "monitoring"
    risk_distance: float = 0.0     # Cached risk distance in price units

    @property
    def lots(self) -> float:
        return self.volume_cents / 100_000


from infra.client_interface import ClientInterface


class PositionManager:
    """
    Polls accounts, evaluates each position against structure/risk rules,
    adjusts SL/TP accordingly.

    Provide either a connected ClientInterface (CtraderClient, TradelockerClient)
    or let the manager create its own CtraderClient.
    """

    def __init__(
        self,
        client: ClientInterface | None = None,
        account_ids: list[int] | None = None,
    ):
        if client is not None:
            self.client = client
        else:
            from infra.ctrader_client import CtraderClient
            if not account_ids:
                default = os.getenv("PM_ACCOUNT_IDS", "")
                account_ids = [int(x) for x in default.split(",") if x.strip()]
                if not account_ids:
                    account_ids = [int(os.getenv("CTRADER_ACCOUNT_ID", "0"))]
            log.info("Connecting accounts %s...", account_ids)
            self.client = CtraderClient(account_ids=account_ids)
            self.client.connect()

        self._account_ids = account_ids or self.client.account_ids
        self._managed: dict[int, ManagedPosition] = {}  # position_id → state
        self._ohlc_cache: dict[str, tuple[float, pd.DataFrame]] = {}
        self._trail_time: dict[int, float] = {}  # position_id → last trail time

        # Analytics
        self._eval_count: int = 0
        self._actions: dict[str, int] = {"breakeven": 0, "trail_structure": 0, "trail_fallback": 0}
        self._heartbeat_interval: int = int(os.getenv("PM_HEARTBEAT", "60"))  # log stats every N polls

    # ── Public ───────────────────────────────────────────────────────────

    def run(self):
        """Main polling loop. Runs forever until interrupted."""
        log.info("Position Manager started  poll=%ds  dry_run=%s  BE@%.1fR  trail@%.1fR",
                 POLL_INTERVAL, DRY_RUN, BE_MULTIPLE, TRAIL_MULTIPLE)

        self._sync_positions()
        self._log_managed_state()

        log.info("Entering poll loop (Ctrl+C to stop)...")
        while True:
            time.sleep(POLL_INTERVAL)
            try:
                self._sync_positions()
                self._evaluate_all()
            except KeyboardInterrupt:
                log.info("Stopped by user")
                break
            except Exception as exc:
                log.error("Poll error: %s", exc, exc_info=True)
                time.sleep(5)

    def eval_once(self):
        """Single evaluation cycle (for testing)."""
        self._sync_positions()
        self._evaluate_all()

    # ── Internal: sync ───────────────────────────────────────────────────

    def _sync_positions(self):
        """Sync open positions from all managed accounts."""
        seen: set[int] = set()
        for aid in self._account_ids:
            try:
                positions = self.client.get_positions(account_id=aid)
                for p in positions:
                    seen.add(p.position_id)
                    if p.position_id not in self._managed:
                        self._add_position(p, aid)
            except Exception as exc:
                log.error("get_positions(%s) failed: %s", aid, exc)

        # Remove closed positions
        closed = set(self._managed.keys()) - seen
        for pid in closed:
            mp = self._managed.pop(pid, None)
            if mp:
                log.info("Position #%s %s %s CLOSED — removing from management",
                         pid, mp.side.upper(), mp.symbol)

    def _add_position(self, pos, account_id: int):
        """Register a new position for management."""
        mp = ManagedPosition(
            position_id=pos.position_id,
            account_id=account_id,
            symbol=pos.symbol,
            side=pos.side,
            entry_price=pos.open_price,
            volume_cents=pos.volume_cents,
            initial_risk_r=0.0,
            current_sl=pos.stop_loss,
            risk_distance=self._estimate_risk_distance(pos),
        )
        mp.initial_risk_r = mp.risk_distance
        self._managed[pos.position_id] = mp
        log.info("NEW  #%s  %s %s %.2f lots @ %.5f  risk_dist=%.5f  SL=%s",
                 pos.position_id, pos.side.upper(), pos.symbol, mp.lots,
                 mp.entry_price, mp.risk_distance, pos.stop_loss)

    def _estimate_risk_distance(self, pos) -> float:
        """Estimate the initial risk distance (R) for a position.

        Prefers actual SL distance. Falls back to 1.5% of entry price.
        """
        if pos.stop_loss and pos.stop_loss > 0 and pos.open_price > 0:
            return abs(pos.open_price - pos.stop_loss)
        if pos.open_price > 0:
            return pos.open_price * 0.015  # 1.5% default
        return 0.001

    # ── Internal: evaluate ───────────────────────────────────────────────

    def _evaluate_all(self):
        """Check every managed position against rules."""
        self._eval_count += 1

        for aid in self._account_ids:
            try:
                current_positions = self.client.get_positions(account_id=aid)
                current_by_id = {p.position_id: p for p in current_positions}
            except Exception as exc:
                log.error("get_positions(%s) failed: %s", aid, exc)
                continue

            for pid, mp in list(self._managed.items()):
                if mp.account_id != aid:
                    continue
                cp = current_by_id.get(pid)
                if cp is None:
                    continue

                current_price = cp.open_price  # latest known price
                self._evaluate_one(mp, current_price)

        # Periodic heartbeat
        if self._eval_count % max(self._heartbeat_interval, 1) == 0:
            self._log_heartbeat()

    def _evaluate_one(self, mp: ManagedPosition, current_price: float):
        """Apply trailing SL rules to a single position."""
        if mp.risk_distance <= 0:
            return

        # Calculate current R multiple
        if mp.side == "buy":
            profit_r = (current_price - mp.entry_price) / mp.risk_distance
        else:
            profit_r = (mp.entry_price - current_price) / mp.risk_distance

        # Phase 1: Trail SL to breakeven
        if profit_r >= BE_MULTIPLE and not mp.be_set:
            new_sl = self._be_price(mp)
            log.info("TRAIL #%s %s %s  profit=%.2fR  → SL to BE @ %.5f",
                     mp.position_id, mp.side.upper(), mp.symbol, profit_r, new_sl)
            self._set_sl(mp, new_sl)
            mp.be_set = True
            mp.last_action = "breakeven"
            self._actions["breakeven"] += 1

        # Phase 1: Trail via swing points
        if profit_r >= TRAIL_MULTIPLE and mp.be_set and not mp.trailing:
            swing_sl = self._find_swing_sl(mp)
            if swing_sl is not None and swing_sl != mp.current_sl:
                log.info("TRAIL #%s %s %s  profit=%.2fR  → SL to structure @ %.5f",
                         mp.position_id, mp.side.upper(), mp.symbol,
                         profit_r, swing_sl)
                self._set_sl(mp, swing_sl)
                mp.trailing = True
                mp.last_action = "trail_structure"
                self._actions["trail_structure"] += 1

        # TODO Phase 2: News-aware partial close
        # if profit_r > 0 and self._is_news_window(mp.symbol):
        #     self._partial_close(mp, NEWS_PARTIAL_PCT)

    def _be_price(self, mp: ManagedPosition) -> float:
        """Calculate breakeven SL price (entry + buffer)."""
        buffer = mp.risk_distance * SPREAD_BUFFER_MULT
        if mp.side == "buy":
            return round(mp.entry_price + buffer, 5)
        else:
            return round(mp.entry_price - buffer, 5)

    # ── OHLC cache ────────────────────────────────────────────────────────

    def _get_ohlc(self, symbol: str) -> pd.DataFrame | None:
        """Cached OHLC fetch — re-fetches every OHLC_CACHE_SEC seconds."""
        import pandas as pd

        now = time.time()
        cached = self._ohlc_cache.get(symbol)
        if cached and now - cached[0] < OHLC_CACHE_SEC:
            return cached[1]

        log.debug("Fetching OHLC for %s...", symbol)
        df = self.client.get_ohlc(
            symbol, period=SWING_PERIOD, count=OHLC_COUNT,
        )
        self._ohlc_cache[symbol] = (now, df) if df is not None else (now, cached[1] if cached else None)
        return df

    def _find_swing_sl(self, mp: ManagedPosition) -> float | None:
        """Find nearest swing point as trailing SL level.

        1. Fetch OHLC data for the symbol
        2. Run swing_points() in causal mode
        3. Find most recent swing point on the correct side
        4. Place SL just below/above with buffer
        5. Fall back to fixed-distance trailing if no structure found
        """
        ohlc = self._get_ohlc(mp.symbol)
        if ohlc is None or len(ohlc) < SWING_LENGTH * 3:
            return self._fallback_swing_sl(mp)

        from backtesting.structure_lib.swing import swing_points
        swings, levels = swing_points(ohlc, swing_length=SWING_LENGTH, causal=True)

        # Swing levels that have been confirmed (not NaN)
        if mp.side == "buy":
            # Most recent swing low
            swing_levels = levels[swings == -1].dropna()
            if swing_levels.empty:
                return self._fallback_swing_sl(mp)
            nearest = swing_levels.iloc[-1]  # most recent confirmed swing low
            buffer = mp.risk_distance * SWING_BUFFER_PCT
            new_sl = round(nearest - buffer, 5)

            # Sanity checks
            if mp.current_sl and new_sl <= mp.current_sl:
                log.debug("Swing SL %.5f not above current SL %.5f — skip",
                          new_sl, mp.current_sl)
                return None
            if new_sl >= mp.entry_price:
                log.debug("Swing SL %.5f above entry %.5f — skip",
                          new_sl, mp.entry_price)
                return None
            return new_sl

        else:  # sell
            swing_levels = levels[swings == 1].dropna()
            if swing_levels.empty:
                return self._fallback_swing_sl(mp)
            nearest = swing_levels.iloc[-1]  # most recent swing high
            buffer = mp.risk_distance * SWING_BUFFER_PCT
            new_sl = round(nearest + buffer, 5)

            if mp.current_sl and new_sl >= mp.current_sl:
                log.debug("Swing SL %.5f not below current SL %.5f — skip",
                          new_sl, mp.current_sl)
                return None
            if new_sl <= mp.entry_price:
                log.debug("Swing SL %.5f below entry %.5f — skip",
                          new_sl, mp.entry_price)
                return None
            return new_sl

    def _fallback_swing_sl(self, mp: ManagedPosition) -> float | None:
        """Simple trailing distance when swing point data isn't available."""
        trail_offset = mp.risk_distance * 0.5
        if mp.side == "buy":
            return round(mp.current_sl + trail_offset, 5) if mp.current_sl else None
        else:
            return round(mp.current_sl - trail_offset, 5) if mp.current_sl else None

    def _is_news_window(self, symbol: str) -> bool:
        """Phase 2: Check if symbol is in a high-impact news window."""
        try:
            from infra.news_calendar import is_news_caution
            return is_news_caution(symbol)
        except Exception:
            return False

    # ── Actions ──────────────────────────────────────────────────────────

    def _set_sl(self, mp: ManagedPosition, sl: float):
        """Set stop loss on the position."""
        if DRY_RUN:
            log.info("[DRY RUN] would set SL #%s to %.5f", mp.position_id, sl)
            mp.current_sl = sl
            return

        try:
            result = self.client.modify_sltp(
                mp.position_id,
                stop_loss=sl,
                account_id=mp.account_id,
            )
            if result.status == "modified":
                mp.current_sl = sl
            else:
                log.error("Failed to set SL #%s: %s", mp.position_id, result.message)
        except Exception as exc:
            log.error("Error setting SL #%s: %s", mp.position_id, exc)

    def _partial_close(self, mp: ManagedPosition, pct: float):
        """Phase 2: Close a fraction of a position."""
        close_vol = max(int(mp.volume_cents * pct), 100)  # min 0.001 lots
        if DRY_RUN:
            log.info("[DRY RUN] would close %.0f%% of #%s (vol=%d)",
                     pct * 100, mp.position_id, close_vol)
            return

        try:
            result = self.client.close_position(
                mp.position_id,
                volume=close_vol,
                account_id=mp.account_id,
            )
            if result.status == "closed":
                mp.volume_cents -= close_vol
                log.info("Partial close #%s: closed %d/%d vol",
                         mp.position_id, close_vol, mp.volume_cents + close_vol)
        except Exception as exc:
            log.error("Partial close #%s failed: %s", mp.position_id, exc)

    def _log_heartbeat(self):
        """Periodic status log with action counts and position summary."""
        n_positions = len(self._managed)
        if n_positions == 0:
            log.info("HEARTBEAT  evals=%d  positions=0  actions=%s",
                     self._eval_count, self._actions)
            return

        # Summarize money at risk
        total_vol = sum(mp.volume_cents for mp in self._managed.values())
        total_lots = total_vol / 100_000
        in_profit = sum(1 for mp in self._managed.values() if mp.be_set)
        at_be = sum(1 for mp in self._managed.values() if mp.be_set and not mp.trailing)
        trailing = sum(1 for mp in self._managed.values() if mp.trailing)

        log.info("HEARTBEAT  evals=%d  positions=%d  lots=%.2f  "
                 "profit=%d  be=%d  trail=%d  actions=%s",
                 self._eval_count, n_positions, total_lots,
                 in_profit, at_be, trailing, self._actions)

    def _log_managed_state(self):
        """Log current managed positions."""
        if not self._managed:
            log.info("No managed positions")
            return
        for pid, mp in self._managed.items():
            log.info("  #%s  %s %s  %.2f lots @ %.5f  SL=%s  BE=%s  trail=%s",
                     pid, mp.side.upper(), mp.symbol, mp.lots,
                     mp.entry_price, mp.current_sl, mp.be_set, mp.trailing)


# ── CLI ───────────────────────────────────────────────────────────────────────


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Position Manager")
    ap.add_argument("--dry-run", action="store_true", help="Log only, no actual trades")
    ap.add_argument("--poll", type=int, default=None, help="Poll interval seconds")
    ap.add_argument("--account-ids", type=str, default=None,
                    help="Comma-separated account IDs to manage")
    ap.add_argument("--test", action="store_true",
                    help="Run one eval cycle and exit (for testing)")
    args = ap.parse_args()

    if args.dry_run:
        os.environ["PM_DRY_RUN"] = "true"
    if args.poll is not None:
        os.environ["PM_POLL_INTERVAL"] = str(args.poll)

    aid_list: list[int] | None = None
    if args.account_ids:
        aid_list = [int(x) for x in args.account_ids.split(",") if x.strip()]

    pm = PositionManager(account_ids=aid_list)

    if args.test:
        pm.eval_once()
        pm._log_managed_state()
        return

    pm.run()


if __name__ == "__main__":
    main()
