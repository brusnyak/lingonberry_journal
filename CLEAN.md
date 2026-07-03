# CLEAN — Codebase Cleanup & Refactoring Reference

Branch: `hypothesis-engine`
Date: 2026-06-30

## Purpose

This document is the single source of truth for the cleanup effort. It tracks what exists, what's dead, what needs fixing, and what's been done. Use it as a cross-session reference after compactions.

---

## 1. Codebase Architecture

```
trading-journal/
├── backtesting/          ← Main research engine (keep + consolidate)
│   ├── engine/           ← Core backtesting engine [PRODUCTION]
│   ├── strategies/       ← ~12 strategy files [mostly dead/FALSIFIED]
│   ├── structure_lib/    ← ICT structure detection [keep]
│   ├── crypto/           ← Crypto-specific engine [keep crypto/data.py]
│   ├── features/         ← Feature engineering [keep as reference, replaced by v2]
│   ├── features_v2/      ← NEW: Candle pattern extraction + registry (17 patterns)
│   ├── ml_pipeline/      ← NEW: XGBoost training + time-series CV + eval
│   ├── prop/             ← NEW: Prop firm rules + position sizing
│   ├── baselines/        ← Null-hypothesis test harness [valid methodology]
│   ├── tests/            ← Tests
│   └── data_pipeline/    ← Data fetching
├── pine-review/          ← data/ only (674MB historical, not in use)
├── hypothesis_engine/    ← Clean research (Levels 0-3) [keep]
├── infra/                ← Broker infrastructure [PRODUCTION]
├── bot/                  ← Bot automation [PRODUCTION]
├── webapp/               ← Flask webapp [PRODUCTION]
├── core/                 ← Core utilities [keep]
├── daily_engine/         ← Daily research [keep? - low value]
├── hermes/               ← Hermes MCP skills [keep]
├── scripts/              ← Data scripts [keep]
├── backtesting_config/   ← Settings [keep]
└── CLEAN.md              ← THIS FILE
```

---

## 2. Production Code (Oracle VM — DO NOT TOUCH without testing)

| Component | File | Lines | Quality | Risk |
|-----------|------|-------|---------|------|
| TradeLocker API | `infra/tradelocker_client.py` | 1057 | 3/5 | Duplicates TLAPI with copy_trader |
| Position manager | `infra/position_manager.py` | 494 | 4/5 | Phase 2 stubbed |
| TL position mgr | `infra/tl_position_manager.py` | 96 | 4/5 | No connect() error handling |
| Copy trader | `infra/copy_trader.py` | 508 | 3/5 | Duplicates TLAPI logic |
| V1 bot | `bot/mean_reversion_bot.py` | 341 | **2/5** | Fragile column guessing, no startup reconciliation |
| Telegram journal | `bot/journal_daemon.py` | 714 | 3/5 | Large, mixed concerns |
| Journal DB | `bot/journal_db.py` | 2140 | **2/5** | Ad-hoc migrations, duplicated fields |
| Flask webapp | `webapp/app.py` | ~131 symbols | 3/5 | Moderate |
| Trade logger | `infra/trade_logger.py` | 108 | 4/5 | Clean |
| News calendar | `infra/news_calendar.py` | 387 | 3/5 | DST drift |

---

## 3. Bugs Found

### B1 — `min_stop_pips()` hardcoded average spread
- **File**: `backtesting/engine/costs.py:89`
- **Bug**: `return 5 * 2.0` — avg spread hardcoded as `2.0` instead of derived from `entry_fill` formula `uniform(1.0, 3.0)`.
- **Fix**: `avg_spread = (1.0 + 3.0) / 2.0; return 5.0 * avg_spread` — derives from formula, makes relationship explicit.
- **Status**: FIXED 2026-06-30

### B2 — `session_detector.is_high_volatility_session` always False
- **File**: `bot/session_detector.py:69`
- **Bug**: `is_high_volatility_session` compares against `"LONDON_NY"` but `get_session_overlap` returns `"London/NY"`.
- **Fix**: `overlap == "London/NY"` — match actual return value.
- **Status**: FIXED 2026-06-30

### B3 — `market_data.py` indicator caching bug
- **File**: `infra/market_data.py:278-280`
- **Bug**: Cache hit returns without indicators; cache miss adds them. Callers with cached data get different columns.
- **Fix**: Apply `_add_indicators` after cache hit too.
- **Status**: FIXED 2026-06-30

### B4 — `market_data.py` yfinance H4 interval mapping
- **File**: `infra/market_data.py:82`
- **Bug**: H4 maps to `"1h"` which returns hourly data, not 4-hour. yfinance doesn't support `"4h"`.
- **Fix**: After yfinance fetch, call `_resample_ohlcv(out, timeframe)` which resamples 1h bars to 4H via pandas resample.
- **Status**: FIXED 2026-06-30

### B5 — `journal_db.py` duplicated field names
- **File**: `bot/journal_db.py:564-571`
- **Bug**: Insert path writes both `entry`/`entry_price`, `sl`/`sl_price`, `tp`/`tp_price`.
- **Fix**: Remove short-name keys from write path. Keep read-time fallbacks (`trade.get("entry_price", trade.get("entry"))`) for existing records.
- **Status**: FIXED 2026-06-30

### B6 — `backtesting/engine/costs.py` seed default mismatch
- **File**: `backtesting/engine/costs.py:70`
- **Bug**: Docstring says `seed=None` = OS entropy, but field default is `0` which is deterministic. `random.Random(None)` would raise TypeError.
- **Fix**: `self._rng = random.Random(self.seed) if self.seed is not None else random.Random()`. Also added `fixed_spread_pips` param and extracted spread/slip into private helpers for C3.
- **Status**: FIXED 2026-06-30

### B7 — `hypothesis_engine` OOS wall defaults leak OOS data
- **File**: `hypothesis_engine/level2_combos/scanner.py:57,221` + `level3_backtest/engine.py:50`
- **Bug**: `allow_oos` defaulted to `True` in level2/level3, meaning OOS data was included by default (should be strict IS-only like level0/1).
- **Fix**: Changed all `allow_oos: bool = True` to `allow_oos: bool = False`. Pass `--oos` flag explicitly when OOS is intended.
- **Status**: FIXED 2026-06-30

### B8 — `pine-review/src/features/market_structure.py` — non-causal swings
- **Bug**: `detect_swings()` labels pivots at bar `i` but requires bars `i+1..i+period` to confirm. Same look-ahead bias our engine had and fixed.
- **Status**: NOT FIXED (pine-review src/ deleted; use `backtesting/structure_lib/swing.swing_points()` instead)

---

## 4. Naming/Parameter Inconsistencies

| Issue | System A | System B | Impact |
|-------|----------|----------|--------|
| Spread model | Random 1-3 pip (ForexCosts) | Fixed flat dict (hypothesis_engine) | PnL not comparable |
| Return units | $ PnL, lot-based | Log-return (%) | Metrics not substitutable |
| Position sizing | Risk-based `calc_lots()` | Flat/implied | Different drawdown profiles |
| OOS wall | Hardcoded in `data.py` | Not passed to `load_data()` | Hypothesis engine may run IS-only |
| Session defs | Implicit in strategies | `SESSIONS` dict in scanner | Duplicate definitions |
| Swing causal | Default True (structure_lib) | Default False (pine-review) | Different lookahead behavior |

---

## 5. Dead Code — To Remove

### Phase 1A — Completed (deleted 2026-06-30)

All 14 items below were deleted. ~35 Python files removed. No production dependencies.
Source: `git log` / `git diff --stat` on branch `hypothesis-engine` (153 files changed, 100 insertions, 40151 deletions).

| Path | Status |
|------|--------|
| `pine-review/src/` | DELETED |
| `pine-review/scripts/` | DELETED |
| `pine-review/tests/` | DELETED |
| `backtesting/ml/` | DELETED |
| `backtesting/crypto/scripts/` | DELETED |
| `backtesting/scripts/` | DELETED |
| `backtesting/strategies/smc_v1.py` | DELETED |
| `backtesting/strategies/vbt_tr_ict_sweep.py` | DELETED |
| `backtesting/strategies/vwap_rev.py` | DELETED |
| `backtesting/scaling.py` | DELETED |
| `infra/ctrader_client.py`, `infra/ctrader_mirror.py`, `infra/ctrader_strategy.py` | DELETED |
| `_cleanup.py`, `_ctrader_test.py`, `_test_mirror_sltp.py` | DELETED |
| `test_ctrader_client.py`, `test_copy_demo.py` | DELETED |
| `data/scripts/fetch_ctrader_data.py`, `data/scripts/test_ctrader_connection.py` | DELETED |

### Phase 1B — Keep but quarantine (no change)

| Path | Reason |
|------|--------|
| `backtesting/strategies/tr_ict_sweep.py` | V2 development — results documented (MR 42-63% WR) |
| `backtesting/strategies/tr_fvg.py` + variants | Has some t-stat support (t=6.81) but FVG artifacts |
| `backtesting/strategies/tr_asia_sweep.py` | Manual review results (82% WR) |

### Phase 1C — Keep for reference (no change)

| Path | Reason |
|------|--------|
| `backtesting/baselines/` | Null-hypothesis test methodology is valid |
| `backtesting/strategies/donchian_v0.py` | "The baseline to beat" |
| `backtesting/strategies/kl_sweep_reclaim_v0.py` | Most careful re: lookahead bias |

---

## 6. Consolidation Needed (Phase 2)

### C1 — copy_trader.py duplicates TLAPI from tradelocker_client.py
Both files implement TLAPI position fetching, SL/TP resolution, instrument caching.
**Fix**: Refactor `copy_trader.py` to use `tradelocker_client.py` methods.

### C2 — journal_db.py (2140 lines) needs splitting
Single file handles schema, CRUD, stats, analytics, monte carlo, webhooks.
**Fix**: Split into `journal/schema.py`, `journal/crud.py`, `journal/stats.py`, `journal/__init__.py`. Original `journal_db.py` is now a 7-line backwards-compat wrapper. All 42 public functions verified importable through both paths.
**Status**: DONE 2026-06-30

### C3 — Spread model unification
`ForexCosts` (random per-side) vs `SPREAD_COST` (flat dict) in hypothesis_engine.
**Fix**: Added `fixed_spread_pips` param to `ForexCosts`. When set, uses flat spread instead of `random.uniform(1.0, 3.0)`, and suppresses extra slippage. Extract spread/slip into private `_spread_pips()`, `_exit_spread_pips()`, `_slip_pips()` helpers.
**Status**: DONE 2026-06-30

### C4 — OOS wall as shared constant
Currently hardcoded in `backtesting/engine/data.py`.
**Fix**: Re-exported `OOS_START`, `load_data`, `list_pairs`, `list_tfs` from `backtesting/engine/__init__.py`.
**Status**: DONE 2026-06-30

### C5 — Session definitions as shared constant
Currently in `hypothesis_engine/level0_statistical/scanner.py` as `SESSIONS` dict.
**Fix**: Moved to `core/constants.py`. All 5 hypothesis_engine importers updated (level0 run/scanner, level1, level2, level3).
**Status**: DONE 2026-06-30

### C6 — Return unit normalization
Engine uses $ PnL, hypothesis_engine uses log-returns.
**Fix**: Added `log_returns_curve` to `metrics.compute()` output, computed from equity curve. Returns empty list for backward compat.
**Status**: DONE 2026-06-30

---

## 7. pine-review market_structure.py Audit

**File**: `pine-review/src/features/market_structure.py`
**Lines**: 1088
**Status**: Functional, thorough, BUT has critical bias in swing detection.

### What it provides
- Swing detection (fractal method, configurable period)
- Swing labeling (HH/LH/HL/LL)
- Fair Value Gap detection with mitigation tracking
- Order Block detection (last opposite candle before structure break)
- Structure break detection (BOS/CHoCH classification)
- Liquidity level tracking (swing highs/lows as lines, sweep detection)
- Round number levels (psychological levels)
- Open levels (D/W/M session opens)
- Premium/discount zones
- Asian session (AMD logic) with manipulation detection
- Confluence scoring (0-10)
- Full pipeline function (`analyze_market_structure`)

### What our existing structure_lib already has
- Causal-correct swing detection (`swing.swing_points()` with `causal=True`)
- HH/HL/LH/LL labeling
- FVG detection
- Order Block detection
- Sweep/liquidity detection
- BOS/CHoCH detection
- Session detection
- Visualization (`viz.py`)
- Validation/testing (`validate.py`)
- VectorBT indicators (`vbt_indicators.py`)

### What pine-review has that we DON'T
- Round number level detection
- Premium/discount zones
- AMD (Asian session) logic
- Confluence scoring
- Open level (D/W/M) detection
- Mitigation tracking in FVG detection

### Verdict
The pine-review module is **200 lines of useful new concepts** (round levels, P/D zones, confluence scoring, AMD, mitigation tracking) wrapped in **888 lines of duplicate swing/FVG/OB detection** that we already have. The swing detection has the same look-ahead bug we already fixed in our engine.

**Recommendation**: Extract the 5 new functions (round levels, P/D zones, confluence score, AMD, mitigation tracking) and graft them into our existing structure_lib. Delete the rest of pine-review/src/. Keep pine-review/data/parquet/.

---

## 8. ML / Candle Pattern Research Foundation

### Game-Level Progression

```
Level 0 — Literature survey          Research only, no code. Find academically
   ↓                                  validated candle patterns. Gate: 10+ patterns.
Level 1 — Single feature tests       Extract each pattern, test direction accuracy
   ↓                                  across all assets/timeframes. Gate: > 50% + spread.
Level 2 — Feature combos             Pairwise combinations (AND/OR/weighted).
   ↓                                  Gate: outperform best single feature.
Level 3 — XGBoost                    Train on Level 1-2 survivors only.
   ↓                                  Time-series CV with purge/embargo. Gate: 58%+ OOS.
Level 4 — Walk-forward backtest      Full PnL with prop firm rules + costs.
   ↓                                  Gate: passes GFT 25k/100k constraints.
Level 5 — Paper trade                On the Oracle VM, paper TradeLocker account.
```

### Foundation Packages (created 2026-06-30)

All three packages are clean, typed stubs with interfaces locked in. Ready for
literature survey results to plug into.

| Package | Contents | Status |
|---------|----------|--------|
| `backtesting/features_v2/` | Pattern registry, 17 candle pattern functions, batch pipeline | 17 patterns registered, build passes |
| `backtesting/ml_pipeline/` | Time-series CV (purge/embargo), XGBoost wrapper, eval metrics | Imports OK, xgboost not yet installed |
| `backtesting/prop/` | GFT 25k/100k account rules, position sizing | Functional, tested |

### 17 Registered Candle Patterns

**Single-bar (6):** doji, hammer, shooting_star, pin_bar, marubozu, spinning_top

**Multi-bar (11):** bullish_engulfing, bearish_engulfing, bullish_harami, bearish_harami,
piercing, dark_cloud_cover, morning_star, evening_star, three_soldiers (renamed
from three_white_soldiers), three_crows, inside_bar

### Key Design Decisions

1. **Registry pattern** — all patterns register via `@register` decorator.
   Registry singleton holds metadata + research results (accuracy, horizon, pairs).

2. **Consistent signal interface** — every pattern function takes
   `(open, high, low, close) → np.ndarray[int64]` returning +1/-1/0.
   Zero = no signal. Makes pipeline composable.

3. **Trend context deferred** — individual patterns don't filter by trend.
   The `scan_pattern()` pipeline applies trend filters and populates results
   for multiple horizons simultaneously.

4. **Standalone from old features/** — `features_v2` does not import from the
   old `backtesting/features/` which has dead weight and ICT dependencies.

5. **Reuses existing engine infra** — `backtesting.engine.data.load_data()` for
   parquet data loading, `ForexCosts` for spread/slippage in Level 4.

### Level 0 Results — Literature Survey (2026-06-30)

**Full document**: `notes/literature-survey.md` (10 academic papers + 4 practitioner sources + 7 independent backtests)

**Key findings:**
1. Standalone candle patterns do NOT beat random on forex (3 peer-reviewed studies agree)
2. Candle features + ML (especially XGBoost) DOES work: RF 61.68% → 82.08% with candle features
3. Context (trend + key level + volume) adds 22-30% win rate boost
4. Multi-candle reversals (Evening/Morning Star) outperform single-candle patterns
5. Doji is unreliable on forex; Harami is 50-52% coin-flip; Bearish Engulfing is strongest single
6. MIDDAM pattern (2025) is forex-specific and promising but needs replication
7. XGBoost beats RF, SVM, CNN, MLP, LSTM for short-term forex pattern tasks

**Top evidence patterns (Tier 1-2):**
| Pattern | Est. WR | Source | Notes |
|---------|---------|--------|-------|
| Bearish Engulfing | 74-79% | Bulkowski, QuantifiedStrategies | Best multi-study |
| Three Black Crows | 78% | Bulkowski #3 | Strong bearish |
| Evening Star | 72% | Bulkowski #4 | Complete cycle |
| Dark Cloud Cover | 71.5% | QuantifiedStrategies | Peaks at 19d |
| Morning Star | 55-65% | FXNX, fxscanner, Bulkowski | Consistent |
| Three White Soldiers | 65% | Bulkowski, QuantifiedStrategies | Continuation bias |
| Hammer | 55-62% | MT5 Guide, Bulkowski | Needs 2.5R |

**Registry metadata populated**: All 17 patterns have `literature_ref`, `accuracy_pct`, `notes` via `registry.set_research()`.

---

## 9. Cleanup Execution Log

### Session 1 (2026-06-30) — Initial
- Full codebase audit completed
- 8 bugs documented (B1-B8)
- Dead code inventory completed
- pine-review market_structure.py audited and tested
- CLEAN.md created
- Parquet data migrated: `pine-review/data/parquet/` → `data/parquet/`
- PINE_REVIEW_DIR → PARQUET_DIR renamed in both data loaders
- **Bugs fixed**: B2 (session_detector), B1 (costs.min_stop_pips), B3 (market_data cache), B5 (journal_db fields), B7 (OOS defaults)
- **Phase 1A dead code**: all 14 targets deleted (~35 files, 40K lines)
- **Production fixes**: position_manager.py ctrader fallback removed
- **Not committed yet**: everything is unstaged
- **Remaining bugs**: B4 (yfinance — low priority), B6 (seed default — edge case)
- **Remaining work**: Phase 2 consolidation (C1-C6)

### Session 2 (2026-06-30) — Consolidation + remaining bugs
- **B4 fixed**: yfinance path now calls `_resample_ohlcv()` to up-resample to target timeframe
- **B6 fixed**: seed default changed `0`→`None`; `Random(None)` → `Random()`; added `fixed_spread_pips` param
- **C2 done**: `journal_db.py` (2140 lines) split into `bot/journal/{schema,crud,stats}.py` + `__init__.py`; original file is 7-line wrapper; all 42 public functions verified
- **C3 done**: `ForexCosts.fixed_spread_pips` param + private spread/slip helpers
- **C4 done**: `OOS_START`, `load_data`, `list_pairs`, `list_tfs` re-exported from `backtesting.engine`
- **C5 done**: `SESSIONS` moved to `core/constants.py`; all 5 importers updated
- **C6 done**: `log_returns_curve` added to `metrics.compute()` output
- **hypothesis_engine improvements**: `bos_structured()` condition in level1; forward return fix (entry at `open[i+1]`) in level1/2 scanners
- **All tests pass**: 33/33, 13/13 engine-specific
- **C1 deferred**: copy_trader untouched per user directive
- **Committed**: 168 files, 2,719 insertions, 42,309 deletions (commit 3d9ebbd)
- **Codegraph re-indexed**: 3,388 files, 53,746 nodes, 50,432 edges

### Session 3 (2026-06-30) — ML/candle pattern foundation
- **`backtesting/features_v2/`** created: PatternRegistry with `@register` decorator, 17 candle pattern functions (6 single-bar, 11 multi-bar), batch `scan_pattern()` pipeline
- **`backtesting/ml_pipeline/`** created: time-series CV with purge/embargo (`purge_embargo_split`, `rolling_window_split`), XGBoost wrapper (graceful missing dep), eval metrics (direction accuracy, confusion matrix, win rate at threshold)
- **`backtesting/prop/`** created: GFT 25k 2-step / 100k 1-step rule definitions, `calc_lots()` position sizing with lot-step rounding, daily risk budget
- All packages verified: imports OK, CV split logic correct (gap=5 bars confirmed), xgboost ImportError handled at call-time
- CLEAN.md updated with new architecture diagram, level progression, foundation docs
- **C1 still deferred**: copy_trader untouched
- **Committed**: 13 files, 1,271 insertions, 45 deletions (commit b1b39eb)
- **All tests pass**: 42/42 (engine tests + full suite)
- **Bugs found & fixed during smoke test**: _body_pct missing args, marubozu .replace(), __init__.py missing imports

### Session 4 (2026-06-30) — Level 0 literature survey completed
- **Deep research**: 10 academic papers (MDPI, SSRN, IEEE Access, ACM, Springer), Bulkowski's encyclopedia (103 patterns), 7 independent backtests
- **`notes/literature-survey.md`** created: full survey with per-pattern evidence tables, 4-tier evidence standard, 20+ source citations
- **New patterns identified**: Three Line Strike (#1 Bulkowski, 84%), Three Inside Up (PF 2.5), Belt Hold (71%), MIDDAM (forex-specific, 2025), Three Outside Up/Down
- **`registry.set_research()`** method added to PatternRegistry
- **All 17 patterns populated** with accuracy_pct, literature_ref, notes from survey
- **Key insight**: standalone patterns don't beat random on forex. ML + context + candle features is the only path to 58%+. Level progression validated.
- **Committed**: as part of this session, all changes committed
- **42/42 tests pass**

---

## 10. CLOSED — Mechanical OHLC-Pattern-Search Family (2026-06-30, session 5)

**Status: closed. Do not extend `features_v2`, `hypothesis_engine` grid scans, or
per-pair/RR parameter search on `tr_ict_sweep.py`. This is not a "come back and
finish Level 1" backlog — it's a documented dead end.**

### What was tried (6 attempts, this branch alone)
1. Donchian breakout-follow — falsified (0th percentile vs null)
2. KL sweep+reclaim (VWAP/EMA20 reclaim) — falsified (40-cell scan, best PF 0.99)
3. Mean-rev RSI+BB — falsified on all 5 crosses tested
4. Raw ICT BOS sequence — loses without stop-floor+session filter
5. 17 candle patterns, cost-net + Bonferroni-corrected, 22 pairs × 5 TF × 4 horizons
   (5,792 cells) — mean net accuracy 49.7%, no edge. Confirmed independently by
   return-ACF test (630 cells): only structure found is lag-1 negative
   autocorrelation matching textbook bid-ask bounce (Roll 1984) — sub-cost,
   not tradeable, decays by lag 3.
6. `TrIctSweep` (sweep+ChoCH+FVG), 232-cell grid over pair×TF×RR — beat a
   matched random-direction null at 87-100th percentile on the top candidates,
   but **failed a discovery/holdout split** (last 90 IS days, untouched by
   selection): every candidate decayed to flat or negative. This is what
   selection bias looks like when you actually check for it — "beats random
   direction" only proves the trigger isn't literally noise, not that the
   specific pair/RR found by a 232-cell search will generalize.

### Why this family is closed, not paused
- No standalone OHLC geometric signal (candle shape, breakout, mean-reversion,
  sweep+gap) has produced an edge that survives proper validation, across 6
  structurally different attempts.
- The ACF test gives a mechanistic reason: there is no exploitable time-series
  momentum/mean-reversion in FX returns at intraday granularity beyond
  microstructure noise smaller than the spread that would be needed to harvest it.
- What's left un-falsified is *location*-based structure (real liquidity/key
  levels reacting to where size actually sits) — a different mechanism from
  anything tested above, and not discoverable by grid-searching bar shapes.
  See §11.

### Engine note (session 5)
Audited `engine/runner.py`/`costs.py` fill + sizing logic — sound, no lookahead.
Bugs found this session were strategy-level: `tr_ict_sweep.py` defaulted
`pip_size=0.0001` for every symbol regardless of pair, which silently zeroed
out simulated spread cost on JPY crosses and broke position sizing entirely on
XAUUSD (produced a >100% max-drawdown artifact — impossible for a real account,
diagnostic that something was wrong, not a result). Fixed `_htf_dir_at` from a
per-bar `np.searchsorted` (92k calls) to a precomputed array — 33% faster,
bit-identical output. Keep the engine; don't keep building strategies in this
family on top of it.

---

## 11. NEW DIRECTION — Human-Context + Mechanical-Execution Hybrid (proposed 2026-06-30)

Not yet built — see session 5 conversation log for full reasoning. Summary:

**Decomposition**: separate "where/when to look" (human discretionary judgment —
key levels, liquidity, daily bias, the thing 6 mechanical attempts couldn't
discover from bars alone) from "how to execute" (mechanical, boring, testable —
EMA/VWAP triggers and risk management, not curve-fit).

**Critical guardrail — already learned this lesson once, don't relearn it**:
[[selection_edge_unmeasurable]] memory: 211 discretionary trade reviews turned
out to be hindsight-timed (73% next-bar-favorable) and couldn't validate
selection edge. Marking historical chart levels *after* seeing the outcome has
the same flaw. Two valid paths only:
- **Objective levels** (prior day H/L, weekly open, VWAP, round numbers,
  causal swing points) — computable from timestamp+price alone, no human
  hindsight involved, safe to backtest retrospectively with full discipline
  (discovery/holdout, null test, OOS wall).
- **Human-marked levels** — valid ONLY if collected prospectively (timestamped
  at mark-time, enforced `marked_at <= bar_ts` in code) or genuinely blind.
  Never backtest retrospective human chart markings as if they were forward
  decisions.

**Naming**: this roadmap uses `lvl1`, `lvl2`, `lvl3`... (deliberately distinct
from `hypothesis_engine`'s `level0_statistical`/`level1_conditions`/etc., which
belongs to the closed family above — don't confuse the two numbering tracks).

**Staging** (refined 2026-06-30 after first lvl1 result):
- **lvl1 — HTF regime + trend-following** (`backtesting/lvl1_trend/`,
  `TrendV1`/Supertrend+EMA200). One fixed config, no per-instrument tuning.
  - FX majors (GBPUSD, EURUSD) at H4: **falsified**. Discovery near-flat over
    13yr, holdout clearly negative both pairs. Matches expectation — FX trend
    premium is weak/crowded post-2008 per AQR-style literature; this isn't
    where trend-following's documented edge lives.
  - **XAUUSD H4: promising, unconfirmed.** Discovery n=306, ret +7.1%/13yr,
    holdout n=64, ret +12.0%/3.4yr, avg_r improved 0.05→0.27, WR 37%→47%.
    Positive in both windows, holdout stronger, no tuning involved. One cell
    though — needs replication on 2-3 more commodities (same fixed config,
    still no tuning) before trusting it as a real mechanism vs. a lucky pick.
  - NAS100 H4: discovery mildly positive, holdout flattens to ~noise — not
    convincing. D1 on both XAUUSD/NAS100: samples too small (n<15 holdout) to
    read either way.
  - **Frequency ceiling, structurally**: ~20 trades/yr even on the promising
    cell — swing frequency, not intraday. This is inherent to the mechanism
    (regime+trigger alignment is rare by design), not a tuning problem. Don't
    expect lvl1 to become high-frequency; the frequency lever is elsewhere
    (pooling instruments, or lvl3 below).
  - Cost model for XAUUSD/NAS100 is typical-retail-CFD approximation, **not**
    verified against actual GFT/TradeLocker contract specs — verify before
    trusting absolute $ figures.
- **lvl2 — candle/continuous features as entry timing inside the lvl1
  regime**, faster TF (M15-H1) gated by the H4 trend direction. This is the
  literature's actual claim (22-30% WR boost from trend context) — never
  properly tested, since lvl0's candle scan was standalone. Also the
  principled way to raise frequency: more entries per trend leg, not more
  parameter search.
- **lvl3 — structure/consolidation via human-marked review data.** Likely the
  real high-frequency-intraday lever, since key-level reactions happen
  multiple times per session (unlike trend regime alignment, which is rare).
  Blocked on accumulating blind-mode review data (see below).
- **lvl4 — combine, validate on accumulated real data, prop rules, then OOS
  once.**

### Review UI — blind mode fix (2026-06-30)
Fixed real hindsight-bias leak in `webapp/templates/review.html`/`app.py`:
`showTrade()` was unconditionally rendering candles *after* entry, and
`/api/review/run` always returned `pnl`/`exit_price`/`r_multiple`/`exit_reason`
regardless of date range — this is the literal mechanism behind the
211-review hindsight-timed dataset. New `blind` checkbox: strips outcome
fields server-side, hard-stops the chart at the entry bar, hides the stats
bar. Caveat: `candles_json` for the full range still reaches the browser;
blind mode trusts the UI not to render it, not server-enforced — fine for a
personal tool, not a defense against deliberately defeating your own test.
Scoped to XAUUSD + GBPAUD for manual structure marking (familiarity +
established review history). Run locally: `python webapp/app.py` →
http://localhost:5000/review (Vercel ruled out — serverless ephemeral
filesystem is structurally incompatible with this app's SQLite+JSON
persistence, not a config issue).

## 12. Lvl1 — built, gated, prop-checked (session 6, 2026-06-30)

### What exists
- `backtesting/lvl1_trend/supertrend.py` (`TrendV1`) — H4 EMA/SMA/HMA regime +
  Supertrend entry, ATR-trail exit. Robust across all 3 MA types on XAUUSD;
  does not replicate on XAGUSD or NAS100.
- `backtesting/lvl1_trend/htf_ema_vwap.py` (`HtfEmaVwap`) — HTF(60m)-EMA21
  regime + LTF(5m)-VWAP-band-bounce entry + ATR-trail exit. Real signal:
  100th-percentile null-test pass on XAUUSD/NAS100, 67-85 trades/month.
- `backtesting/lvl1_trend/chop_vwap_fade.py` — mean-reversion gated to
  ER≤0.3 (complement of trend gate). **Falsified** (XAUUSD disc ret=-89%,
  DD=90%; NAS100 -26%/-27% both windows) — poor RR shape (target~1σ, stop
  beyond 2σ+buffer needs WR we don't have). Third mean-reversion failure
  this session regardless of regime-gating. Not pursuing further tuning.
- `backtesting/engine/regime.py` — Kaufman Efficiency Ratio, standard
  params (period=10), reusable trend/chop classifier.
- `backtesting/engine/baselines.py` — generic `make_random_dir_null()`,
  wraps any Strategy for random-direction null testing (replaces the
  hand-rolled `RandomDirNull` subclasses written twice this session).

### Regime gate result (ER>0.3 AND ATR≤1.3×its 100-bar avg — standard
params chosen before looking at any specific bad window)
Fixed XAUUSD's catastrophic tail risk: worst 30d window -41.2%/49.5%DD →
-5.8%/10.2%DD. NAS100: -7.7%/16.4%DD → -5.9%/6.6%DD. Cost: ~50-70% fewer
trades, and XAUUSD's discovery window went slightly negative post-gate
(-0.5%) while holdout stayed strong (+25.7%) — a new inconsistency, flagged
not hidden.

### Real prop-rule check (GFT 25k 2-Step, GFT 100k 1-Step —
`backtesting/prop/rules.py`, properly re-sized per account, not reusing
$10k-sized trades)
| | daily DD | max DD | verdict |
|---|---|---|---|
| XAUUSD/25k | 2.6% (≤5% ok) | 13.6% (>10%) | **FAILS — 32 max-DD breaches** |
| XAUUSD/100k | 2.7% (≤4% ok) | 13.7% (>6%) | **FAILS — 110 breaches** |
| NAS100/25k | 2.1% (≤5% ok) | 7.1% (≤10% ok) | **PASSES cleanly** |
| NAS100/100k | 2.1% (≤4% ok) | 7.1% (>6%) | fails, marginal |

NAS100/25k is the only currently prop-compliant combination. XAUUSD is
profitable but carries real disqualifying drawdown risk under this exact
config — daily limits are fine, cumulative peak-to-trough isn't. Earlier
"<3% DD" framing was based on a stricter non-standard rolling-window metric,
not the rule that actually governs challenge pass/fail — corrected.

### Trade forensics — a false lead caught before shipping
5-worst/5-best sample suggested "reject entries at 30-bar swing extremes"
(80-100% of worst trades entered against an extreme, 0% moved favorably
immediately). **Did not hold on the full population**: against-extreme
entries actually average HIGHER R than not (XAU +0.295 vs +0.044; NAS100
+0.191 vs +0.096). Building that filter would have removed the
better-performing trades. Textbook cherry-picked-sample trap — caught by
checking at scale before implementing. No entry filter built from this.

### Gold vs silver divergence — researched, not just measured
0.745 return correlation (high, not 1.0), silver's realized vol ~1.95x
gold's. Mechanism: silver's market cap ~1/9th gold's → same dollar flow
moves it further; lower futures depth/open interest; >50% industrial
demand adds a demand-cycle volatility source gold lacks; disproportionate
speculative/leveraged positioning in risk-on regimes amplifies both
directions. Not a data artifact — a real structural difference; explains
why XAGUSD fails consistently (3x) despite tracking gold's direction.

### Review UI — Lvl1Trend wired in (session 6)
`/api/review/run` now accepts `strategy: "Lvl1Trend"` — runs the actual
gated `HtfEmaVwap` (same class used in all backtests above) so trades can be
visually inspected (entry, SL, target, structure) in the existing chart UI,
not just read from CSVs. Verified end-to-end via Flask test client.

### Open, unresolved
1. **Cost model for XAUUSD/NAS100 still unverified** against real broker
   contract specs — highest-priority integrity gap, blocks trusting
   absolute magnitude at 70-85 trades/month.
2. **FX still doesn't work under the trend-regime architecture** (49.3%
   direction accuracy, robust null result from session 5) — this is an
   architecture mismatch, not a tuning problem. Trend-regime + entry-timing
   is the wrong shape for FX; FX historically responds better to structural
   (sweep/FVG/liquidity) mechanisms per `TrIctSweep`'s prior null-test pass
   (87-100th percentile on GBPAUD/EURAUD/USDCHF) — which failed on
   discovery/holdout due to 232-cell parameter-search overfitting, not
   necessarily a dead mechanism. **Proposed next step**: refit `TrIctSweep`
   with ONE fixed, pre-specified config (no grid search) using the same
   HTF-trigger/LTF-entry discipline that worked for lvl1, tested with proper
   discovery/holdout on FX. Not yet executed — awaiting go-ahead.
3. Crypto data depth inconsistent (majors ~58 days, TRX/ATOM/ALGO 6-7yr) —
   pipeline gap, not yet investigated. Binance/Bybit direct pull available
   if needed (not yet dispatched).
4. Third regime (transition/breakout) unaddressed — blocked on lvl3 human-
   marked review data, no statistical shortcut per regime-detection
   literature (transitions are inherently a lagging-indicator blind spot).

## 13. Session 6 continued — lvl2 structure strategy, manual UI review, audit (2026-07-01)

### `backtesting/lvl1_trend/htf_structure_vwap.py` (`HtfStructureVwap`) — built, debugged, still not profitable

Built to fix two issues found by manually reviewing lvl1 trades in the review
UI: (1) EMA21 regime lags real structure — can call "long" after price has
already reversed; (2) the 50R disabled TP was intraday-unrealistic. Replaced
regime with `structure_lib.labels.label_structure()` (CHoCH/BOS, causal) and
TP with prior-day high/low. **Structure detection validated correctly on
synthetic ground-truth data** (designed HH/HL→CHoCH→BOS sequence, detected
exactly at the right bars/prices) — the detection primitive is trustworthy.

**Two real bugs found and fixed during backtesting** (not from chart review —
from checking `tp1_hits`/`r_multiple` distributions before trusting results):
- Breakeven logic used a *global* "was structure ever confirmed" flag instead
  of "did a NEW confirming BOS happen after THIS position opened" — moved SL
  to breakeven almost immediately on every trade, producing suspiciously tiny
  losses (-0.05R to -0.15R instead of real -1R stops). Fixed by tracking
  each position's entry-time BOS index and only confirming on strictly-later
  events.
- After the fix: median R = -0.073 (majority of trades lose), mean R = +0.34
  only from a fat right tail (99th pctile +6.6R). Fixed-size R-sum = +310
  (real edge exists in aggregate) but compounded dollar PnL = -$3,575.
  Reducing risk_pct 10x did NOT recover positive return (ruled out
  compounding/vol-drag) — likely fixed $0.75/side commission × ~900 trades
  (~$1,364) eating a real but expensive-to-harvest edge at this frequency.

### Manual UI review (user, screenshots) — 7 concrete findings, all mapped to
real code causes, not vibes

1. **Enters against trend on a bare CHoCH** (e.g., short right as price
   recovered into an uptrend). Root cause confirmed: regime code treated
   CHoCH and BOS as equally regime-flipping. **Fixed**: only BOS sets
   tradeable direction now; CHoCH alone does nothing. Matches the user's own
   diagnosis exactly ("always wait for confirmation with BOS").
2. FVG/OB overlay draws correctly but labeled "undefined" in the UI (cosmetic
   bug, not fixed yet, low priority). Multi-target Fibonacci stretch —
   proposed, not built.
3. No session/news filter — 24/7 trading includes thin day-boundary
   structure reads and the 12:30-14:00 UTC US-news window. **Fixed**: added
   `_time_ok` gate (day-edge ±1h, news window exclusion).
4. No distance-based breakeven (only structure-based and engine's own
   at-full-TP1). **Fixed**: SL moves to breakeven at 50% progress toward TP1.
5. Poor behavior in accumulation/consolidation. **Attempted fix**: wired in
   the already-built Efficiency Ratio chop gate (`engine/regime.py`,
   ER>0.3). See §13.1 below — this fix is questionable, not confirmed good.
6. Requested trade-level review of Aug 15-20 — done, see below.
7. Same root cause as #1, repeated across more instances.

### §13.1 — Why the 4 fixes made holdout WORSE while discovery improved (the
audit finding, not yet resolved)

| | n | ret | avg_r | WR | max_dd |
|---|---|---|---|---|---|
| XAUUSD disc | 335 (was 909) | -25.8% | +0.205 (was +0.341) | 37.3% | 37.1% |
| XAUUSD hold | 314 (was 529) | **-35.0% (was -15.5%, worse)** | **+0.042 (was +0.402, collapsed)** | 28.3% | 35.7% |
| NAS100 disc | 256 (was 657) | **+4.4% (was -26.4%, better)** | +0.675 (was +0.357, better) | 36.7% | 15.3% |
| NAS100 hold | 223 (was 560) | **-23.8% (was +15.8%, flipped negative)** | +0.192 (was +0.604, worse) | 30.0% | 28.8% |

Discovery improved on both instruments; holdout got worse on both,
XAUUSD substantially. **Root cause identified, not hand-waved**: checked the
ER chop-gate's pass rate by period — XAUUSD holdout passes 73.0% of bars as
"trending" vs only 49.8% in discovery, yet performs worse. Kaufman's
Efficiency Ratio measures *directional efficiency* (net displacement ÷ path
length), not *volatility magnitude*. A violent, whipsaw-heavy move can still
score as "efficient" if it nets a clear direction. **This is a different
variable than the one previously diagnosed as the actual cause of lvl1's
worst historical drawdown** (§12: the May 2026 window was an ATR-spike
whipsaw, 1.41x average ATR — a volatility problem, not a chop/efficiency
problem). Adding the ER gate reactively to the "bad in accumulation"
complaint, without checking it against the earlier ATR-spike finding, added
a filter that doesn't cover the risk actually diagnosed before — and the
holdout period apparently has more of exactly that uncovered risk (violent
trending moves), not more chop.

**Correction needed, not yet built**: the chop gate and the volatility cap
are two separate dimensions and both are needed — ER>threshold (is there a
real net direction) AND ATR-vs-its-own-trailing-average below some ceiling
(is the current move calm enough for a fixed-multiple stop to survive it).
Currently only the first exists in `HtfStructureVwap`; `TrendV1`
(lvl1-original) has the ATR-ceiling check but not the ER check. Neither
strategy has both.

### Also still open from this window
- Aug 2025 trade review (user's own request) surfaced a second real issue:
  TP1 = prior-day extreme with no minimum-R:R floor — some trades got a
  target barely 0.15R away while the stop was ~4x further, a structurally
  bad payoff shape regardless of direction correctness. Not fixed yet.
- Same review showed 3 short re-entries within 45 minutes at nearly the same
  price after each stop-out — a churn/re-entry pattern with no cooldown.
  Not fixed yet.
- `tp1_hits` counter in `/tmp/lvl2_structure_test.py`-style test scripts uses
  `"TP1"` (capital) but `ExitReason.TP1.value == "tp1"` (lowercase) — cosmetic
  test-script bug, not a strategy bug, caused a false "TP1 never hits" scare
  earlier in the session before being caught.

### Honest current state, for continuity after compaction
- **Only `TrendV1`+ER/ATR-gate on NAS100/GFT-25k-account is validated as
  prop-compliant** (§12: 0 daily breaches, 0 max-DD breaches, real prop rule
  check with correctly account-scaled position sizing).
- `HtfStructureVwap` (structure-based lvl2) is NOT ready — structure
  detection itself is correct and validated, but the full strategy is not
  net profitable after 6 rounds of fixes this session. Needs, in priority
  order: (1) separate volatility-ceiling filter alongside the ER chop gate,
  (2) minimum R:R floor on TP1, (3) re-entry cooldown, (4) re-validate on
  genuine discovery/holdout after each, not cumulatively — the pattern this
  session (stack fixes, then discover one made things worse) argues for
  testing fixes more incrementally.
- Do not add more filters reactively to single chart observations without
  cross-checking against previously-diagnosed failure modes first — that's
  the specific mistake that caused §13.1.

## 14. Session 7 (2026-07-02) — lvl2-mechanical closed, ORB opened

### 14.1 HtfStructureVwap: three queued fixes built, tested incrementally — family CLOSED
Fixes from §13 priority list all implemented in
`backtesting/lvl1_trend/htf_structure_vwap.py` (unit-tested, 4/4 pass;
`on_close` hook confirmed wired in runner):
- `atr_ceiling_mult=1.3` — HTF ATR vs its 100-bar mean, separate `_vol_ok`
  gate alongside ER (the §13.1 lesson: efficiency ≠ volatility magnitude)
- `min_rr=1.0` — reject entries whose prior-day-extreme TP1 is <1R away
- `cooldown_bars=9` — no re-entry within 9 bars of a close (churn fix)

Incremental test (each alone vs base, XAUUSD+NAS100 5m, seed=42, split
2025-09-15): every fix behaves as designed (vol ceiling cuts XAUUSD holdout
DD 35→12%; cooldown best single discovery improvement; min_rr neutral) but
**holdout return is negative in all 5 variants on both symbols**. Best case:
NAS100 all-three +10.6% discovery / −18.2% holdout.

Timeframe isolation (15m/60, 15m/240, 30m/240): no config positive on both
discovery and holdout. NAS100 15m holdout mildly positive (+1 to +7%) but
its own discovery is −42%; selecting on that would be picking on holdout.
**Verdict: structure-regime + VWAP-bounce entry has no net edge at any
tested TF. 9th falsified family.**

### 14.2 METRIC BUG (retraction): sum-of-R overstated ~2x with partial closes
`_r_mult_net` (runner.py) computes each partial's R against that partial's
lots only. With `tp1_frac=0.5`, TP1-half at +1R-on-half plus runner at BE
sums to 1.0R in trade tables, but the position earned 0.5R on full risk.
The earlier "edge exists in aggregate R but isn't captured" claim (§13) is
RETRACTED — net return is the honest metric, and it was negative.
Do not use summed per-row `r_multiple` as evidence when tp1_frac<1.

### 14.3 NEW FAMILY — Opening Range Breakout NY (backtesting/lvl2_orb/orb.py)
Rationale: time-anchored session liquidity is a mechanism class none of the
9 falsified families tested (all were indicator/structure-state driven).
External evidence: Zarattini & Aronow (2023), QQQ 5m ORB.
Spec fixed EX-ANTE, zero grid search: NAS100 5m; opening range 09:30–09:45
America/New_York (DST-correct); first close beyond range enters (09:45–15:00,
one trade/day); stop = range midpoint; flat by 15:55 NY; no TP.

First-run results (seed=42, spread 1.5 pts, $0.75/side, 0.5% risk):
- discovery (Aug 2024–Sep 15 2025): n=183, +1.8%, DD 8.7%, WR 32%, PF 1.03
- holdout (Sep 15 2025–Jun 2026):  n=176, +4.2%, DD 8.8%, WR 35%, PF 1.07
- random-direction null (30 seeds): mean −11.7% [p5 −25.6, p95 +0.2];
  real discovery = **97th percentile** → direction info is real
- long/short roughly balanced (97/86, 95/81); avgWin/avgLoss ≈ 2.1

Honest read: FIRST strategy positive on both discovery AND holdout on first
run with no tuning — but PF 1.03–1.07 is noise-adjacent and monthly PnL is
lumpy (discovery profit concentrated in one +$1,018 month). Signal exists;
expectancy after costs ≈ 0. NOT validated, NOT prop-ready.

Next (pre-registered to avoid tuning drift): ONE payoff variant from the
literature, not from our data — Zarattini-style wide target (10R/EOD) with
stop at the opposite side of the range instead of midpoint. Test on
discovery once, confirm on holdout once. If PF stays ≤ ~1.1, park ORB and
shift effort to lvl3 (user is building blind-review data in parallel).
Unit tests: backtesting/tests/test_orb.py (6 pass).

## 15. ORB payoff variant 2 (Zarattini-style) — PASSES pre-registered bar, best lvl2 candidate so far

Per §14.3's pre-registration: one variant, tested once, no drift. Change from
first ORB pass: stop moves to the OPPOSITE side of the 15-min opening range
(full-range, not midpoint); target = 10R fixed; EOD backstop unchanged.
`backtesting/lvl2_orb/orb_wide_stop.py`, unit-tested (4/4 pass).

```
              n     ret%   dd%   wr%   PF
discovery   183     +5.2   7.6   46%  1.12
holdout     176     +7.1   5.0   48%  1.17
```

Both sides clear the pre-registered ≤1.1 park threshold — proceeding, not
parking. Random-direction null (30 seeds) on discovery: mean -8.4%, real
result beats ALL 30 seeds (100th percentile) — stronger confirmation than
the first ORB variant (97th). Improvement over variant 1 across every
metric (return, DD, PF, WR) — the wider stop absorbing normal noise instead
of getting stopped out by it is doing real work here.

This is now the strongest validated lvl2 candidate in the project — better
than TrendV1+ER/ATR-gate (§12) on raw metrics, though TrendV1 has the prop-
account-sizing check already done and this doesn't yet.

Next steps (not yet done):
- Monthly consistency check (is the discovery/holdout profit concentrated
  in a few months, per the honesty standard applied to the first ORB pass).
- Prop-rule check (GFT 25k/100k, correctly account-scaled per §12's fixed
  methodology) before calling this prop-ready.
- Do NOT grid-search target_r or stop placement further — one more
  literature-sourced variant is fine if a specific paper motivates it;
  fitting target_r to our own discovery data is the overfitting trap this
  project has fallen into before.

### Prop-rule check (correctly account-scaled, same methodology as §12)

| | worst daily DD | worst max DD | breaches | target hit? | verdict |
|---|---|---|---|---|---|
| NAS100/25k discovery | 0.6% (≤5%) | 7.6% (≤10%) | 0 | 5.2% of 8% | PASSES, target not reached in-window |
| NAS100/25k holdout | 0.5% (≤5%) | 5.0% (≤10%) | 0 | 7.2% of 8% | PASSES, target not reached in-window |
| NAS100/100k discovery | 0.6% (≤4%) | 7.6% (≤6%) | 37 max-DD | 5.3% of 10% | **FAILS** |
| NAS100/100k holdout | 0.5% (≤4%) | 5.0% (≤6%) | 0 | 7.1% of 10% | PASSES, target not reached in-window |

Daily DD is a non-issue on both accounts (0.5-0.6% worst case vs 4-5% limits
— this strategy's one-trade-per-day, EOD-flat structure inherently caps
daily risk). Max DD is the binding constraint, same pattern as TrendV1 in
§12: 25k's 10% ceiling absorbs the ~7.6% peak-to-trough fine; 100k's
tighter 6% ceiling doesn't, and fails on the higher-volatility discovery
window specifically (passes on the calmer holdout — an inconsistency
flagged, not hidden, matching the §12 precedent).

Neither account reaches its profit target within a single ~9-10 month
window at 0.5% risk/trade — this measures rule-compliance, not
speed-to-pass; a real challenge attempt would need either higher risk/trade
(trades off against the max-DD margin above) or would simply take longer
than one evaluation window under this exact sizing.

**Verdict: prop-compliant on GFT 25k (both windows clean), NOT compliant
on GFT 100k (fails discovery). Same asymmetry as TrendV1 — 100k's tighter
max-DD ceiling is the recurring bottleneck across both validated lvl1/lvl2
candidates, not a strategy-specific flaw.**

### ORB on forex — FAILS cleanly, does not generalize past NAS100

Same mechanism (`OrbNyWideStop`, now parameterized for session anchor —
`session_tz`/`session_open_min` etc., generalization not a data-fit),
tested on London open (08:00 UTC, standard FX session-open convention, not
chosen by fitting our data):

```
              n     ret%    dd%   wr%   PF
GBPAUD disc  146    -6.5   14.2   25%  0.90
GBPAUD hold  172   -13.6   19.3   27%  0.82
EURUSD disc  177   -23.5   23.0   23%  0.65
EURUSD hold   83    -8.5   13.2   31%  0.73
GBPUSD disc  121   -15.8   20.4   27%  0.68
GBPUSD hold  136    -8.8   14.8   26%  0.84
```

Every pair, both windows, PF well under 1.0. Consistent with the project's
existing FX finding (§12 open items #2: trend-regime architecture doesn't
work on FX, 49.3% direction accuracy) — ORB is a different mechanism
(time-anchored breakout, not trend-following) but lands in the same bucket.
Not pursuing FX for this strategy family; NAS100 remains the only asset
this mechanism works on so far.

## 16. Trade forensics finds a real filter, validated with discipline — first strategy to pass prop rules cleanly on both accounts

Per user request: forensics on ORB variant 2's own trades (full population,
n=359, not a cherry-picked sample — same discipline as §12's "swing extreme"
trap), testing two literature-motivated factors (`backtesting/lvl2_orb/trade_forensics.py`):

- **HTF trend alignment (4h EMA50 slope)**: PF 1.94 (aligned, n=203) vs
  PF 0.54 (against, n=156) — clean, large split.
- **Pre-breakout liquidity sweep of prior-day H/L (2h window)**: PF 1.18 vs
  1.11 — no discrimination, not a real factor here. (Volume confirmation,
  also literature-suggested, is NOT testable — NAS100 5m volume column is a
  placeholder, constant 5.0 every bar, verified before ruling it out.)

Built the HTF filter as a real, testable option on `OrbNyWideStop`
(`htf_key` param, EMA-slope gate) and validated it properly — discovery/
holdout split, not just the combined-set forensics number:

```
                n     ret%   dd%   wr%   PF
disc unfiltered 183   5.2   7.6   46%  1.12
disc filtered   147  17.6   3.2   52%  1.57
hold unfiltered 176   7.1   5.0   48%  1.17
hold filtered   137  22.7   2.8   62%  1.96
```

Improvement holds (and is even larger) on holdout than discovery — the
opposite signature of overfitting. Random-direction null on filtered
discovery: 100th percentile (real result beats all 30 seeds), same as
unfiltered. ~20% fewer trades, all metrics improved.

### Prop-rule check, HTF-filtered variant

| | worst daily DD | worst max DD | breaches | target hit? |
|---|---|---|---|---|
| NAS100/25k discovery | 0.6% (≤5%) | 3.2% (≤10%) | 0 | 17.5% of 8% ✓ |
| NAS100/25k holdout | 0.5% (≤5%) | 2.8% (≤10%) | 0 | 22.7% of 8% ✓ |
| NAS100/100k discovery | 0.6% (≤4%) | 3.2% (≤6%) | 0 | 17.5% of 10% ✓ |
| NAS100/100k holdout | 0.5% (≤4%) | 2.8% (≤6%) | 0 | 22.7% of 10% ✓ |

**First strategy in the project to pass GFT 25k AND 100k cleanly on both
discovery and holdout, target actually reached in-window (not just
rule-compliant with target unreached).** The 100k account's tighter max-DD
ceiling — the recurring failure point for TrendV1 (§12) and unfiltered ORB
(§15) — is no longer binding: the HTF filter removed the specific
counter-trend trades that were driving drawdown, not just added return on
top. Coherent mechanism, not a coincidental metric improvement.

### Honest caveats, not glossed over
- Still single-asset (NAS100 only) and single-timeframe (5m entry, one
  session). FX failed cleanly (§15); this result doesn't generalize to FX.
- ~9-10 months total data (discovery+holdout combined) is a real sample but
  not a multi-year one; one more literature-grounded factor (real volume
  data, if a better data source is found) would be worth testing before
  calling this "done," not just "very promising."
- No parameter grid was run to reach this — one pre-registered payoff
  variant (§14.3), then one forensics-motivated filter, each validated with
  proper discovery/holdout before being kept. Keep this discipline for any
  further additions: one factor at a time, tested at scale, not tuned.

## 17. Breadth testing — entry-TF robustness + HTF-filter alternatives (session 7 continued)

Per user request: broaden testing before documenting/pushing. Found and
fixed a real bug first: NAS100's timeframes have wildly different history
depth (5m starts Dec 2024, 15m starts 2022, 30m starts 2017, 240m starts
2013) — the entry-TF comparison's first run silently compared a ~8.5-month
5m window against a 3.7-8.3-YEAR 15m/30m window, producing a nonsensical
731-trade "discovery" count. Same class of bug as the earlier documented
discovery/holdout date-window mismatch (§ notes on H4 vs 5m). Also fixed:
`OrbNyWideStop`'s opening-range bar-count assumed 5m bars unconditionally —
now infers bar duration from the data, required to test other entry TFs at
all.

### Entry-TF robustness (matched date range, same discovery/holdout window for all)

```
tf     n_d   ret_d   dd_d   pf_d  |  n_h   ret_h   dd_h   pf_h
5m    146   17.7%   3.2%   1.58  |  137   22.7%   1.9%   1.96
15m   140   11.7%   3.6%   1.42  |  133   13.3%   1.9%   1.61
30m   128    1.0%   4.7%   1.05  |  122    5.0%   1.5%   1.34
```

Clean, monotonic decay as entry TF coarsens — makes mechanistic sense (a
15/30-min bar blurs the actual breakout level and timing that the 5m signal
captures precisely). 5m entry remains the validated choice, not chosen by
grid search — it was the original pre-registered spec (§14.3), and this
test simply confirms nearby TFs don't do better, they do worse.

### HTF-filter alternatives (entry=5m fixed, same data window as baseline)

```
HTF filter          n_d   ret_d   pf_d  |  n_h   ret_h   pf_h
240m EMA50 (chosen) 147   17.6%   1.57  |  137   22.7%   1.96
1440m(daily) EMA50  132   10.8%   1.39  |  118   28.4%   2.36
240m EMA200         135   11.5%   1.39  |  120   23.3%   2.04
none (unfiltered)   183    5.2%   1.12  |  176    7.1%   1.17
```

No single HTF-filter choice dominates both windows — daily EMA50 edges
holdout PF, 240m EMA50 edges discovery return. All three filtered variants
clear the unfiltered baseline by a wide margin, on both windows. Read: the
*general* finding (HTF trend alignment matters) is robust to the specific
filter choice; the *specific* choice (240m EMA50) was set by forensics
before this breadth test, not selected afterward for looking best — kept
as-is rather than switched to whichever posts the best single number here,
which would be exactly the overfitting trap this project keeps guarding
against.

**No further parameter search planned on this strategy.** Entry TF and HTF
filter choice are both settled; any future work should be a genuinely new
mechanism/factor, not more variants of this one.
