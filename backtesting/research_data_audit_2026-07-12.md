# Research/Data Audit - 2026-07-12

Branch: `crypto-engine` (`origin/crypto-engine`, ahead 17).

## Verdict

The repo is strong enough for a crypto research phase after the 2026-07-12
cleanup/refresh, but not ready for cross-asset strategy claims.

Do not build another ICT/SMC strategy yet. First fix the multi-asset research substrate:

1. separate pure exchange-scoped crypto data from legacy-merged crypto data;
2. refresh stale funding/OHLCV/structure features;
3. build an event-outcome atlas for price action before strategy construction.

Status after cleanup:

- Active Binance/Bybit crypto OHLCV, funding, specs, and `L2_R2` structure
  cache were refreshed for 14 active symbols.
- Funding-aware crypto batch runs now fail on stale/incomplete funding coverage
  unless `--allow-stale-funding` is passed.
- FX, metals, indices, and legacy crypto remain stale and should not be used
  for current/live claims without refresh.

## Verified

- Data directory size: `2.7G`.
- Tests: `PYTHONPATH=. pytest -q backtesting/tests/test_validation.py backtesting/tests/test_engine.py backtesting/tests/test_crypto_validation.py backtesting/tests/test_crypto_reports.py backtesting/tests/test_pair_feasibility.py backtesting/tests/test_structure_features.py` -> `45 passed`.
- Crypto exchange-scoped OHLCV:
  - Binance: 14 symbols, 107 OHLCV files, 14 funding files, 1 market specs file.
  - Bybit: 14 symbols, 107 OHLCV files, 14 funding files, 1 market specs file.
  - Core tfs: `1,3,5,15,60,240,1440`; `30m` exists for only 9/14 raw exchange-scoped symbols, but structure cache has 30m for all 14.
- FX:
  - 21 symbols, 146 parquet files.
  - Tfs: `1,5,15,30,60,240`; daily missing for `EURUSD`.
- Metals:
  - `XAUUSD`, `XAGUSD`, all 7 standard tfs.
- Indices:
  - `DAX`, `NAS100`, `SPX500`, `UK100`, `US30`, all 7 standard tfs.
- Structure cache:
  - `224` files under `data/features/structure/L2_R2`.
  - 14 symbols x 2 exchanges x 8 tfs.
  - No `known_after_ts < ts` rows found.
  - No duplicate `known_after_ts` rows found.

## Data Freshness

Current date: 2026-07-12.

Representative latest timestamps:

| Dataset | Latest timestamp | Stale |
|---|---:|---:|
| Binance `BTCUSDT5` | 2026-07-04 17:50 UTC | 7.26 days |
| Bybit `BTCUSDT5` | 2026-07-04 17:50 UTC | 7.26 days |
| Binance `BTCUSDT` funding | 2026-06-26 08:00 UTC | 15.67 days |
| Binance `BTCUSDT` 30m structure cache | 2026-06-25 13:30 UTC | 16.44 days |
| `EURUSD5` raw parquet | 2026-06-23 06:55 UTC | 18.71 days |
| `XAUUSD5` raw parquet | 2026-06-24 19:55 UTC | 17.17 days |
| `NAS1005` raw parquet | 2026-06-24 12:55 UTC | 17.46 days |

Conclusion: old results are fine for historical audit, but not enough for current
rolling-window claims. After the refresh, this warning no longer applies to the
active Binance/Bybit crypto scope, but still applies to FX, metals, indices, and
legacy crypto. Future stock support should enter through the same asset-specific
discovery and loader contract.

## Loader Risks

### 1. Crypto exchange purity is broken

Pre-cleanup, `backtesting/crypto/data.py::_load_from_crypto_dir` merged `legacy` data first, then exchange-scoped data.

Observed:

- `load_data("BTCUSDT", "5", asset_type="crypto", exchange="binance")`
  returns `932436` rows from `2017-08-17` to `2026-07-04`.
- Raw Binance-scoped `BTCUSDT5.parquet` has only `107927` rows from `2025-06-25` to `2026-07-04`.

For Binance BTC, legacy and Binance overlap matched exactly over checked overlap. For Bybit BTC, legacy differs from Bybit on `99.85%` of overlapping closes, median close diff about `4.18`, max diff about `275.16`.

Failure mode: Bybit research can silently include Binance/legacy history before the scoped period, contaminating exchange-specific conclusions.

Fix before serious crypto research:

- Add a strict/pure exchange loader mode. Done in cleanup: explicit `exchange=` loads now default to `crypto_source="exchange"`.
- Preserve legacy only as `source="legacy"` or `source="merged"` with provenance tags. Partial: `crypto_source="merged"` keeps the old behavior available, but row-level provenance is still not attached.
- Make audit runners use pure exchange data by default.

### 2. `list_pairs(asset_type=...)` ignores asset type

Pre-cleanup observed:

- `list_pairs(None)` -> 52 symbols.
- `list_pairs("crypto")` -> same 52 symbols.
- `list_pairs("forex")` -> same 52 symbols.

Failure mode: scanners can accidentally include wrong assets unless they apply their own filtering.

Fix:

- Implement asset-specific pair listing. Done in cleanup.
- Add tests for `list_pairs("crypto")`, `list_pairs("forex")`, `list_pairs("commodity")`, `list_pairs("index")`. Done in cleanup.

### 3. Funding is stale relative to OHLCV

Crypto OHLCV goes to 2026-07-04, funding mostly ends 2026-06-25/26.

Failure mode: funding-sensitive tests after 2026-06-26 undercount costs/signals.

Fix:

- Refresh funding before funding-aware crypto work.
- Fail fast if OHLCV extends beyond funding by more than one funding interval for funding-aware strategies.

## Existing Result Artifacts

### Crypto

- `audit_tr_bos_fade.csv`: bad. Median PF about `0.265`; median return about `-98.13%`.
- `audit_crypto_tsmom.csv`: weak. Median PF about `0.776`; median return about `-32.97%`.
- `crypto_structure_pullback_v1_smoke_summary.csv`: no trades.
- `trfvg_10x_trade_review_summary.csv`: looks interesting but too small and not enough for a claim:
  - `AVAXUSDT 15m bull`: 39 trades, PF `1.975`, return `37.28%`, max DD `9.22%`.
  - `DOGEUSDT 5m bull`: 5 trades, PF `5.785`, too small.

Crypto verdict: not dead, but any "winner" must be retested after pure-exchange loader and refresh.

### FX / Metals

- `liquidity_fvg_5fx_180d_rolling30.csv`: one strong 30d window, several bad windows.
  - Best: `+8.69%`.
  - Bad windows: `-3.01%`, `-5.20%`, `-1.01%`, `-6.18%`.
- `bucket_model_walk_forward_v1_summary.csv`: too few trades; not enough evidence.
- `prop_walk_forward_490d_costed_v1_300x30_summary.csv`: selected rules mostly zero or losing; not viable.

FX verdict: research-only. No deployment-grade edge shown.

## Research-Ready Scope

Good enough now:

- Crypto historical/current event discovery on active Binance/Bybit scope.
- Crypto price-action event cataloging.
- Crypto structure-regime analysis on refreshed cached features.
- FX/metals/index exploratory studies only if not claiming current/live readiness.

Not good enough yet:

- Current cross-asset rolling-window claims.
- Any live or prop challenge deployment claim.
- BingX or stock research.

## Next Step

Do this before writing new strategies:

1. Fix data integrity:
   - strict crypto exchange loader; done for explicit `exchange=`;
   - asset-specific `list_pairs`; done;
   - freshness audit command; done;
   - funding/OHLCV alignment check; done for crypto batch runners.
2. Refresh data:
   - crypto OHLCV/funding/specs; done for active Binance/Bybit scope;
   - structure cache; done for active Binance/Bybit scope;
   - FX/metals/index if the research should include recent windows.
3. Build the event atlas:
   - input: OHLCV + structure features + funding/OI later;
   - events: sweep/reclaim, failed breakout, displacement, inside-bar compression, wick rejection, FVG touch/reclaim;
   - outcomes: `+1R`, `+2R`, `-1R`, MFE, MAE, time-to-target, expiration;
   - validation: rolling windows, symbol/exchange split, no single-symbol dependence.

Only after that should we implement a new strategy.

## Repository Objective

Short term:

- Make the repository a clean multi-asset research lab.
- Assets: crypto, FX, metals, indices now; stocks later.
- Crypto exchanges: Binance and Bybit now; BingX or others should be added as exchange namespaces, not mixed into generic crypto files.
- First output: reliable event-outcome datasets, not more named-strategy code.

Middle term:

- Turn the lab into a repeatable strategy factory:
  - ingest asset/exchange data;
  - validate quality/freshness;
  - generate causal structure and price-action events;
  - label forward outcomes;
  - select robust event buckets across rolling windows;
  - only then build execution strategies.

Non-goal:

- Do not chase a monolithic ICT/SMC engine.
- Do not optimize one equity curve.
- Do not treat crypto evidence as FX evidence, or Binance evidence as Bybit/BingX evidence.
