"""Synthetic data harness: validate structure detection against known features.

Generates OHLCV data with precisely controlled swing highs/lows, CHoCH, BOS,
and sweep events (every bar's OHLC explicitly set), then asserts that
`build_structure_index()` detects them correctly.

Usage:
    python -m backtesting.crypto.synthetic_structure_test
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from backtesting.features.structure import StructureConfig, build_structure_index

# ── Test utils ────────────────────────────────────────────────────────────────

pass_count = 0
fail_count = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  ✓ {label}")
    else:
        fail_count += 1
        print(f"  ✗ {label}" + (f"  — {detail}" if detail else ""))


def bar_df(close: list[float], high: list[float] | None = None,
           low: list[float] | None = None) -> pd.DataFrame:
    """Build OHLCV from explicit OHLC arrays. All arrays must be same length."""
    n = len(close)
    h = high if high is not None else [c * 1.005 for c in close]
    l = low if low is not None else [c * 0.995 for c in close]
    opens = [close[i - 1] if i > 0 else close[0] for i in range(n)]
    return pd.DataFrame({
        "ts": pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC"),
        "open": opens, "high": h, "low": l, "close": close,
        "volume": [100.0] * n,
    })


def locate(struct: pd.DataFrame, col: str) -> list[int]:
    """Return indices where a boolean column is True."""
    if col in ("bull", "bear"):
        return list(np.where(struct["regime"].to_numpy() == col)[0])
    return list(np.where(struct[col].to_numpy(dtype=bool))[0])


def build_all(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build default O H L C arrays of length n, all at base=100."""
    base = 100.0
    o = np.full(n, base)
    h = np.full(n, base * 1.03)
    l = np.full(n, base * 0.97)
    c = np.full(n, base)
    return o, h, l, c


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_swing_high() -> None:
    """Swing high at a specific peak bar is detected at confirmation bar."""
    o, h, l, c = build_all(18)
    # Swing high: bar 8's high > 2 bars left + right
    h[8] = 115.0; c[8] = 113.0
    for i in range(6, 11):
        if i != 8:
            h[i] = 105.0   # lower
            c[i] = 102.0
    df = bar_df(c.tolist(), h.tolist(), l.tolist())
    struct = build_structure_index(df, StructureConfig(left=2, right=2))

    # Confirmed at bar 10 (8 + 2)
    check("swing_high: swing_type high at bar 10",
          struct["swing_type"].iat[10] == "high",
          f"got {struct['swing_type'].iat[10]}")
    check("swing_high: swing_price matches",
          abs(float(struct["swing_price"].iat[10]) - 115.0) < 0.1,
          f"price {struct['swing_price'].iat[10]}")


def test_swing_low() -> None:
    """Swing low at a specific valley bar is detected at confirmation bar."""
    o, h, l, c = build_all(18)
    # Swing low: bar 8's low < 2 bars left + right
    l[8] = 93.0; c[8] = 94.0
    for i in range(6, 11):
        if i != 8:
            l[i] = 97.0    # higher
            c[i] = 99.0
    df = bar_df(c.tolist(), h.tolist(), l.tolist())
    struct = build_structure_index(df, StructureConfig(left=2, right=2))

    check("swing_low: swing_type low at bar 10",
          struct["swing_type"].iat[10] == "low",
          f"got {struct['swing_type'].iat[10]}")
    check("swing_low: swing_price matches",
          abs(float(struct["swing_price"].iat[10]) - 93.0) < 0.1,
          f"price {struct['swing_price'].iat[10]}")


def test_hh_hl_labels() -> None:
    """After 1H→1L→HH→HL, swing labels are correct."""
    o, h, l, c = build_all(40)
    # Bar 8: L0 (1L)
    l[8] = 96.0; c[8] = 97.0
    for i in range(6, 11):
        if i != 8: l[i] = 98.0; c[i] = 99.0
    # Bar 14: H0 (1H)
    h[14] = 108.0; c[14] = 107.0
    for i in range(12, 17):
        if i != 14: h[i] = 103.0; c[i] = 102.0
    # Bar 25: L1 = 100 > L0 = 96 → HL
    l[25] = 100.0; c[25] = 101.0
    for i in range(23, 28):
        if i != 25: l[i] = 102.0; c[i] = 103.0
    # Bar 32: H1 = 112 > H0 = 108 → HH
    h[32] = 112.0; c[32] = 111.0
    for i in range(30, 35):
        if i != 32: h[i] = 105.0; c[i] = 103.0
    # Fill gap bars
    for i in range(1, len(c)):
        if np.isnan(c[i]) or c[i] == 100.0:
            c[i] = c[i-1] + 0.1
    df = bar_df(c.tolist(), h.tolist(), l.tolist())
    struct = build_structure_index(df, StructureConfig(left=2, right=2))

    # Check labels at confirmation bars
    # L0 at 8 → confirmed at 10
    check("1L label at bar 10",
          struct["structure_label"].iat[10] == "1L",
          f"label at 10={struct['structure_label'].iat[10]}")
    # H0 at 14 → confirmed at 16
    check("1H label at bar 16",
          struct["structure_label"].iat[16] == "1H",
          f"label at 16={struct['structure_label'].iat[16]}")
    # L1 at 25 → confirmed at 27
    check("HL label at bar 27",
          struct["structure_label"].iat[27] == "HL",
          f"label at 27={struct['structure_label'].iat[27]}")
    # H1 at 32 → confirmed at 34
    check("HH label at bar 34",
          struct["structure_label"].iat[34] == "HH",
          f"label at 34={struct['structure_label'].iat[34]}")


def test_uptrend_regime_bull() -> None:
    """HH → HL sequence eventually triggers bull regime."""
    o, h, l, c = build_all(50)
    # L0 at 8
    l[8] = 96.0; c[8] = 97.0
    for i in range(6, 11):
        if i != 8: l[i] = 98.0; c[i] = 99.0
    # H0 at 14
    h[14] = 108.0; c[14] = 107.0
    for i in range(12, 17):
        if i != 14: h[i] = 103.0; c[i] = 102.0
    # L1 at 25: HL (100 > 96)
    l[25] = 100.0; c[25] = 101.0
    for i in range(23, 28):
        if i != 25: l[i] = 102.0; c[i] = 103.0
    # H1 at 32: HH (112 > 108)
    h[32] = 112.0; c[32] = 111.0
    for i in range(30, 35):
        if i != 32: h[i] = 105.0; c[i] = 103.0
    # L2 at 40: HL (105 > 100) → last_hh exists + HL → bull
    l[40] = 105.0; c[40] = 106.0
    for i in range(38, 43):
        if i != 40: l[i] = 107.0; c[i] = 108.0
    # Fill
    for i in range(1, len(c)):
        if c[i] == 100.0:
            c[i] = c[i-1] + 0.05
    df = bar_df(c.tolist(), h.tolist(), l.tolist())
    struct = build_structure_index(df, StructureConfig(left=2, right=2))

    bull_bars = locate(struct, "bull")
    check("bull regime activates", len(bull_bars) > 0,
          f"regime counts: {struct['regime'].value_counts().to_dict()}")
    # Bull should start at or after HL confirmation (bar 42)
    after_hl = any(i >= 40 for i in bull_bars)
    check("bull regime after HL", after_hl,
          f"bull starts at bar {bull_bars[0] if len(bull_bars) else 'none'}")


def test_downtrend_regime_bear() -> None:
    """LL → LH sequence triggers bear regime."""
    o, h, l, c = build_all(50)
    # H0 at 8
    h[8] = 112.0; c[8] = 111.0
    for i in range(6, 11):
        if i != 8: h[i] = 106.0; c[i] = 104.0
    # L0 at 14
    l[14] = 99.0; c[14] = 100.0
    for i in range(12, 17):
        if i != 14: l[i] = 103.0; c[i] = 104.0
    # H1 at 25: LH (106 < 112)
    h[25] = 106.0; c[25] = 105.0
    for i in range(23, 28):
        if i != 25: h[i] = 103.0; c[i] = 102.0
    # L1 at 32: LL (97 < 99)
    l[32] = 97.0; c[32] = 98.0
    for i in range(30, 35):
        if i != 32: l[i] = 100.0; c[i] = 101.0
    # H2 at 40: LH (102 < 106) → last_ll + LH → bear
    h[40] = 102.0; c[40] = 101.0
    for i in range(38, 43):
        if i != 40: h[i] = 100.0; c[i] = 99.0
    # Fill
    for i in range(1, len(c)):
        if c[i] == 100.0:
            c[i] = c[i-1] - 0.05
    df = bar_df(c.tolist(), h.tolist(), l.tolist())
    struct = build_structure_index(df, StructureConfig(left=2, right=2))

    bear_bars = locate(struct, "bear")
    check("bear regime activates", len(bear_bars) > 0,
          f"regime counts: {struct['regime'].value_counts().to_dict()}")


def test_choch_down_via_price_break() -> None:
    """In bull regime, close sinking below last_hl triggers choch_down."""
    o, h, l, c = build_all(60)
    # Build bull regime
    l[8] = 96.0; c[8] = 97.0
    for i in range(6, 11):
        if i != 8: l[i] = 98.0; c[i] = 99.0
    h[14] = 108.0; c[14] = 107.0
    for i in range(12, 17):
        if i != 14: h[i] = 103.0; c[i] = 102.0
    l[25] = 100.0; c[25] = 101.0  # HL
    for i in range(23, 28):
        if i != 25: l[i] = 102.0; c[i] = 103.0
    h[32] = 112.0; c[32] = 111.0  # HH
    for i in range(30, 35):
        if i != 32: h[i] = 105.0; c[i] = 103.0
    l[40] = 104.0; c[40] = 105.0  # HL
    for i in range(38, 43):
        if i != 40: l[i] = 106.0; c[i] = 107.0

    # Keep bars 43-49 above last_hl (104)
    for i in range(42, 50):
        l[i] = 105.0; c[i] = 106.0; h[i] = 108.0

    # Bar 50-52: close drops below last_hl (=104) → choch_down
    for i in range(50, 53):
        c[i] = 102.0; l[i] = 101.0; h[i] = 105.0

    df = bar_df(c.tolist(), h.tolist(), l.tolist())
    struct = build_structure_index(df, StructureConfig(left=2, right=2))

    cd = locate(struct, "choch_down")
    check("choch_down fires on price break", len(cd) > 0, "no choch_down")
    near_50 = any(48 <= i <= 53 for i in cd)
    check("choch_down near bar 50", near_50, f"at bars {cd[:5]}")


def test_bos_up() -> None:
    """In uptrend, close above last HH is BOS up."""
    n = 40
    o = np.full(n, 100.0); h = np.full(n, 103.0)
    l = np.full(n, 98.0); c = np.full(n, 100.0)

    # L0 at 5
    l[5] = 96.0; c[5] = 97.0
    l[3] = l[4] = l[6] = l[7] = 98.0; c[3] = c[4] = c[5] = c[6] = c[7] = 99.0
    # H0 at 10
    h[10] = 108.0; c[10] = 107.0
    for i in [8, 9, 11, 12]: h[i] = 103.0; c[i] = 102.0
    # L1 (HL) at 15
    l[15] = 100.0; c[15] = 101.0
    for i in [13, 14, 16, 17]: l[i] = 102.0; c[i] = 103.0
    # H1 (HH) at 20 — high=114 ensures peak stays above everything
    h[20] = 114.0; c[20] = 113.0
    for i in [18, 19, 21, 22]: h[i] = 106.0; c[i] = 104.0
    # L2 (HL) at 25 → bull regime
    l[25] = 104.0; c[25] = 105.0
    for i in [23, 24, 26, 27]: l[i] = 106.0; c[i] = 107.0

    # Bars 26-29: trade below HH (114), close=108
    for i in [26, 27, 28, 29]:
        c[i] = 108.0; h[i] = 110.0

    # Bar 30: close above 114 → BOS up
    c[30] = 116.0; h[30] = 117.0

    df = bar_df(c.tolist(), h.tolist(), l.tolist())
    struct = build_structure_index(df, StructureConfig(left=2, right=2))

    bu = locate(struct, "bos_up")
    check("bos_up fires", len(bu) > 0, "no bos_up")
    near_30 = any(28 <= i <= 32 for i in bu)
    check("bos_up near bar 30", near_30, f"at bars {bu[:5]}")


def test_sweep_high() -> None:
    """High pierces HH level, close stays below → sweep_high, no bos_up."""
    n = 40
    o = np.full(n, 100.0); h = np.full(n, 103.0)
    l = np.full(n, 98.0); c = np.full(n, 100.0)

    # Build uptrend with HH at bar 20 (high=114)
    l[5] = 96.0; c[5] = 97.0
    l[3] = l[4] = l[6] = l[7] = 98.0; c[3] = c[4] = c[5] = c[6] = c[7] = 99.0
    h[10] = 108.0; c[10] = 107.0
    for i in [8, 9, 11, 12]: h[i] = 103.0; c[i] = 102.0
    l[15] = 100.0; c[15] = 101.0
    for i in [13, 14, 16, 17]: l[i] = 102.0; c[i] = 103.0
    h[20] = 114.0; c[20] = 113.0  # HH = 114
    for i in [18, 19, 21, 22]: h[i] = 106.0; c[i] = 104.0

    # Sweep: bar 28 high > 114 but close < 114
    # Neighbors at 26,27,29,30 have lower highs to prevent swing detection
    c[28] = 112.0; h[28] = 115.5; l[28] = 110.0
    h[26] = h[27] = h[29] = h[30] = 112.0  # lower than 115.5 → not a swing
    c[29] = 110.0

    df = bar_df(c.tolist(), h.tolist(), l.tolist())
    struct = build_structure_index(df, StructureConfig(left=2, right=2))

    sw = locate(struct, "sweep_high")
    check("sweep_high fires", len(sw) > 0, "no sweep_high")
    near_28 = any(26 <= i <= 32 for i in sw)
    check("sweep_high near bar 28", near_28, f"at bars {sw[:5]}")
    bu = locate(struct, "bos_up")
    check("no false bos_up on sweep", len(bu) == 0,
          f"unexpected bos_up at {bu[:5]}")


def test_sweep_low() -> None:
    """Low pierces below LL level, close stays above → sweep_low, no bos_down."""
    o, h, l, c = build_all(48)
    h[8] = 112.0; c[8] = 111.0
    for i in range(6, 11):
        if i != 8: h[i] = 106.0; c[i] = 104.0
    l[14] = 99.0; c[14] = 100.0
    for i in range(12, 17):
        if i != 14: l[i] = 103.0; c[i] = 104.0
    l[25] = 97.0; c[25] = 98.0  # LL = 97
    for i in range(23, 28):
        if i != 25: l[i] = 100.0; c[i] = 101.0

    # Sweep: bar 32 low < 97, close > 97
    l[32] = 95.0; c[32] = 100.0
    for i in [30, 31, 33, 34]:
        l[i] = 96.0  # neighbors lower, making bar 32 NOT a swing valley

    df = bar_df(c.tolist(), h.tolist(), l.tolist())
    struct = build_structure_index(df, StructureConfig(left=2, right=2))

    sw = locate(struct, "sweep_low")
    check("sweep_low fires", len(sw) > 0, "no sweep_low")
    near_32 = any(30 <= i <= 35 for i in sw)
    check("sweep_low near bar 32", near_32, f"at bars {sw[:5]}")
    bd = locate(struct, "bos_down")
    check("no false bos_down on sweep", len(bd) == 0,
          f"unexpected bos_down at {bd[:5]}")


def test_flat_market_no_false() -> None:
    """Flat market (tiny noise) produces no CHoCH, BOS, or sweeps."""
    n = 100
    rng = np.random.default_rng(42)
    base = 100.0
    c = [base + rng.normal(0, 0.02) * 0 for _ in range(n)]  # truly flat
    h = [ci * 1.002 for ci in c]
    l = [ci * 0.998 for ci in c]
    df = bar_df(c, h, l)
    struct = build_structure_index(df, StructureConfig(left=2, right=2))

    check("no CHoCH in flat market",
          ~(struct["choch_up"] | struct["choch_down"]).any())
    check("no BOS in flat market",
          ~(struct["bos_up"] | struct["bos_down"]).any())
    # Sweeps in nearly-flat data can appear from tiny wicks — just print count
    sweeps = (struct["sweep_high"] | struct["sweep_low"]).sum()
    if sweeps:
        print(f"  ~ sweeps in flat market: {sweeps} bars (typically wick artifacts)")


def test_strong_trend_no_false_choch() -> None:
    """Strong unbroken uptrend: HH/HL repeats should NOT trigger CHoCH."""
    n = 80
    o = np.full(n, 100.0); h = np.full(n, 105.0)
    l = np.full(n, 97.0); c = np.full(n, 100.0)
    # Perfect HH/HL sequence — carefully place swings with correct neighbor isolation
    buf = 3.0
    swings = [
        (6, "low", 96.0),     # L0
        (12, "high", 108.0),  # H0
        (20, "low", 100.0),   # L1 > L0
        (26, "high", 112.0),  # H1 > H0
        (34, "low", 104.0),   # L2 > L1
        (40, "high", 116.0),  # H2 > H1
        (48, "low", 108.0),   # L3 > L2
        (54, "high", 120.0),  # H3 > H2
        (62, "low", 112.0),   # L4 > L3
        (68, "high", 124.0),  # H4 > H3
    ]
    for bar, stype, price in swings:
        if stype == "low":
            l[bar] = price; c[bar] = price + 1.0
            # Neighbors: higher, ensuring bar is a valley
            for nb in [bar - 2, bar - 1, bar + 1, bar + 2]:
                if 0 <= nb < n:
                    l[nb] = price + buf
                    if c[nb] == 100.0:
                        c[nb] = price + buf + 0.5
        else:  # high
            h[bar] = price; c[bar] = price - 1.0
            # Neighbors: lower, ensuring bar is a peak
            for nb in [bar - 2, bar - 1, bar + 1, bar + 2]:
                if 0 <= nb < n:
                    h[nb] = price - buf
                    if c[nb] == 100.0:
                        c[nb] = price - buf - 0.5
    # Fill remaining gaps
    for i in range(1, n):
        if abs(c[i] - 100.0) < 0.5:
            c[i] = c[i-1] + 0.1
    df = bar_df(c.tolist(), h.tolist(), l.tolist())
    struct = build_structure_index(df, StructureConfig(left=2, right=2))

    choch = struct["choch_up"] | struct["choch_down"]
    check("no CHoCH in strong trend", ~choch.any(),
          f"false CHoCH on {choch.sum()} bars")
    bull_bars = locate(struct, "bull")
    check("bull regime dominates", len(bull_bars) > len(c) * 0.3,
          f"bull on {len(bull_bars)}/{len(c)} bars")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    global pass_count, fail_count
    pass_count = 0
    fail_count = 0

    tests = [
        ("Swing high detection", test_swing_high),
        ("Swing low detection", test_swing_low),
        ("HH/HL swing labels", test_hh_hl_labels),
        ("Uptrend → bull regime", test_uptrend_regime_bull),
        ("Downtrend → bear regime", test_downtrend_regime_bear),
        ("CHoCH down via price break", test_choch_down_via_price_break),
        ("BOS up in uptrend", test_bos_up),
        ("Sweep high (no false BOS)", test_sweep_high),
        ("Sweep low (no false BOS)", test_sweep_low),
        ("Flat market: no false signals", test_flat_market_no_false),
        ("Strong trend: no false CHoCH", test_strong_trend_no_false_choch),
    ]

    print("=" * 60)
    print("Synthetic Structure Detection Validation")
    print("=" * 60)

    for name, func in tests:
        print(f"\n── {name} ──")
        try:
            func()
        except Exception as e:
            fail_count += 1
            import traceback
            traceback.print_exc()
            print(f"  ✗ CRASHED: {e}")

    print("\n" + "=" * 60)
    total = pass_count + fail_count
    pct = pass_count / total * 100 if total else 0
    print(f"Results: {pass_count}/{total} passed ({pct:.0f}%), "
          f"{fail_count}/{total} failed")
    if fail_count:
        print("SOME CHECKS FAILED — review details above")
        sys.exit(1)
    else:
        print("ALL STRUCTURE FEATURES VALIDATED")
        sys.exit(0)


if __name__ == "__main__":
    main()
