"""
TrIct — ICT/SMC strategy using structure_lib pipeline — CAUSAL (look-ahead fixed).

Data required: {"30": df_30m}
Optional: {"240": df_4h} for HTF context.

Signal sequence:
  1. Liquidity pool swept (session/swing extreme)
  2. BOS or ChoCH within 5 bars confirms direction
  3. FVG or OB in retracement zone → entry at FVG CE
  4. SL beyond sweep extreme
  5. TP at opposite liquidity pool (min 1.5R enforced)

Session filter: Asia (00-07 UTC) + NY Late (17-24 UTC).
Entry: 30m bar touches FVG CE level within 2h of signal.

Causal design:
  init() pre-computes static structure (swings, labels, FVGs, OBs, pools)
  that do not reference future bars. Sweep detection and signal generation
  happen incrementally in next(), processing only the current bar — no
  O(n²) batch recomputation on every call.
"""

from __future__ import annotations

import bisect
from typing import Optional

import numpy as np
import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.structure_lib.swing import swing_points
from backtesting.structure_lib.labels import label_structure
from backtesting.structure_lib.fvg import detect_fvgs, FVG
from backtesting.structure_lib.ob import detect_order_blocks, OrderBlock
from backtesting.structure_lib.sweep import detect_pools, LiquidityPool, Sweep


# Sessions where edge exists (UTC hours, inclusive start, exclusive end)
_SESSIONS = [
    (0, 7),   # Asia
    (17, 24), # NY Late
]

# Signal validity window after structure shift
_SIGNAL_EXPIRY_H = 2

# Max bars to look back from a structure shift for a matching sweep
_MAX_SWEEP_LOOKBACK = 5



class TrIct(Strategy):
    """ICT/SMC strategy — incremental causal sweep + signal detection."""

    _signal_source = "init_precomputed"

    def __init__(
        self,
        risk_pct: float = 0.005,
        min_rr: float = 1.5,
        sessions_only: bool = True,
        swing_length: int = 1,
        min_stop_pct: Optional[float] = None,
        multi_target: bool = False,
        tp1_r: float = 1.0,
        tp1_frac: float = 0.4,
        tp2_frac: float = 0.35,
        use_body_swings: bool = False,  # opt-in: True uses body-based structure pivots (2026-07-18 fix), False preserves prior wick-based behavior for existing callers/tests
    ):
        self.risk_pct = risk_pct
        self.min_rr = min_rr
        self.sessions_only = sessions_only
        self.swing_length = swing_length
        # Audit finding (CLEAN.md Phase 6E): fees scale with notional, not
        # risk, so a fixed dollar-risk trade with a very tight stop pays a
        # disproportionate fee (and is far more slippage-exposed) relative
        # to its intended risk. min_stop_pct drops trades whose stop is
        # tighter than this % of entry price. None = no filter (old
        # behavior). Informal check on XRP found stop>=0.25% held return
        # while raising win rate 54%->64% -- not yet re-validated with a
        # full null/split-half pass, treat as an experimental knob.
        self.min_stop_pct = min_stop_pct
        # Multi-target ladder + breakeven-after-TP1 (the engine already
        # moves SL to entry on any TP1 partial-close -- see runner.py's
        # `pos.sl = pos.entry_price` on exit_code==2 -- so enabling this
        # just means TrIct actually uses tp1/tp2/tp3 instead of a single
        # full-size exit). tp1 = tp1_r*R (quick partial, locks in profit
        # and arms breakeven early); tp2 = the original pool-based target;
        # tp3 = the next liquidity pool beyond tp2, or a 1R extension if
        # none exists. Remaining frac (1 - tp1_frac - tp2_frac) rides tp3.
        self.multi_target = multi_target
        self.tp1_r = tp1_r
        self.tp1_frac = tp1_frac
        self.tp2_frac = tp2_frac
        self.use_body_swings = use_body_swings

        # Set in init()
        self._df30: pd.DataFrame = None
        self._pools: list[LiquidityPool] = None
        self._fvgs: list[FVG] = None
        self._obs: list[OrderBlock] = None

        # Incremental state (set/updated in next())
        self._sweeps: list[Sweep] = []          # all sweeps found so far
        self._pending: dict = {}                # signal_key → TradeSignal

        # Pre-indexed FVG/OB/pool lists for O(log N) lookups in _build_signal
        self._fvg_by_time: list[tuple[pd.Timestamp, FVG]] = []
        self._ob_by_time: list[tuple[pd.Timestamp, OrderBlock]] = []
        self._buy_pool_levels: list[float] = []
        self._sell_pool_levels: list[float] = []

        # Label arrays
        self._bullish_choch: np.ndarray = None
        self._bearish_choch: np.ndarray = None
        self._bullish_bos: np.ndarray = None
        self._bearish_bos: np.ndarray = None

    def init(self, data: dict[str, pd.DataFrame]) -> None:
        """Pre-compute static structure on 30m data (all causal)."""
        if "30" not in data:
            raise ValueError("TrIct requires '30' (30m) timeframe in data dict")

        df30_raw = data["30"]
        df30 = df30_raw.set_index("ts") if "ts" in df30_raw.columns else df30_raw.copy()
        df30.index = pd.DatetimeIndex(df30.index)
        df30 = df30.rename(columns=str.lower)
        for col in ("open", "high", "low", "close"):
            df30[col] = df30[col].astype(float)

        self._n = len(df30)
        self._df30 = df30

        swings, levels = swing_points(df30, swing_length=self.swing_length, causal=True,
                                       use_body=self.use_body_swings)
        labels = label_structure(df30, swings, levels)
        self._fvgs = detect_fvgs(df30)
        self._obs = detect_order_blocks(df30, labels)
        self._pools = detect_pools(df30, swings, levels)

        # Pre-index FVGs by c2_time
        self._fvg_by_time = sorted(
            [(f.c2_time, f) for f in self._fvgs],
            key=lambda x: x[0],
        )
        # Pre-index OBs by time
        self._ob_by_time = sorted(
            [(o.time, o) for o in self._obs],
            key=lambda x: x[0],
        )
        # Pre-sort pool levels
        self._buy_pool_levels = sorted([p.level for p in self._pools if p.side == "buy"])
        self._sell_pool_levels = sorted([p.level for p in self._pools if p.side == "sell"])

        # Stateful active/broken pool tracking for O(log n) sweep detection
        # (see _detect_sweeps_at_bar docstring for why this replaced a full
        # per-bar scan over all pools).
        buy_pools = sorted([p for p in self._pools if p.side == "buy"], key=lambda p: p.level)
        sell_pools = sorted([p for p in self._pools if p.side == "sell"], key=lambda p: p.level)
        self._buy_active_levels = [p.level for p in buy_pools]
        self._buy_active_pools = buy_pools
        self._buy_broken_levels: list[float] = []
        self._buy_broken_pools: list[LiquidityPool] = []
        self._sell_active_levels = [p.level for p in sell_pools]
        self._sell_active_pools = sell_pools
        self._sell_broken_levels: list[float] = []
        self._sell_broken_pools: list[LiquidityPool] = []

        # Label arrays for fast access
        self._bullish_choch = labels["bullish_choch"].to_numpy(bool)
        self._bearish_choch = labels["bearish_choch"].to_numpy(bool)
        self._bullish_bos = labels["bullish_bos"].to_numpy(bool)
        self._bearish_bos = labels["bearish_bos"].to_numpy(bool)

    # ── Incremental sweep detection ─────────────────────────────────────────

    def _detect_sweeps_at_bar(self, i: int) -> list[Sweep]:
        """Return sweeps (new pool breaks) at bar i.

        Perf note: this used to loop over ALL pools on every bar
        (O(bars * pools) = O(n^2) since pool count grows with history
        length — confirmed empirically: 30d/60d/90d ran 3.4s/12.2s/27.6s,
        an ~8x runtime increase for a 3x data increase). Fixed by tracking
        each pool's active/broken state explicitly and using bisect on
        sorted level arrays, so each bar only touches pools whose level
        is within the current bar's actual price range — O(log n) typical,
        O(k) worst case where k is the number of pools that change state.

        A pool starts "active" (unbroken). It becomes "broken" the bar its
        level is first breached (buy: hi > level; sell: lo < level) and
        emits a Sweep. It becomes "active" again once price closes back
        beyond the level (buy: close < level; sell: close > level), so it
        can be re-swept later — matching the original re-sweep semantics
        (a pool that stays broken forever no longer re-emits a Sweep every
        single bar, which was the other bug in the old scan: it flooded
        self._sweeps with a fresh "sweep" every bar for any pool price
        happened to still be sitting past, not just on genuine breaches).
        """
        row = self._df30.iloc[i]
        hi, lo, cl = row["high"], row["low"], row["close"]
        ts = self._df30.index[i]
        found: list[Sweep] = []

        # ── Buy-side pools: broken when hi > level, reclaimed when cl < level ──
        idx = bisect.bisect_left(self._buy_active_levels, hi)
        if idx > 0:
            newly_broken = self._buy_active_pools[:idx]
            del self._buy_active_levels[:idx]
            del self._buy_active_pools[:idx]
            for pool in newly_broken:
                found.append(Sweep(
                    pool=pool, sweep_time=ts,
                    direction="bearish", reclaim=False, wick_only=(cl <= pool.level),
                ))
                ins = bisect.bisect_left(self._buy_broken_levels, pool.level)
                self._buy_broken_levels.insert(ins, pool.level)
                self._buy_broken_pools.insert(ins, pool)

        ridx = bisect.bisect_right(self._buy_broken_levels, cl)
        if ridx < len(self._buy_broken_levels):
            reclaimed = self._buy_broken_pools[ridx:]
            del self._buy_broken_levels[ridx:]
            del self._buy_broken_pools[ridx:]
            for pool in reclaimed:
                ins = bisect.bisect_left(self._buy_active_levels, pool.level)
                self._buy_active_levels.insert(ins, pool.level)
                self._buy_active_pools.insert(ins, pool)

        # ── Sell-side pools: broken when lo < level, reclaimed when cl > level ──
        idx = bisect.bisect_right(self._sell_active_levels, lo)
        if idx < len(self._sell_active_levels):
            newly_broken = self._sell_active_pools[idx:]
            del self._sell_active_levels[idx:]
            del self._sell_active_pools[idx:]
            for pool in newly_broken:
                found.append(Sweep(
                    pool=pool, sweep_time=ts,
                    direction="bullish", reclaim=False, wick_only=(cl >= pool.level),
                ))
                ins = bisect.bisect_left(self._sell_broken_levels, pool.level)
                self._sell_broken_levels.insert(ins, pool.level)
                self._sell_broken_pools.insert(ins, pool)

        lidx = bisect.bisect_left(self._sell_broken_levels, cl)
        if lidx > 0:
            reclaimed = self._sell_broken_pools[:lidx]
            del self._sell_broken_levels[:lidx]
            del self._sell_broken_pools[:lidx]
            for pool in reclaimed:
                ins = bisect.bisect_left(self._sell_active_levels, pool.level)
                self._sell_active_levels.insert(ins, pool.level)
                self._sell_active_pools.insert(ins, pool)

        return found

    # ── Signal builder (portable from trade_signals.py) ─────────────────────

    def _build_signal(self, sweep: Sweep, shift_idx: int, shift_dir: str) -> Optional[object]:
        """Build a TradeSignal from a sweep + structure shift at shift_idx.

        This is a minimal causal re-implementation of the batch
        generate_signals() — only processes one sweep+shift pair.
        """
        trade_dir = "long" if shift_dir == "bullish" else "short"
        shift_ts = self._df30.index[shift_idx]

        # Find matching FVG (between sweep_time and shift_time + 15m)
        matching_fvg = None
        sweep_ts = sweep.sweep_time
        shift_plus_15 = shift_ts + pd.Timedelta(minutes=15)

        fvg_left = bisect.bisect_left(self._fvg_by_time, (sweep_ts,))
        fvg_right = bisect.bisect_right(self._fvg_by_time, (shift_plus_15,))
        for idx in range(fvg_left, min(fvg_right, len(self._fvg_by_time))):
            fvg = self._fvg_by_time[idx][1]
            if (trade_dir == "long" and fvg.kind == "bullish") or \
               (trade_dir == "short" and fvg.kind == "bearish"):
                matching_fvg = fvg
                break

        # Find matching OB (with displacement_idx == shift_idx)
        matching_ob = None
        ob_left = bisect.bisect_left(self._ob_by_time, (sweep_ts,))
        for idx in range(ob_left, len(self._ob_by_time)):
            ob = self._ob_by_time[idx][1]
            if ob.displacement_idx == shift_idx:
                if (trade_dir == "long" and ob.kind == "bullish") or \
                   (trade_dir == "short" and ob.kind == "bearish"):
                    matching_ob = ob
                    break

        if matching_fvg is None and matching_ob is None:
            return None

        # Entry price
        if matching_fvg:
            entry = matching_fvg.ce
        else:
            entry = matching_ob.top if trade_dir == "long" else matching_ob.bottom

        # SL (beyond sweep level with buffer)
        shift_range = (self._df30["high"].iloc[shift_idx] -
                       self._df30["low"].iloc[shift_idx]) * 0.3
        if trade_dir == "long":
            sl = min(sweep.pool.level,
                     matching_fvg.bottom if matching_fvg else entry) - shift_range
        else:
            sl = max(sweep.pool.level,
                     matching_fvg.top if matching_fvg else entry) + shift_range

        # TP via binary search on opposite pool. Also grab the NEXT pool
        # beyond it (tp_ext) for the multi-target ladder's runner leg.
        tp = None
        tp_ext = None
        if trade_dir == "long":
            idx = bisect.bisect_right(self._buy_pool_levels, entry)
            if idx < len(self._buy_pool_levels):
                tp = self._buy_pool_levels[idx]
                if idx + 1 < len(self._buy_pool_levels):
                    tp_ext = self._buy_pool_levels[idx + 1]
        else:
            idx = bisect.bisect_left(self._sell_pool_levels, entry) - 1
            if idx >= 0:
                tp = self._sell_pool_levels[idx]
                if idx - 1 >= 0:
                    tp_ext = self._sell_pool_levels[idx - 1]

        if tp is None:
            return None

        # R:R check
        risk_abs = abs(entry - sl)
        reward_abs = abs(tp - entry)
        if risk_abs == 0:
            return None
        rr = reward_abs / risk_abs
        if rr < self.min_rr:
            return None

        # Cost-fragility filter (Phase 6E audit): fees/slippage are a
        # disproportionate share of intended risk on very tight stops.
        if self.min_stop_pct is not None and (risk_abs / entry * 100) < self.min_stop_pct:
            return None

        if tp_ext is None:
            tp_ext = tp + (tp - entry)  # 1R-of-the-move extension fallback

        # Confidence — same logic as batch generate_signals()
        confidence = "medium"
        if matching_fvg and matching_ob:
            confidence = "high"
        elif "prior_day" in sweep.pool.source or "session" in sweep.pool.source:
            confidence = "high"
        elif matching_fvg:
            confidence = "high"

        # Build a lightweight signal dict (not a full TradeSignal to avoid
        # depending on the structure_lib dataclass)
        return {
            "direction": trade_dir,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "tp_ext": tp_ext,
            "signal_time": shift_ts,
            "confidence": confidence,
            "pool_source": sweep.pool.source,
        }

    # ── Main entry point ────────────────────────────────────────────────────

    def _signal_key(self, sig: dict) -> tuple:
        return (sig["signal_time"], sig["direction"], round(sig["entry"], 5))

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        if state.has_open_position:
            return None

        i = bar.index
        if i >= self._n:
            return None
        bar_ts = pd.Timestamp(bar.ts)

        if self.sessions_only:
            hour = bar_ts.hour
            if not any(s <= hour < e for s, e in _SESSIONS):
                return None

        # ── Step 1: detect ALL sweeps at current bar ──
        for sweep in self._detect_sweeps_at_bar(i):
            self._sweeps.append(sweep)

        # ── Step 2: structure shift at current bar? ──
        shift_dir = None
        if self._bullish_choch[i] or self._bullish_bos[i]:
            shift_dir = "bullish"
        elif self._bearish_choch[i] or self._bearish_bos[i]:
            shift_dir = "bearish"

        # ── Step 3: if shift found, look back for matching sweep ──
        if shift_dir is not None:
            # Walk sweeps in reverse (most recent first)
            for s in reversed(self._sweeps):
                try:
                    sweep_bar = self._df30.index.get_loc(s.sweep_time)
                except KeyError:
                    continue
                if i - sweep_bar > _MAX_SWEEP_LOOKBACK:
                    break  # too old; sweeps are chronological, rest are even older
                if s.direction != shift_dir:
                    continue
                if s.wick_only and not s.reclaim:
                    continue  # wick-only without reclaim is not valid

                sig = self._build_signal(s, i, shift_dir)
                if sig is not None:
                    key = self._signal_key(sig)
                    if key not in self._pending:
                        self._pending[key] = sig
                    break  # one signal per shift event

        # ── Step 4: check pending signals for entry ──
        expiry = pd.Timedelta(hours=_SIGNAL_EXPIRY_H)
        expired_keys = []

        for key, sig in list(self._pending.items()):
            if sig["signal_time"] + expiry < bar_ts:
                expired_keys.append(key)
                continue

            # Check if price touched the entry zone this bar
            if sig["direction"] == "long":
                touched = bar.low <= sig["entry"]
            else:
                touched = bar.high >= sig["entry"]

            if not touched:
                continue

            # ENTRY
            del self._pending[key]
            direction = Direction.LONG if sig["direction"] == "long" else Direction.SHORT
            label = f"ict_{sig['confidence']}_{sig['pool_source']}"

            if self.multi_target:
                risk_abs = abs(sig["entry"] - sig["sl"])
                sign = 1.0 if sig["direction"] == "long" else -1.0
                quick_tp = sig["entry"] + sign * self.tp1_r * risk_abs
                # Keep the ladder monotonic: the quick partial must sit
                # strictly before the pool-based target, or it isn't a
                # meaningful partial (just skip straight past it).
                pool_tp_is_further = (
                    (sign > 0 and quick_tp < sig["tp"]) or (sign < 0 and quick_tp > sig["tp"])
                )
                if pool_tp_is_further:
                    return Signal(
                        direction=direction, entry=sig["entry"], sl=sig["sl"],
                        tp1=quick_tp, tp2=sig["tp"], tp3=sig["tp_ext"],
                        risk_pct=self.risk_pct,
                        tp1_frac=self.tp1_frac, tp2_frac=self.tp2_frac,
                        trail=False, label=label,
                    )
                # Fall through to single-target below if the pool is too
                # close for a meaningful quick partial ahead of it.

            return Signal(
                direction=direction,
                entry=sig["entry"],
                sl=sig["sl"],
                tp1=sig["tp"],
                tp2=None,
                tp3=None,
                risk_pct=self.risk_pct,
                tp1_frac=1.0,
                tp2_frac=0.0,
                trail=False,
                label=label,
            )

        for k in expired_keys:
            self._pending.pop(k, None)

        return None

    def should_close(self, position, bar: BarData, state: EngineState) -> bool:
        """Exit early if the structural premise that justified this trade
        has been invalidated -- an opposing BOS/ChoCH prints while the
        position is still underwater.

        This is the "don't hold the loss" rule: a fresh BOS/ChoCH against
        the position means the sweep-reversal thesis this trade was based
        on no longer holds, so there's no reason to keep waiting on the
        hard SL. Only fires while the position is at a loss (bar.close
        past entry against it) -- a winning trade that's already banked
        R via TP1/breakeven shouldn't be cut just because of a
        counter-structure wiggle; the hard SL/trail already protects it.
        """
        i = bar.index
        if i >= self._n:
            return False

        if position.direction == Direction.LONG:
            losing = bar.close < position.entry_price
            invalidated = bool(self._bearish_choch[i] or self._bearish_bos[i])
        else:
            losing = bar.close > position.entry_price
            invalidated = bool(self._bullish_choch[i] or self._bullish_bos[i])

        return losing and invalidated
