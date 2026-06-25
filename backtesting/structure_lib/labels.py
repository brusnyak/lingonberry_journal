"""
Step 2 — Market Structure Labels + BOS / CHoCH.

ICT definitions (from research):
  HH = Higher High (swing high > last swing high)
  HL = Higher Low  (swing low  > last swing low)
  LH = Lower High   (swing high < last swing high)
  LL = Lower Low    (swing low  < last swing low)

  BOS  = Break of Structure — trend CONTINUATION.
         Bullish: first close > last HH while in bullish trend.
         Bearish: first close < last LL while in bearish trend.

  CHoCH = Change of Character — trend REVERSAL warning.
           Bearish: in bullish trend, first close < last HL.
           Bullish: in bearish trend, first close > last LH.

Rules:
  - Only candle body CLOSE counts (not wicks).
  - BOS/CHoCH fires ONCE per level (tracked by broken flags).
  - CHoCH is a WARNING, not an entry signal. Trend doesn't reverse
    until new structure confirms (new HH+HL or LH+LL).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def label_structure(
    ohlc: pd.DataFrame,
    swings: pd.Series,
    levels: pd.Series,
) -> pd.DataFrame:
    """
    Label each swing point with HH/HL/LH/LL.
    Detect BOS and CHoCH on close breaks.

    Returns DataFrame with columns:
        structure_label : 'HH', 'HL', 'LH', 'LL' or '' (empty = no swing)
        trend           : 'bullish', 'bearish', 'neutral'
        last_hh         : most recent HH level
        last_hl         : most recent HL level
        last_lh         : most recent LH level
        last_ll         : most recent LL level
        bullish_bos     : True at the candle that first closes above last HH
        bearish_bos     : True at the candle that first closes below last LL
        bullish_choch   : True at the candle that first closes above last LH (in downtrend)
        bearish_choch   : True at the candle that first closes below last HL (in uptrend)
        choch_level     : the level that was broken by the CHoCH
        bos_level       : the level that was broken by the BOS
    """
    high = ohlc["high"].values
    low = ohlc["low"].values
    close = ohlc["close"].values
    n = len(ohlc)

    # Output arrays
    struct_label = np.full(n, "", dtype=object)
    trend = np.full(n, "neutral", dtype=object)

    last_hh_arr = np.full(n, np.nan)
    last_hl_arr = np.full(n, np.nan)
    last_lh_arr = np.full(n, np.nan)
    last_ll_arr = np.full(n, np.nan)

    bull_bos = np.zeros(n, dtype=bool)
    bear_bos = np.zeros(n, dtype=bool)
    bull_choch = np.zeros(n, dtype=bool)
    bear_choch = np.zeros(n, dtype=bool)
    bos_level = np.full(n, np.nan)
    choch_level = np.full(n, np.nan)

    # ── State ──
    prev_swing_high = np.nan  # last swing high level
    prev_swing_low = np.nan   # last swing low level

    # Current structure levels for BOS/CHoCH detection
    _hh = np.nan  # most recent HH level
    _hl = np.nan  # most recent HL level
    _lh = np.nan  # most recent LH level
    _ll = np.nan  # most recent LL level
    _trend = "neutral"
    _bullish_count = 0  # consecutive bullish swing labels
    _bearish_count = 0  # consecutive bearish swing labels

    # Track whether each level has been "broken" yet
    hh_broken = False   # last HH already triggered bullish BOS?
    hl_broken = False   # last HL already triggered bearish CHoCH?
    lh_broken = False   # last LH already triggered bullish CHoCH?
    ll_broken = False   # last LL already triggered bearish BOS?

    swings_arr = swings.values
    levels_arr = levels.values

    for i in range(n):
        # ── Copy forward previous values ──
        if i > 0:
            trend[i] = trend[i - 1]
            last_hh_arr[i] = last_hh_arr[i - 1]
            last_hl_arr[i] = last_hl_arr[i - 1]
            last_lh_arr[i] = last_lh_arr[i - 1]
            last_ll_arr[i] = last_ll_arr[i - 1]

        # ── Process swing point (first, before BOS/CHoCH) ──
        sv = swings_arr[i]
        did_choch = False
        is_bearish_choch = False
        is_bullish_choch = False

        if not np.isnan(sv):
            lv = levels_arr[i]

            if sv == 1:  # Swing high
                if not np.isnan(prev_swing_high):
                    if lv > prev_swing_high:
                        struct_label[i] = "HH"
                    else:
                        struct_label[i] = "LH"
                else:
                    struct_label[i] = "1H"
                prev_swing_high = lv

            else:  # sv == -1, Swing low
                if not np.isnan(prev_swing_low):
                    if lv > prev_swing_low:
                        struct_label[i] = "HL"
                    else:
                        struct_label[i] = "LL"
                else:
                    struct_label[i] = "1L"
                prev_swing_low = lv

        # ── Only track structure levels relevant to current trend ──
        # In bullish: only HH and HL matter (LH/LL are pullback noise)
        # In bearish: only LH and LL matter (HH/HL are bounce noise)
        # In neutral/transitional: track everything
        lbl = struct_label[i]
        if lbl == "HH":
            _hh = lv
            hh_broken = False
        elif lbl == "HL":
            _hl = lv
            hl_broken = False
        elif lbl == "LH" and _trend in ("neutral", "transitional", "bearish"):
            _lh = lv
            lh_broken = False
        elif lbl == "LL" and _trend in ("neutral", "transitional", "bearish"):
            _ll = lv
            ll_broken = False
        # In bullish trend: LH and LL are pullbacks, don't update structure levels

        # ── Detect BOS/CHoCH on close (once per level) ──
        # BOS = break WITH the trend direction (continuation)
        # CHoCH = break AGAINST the trend direction (reversal warning)
        #
        # During transitional: BOTH CHoCH and BOS can fire.
        #   CHoCH in transitional: close > LH (bullish reversal) or close < HL (bearish reversal)
        #   BOS in transitional: close > HH or close < LL (continuation in expected direction)
        # CHoCH takes priority (clears opposite-direction levels).
        if _trend == "bullish":
            if not hh_broken and not np.isnan(_hh) and close[i] > _hh:
                bull_bos[i] = True
                bos_level[i] = _hh
                hh_broken = True
            if not hl_broken and not np.isnan(_hl) and close[i] < _hl:
                bear_choch[i] = True
                choch_level[i] = _hl
                hl_broken = True
                is_bearish_choch = True
                did_choch = True

        elif _trend == "bearish":
            if not ll_broken and not np.isnan(_ll) and close[i] < _ll:
                bear_bos[i] = True
                bos_level[i] = _ll
                ll_broken = True
            if not lh_broken and not np.isnan(_lh) and close[i] > _lh:
                bull_choch[i] = True
                choch_level[i] = _lh
                lh_broken = True
                is_bullish_choch = True
                did_choch = True

        elif _trend == "transitional":
            # New CHoCH in transitional — price reverses the expected direction
            if not lh_broken and not np.isnan(_lh) and close[i] > _lh:
                bull_choch[i] = True
                choch_level[i] = _lh
                lh_broken = True
                is_bullish_choch = True
                did_choch = True
            if not hl_broken and not np.isnan(_hl) and close[i] < _hl:
                bear_choch[i] = True
                choch_level[i] = _hl
                hl_broken = True
                is_bearish_choch = True
                did_choch = True
            # BOS in transitional — continuation in expected direction
            # (only fire if no CHoCH fired on this candle)
            if not did_choch:
                if not hh_broken and not np.isnan(_hh) and close[i] > _hh:
                    bull_bos[i] = True
                    bos_level[i] = _hh
                    hh_broken = True
                if not ll_broken and not np.isnan(_ll) and close[i] < _ll:
                    bear_bos[i] = True
                    bos_level[i] = _ll
                    ll_broken = True

        # ── Determine trend state ──
        lbl = struct_label[i]
        if lbl in ("HH", "HL"):
            _bullish_count += 1
            _bearish_count = 0
        elif lbl in ("LH", "LL"):
            _bearish_count += 1
            _bullish_count = 0

        if did_choch:
            if is_bearish_choch:
                _trend = "transitional"
                _hh = np.nan
                _hl = np.nan
            elif is_bullish_choch:
                _trend = "transitional"
                _lh = np.nan
                _ll = np.nan
            _bullish_count = 0
            _bearish_count = 0
        elif _trend == "transitional":
            # BOS is the primary trend confirmation — a break of higher-highs
            # (bullish BOS) or lower-lows (bearish BOS) confirms the new trend.
            # In ICT: after CHoCH, a BOS in the expected direction = MSS confirmed.
            if bull_bos[i]:
                _trend = "bullish"
                _lh = np.nan; _ll = np.nan
                lh_broken = True; ll_broken = True
            elif bear_bos[i]:
                _trend = "bearish"
                _hh = np.nan; _hl = np.nan
                hh_broken = True; hl_broken = True
            # Fallback: 3 consecutive swings confirm (covers cases where
            # price doesn't clear the old HH/LL but still steps consistently).
            elif _bullish_count >= 3:
                _trend = "bullish"
                _lh = np.nan; _ll = np.nan
                lh_broken = True; ll_broken = True
            elif _bearish_count >= 3:
                _trend = "bearish"
                _hh = np.nan; _hl = np.nan
                hh_broken = True; hl_broken = True
        else:
            if not np.isnan(_hh) and not np.isnan(_hl):
                _trend = "bullish"
                _lh = np.nan; _ll = np.nan  # clear bearish levels in uptrend
                lh_broken = True; ll_broken = True
            elif not np.isnan(_lh) and not np.isnan(_ll):
                _trend = "bearish"
                _hh = np.nan; _hl = np.nan  # clear bullish levels in downtrend
                hh_broken = True; hl_broken = True

        trend[i] = _trend
        last_hh_arr[i] = _hh
        last_hl_arr[i] = _hl
        last_lh_arr[i] = _lh
        last_ll_arr[i] = _ll

    return pd.DataFrame(
        {
            "structure_label": struct_label,
            "trend": trend,
            "last_hh": last_hh_arr,
            "last_hl": last_hl_arr,
            "last_lh": last_lh_arr,
            "last_ll": last_ll_arr,
            "bullish_bos": bull_bos,
            "bearish_bos": bear_bos,
            "bullish_choch": bull_choch,
            "bearish_choch": bear_choch,
            "choch_level": choch_level,
            "bos_level": bos_level,
        },
        index=ohlc.index,
    )


# ── Verification ─────────────────────────────────────────────


def debug_day(ohlc: pd.DataFrame, date_str: str, swing_length: int = 3) -> None:
    """Print structure labels + BOS/CHoCH for a full day."""
    from backtesting.struct.swing import swing_points

    day = ohlc[ohlc.index.date == pd.Timestamp(date_str).date()].copy()
    if len(day) == 0:
        print(f"No data for {date_str}")
        return

    swings, levels = swing_points(day, swing_length=swing_length)
    labels = label_structure(day, swings, levels)

    print(f"\n═══ {date_str} — {len(day)} candles (5m) ═══")
    print(f"Total swings: {int(swings.notna().sum())}")
    print()

    # Only print rows with structure events
    has_structure = (labels["structure_label"] != "") | \
                    labels["bullish_bos"] | labels["bearish_bos"] | \
                    labels["bullish_choch"] | labels["bearish_choch"]

    events = labels[has_structure]

    if len(events) == 0:
        print("No structure events")
        return

    print(f"{'Time':>8} {'Label':>6} {'Level':>8} {'Trend':>10}  Events")
    print("-" * 60)

    for idx, row in events.iterrows():
        ts_str = idx.strftime("%H:%M")
        lbl = row["structure_label"]
        tr = row["trend"]

        # Get level from swing data
        pos = day.index.get_loc(idx)
        lv_str = f"{levels.iloc[pos]:.5f}" if lbl in ("HH", "HL", "LH", "LL", "1H", "1L") else ""

        extras = []
        if row["bullish_bos"]:
            extras.append(f"↑BOS @ {row['bos_level']:.5f}")
        if row["bearish_bos"]:
            extras.append(f"↓BOS @ {row['bos_level']:.5f}")
        if row["bullish_choch"]:
            extras.append(f"↑CHoCH @ {row['choch_level']:.5f}")
        if row["bearish_choch"]:
            extras.append(f"↓CHoCH @ {row['choch_level']:.5f}")

        extra_str = f"  ({', '.join(extras)})" if extras else ""
        print(f"{ts_str:>8}  {lbl:>6}  {lv_str:>8}  {tr:>10}{extra_str}")
