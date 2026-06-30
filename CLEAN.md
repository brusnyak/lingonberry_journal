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
│   ├── features/         ← Feature engineering [keep as reference]
│   ├── baselines/        ← Null-hypothesis test harness [valid methodology]
│   ├── tests/            ← Tests
│   └── data_pipeline/    ← Data fetching
├── pine-review/          ← source/scripts/tests deleted; data/ only (674MB historical)
│   └── data/             ← Historical review artifacts charts sessions (not in use)
├── hypothesis_engine/    ← Clean research (Levels 0-3) [keep]
├── infra/                ← Broker infrastructure [PRODUCTION, 3 files removed]
├── bot/                  ← Bot automation [PRODUCTION]
├── webapp/               ← Flask webapp [PRODUCTION]
├── core/                 ← Core utilities [keep]
├── daily_engine/         ← Daily research [keep? - low value]
├── hermes/               ← Hermes MCP skills [keep]
├── scripts/              ← Data scripts [keep]
├── backtesting_config/   ← Settings [keep]
└── CLEAN.md              ← THIS FILE
├── hypothesis_engine/    ← NEW clean research (Levels 0-3) [keep]
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

## 8. Cleanup Execution Log

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
- **Ready to commit**: all changes verified and staged

---

## 9. Next Session — Entry Point

### Remaining cleanup work
1. **Codegraph re-index** — after file deletions and restructure, stale entries exist.
2. **C1 deferred**: Refactor `copy_trader.py` to use `tradelocker_client.py` (risk: live trading path — user explicitly asked to not touch this session)

### Next research direction
After cleanup is committed:
1. Literature survey of academically validated candle patterns for forex direction prediction
2. ML feature engineering pipeline based on patterns
3. XGBoost time-series cross-validation
4. Target: 58%+ direction accuracy on 5m forex, after spread

### Key files
- **CLEAN.md** — this file, session reference
- `backtesting/engine/costs.py:89-91` — B1 fixed
- `backtesting/engine/costs.py:70-73` — B6 + C3 fixed (seed default, fixed_spread_pips)
- `backtesting/engine/metrics.py:90-105` — C6 fixed (log_returns_curve)
- `backtesting/engine/__init__.py:5` — C4 fixed (re-exports)
- `backtesting/engine/data.py:138-141` — PARQUET_DIR, _load_from_flat_parquet
- `infra/market_data.py:117,280-282` — B3 (cache indicators) + B4 (yfinance resample)
- `infra/market_data.py:123-153` — `_resample_ohlcv()` function
- `bot/journal_db.py` — C2, now 7-line wrapper
- `bot/journal/` — C2, split package (schema.py, crud.py, stats.py)
- `bot/session_detector.py:69` — B2 fixed (string match)
- `core/constants.py` — C5, SESSIONS dict
- `hypothesis_engine/level1_conditions/conditions.py:155-225` — `bos_structured()`
- `hypothesis_engine/level1_conditions/scanner.py:69-72` — forward return fix
- `hypothesis_engine/level2_combos/scanner.py:99-103` — forward return fix
- `hypothesis_engine/level2_combos/scanner.py:58` — B7 (allow_oos=False)
- `hypothesis_engine/level3_backtest/engine.py` — B7 (allow_oos=False)
- `infra/position_manager.py` — ctrader fallback removed

**Current branch**: `hypothesis-engine`
