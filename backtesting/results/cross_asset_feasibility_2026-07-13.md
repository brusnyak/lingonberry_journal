# Cross-Asset Feasibility Audit

Date: 2026-07-13.

## Verdict

Do not use FX, metals, or indices as current validation for the crypto engine yet.

Reason: data is stale. It can support historical feasibility research, but not a current deployment claim.

## Data Freshness

Audit run:

```bash
PYTHONPATH=. python -m backtesting.data_audit --as-of 2026-07-13T00:00:00Z --max-stale-days 7
```

Summary:

| Asset Class | Source | Freshness |
| --- | --- | --- |
| Crypto Binance/Bybit OHLCV | exchange-scoped | current, max stale about `1.0d` |
| Crypto structure cache | `data/features/structure/L2_R2` | current, max stale about `0.65d` |
| Forex | primary | stale, about `19-20d` |
| Commodity / metals | primary | stale, about `18-19d` |
| Indices | primary | mixed stale, about `9-19d` |

Sample 15m coverage:

| Asset | Symbol | Last Bar |
| --- | --- | --- |
| Index | NAS100 | `2026-06-24 12:45 UTC` |
| Index | SPX500 | `2026-07-03 16:45 UTC` |
| Index | US30 | `2026-07-03 16:45 UTC` |
| Index | UK100 | `2026-07-03 19:45 UTC` |
| Forex | EURUSD | `2026-06-23 06:45 UTC` |
| Forex | GBPUSD | `2026-06-23 06:45 UTC` |
| Forex | GBPJPY | `2026-06-23 06:45 UTC` |
| Commodity | XAUUSD | `2026-06-24 19:45 UTC` |
| Commodity | XAGUSD | `2026-06-25 15:45 UTC` |

## Gold Benchmark

Existing XAUUSD candidate was rerun as a stale-data feasibility benchmark, not a crypto-engine port.

Command:

```bash
PYTHONPATH=. python backtesting/xauusd_ny_short_runner.py --days 90 --risk-pcts 0.30 --tag xauusd_ny_short_90d_20260713_feasibility
```

Result:

| Asset | Window | Trades | Return | Max DD | Max Daily Loss | Win Rate | Avg R |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| XAUUSD | stale 90d | 21 | +1.91% | 0.61% | 0.30% | 61.9% | +0.303 |

Interpretation:

- Controlled, slow, and worth keeping as a separate gold module.
- Not comparable to the crypto MTF engine.
- Not deployment-ready because data is stale and no current broker-spread validation was run.

## Should We Port Crypto Logic To FX/Indices Now?

No.

Failure mode: a crypto setup can appear to generalize only because stale data covers a favorable historical segment. FX, metals, and indices have different session behavior, spread behavior, news shocks, and leverage/margin constraints.

Correct order:

1. Refresh FX/metals/index data.
2. Build the same causal structure cache for those assets.
3. Run a separate cross-asset foundation journal.
4. Compare setup families, not raw rules:
   - trend continuation,
   - range reversal,
   - shock/fade,
   - session open/close behavior.

## Next Cross-Asset Work

If cross-asset research becomes priority:

1. Refresh `forex`, `commodity`, and `index` OHLCV to current date.
2. Index no-lookahead structure for `15m`, `60m`, `240m`.
3. Run a minimal MTF structure journal on:
   - `XAUUSD`,
   - `NAS100`,
   - `SPX500`,
   - `EURUSD`,
   - `GBPUSD`,
   - `GBPJPY`.
4. Do not mix those results into crypto until each asset class has its own cost model and session model.
