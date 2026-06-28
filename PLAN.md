# Prop Firm Engine — Development Plan

Last updated: 2026-06-28

## Goal

Build a mechanical trading engine that can pass Goat Funded Trader challenges:

- 25k 2 Step GOAT account.
- 100k 1 Step account.

The target is not a pretty full-period backtest. The target is repeated 30-day challenge windows with enough return, low drawdown, and no rule breaches.

## Data Summary (Manual Trades)

| Trigger | Wins | Losses | WR |
|---------|------|--------|----|
| CHoCH/BOS | 52 | 4 | 93% |
| Liquidity sweep | 27 | 4 | 87% |
| FVG 50% entry | 13 | 2 | 87% |
| OB retest | 55 | 20 | 73% |

**Session breakdown**: London dominates (91W/23L), NY has better WR (89%). Balanced long/short.

**Key insight**: These are actual trades with notes like "entry after choch/bos to collect asia liquidity aiming at 50% of order block accumulation." The strategy is in your head — we codify it.

## Core Philosophy

Structure is the operating model, but structure is not magic. The engine must prove:

1. Direction filter: higher-timeframe state gives enough directional accuracy.
2. Entry quality: sweep/MSS/FVG/OB sequence beats random intraday noise.
3. Risk control: if structure changes against the trade, the trade is cut or reduced before a full stop whenever possible.
4. Re-entry logic: one failed entry does not invalidate the daily thesis, but re-entry requires a fresh structure state.
5. Challenge fit: every result is judged by 30-day windows and GFT drawdown rules.

Bullshit failure mode: calling a discretionary chart idea an "engine" before it survives rolling OOS windows.

Current evidence: structure direction is not globally correct. It is asset/session/regime-specific. XAU short Asia and GBPAUD short NY have useful pockets; XAU HTF-bull London/NY and NAS100 HTF-bear are anti-edge in the latest 120D direction test.

Direction fix: use strict ICT sequencing, not loose regime labels. Bullish direction requires HH/HL plus bullish BOS. Bearish direction requires bearish CHoCH, new LL/LH, then bearish BOS. CHoCH alone is transition/no-trade.

## Strategy Architecture

```
4H (240m) ──► HH/HL/LH/LL labels ──► macro bias (bullish/bearish)
1H (60m)   ──► HH/HL/LH/LL labels ──► intermediate bias (confluence)
15m        ──► HH/HL/LH/LL labels ──► sweep + MSS detection + structural SL
1m (or 5m) ──► HH/HL/LH/LL labels ──► FVG detection + entry + trailing SL
```

Structure (HH/HL = bullish, LH/LL = bearish) everywhere. Labels are consistent across all timeframes using the same algorithm with different swing lengths.

### Entry Sequence (Mandatory — all 6 steps must pass)

```
1. 4H structure bullish/bearish → bias set
2. 1H structure same direction → confluence (TEST: both vs either vs 4H only)
3. 15m sweep: price wicks beyond a swing point (LL for longs, HH for shorts)
   AND body closes back inside → sweep confirmed
4. 15m MSS: after the sweep, price breaks a swing point in the bias direction
   with displacement (aggressive body close, often with FVG)
5. 1m/5m FVG forms in the bias direction during MSS displacement
6. 1m/5m price retraces into the FVG → entry on limit at FVG CE (50% level)
```

Sweep detection rules (from ICT methodology):
- **Wick-rejection**: wick extends beyond the swing, body closes inside
- **Close-reclaim**: body briefly closes beyond, next bar reverses inside
- **No sweep = no setup** — price drifting to a level without stop-hunt is not an ICT reversal setup
- **MSS required** (not just CHoCH) — CHoCH without sweep context is a warning, not a trade signal
- All signals use `close[1]` (confirmed previous bar), never `close[0]`

### Stop Loss

Structural — placed beyond the swept level with ATR buffer:

- **Long**: stop below the swept LL + 0.5× ATR(14) buffer
- **Short**: stop above the swept HH + 0.5× ATR(14) buffer

If price returns to re-sweep the level, the stop holds. If structure breaks against us (new LL below for longs, new HH above for shorts), we exit.

### Exit System (Hybrid — Partial Scale-Out)

| Level | Allocation | Trigger | Action |
|-------|-----------|---------|--------|
| TP1 | **50%** | Nearest target | Close, move stop to BE |
| TP2 | **30%** | Further target | Close |
| Runner | **20%** | Structure trailing | Trail on 1m HL/LH until stopped |

Also testing: 50/50, 30/30/40, 100 (single exit).

**Targets evaluated** (trade hits the nearest one first):
1. Previous daily high/low
2. Previous 1H session high/low
3. 50% FVG level (consequent encroachment)
4. Fib extension: 1.0× / 1.272× / 1.618× of the MSS swing range

**Trailing method for runner (20%)**: 1m structure labels. New 1m HL = raise trailing stop for longs. New 1m LH = lower trailing stop for shorts. Exit when 1m CHoCH fires — structure has shifted, we're done.

### Fibonacci for TP

```
Long setup (example):
  15m MSS sweep low = L, MSS swing high = H
  Range = H - L
  TP1: H + 1.0 × Range
  TP2: H + 1.272 × Range
  TP3: H + 1.618 × Range
```

This adapts to current volatility automatically. In high-volatility periods the swing range is wider → TPs are further apart. In low-volatility periods TPs are tighter.

## Cost Model

- **Spread**: random uniform 1-3 pips on entry + 0.5-1.5 pips on exit
- **SL slippage**: random 0-1 pip extra on stop hits
- **Commission**: $0.75 per side ($1.50 round-trip)
- **Minimum stop rule**: stop distance must be ≥ 5× average spread

This matches the industry-standard cost model. Previously in strategy_v2.py.

## Prop Firm Rules (Non-Negotiable)

Primary source: Goat Funded Trader FAQ, checked 2026-06-26.

| Account | Model | Target | Daily DD | Max Loss | Min Trading Days | Leverage Eval |
|---------|-------|--------|----------|----------|------------------|---------------|
| 25k | 2 Step GOAT | Phase 1: 8%, Phase 2: 6% | 4% | 10% static | 3 days each phase | FX 1:100, indices/commodities 1:20 |
| 100k | 1 Step | 10% | 4% | 6% static | 3 days | FX 1:100, indices/commodities 1:20 |

Internal pass gate is stricter than the firm:

| Gate | Requirement |
|------|-------------|
| Rolling window | Every 30D test window reported separately |
| Max DD | Prefer <2%; reject >3% unless return is exceptional |
| Daily loss | Prefer <1.5%; hard reject near 4% |
| Return | 25k 2-step phase target: 8% and 6%; 100k 1-step target: 10% |
| Trades | Zero-trade days allowed; forced activity is a bug |
| Risk/trade search | 0.10%, 0.15%, 0.20%, 0.25%, 0.30%, 0.40%, 0.50% |

Binding constraint: 100k 1-step has only 6% static max loss, so it controls the portfolio risk design.

## Realistic Expectations

| Metric | Manual | Mechanical (Expected) |
|--------|--------|----------------------|
| Win rate | 83% | 55-65% |
| Risk:Reward | 1:1.5-1:2 | 1:1.5-1:2 |
| 30D return | — | 6-10% only after OOS proof |
| Max DD | — | <2-3% preferred |
| Trades/day | — | 1-3 |

**Why the drop**: Discretionary + hindsight vs. mechanical rules. The edge is real, but execution won't be perfect.

## Test Matrix — First Sweep

| Variable | Values | Purpose |
|----------|--------|---------|
| Assets | XAUUSD, NAS100, GBPJPY, GBPUSD, EURUSD, GBPAUD | Gold and NAS are allowed; FX remains the structure thesis |
| Bias TF | 4H only, 1H only, 4H+1H same | Test all |
| Entry TF | 1m, 5m | Compare noise vs precision |
| Sweep | Required, Not required | Test filter impact |
| Partials | 50/30/20, 50/50, 30/30/40, 100 (single) | Test all |
| Targets | Daily, Session, 50% FVG, Fib exts, ALL | Test individually |
| Trade management | fixed SL, structure-cut, scale-down-on-CHoCH, re-entry allowed once | Test whether structure monitoring reduces DD |
| Data window | rolling 30D + 7-14D structure warmup | Challenge-realistic comparison |

First target is not max return. First target is a stable profile: positive 30D return, DD below 2-3%, no daily breach, and no obvious lookahead.

## Data Sources

| Asset class | State |
|-------------|-------|
| FX majors/crosses | 21 symbols with 5m/15m/30m/60m/240m coverage to 2026-06-23; 1m is shorter, roughly from 2026-03-16 |
| Gold | XAUUSD available and currently produces the most TrIct trades |
| NAS100 | CSV exists, but format/history must be normalized before serious tests |
| Crypto | Useful architecture from `feature/crypto-scaling-engine`, but not part of this GFT forex/index/commodity challenge engine |

## Obsidian Vault

The existing `/Trading/` directory in Obsidian contains previous V2 work that is known to have issues (overfitting, missing spread model, flawed rolling analysis). This data is **not relied upon** for Prop Firm Engine decisions.

Action: archive old content, rebuild with only validated results from our own sweep runs.

## Work Plan

### Phase 1: Infrastructure & Speed (Jun 28 — Done)
- [x] Conda env `trade` with Python 3.11, Numba, LLVM, Apple vecLib BLAS pinned
- [x] VectorBT 1.0.0 with Rust engine (M1 Pro optimized)
- [x] TA-Lib (61 candlestick patterns), Polars 1.42, LightGBM/XGBoost/CatBoost
- [x] Baseline benchmark: 0.34s for 30k bars (single run), ~5min for 486 combos

### Phase 2: VectorBT Migration (Jun 28 — Done)
- [x] Structure lib → `vbt.IndicatorFactory` wrappers (SwingPoints, FVGInd, StructureLabels, LiquiditySweeps)
- [x] `compute_all()` helper: runs all indicators in one call
- [x] `VbtRunner` hybrid runner: strategy.next() collects signals → `vbt.Portfolio.from_signals`
- [x] `sweep.py`: multiprocessing param grid sweep
- [x] Performance: single run 0.37s (matches original, VectorBT handles exits)

### Phase 3: ML Pipeline (Jun 28 — Done)
- [x] `ml/labels.py`: Triple-barrier 3-class labeling (HOLD/LONG/SHORT)
- [x] `ml/features.py`: Feature matrix from structure_lib (trend, FVG, sweeps, session/volatility)
- [x] `ml/train.py`: LightGBM+XGBoost+CatBoost ensemble, walk-forward expanding window, purged CV
- [x] `ml/predict.py`: Mlpredictor → filter strategy signals by ML probability > threshold
- [x] Training test: 60d GBPAUD 5m, 264 signals, 28 features, 48.8% accuracy
- [ ] More data for training (120d+)
- [ ] Sensitivity analysis on threshold (0.5–0.8)
- [ ] Feature importance: drop low-importance features, retrain

### Phase 4: Engine Candidate — Complete Integration
- [ ] Implement state machine: HTF bias -> liquidity sweep -> MSS/ChoCH -> FVG/OB retest -> entry.
- [ ] Add active structure monitor: exit/reduce if 1m/5m structure flips against the trade.
- [ ] Add ML filter to strategy: `if Mlpredictor.filter_signal(structure_dir, features): place_trade()`
- [ ] Add intraday re-entry: max 1-2 attempts per thesis, only after fresh sweep/MSS.
- [ ] Add target hierarchy: opposing liquidity first, then partials, then structure runner.
- [ ] Run first sweep on XAUUSD, then NAS100 after normalization, then FX basket.

### Phase 5: Validate
- [ ] Review sweep results, fix bugs
- [ ] Run rolling 30D windows with 7-14D structure warmup.
- [x] Add first online parity check for causal structure features.
- [ ] Expand parity checks across all target assets/timeframes before trusting any result.
- [ ] OOS test on 2024-2025 data (unseen)
- [ ] Prop firm simulation (daily DD, max loss limits)
- [ ] Test account sizes/rules separately: 25k 2-step GOAT, 100k 1-step

### Phase 6: Deploy
- [ ] Document validated configs
- [ ] TradeLocker demo paper execution with ML filter
- [ ] GFT live account after demo stability
- [ ] LLM-assisted post-trade review pipeline

## Non-Goals (Removed from Scope)

- VWAP/EMA bias (replaced with pure structure)
- ATR-only stops (ATR buffer is allowed around structural stops)
- Session filters as blind optimization (sessions are context, not edge by themselves)
- Telegram scraper (visual content not reliably extractable)
- Fixed R:R-only exits (adaptive hybrid exit remains in scope)

## Latest Structure Findings

Test date: 2026-06-26. Data window: latest 120D unless stated.

Direction accuracy says structure is a filter candidate, not a complete strategy:

| Slice | Sample | Direction Read |
|-------|-------:|----------------|
| XAUUSD HTF-bull long NY/London | 36 each | Strong anti-edge in forward 24 bars |
| XAUUSD bear/short Asia/NY | 2,628+ HTF-bear NY, 5,627 entry-bear Asia | Positive but not enough alone |
| GBPAUD entry+HTF bear short NY | 2,140 | Best high-sample FX pocket |
| NAS100 HTF-bear short | 5,477+ | Anti-edge; do not short NAS just because structure says bear |

Target-before-stop study:

| Slice | n | Best Read |
|-------|--:|-----------|
| EURUSD HTF-bull long London | 36 | Strong 1.5R/2R math, but V1 sweep/MSS produced 0 trades in latest 30D |
| GBPAUD entry+HTF bear short NY | 2,140 | Positive but modest: `exp_1.5R +0.11R`, `exp_2R +0.14R` |
| XAUUSD BOS-down short NY | 88 | Positive: `exp_1R +0.22R`, `exp_2R +0.28R` |
| XAUUSD entry+HTF bear short | 2,201 NY / 4,698 Asia | 1R weak, 1.5R/2R slightly positive |

V1 strategy results:

| Config | Window | Trades | Return | Max DD | Verdict |
|--------|--------|-------:|-------:|-------:|---------|
| GBPAUD short NY, HTF, 2R, no structure-cut | 2026-05-24..2026-06-23 | 7 | +0.92% | 0.63% | Clean but too few trades and too low return |
| GBPAUD short NY, HTF, 2R, no structure-cut | 2026-02-24..2026-06-23 | 28 | -1.45% | 3.27% | Reject: 30D slice was noise |
| XAUUSD short Asia, 2R, no structure-cut | 2026-02-24..2026-06-23 | 61 | +4.21% | 3.57% | Research-only: return decent, DD too high, misses target |

Conclusion: if direction is right, target selection matters. But V1 proves the stronger point: direction is only right in specific pockets, and the current sweep/MSS entry does not harvest enough of those pockets to pass GFT rules.

Strict ICT audit:

| Test | Result |
|------|--------|
| XAUUSD 5m latest 30D strict ICT | 1,298 swings, 43 bullish BOS, 42 bearish BOS, 42 bullish CHoCH, 42 bearish CHoCH |
| SMC reference on same sample | 1,536 swings, 378 BOS, 203 CHoCH |
| Verdict | SMC is useful for cross-checking definitions, but too noisy/permissive as the production direction engine without causal filtering |

Strict ICT 120D triple-barrier direction result:

| Slice | n | Hit 1R | Exp 1R | Exp 2R | Verdict |
|-------|--:|-------:|-------:|-------:|---------|
| XAUUSD bearish BOS NY | 24 | 58.3% | +0.38R | +0.52R | Best pocket, needs more sample |
| EURUSD bearish BOS Asia | 59 | 55.9% | +0.30R | +0.25R | Useful candidate |
| NAS100 bullish BOS Asia | 49 | 46.9% | +0.19R | +0.24R | Long-only candidate; avoids bearish anti-edge |
| GBPAUD bearish state NY | 58 | 46.6% | +0.14R | +0.14R | Modest, not enough alone |

## Param Sweep Speed — Status & Path to Target (2026-06-28)

### Benchmark Results (GBPAUD 30d, 30,578 bars)

| Config | Time | ms/combo | vs Target |
|--------|:----:|:--------:|:---------:|
| Single run (cold) | 1.55s | — | baseline |
| Single run (hot/cached) | 0.29s | — | reference |
| Sweep 16 combos (1 worker, warm) | 7.3s | 457ms | — |
| Sweep 16 combos (8 workers) | 11.9s | 744ms | workers pay Numba overhead |
| Full grid 540 combos (sequential) | ~247s | 457ms | 50x off target |
| **VBT broadcast (108 cols)** | **0.20s** | **1.88ms** | ✓ under 5s target |

### Breakdown of 457ms per combo (hybrid VbtRunner)

| Component | Time | % |
|-----------|:----:|:-:|
| Strategy `init()` | 74ms | 16% |
| Strategy `next()` loop (30k calls) | 123ms | 27% |
| VBT `from_signals` + conversion | ~100ms | 22% |
| VBT `pf.stats()` | 94ms | 21% |
| Pandas conversions | 66ms | 14% |

### The Target: < 5s for 486 combos → VBT Multi-Column Broadcasting

The VBT broadcast approach (running all param combos as columns in one `from_signals` call) hits **1.88ms/combo** — fast enough for the full grid in < 1s.

**Path to VBT broadcast:**
1. Convert structure detection to `vbt.IndicatorFactory` Numba kernels (already done in `vbt_indicators.py`)
2. Generate boolean signal masks per param combo: `(n_bars × n_combos)` arrays for entries, SL, TP
3. Single `vbt.Portfolio.from_signals(close, entries, sl_stop, tp_stop)` with broadcast arrays
4. `pf.stats()` for all columns at once (~0.2s)

**Deferred**: this requires rewriting `TrIctSweep.next()` to produce masks instead of per-bar Signals. The pure-vectorized version (`vbt_tr_ict_sweep.py`) is the reference for this conversion.

### Practical Optimization Applied
- `sweep.py` now pre-warms Numba in each worker (reduces cold-start from 1.5s to 0.25s per worker)
- `_report_from_pf()` computes metrics directly from `pf.trades` instead of calling `pf.stats()` (saves 0.1s/combo)
- Grid reduced: `min_fvg_pts` removed from sweep (auto-scales from `pip_size`)

## Forensic Analysis — Feature Engineering Results (2026-06-28)

### Methodology
Extracted 30 bars before/after the 100 best and 100 worst structure events (BOS, ChoCH, state transitions) on GBPAUD 5m 120d. Ran 81 per-bar features (PA, candle patterns, window-context) and t-tested for separation.

### Best vs Worst Discriminators (p < 0.001, sorted by effect size)

| Feature | Best Mean | Worst Mean | Delta | p-value | Interpretation |
|---------|:--------:|:---------:|:-----:|:-------:|----------------|
| `displacement_20` | +0.27R | -0.12R | +0.39 | <0.001 | Price moving in trade direction 20 bars before entry = best predictor |
| `st_bullish_pct` | 58% | 26% | +32pp | <0.001 | Pre-window structure alignment dominates |
| `bos_imbalance_20` | +0.14 | -0.09 | +0.23 | <0.001 | Net bullish BOS density in window |
| `pa_bullish_10` | 55% | 47% | +8pp | <0.001 | More green bars last 10 before best |
| `pa_pin_10` | 34% | 27% | +7pp | <0.001 | More pin bars = reversal ready |
| `outside_bar_10` | 6.5% | 10.6% | -4pp | <0.001 | LESS outside bars before best (smoother) |
| Hammer rate | 1.0% | 2.2% | -1.2pp | 0.001 | Hammers appear more in failures |
| Morning Star | 0.7% | 0.3% | +0.4pp | 0.009 | Confirms bullish reversal setups |
| Evening Star | 0.0% | 0.4% | -0.4pp | <0.001 | Bearish patterns before worst |

### Key Insight
The best predictor is **structural alignment over the pre-entry window** — not the signal bar itself. A trade thesis is much stronger when the last 20 bars show consistent structure movement in the trade direction, with bullish BOS dominance and bullish bar majority. Single-bar candle patterns (hammer, shooting star) are weak predictors alone but add signal as rates over windows.

### Feature Count Change

| Group | Before | After | Added |
|-------|:------:|:-----:|:-----:|
| Price action | 0 | 12 | body%, wicks, pin, inside/outside, range expansion/contraction, coil |
| Candle patterns | 0 | 22 | TA-Lib: engulfing, hammer, doji, harami, morning/evening star, marubozu, spinning top, etc. |
| Window-context | 0 | 21 | rolling BOS rates, displacement, bull bar ratio, pin rate, con rate for 5/10/20 windows |
| Structure | 9 | 9 | unchanged |
| FVG/Sweep | 6 | 6 | unchanged |
| Time/Session | 6 | 6 | unchanged |
| Volatility | 4 | 4 | unchanged |
| Prices | 4 | 4 | unchanged (open/high/low/close/ts) |
| **Total** | **28** | **84** | **+56** |

### ML Performance Comparison (2-class directional, 5-fold CV)

| Feature Set | Accuracy | Delta |
|-------------|:--------:|:-----:|
| Old (27 feats) | 92.83% ± 2.12% | baseline |
| All (81 feats) | 93.85% ± 1.80% | +1.0pp, lower variance |

Candle patterns individually add little (single-bar indicators), but window-context features (displacement, bull_bar_ratio, con_rate) are top-ranked. The 2-class directional separation is strong (94%) because LONG vs SHORT outcomes map to clear pre-window structure differences.

### Action Items
1. Keep window-context features (displacement, bull/bear BOS rates, bull bar ratio) — they dominate
2. Keep PA per-bar features (body%, pin bar) — moderate signal
3. Candle patterns are low-signal per-bar but included as cheap no-lookahead features
4. Use 2-class LONG/SHORT model (not 3-class) for ML filter — directional accuracy > 94%

## Code Locations

| Component | Path |
|-----------|------|
| Structure lib (Numba) | `backtesting/structure_lib/vbt_indicators.py` |
| Engine (hybrid) | `backtesting/engine/vbt_runner.py` |
| Param sweep | `backtesting/engine/sweep.py` |
| ML: labels | `backtesting/ml/labels.py` |
| ML: features | `backtesting/ml/features.py` |
| ML: train | `backtesting/ml/train.py` |
| ML: inference | `backtesting/ml/predict.py` |
| Strategy: TrIctSweep | `backtesting/strategies/tr_ict_sweep.py` |
| Strategy: SMC v1 | `backtesting/strategies/smc_v1.py` |
| Strategy: VBT (WIP) | `backtesting/strategies/vbt_tr_ict_sweep.py` |
| ICT state machine | `backtesting/features/ict_structure.py` |
| Direction accuracy | `backtesting/scripts/ict_direction_accuracy.py` |

## Obsidian References

- [[Strategy/Prop-Firm-Engine]] — Development plan
- [[Strategy/V2-ICT-SMC-Overview]] — Previous strategy architecture
- [[Strategy/Sweep-Results-Jun2026]] — First sweep results
- [[Strategy/Rolling-Analysis-Jun2026]] — Rolling window validation
- [[Goals]] — Trading goals and milestones
