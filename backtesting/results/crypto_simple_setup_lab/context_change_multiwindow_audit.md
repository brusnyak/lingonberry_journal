# Context Change Multi-Window Audit

Setup: `context_change`

Rules:

- 15m entry.
- 240m/30m/15m strict direction context.
- Structural stop and fixed `2R` target.
- Sessions: `asia,london,ny`.
- Shock filter: `no_shock`.
- Cost gates: base cost <= `0.12R`, stress cost <= `0.40R`.
- Portfolio risk: `0.2%` risk/trade, max `3` open, max `1` open per symbol, daily loss limit `0.5%`.

## Baskets

- `multiasset`: `BTC, ETH, SOL, XRP, DOGE, BNB, AVAX`.
- `liquid-no-avax`: `BTC, ETH, SOL, XRP, DOGE, BNB`.

## Portfolio Results

| Basket | Days | Candidates | Accepted | PF | Return | Max DD | Return/DD | Win | Stop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| multiasset | 30 | 33 | 25 | 0.662 | -1.41% | 2.75% | -0.51 | 32.0% | 68.0% |
| multiasset | 60 | 122 | 78 | 1.269 | +2.73% | 3.95% | 0.69 | 43.6% | 52.6% |
| multiasset | 90 | 186 | 131 | 1.272 | +4.51% | 3.95% | 1.14 | 44.3% | 51.1% |
| multiasset | 180 | 357 | 260 | 1.247 | +8.13% | 5.95% | 1.37 | 43.8% | 51.9% |
| liquid-no-avax | 30 | 29 | 23 | 0.745 | -0.94% | 2.29% | -0.41 | 34.8% | 65.2% |
| liquid-no-avax | 60 | 103 | 70 | 1.566 | +4.62% | 3.36% | 1.37 | 48.6% | 47.1% |
| liquid-no-avax | 90 | 151 | 112 | 1.561 | +7.14% | 3.36% | 2.13 | 49.1% | 45.5% |
| liquid-no-avax | 180 | 303 | 228 | 1.437 | +11.77% | 4.11% | 2.86 | 47.4% | 47.8% |

## Read

- `30d` is bad in both baskets. Current/recent regime is hostile for this setup.
- Removing `AVAX` materially improves every tested window.
- `liquid-no-avax` is the better current basket.
- The strongest validation slice is `90d liquid-no-avax`: PF `1.561`, return/DD `2.13`, all rolling windows positive.
- `180d liquid-no-avax` has better total return and return/DD, but rolling windows are weaker (`60%` stress-positive), so it is less clean than the 90d slice.

## Decision

- Keep `context_change` as the current best setup.
- Do not include `AVAX` until it passes an asset-specific filter or separate setup logic.
- Do not deploy from this yet. Recent 30d weakness is a real warning.
- Next research should rank/filter baseline candidates by asset, DMI alignment, trend state, and recent performance regime before adding more setups.
