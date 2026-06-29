"""
Side-by-side comparison of the two structure engines:
  - Verified: backtesting/features/structure.py
  - ML/vbt:   backtesting/structure_lib/vbt_indicators.py

Runs both on the same data and reports discrepancies.
"""
import numpy as np
import pandas as pd
import itertools

from backtesting.engine.data import load_data
from backtesting.features.structure import build_structure_index, StructureConfig
from backtesting.structure_lib.vbt_indicators import compute_all

symbol = "GBPAUD"
tf = "60"
days = 90
df = load_data(symbol, tf, days=days)
print(f"Loaded {len(df)} bars of {symbol} {tf}m")

# === VERIFIED ENGINE ===
st_verified = build_structure_index(df, StructureConfig())  # default left=2, right=2
st_verified_33 = build_structure_index(
    df, StructureConfig(left=3, right=3, min_swing_atr=0.0)
)

# === ML ENGINE ===
ind = compute_all(df, swing_left=3, swing_right=3)
struct_ml = ind["structure"]

v_swings = st_verified[st_verified["swing_type"] != ""].copy()
v33_swings = st_verified_33[st_verified_33["swing_type"] != ""].copy()

ml_label_arr = struct_ml.label.values[:, 0]
ml_swing_bars = np.where(ml_label_arr != 0)[0]
ml_labels_at_swing = ml_label_arr[ml_swing_bars]

# ── Swing counts ──
print("\n" + "=" * 66)
print("SWING POINT COMPARISON")
print("=" * 66)
print(f"{'Engine':26s} {'Swings':>7s}  {'HH':>5s} {'HL':>5s} {'LH':>5s} {'LL':>5s}")
print("-" * 66)

def count_labels(swing_df, label_col):
    return [int((swing_df[label_col] == lbl).sum()) for lbl in ["HH","HL","LH","LL"]]

v_cnt = count_labels(v_swings, "structure_label")
v33_cnt = count_labels(v33_swings, "structure_label")
ml_cnt = [
    int(np.sum(ml_labels_at_swing == 1)),
    int(np.sum(ml_labels_at_swing == 2)),
    int(np.sum(ml_labels_at_swing == 3)),
    int(np.sum(ml_labels_at_swing == 4)),
]

print(f"{'Verified (L2/R2)':26s} {len(v_swings):>7d}  {v_cnt[0]:>5d} {v_cnt[1]:>5d} {v_cnt[2]:>5d} {v_cnt[3]:>5d}")
print(f"{'Verified (L3/R3)':26s} {len(v33_swings):>7d}  {v33_cnt[0]:>5d} {v33_cnt[1]:>5d} {v33_cnt[2]:>5d} {v33_cnt[3]:>5d}")
print(f"{'ML vbt (L3/R3)':26s} {len(ml_swing_bars):>7d}  {ml_cnt[0]:>5d} {ml_cnt[1]:>5d} {ml_cnt[2]:>5d} {ml_cnt[3]:>5d}")

# Check agreement rate: what % of ML swing bars match Verified (L3/R3)?
matched = 0
v33_label_map = v33_swings["structure_label"].to_dict()
v33_swing_set = set(v33_swings.index)
for b in ml_swing_bars:
    if b in v33_swing_set:
        v_lbl = v33_label_map[b]
        ml_lbl_code = int(ml_label_arr[b])
        ml_lbl_name = {1:"HH",2:"HL",3:"LH",4:"LL"}.get(ml_lbl_code, "")
        if v_lbl == ml_lbl_name:
            matched += 1
total_check = len([b for b in ml_swing_bars if b in v33_swing_set])
print(f"\nSwing label agreement (ML vs Verified L3/R3, same bar): {matched}/{total_check} = {100*matched/total_check:.1f}%" if total_check > 0 else "No common bars to compare")

# ── Lookahead analysis ──
print(f"\n{'='*66}")
print(f"LOOKAHEAD ANALYSIS")
print(f"{'='*66}")
print(f"Verified engine: first swing at bar {v_swings.index[0]} (of {len(df)})")
print(f"  swing_ts={v_swings['swing_ts'].iloc[0]}, confirm_ts={v_swings['confirm_ts'].iloc[0]}")
print(f"ML engine: first swing at bar {ml_swing_bars[0]} (of {len(df)})")
print(f"  (swing emitted at pivot bar, no confirm delay)")
early_bars = [b for b in ml_swing_bars if b < 6]
print(f"ML swings in first 6 bars (would indicate lookahead): {len(early_bars)}")

# ── Regime distribution ──
print(f"\n{'='*66}")
print(f"REGIME / TREND DISTRIBUTION")
print(f"{'='*66}")
v_reg = st_verified["regime"].value_counts()
v33_reg = st_verified_33["regime"].value_counts()
ml_trend = struct_ml.trend.values[:, 0]
ml_bull = int(np.sum(ml_trend == 1))
ml_bear = int(np.sum(ml_trend == -1))
ml_neut = int(np.sum(ml_trend == 0))
print(f"{'Verified (L2/R2):':26s} bull={v_reg.get('bull',0):>6d} bear={v_reg.get('bear',0):>6d} neut={v_reg.get('neutral',0):>6d}")
print(f"{'Verified (L3/R3):':26s} bull={v33_reg.get('bull',0):>6d} bear={v33_reg.get('bear',0):>6d} neut={v33_reg.get('neutral',0):>6d}")
print(f"{'ML vbt:':26s} bull={ml_bull:>6d} bear={ml_bear:>6d} neut={ml_neut:>6d}")

# ── BOS/CHOCH events ──
print(f"\n{'='*66}")
print(f"BOS / CHOCH EVENTS")
print(f"{'='*66}")
v_bos = st_verified[["bos_up","bos_down","choch_up","choch_down"]].sum()
v33_bos = st_verified_33[["bos_up","bos_down","choch_up","choch_down"]].sum()
ml_bull_bos = int(np.sum(struct_ml.bullish_bos.values[:, 0]))
ml_bear_bos = int(np.sum(struct_ml.bearish_bos.values[:, 0]))
ml_bull_choch = int(np.sum(struct_ml.bullish_choch.values[:, 0]))
ml_bear_choch = int(np.sum(struct_ml.bearish_choch.values[:, 0]))
print(f"{'Event':15s} {'Verif L2/R2':>12s} {'Verif L3/R3':>12s} {'ML vbt':>10s}")
print("-" * 49)
print(f"{'BOS UP':15s} {int(v_bos['bos_up']):>12d} {int(v33_bos['bos_up']):>12d} {ml_bull_bos:>10d}")
print(f"{'BOS DOWN':15s} {int(v_bos['bos_down']):>12d} {int(v33_bos['bos_down']):>12d} {ml_bear_bos:>10d}")
print(f"{'CHOCH UP':15s} {int(v_bos['choch_up']):>12d} {int(v33_bos['choch_up']):>12d} {ml_bull_choch:>10d}")
print(f"{'CHOCH DOWN':15s} {int(v_bos['choch_down']):>12d} {int(v33_bos['choch_down']):>12d} {ml_bear_choch:>10d}")

# ── Bar-by-bar comparison ──
print(f"\n{'='*66}")
print(f"BAR-BY-BAR SWING COMPARISON (first 20 swing bars across all engines)")
print(f"{'='*66}")
v_swing_set = set(v_swings.index)
v33_swing_set = set(v33_swings.index)
ml_swing_set = set(ml_swing_bars)
all_swing_bars = sorted(set(itertools.chain(v_swing_set, v33_swing_set, ml_swing_set)))[:20]

v33_label_by_bar = v33_swings["structure_label"].to_dict()
print(f"{'Bar':>5s} {'Ts':>20s} {'V(L2R2)':>10s} {'V(L3R3)':>10s} {'ML':>8s}")
print("-" * 55)
for b in all_swing_bars:
    v_lbl = st_verified.loc[b, "structure_label"] if b in st_verified.index else "-"
    v33_lbl = st_verified_33.loc[b, "structure_label"] if b in st_verified_33.index else "-"
    ml_code = int(ml_label_arr[b]) if ml_label_arr[b] != 0 else 0
    ml_lbl = {1:"HH",2:"HL",3:"LH",4:"LL",0:"-"}.get(ml_code, "?")
    ts = str(df["ts"].iloc[b])[:19]
    print(f"{b:>5d} {ts:>20s} {v_lbl:>10s} {v33_lbl:>10s} {ml_lbl:>8s}")

# ── Summary ──
print(f"\n{'='*66}")
print(f"SUMMARY OF STRUCTURE ENGINE DISCREPANCIES")
print(f"{'='*66}")
discrepancies = [
    ("Default params", "Verified uses left=2, right=2; ML uses left=3, right=3"),
    ("Swing detection method", "Verified: strength-based (high_strength = pivot - max(neighbors)). ML: binary peak/trough (high[i] == max(...))"),
    ("Min swing ATR filter", "Verified: has min_swing_atr threshold. ML: none — every pivot counts"),
    ("Dual-pivot resolution", "Verified: picks stronger type when bar is both high & low swing. ML: no dual-pivot logic"),
    ("Consecutive same-type", "Verified: alternates (prevents HH→HH). ML: keeps most extreme of two consecutive"),
    ("Lookahead", "Verified: emits swing at confirm_ts (pivot_i + right). ML: emits at pivot bar (NO confirm delay)"),
    ("Label encoding", "Verified: strings (HH/HL/LH/LL/1H/1L). ML: ints (1=HH,2=HL,3=LH,4=LL)"),
    ("Regime logic", "Verified: needs HH+HL pair for bull, LH+LL pair for bear. ML: needs 3 consecutive bull/bear labels"),
    ("Regime after CHOCH", "Verified: goes neutral. ML: also goes 0 (neutral) but resets different counters"),
    ("Sweep detection", "Verified: built-in (high>swing_high and close<swing_high). ML: separate LiquiditySweeps module"),
    ("BOS condition", "Verified: close > last_hh. ML: close > _hh (same concept but different variable tracking)"),
]
for i, (topic, desc) in enumerate(discrepancies, 1):
    print(f"{i:>2d}. {topic:30s} {desc}")

print(f"\n{'='*66}")
print(f"CRITICAL CONCERN: LOOKAHEAD BIAS IN ML ENGINE")
print(f"{'='*66}")
print("""
The ML engine (vbt_indicators) emits swing points at the pivot bar index, NOT
at the confirmation index (pivot + right_bars). This means:
  - A swing detected at bar i uses data from bars i-left to i+right
  - The label at bar i already "knows" about this swing
  - But a trader at the close of bar i CANNOT know the swing is confirmed yet
  - Actual confirmation can only happen at bar i+right

Therefore, the ML feature matrix built from vbt_indicators contains data that
was NOT available at that bar's close. The features at bar i reference swing
levels that aren't confirmed yet. This is a DATA LEAKAGE / LOOKAHEAD BIAS
that inflates apparent ML accuracy.

The verified engine (features/structure.py) fixes this by emitting swings at
their confirmation timestamp (bar i+right, stored as 'confirm_ts'). A strategy
entering at the NEXT bar after confirm_ts can safely use the swing information.
""")
