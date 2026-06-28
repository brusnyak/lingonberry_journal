#!/usr/bin/env python3
"""
cTrader Trend Strategy — configurable MA-based entries on the 25K master.

Opens trades on the master cTrader account with ATR-based SL/TP.
Mirror copies to 100K, position manager trails SL.

Strategy types (TREND_STRATEGY env var):
  sma_cross     — fast SMA crosses above/below slow SMA
  ema_cross     — fast EMA crosses above/below slow EMA
  price_vs_ma   — price crosses above/below a single MA

Supports dry-run mode (TREND_DRY_RUN=true) — logs signals, no orders.
"""

from __future__ import annotations

import logging
import os
import sys
import time

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
log = logging.getLogger("ctrader-strategy")

# ── Config from env ───────────────────────────────────────────────────────────

SYMBOL = os.getenv("TREND_SYMBOL", "BTCUSD").upper()
STRATEGY = os.getenv("TREND_STRATEGY", "ema_cross")  # sma_cross | ema_cross | price_vs_ma
MA_FAST = int(os.getenv("TREND_MA_FAST", "20"))
MA_SLOW = int(os.getenv("TREND_MA_SLOW", "50"))
TIMEFRAME = int(os.getenv("TREND_TIMEFRAME", "2"))        # 2 = M5
OHLC_COUNT = int(os.getenv("TREND_OHLC_COUNT", "100"))

POSITION_SIZE = float(os.getenv("TREND_POSITION_SIZE", "0.001"))  # lots on 25K
DRY_RUN = os.getenv("TREND_DRY_RUN", "true").lower() == "true"
POLL_INTERVAL = int(os.getenv("TREND_POLL_INTERVAL", "15"))       # seconds
COOLDOWN_BARS = int(os.getenv("TREND_COOLDOWN_BARS", "3"))        # bars after signal before new signal

# SL/TP via ATR
SL_ATR_MULT = float(os.getenv("TREND_SL_ATR", "2.0"))     # SL = entry ± ATR * this
TP_RR = float(os.getenv("TREND_TP_RR", "1.5"))            # TP = entry ± SL_distance * this

MASTER_ACCOUNT_ID = int(os.getenv("CTRADER_ACC_NUM_MASTER", "44798689"))

# ── Strategy registry ─────────────────────────────────────────────────────────

_STRATEGIES: dict[str, str] = {
    "sma_cross": "SMA crossover: fast SMA crosses slow SMA",
    "ema_cross": "EMA crossover: fast EMA crosses slow EMA",
    "price_vs_ma": "Price vs MA: price crosses above/below a single MA",
}


def list_strategies() -> dict[str, str]:
    return dict(_STRATEGIES)


# ── Signal helpers ────────────────────────────────────────────────────────────


def _compute_atr(df, period: int = 14) -> float:
    """Compute ATR from the last N bars in an OHLC DataFrame."""
    if len(df) < period + 1:
        return 0.0
    tr_series = []
    for i in range(1, min(period + 1, len(df))):
        h = df["high"].iloc[-i]
        l = df["low"].iloc[-i]
        pc = df["close"].iloc[-i - 1]
        tr_series.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not tr_series:
        return 0.0
    return sum(tr_series) / len(tr_series)


def _get_current_trend(df, fast: int, slow: int, ma_type: str = "ema") -> str | None:
    """Get current market trend direction from the last completed bar.

    Returns 'bullish' (fast > slow), 'bearish' (fast < slow), or None if
    insufficient data.
    """
    import pandas as pd
    min_bars = max(slow, 20) + 2
    if len(df) < min_bars:
        return None

    if ma_type == "ema":
        fast_ma = df["close"].ewm(span=fast, adjust=False).mean()
        slow_ma = df["close"].ewm(span=slow, adjust=False).mean()
    else:
        fast_ma = df["close"].rolling(fast).mean()
        slow_ma = df["close"].rolling(slow).mean()

    val = fast_ma.iloc[-2] - slow_ma.iloc[-2]
    if pd.isna(val):
        return None
    return "bullish" if val > 0 else "bearish"


def _get_price_vs_ma_trend(df, period: int) -> str | None:
    """Get current price vs MA position for price_vs_ma strategy."""
    import pandas as pd
    if len(df) < period + 2:
        return None
    ma = df["close"].rolling(period).mean()
    diff = df["close"].iloc[-2] - ma.iloc[-2]
    if pd.isna(diff):
        return None
    return "bullish" if diff > 0 else "bearish"


# ── Main strategy process ─────────────────────────────────────────────────────


class TrendStrategy:
    """Configurable MA trend-following strategy. Opens trades on master."""

    def __init__(self, client=None):
        self.strategy_name = STRATEGY
        self.symbol = SYMBOL
        self.account_id = MASTER_ACCOUNT_ID

        if client is not None:
            self.client = client
        else:
            from infra.ctrader_client import CtraderClient
            log.info("Connecting account %s for strategy...", self.account_id)
            self.client = CtraderClient(account_ids=[self.account_id])
            self.client.connect()

        from infra.trade_logger import get_logger
        self._tlog = get_logger()

        self._bar_count: int = 0
        self._prev_trend: str | None = None  # previous poll's trend direction

        # Cache for OHLC
        self._ohlc_df = None
        self._ohlc_time: float = 0
        self._ohlc_cache_sec: int = int(os.getenv("TREND_OHLC_CACHE", "30"))

        # Analytics
        self._poll_count: int = 0
        self._signals: dict[str, int] = {"buy": 0, "sell": 0}
        self._trades: dict[str, int] = {"opens": 0, "closes": 0, "errors": 0}
        self._heartbeat_interval: int = int(os.getenv("TREND_HEARTBEAT", "20"))

        log.info("Strategy configured: %s  %s  MA(%s,%s)  timeframe=M%s  dry_run=%s",
                 self.strategy_name, self.symbol, MA_FAST, MA_SLOW,
                 {1: 1, 2: 5, 3: 15, 4: 30, 5: 60, 6: 240, 7: 1440}.get(TIMEFRAME, TIMEFRAME),
                 DRY_RUN)

    # ── Public ────────────────────────────────────────────────────────────

    def run(self):
        """Main polling loop."""
        log.info("Trend Strategy started  poll=%ds", POLL_INTERVAL)

        self._fetch_ohlc()
        self._log_heartbeat()

        while True:
            time.sleep(POLL_INTERVAL)
            try:
                self._evaluate()
            except KeyboardInterrupt:
                log.info("Stopped by user")
                break
            except Exception as exc:
                log.error("Poll error: %s", exc, exc_info=True)
                time.sleep(5)

    def eval_once(self):
        """Single evaluation cycle (for testing)."""
        self._evaluate()

    # ── OHLC ──────────────────────────────────────────────────────────────

    def _fetch_ohlc(self) -> bool:
        """Fetch OHLC from cTrader. Returns True if data changed."""
        import pandas as pd
        try:
            df = self.client.get_ohlc(
                self.symbol, period=TIMEFRAME, count=OHLC_COUNT,
            )
            if df is None or df.empty:
                log.warning("Empty OHLC for %s", self.symbol)
                return False
            self._ohlc_df = df
            self._ohlc_time = time.time()
            return True
        except Exception as exc:
            log.error("OHLC fetch failed: %s", exc)
            return False

    def _get_ohlc(self):
        """Cached OHLC fetch."""
        if self._ohlc_df is None or time.time() - self._ohlc_time > self._ohlc_cache_sec:
            self._fetch_ohlc()
        return self._ohlc_df

    # ── Evaluation ────────────────────────────────────────────────────────

    def _evaluate(self):
        """One eval cycle: check for signal → open/close positions."""
        self._poll_count += 1
        self._bar_count += 1

        df = self._get_ohlc()
        if df is None or len(df) < max(MA_SLOW, 20) + 2:
            log.debug("Not enough data yet (%d bars)", len(df) if df is not None else 0)
            return

        # Get current trend
        side, reason = self._detect_signal(df)

        # Log signal even if no trade
        if side:
            self._signals[side] += 1
            self._tlog.log("signal", self.symbol, side=side, strategy=self.strategy_name,
                           reason=reason, price=df["close"].iloc[-2])

        # Execute if we have a fresh signal
        if side and self._bar_count >= COOLDOWN_BARS:
            self._execute_signal(side, df)

        # Heartbeat
        if self._poll_count % max(self._heartbeat_interval, 1) == 0:
            self._log_heartbeat()

    def _detect_signal(self, df):
        """Run the configured signal detection. Returns (side, reason)."""
        if STRATEGY == "sma_cross":
            current = _get_current_trend(df, MA_FAST, MA_SLOW, ma_type="sma")
        elif STRATEGY == "ema_cross":
            current = _get_current_trend(df, MA_FAST, MA_SLOW, ma_type="ema")
        elif STRATEGY == "price_vs_ma":
            current = _get_price_vs_ma_trend(df, MA_FAST)
        else:
            return None, f"unknown strategy: {STRATEGY}"

        if current is None:
            return None, "insufficient data"

        # Signal when trend changes compared to previous poll
        if self._prev_trend is not None and current != self._prev_trend:
            old_trend = self._prev_trend
            self._prev_trend = current
            if current == "bullish":
                return "buy", f"trend changed to bullish (was {old_trend})"
            else:
                return "sell", f"trend changed to bearish (was {old_trend})"

        self._prev_trend = current
        return None, f"trend unchanged ({current})"

    # ── Execution ─────────────────────────────────────────────────────────

    def _execute_signal(self, side: str, df):
        """Execute a signal: close opposing position, open new one."""
        # Check existing positions
        current_positions = self._get_positions()
        existing = [p for p in current_positions if p.symbol == self.symbol]

        # Close positions in opposite direction
        for pos in existing:
            if (side == "buy" and pos.side == "sell") or (side == "sell" and pos.side == "buy"):
                log.info("REVERSAL  closing opposite %s #%s", pos.side, pos.position_id)
                self._close_position(pos)
                time.sleep(1)

        # Skip if we already have a position in this direction
        for pos in existing:
            if pos.side == side:
                log.debug("Already in %s position #%s — skip new entry", side, pos.position_id)
                return

        # Calculate SL/TP from ATR
        atr = _compute_atr(df)
        if atr <= 0:
            log.warning("ATR is zero — using 1%% of price as SL distance")
            atr = df["close"].iloc[-1] * 0.01

        sl_distance = atr * SL_ATR_MULT
        entry_price = df["close"].iloc[-1]  # use latest close as approximation

        if side == "buy":
            sl = round(entry_price - sl_distance, 5)
            tp = round(entry_price + sl_distance * TP_RR, 5)
        else:
            sl = round(entry_price + sl_distance, 5)
            tp = round(entry_price - sl_distance * TP_RR, 5)

        # Place order
        log.info("SIGNAL %s  %s  entry=%.5f  SL=%.5f  TP=%.5f  atr=%.5f",
                 side.upper(), self.symbol, entry_price, sl, tp, atr)

        if DRY_RUN:
            log.info("[DRY RUN] would open %s %s %.4f lots (SL=%.5f TP=%.5f)",
                     side, self.symbol, POSITION_SIZE, sl, tp)
            self._tlog.log("open", self.symbol, side=side, price=entry_price,
                           qty=POSITION_SIZE, sl=sl, tp=tp,
                           atr=atr, dry_run=True)
            return

        result = self.client.create_order(
            symbol=self.symbol,
            quantity=POSITION_SIZE,
            side=side,
            stop_loss=sl,
            take_profit=tp,
            account_id=self.account_id,
            entry_price=entry_price,
        )
        if result.order_id:
            log.info("ORDER FILLED  id=%s  %s %s %.4f lots", result.order_id,
                     side.upper(), self.symbol, POSITION_SIZE)
            self._trades["opens"] += 1
            self._tlog.log("open", self.symbol, side=side, price=entry_price,
                           qty=POSITION_SIZE, sl=sl, tp=tp,
                           atr=atr, order_id=result.order_id)
        else:
            log.error("ORDER FAILED: %s", result.message)
            self._trades["errors"] += 1
            self._tlog.log("error", self.symbol, action="open",
                           message=result.message)

    # ── Position helpers ──────────────────────────────────────────────────

    def _get_positions(self):
        """Get current positions for the strategy account."""
        try:
            return self.client.get_positions(account_id=self.account_id)
        except Exception as exc:
            log.error("get_positions failed: %s", exc)
            return []

    def _close_position(self, pos):
        """Close a position."""
        if DRY_RUN:
            log.info("[DRY RUN] would close #%s %s %s", pos.position_id, pos.side, pos.symbol)
            return

        try:
            result = self.client.close_position(
                pos.position_id, account_id=self.account_id,
            )
            if result.status == "closed":
                log.info("CLOSED #%s %s %s", pos.position_id, pos.side, pos.symbol)
                self._trades["closes"] += 1
                self._tlog.log("close", pos.symbol, side=pos.side,
                               position_id=pos.position_id)
            else:
                log.warning("Close #%s failed: %s", pos.position_id, result.message)
                self._trades["errors"] += 1
        except Exception as exc:
            log.error("Close #%s error: %s", pos.position_id, exc)

    # ── Analytics ─────────────────────────────────────────────────────────

    def _log_heartbeat(self):
        log.info("HEARTBEAT  polls=%d  signals=%s  trades=%s",
                 self._poll_count, self._signals, self._trades)


# ── CLI ───────────────────────────────────────────────────────────────────────


def main():
    import argparse
    ap = argparse.ArgumentParser(description="cTrader Trend Strategy")
    ap.add_argument("--dry-run", action="store_true", help="Log only, no orders")
    ap.add_argument("--list-strategies", action="store_true", help="List available strategies")
    ap.add_argument("--poll", type=int, default=None, help="Poll interval seconds")
    ap.add_argument("--test", action="store_true", help="One eval cycle and exit")
    args = ap.parse_args()

    if args.list_strategies:
        for name, desc in list_strategies().items():
            print(f"  {name:20s}  {desc}")
        return

    if args.dry_run:
        os.environ["TREND_DRY_RUN"] = "true"
    if args.poll is not None:
        os.environ["TREND_POLL_INTERVAL"] = str(args.poll)

    strategy = TrendStrategy()

    if args.test:
        strategy.eval_once()
        strategy._log_heartbeat()
        return

    strategy.run()


if __name__ == "__main__":
    main()
