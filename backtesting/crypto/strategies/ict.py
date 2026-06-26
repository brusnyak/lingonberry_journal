"""
TrIct — ICT/SMC strategy using structure_lib pipeline.

Data required: {"5": df_5m, "30": df_30m}
For crypto: include "240" for HTF context.

Signal sequence (standard ICT):
  1. Liquidity pool swept (session/swing extreme)
  2. BOS or ChoCH within 5 bars confirms direction
  3. FVG or OB in retracement zone → entry at FVG CE
  4. SL beyond sweep extreme
  5. TP at opposite liquidity pool (min 1.5R enforced)

Session filter: Asia (00–07 UTC) + NY Late (17–24 UTC).
Entry: 5m bars touching FVG CE level within 2h of signal.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from backtesting.engine.base import BarData, EngineState, Strategy
from backtesting.engine.orders import Direction, Signal
from backtesting.structure_lib.swing import swing_points
from backtesting.structure_lib.labels import label_structure
from backtesting.structure_lib.fvg import detect_fvgs
from backtesting.structure_lib.ob import detect_order_blocks
from backtesting.structure_lib.sweep import detect_pools, detect_sweeps
from backtesting.structure_lib.trade_signals import TradeSignal, generate_signals


# Sessions where edge exists (UTC hours, inclusive start, exclusive end)
_SESSIONS = [
    (0, 7),   # Asia
    (17, 24), # NY Late
]

# Signal validity window after structure shift
_SIGNAL_EXPIRY_H = 2


class TrIct(Strategy):
    """
    Parameters
    ----------
    risk_pct : float
        Fraction of equity to risk per trade (default 0.005 = 0.5%).
    min_rr : float
        Minimum risk-reward ratio required by generate_signals (default 1.5).
    sessions_only : bool
        If True, only trade during Asia + NY Late. If False, trade all hours.
    swing_length : int
        Swing detection lookback on 30m (default 1 = ~18 pivots/day on XAUUSD).
    context_days : int
        Days of 30m history to load before the entry TF for swing context.
    """

    def __init__(
        self,
        risk_pct: float = 0.005,
        min_rr: float = 1.5,
        sessions_only: bool = True,
        swing_length: int = 1,
    ):
        self.risk_pct = risk_pct
        self.min_rr = min_rr
        self.sessions_only = sessions_only
        self.swing_length = swing_length

        self._signals: list[TradeSignal] = []
        self._used: set[pd.Timestamp] = set()  # signal_times already traded

    def init(self, data: dict[str, pd.DataFrame]) -> None:
        """Pre-compute structure on 30m data."""
        if "30" not in data:
            raise ValueError("TrIct requires '30' (30m) timeframe in data dict")

        df30_raw = data["30"]
        df30 = df30_raw.set_index("ts") if "ts" in df30_raw.columns else df30_raw.copy()
        df30.index = pd.DatetimeIndex(df30.index)
        df30 = df30.rename(columns=str.lower)
        for col in ("open", "high", "low", "close"):
            df30[col] = df30[col].astype(float)

        swings, levels = swing_points(df30, swing_length=self.swing_length, causal=True)
        labels = label_structure(df30, swings, levels)
        fvgs = detect_fvgs(df30)
        obs = detect_order_blocks(df30, labels)
        pools = detect_pools(df30, swings, levels)
        sweeps = detect_sweeps(df30, pools)

        self._signals = generate_signals(
            ohlc=df30,
            labels=labels,
            sweeps=sweeps,
            fvgs=fvgs,
            obs=obs,
            pools=pools,
            min_rr=self.min_rr,
        )
        self._used = set()

    def next(self, bar: BarData, state: EngineState) -> Optional[Signal]:
        if state.has_open_position:
            return None

        bar_ts = pd.Timestamp(bar.ts)
        hour = bar_ts.hour

        if self.sessions_only and not any(s <= hour < e for s, e in _SESSIONS):
            return None

        expiry = pd.Timedelta(hours=_SIGNAL_EXPIRY_H)

        for sig in self._signals:
            if sig.signal_time in self._used:
                continue
            if bar_ts < sig.signal_time:
                continue
            if bar_ts > sig.signal_time + expiry:
                continue

            # Check if price reached the entry zone this bar
            if sig.direction == "long":
                touched = bar.low <= sig.entry
            else:
                touched = bar.high >= sig.entry

            if not touched:
                continue

            self._used.add(sig.signal_time)

            return Signal(
                direction=Direction.LONG if sig.direction == "long" else Direction.SHORT,
                entry=sig.entry,
                sl=sig.sl,
                tp1=sig.tp,
                tp2=None,
                tp3=None,
                risk_pct=self.risk_pct,
                tp1_frac=1.0,   # full close at TP — no partials for now
                tp2_frac=0.0,
                trail=False,
                label=f"ict_{sig.confidence}_{sig.pool.source}",
            )

        return None
