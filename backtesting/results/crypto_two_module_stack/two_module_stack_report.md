# Crypto Two-Module Stack

Date: 2026-07-13.

## Scope

- Exchange: `binance`.
- Timeframe: `15m`.
- Window: `60d`.
- Symbols: reviewed `11`-symbol crypto basket.
- Portfolio risk proxy: `0.20%` per trade, max `6` open, max `1` open per symbol, daily loss cap `0.50%`.

## Modules

1. `late_us_short`
   - Session: `late_us`.
   - Direction: `short`.
   - Context: `4H neutral`, `4H/1H/15m bearish EMA`.
   - Entry: `fvg_ce_retest`.
   - Target: `fixed_2r`.
   - Management: `hold_target_expiry`.

2. `london_long`
   - Session: `london`.
   - Direction: `long`.
   - Context: `4H bull`, `1H+15m bullish EMA`.
   - Entry: `structure_confirmed_next_open`.
   - Target: `fixed_2r`.
   - Management: `be_after_half_target`.

## Portfolio Result

| Metric | Value |
| --- | ---: |
| Candidate trades | `217` |
| Accepted trades | `120` |
| Acceptance rate | `55.3%` |
| Symbols | `11` |
| Total R | `+44.363R` |
| Avg R | `+0.370R` |
| Median R | `+0.271R` |
| Profit factor | `2.28` |
| Gross return | `+8.87%` |
| Max DD | `1.81%` |
| Daily max DD | `1.47%` |
| Return/DD | `4.91` |
| Win rate | `56.7%` |
| Stop rate | `20.8%` |
| Expiry rate | `49.2%` |

## Module Split

| Module | Trades | Avg R | Total R | Stop | Expiry |
| --- | ---: | ---: | ---: | ---: | ---: |
| `late_us_short` | `53` | `+0.355R` | `+18.815R` | `22.6%` | `54.7%` |
| `london_long` | `67` | `+0.381R` | `+25.548R` | `19.4%` | `44.8%` |

## Symbol Split

| Symbol | Trades | Avg R | Total R | Stop | Expiry |
| --- | ---: | ---: | ---: | ---: | ---: |
| `AVAXUSDT` | `7` | `-0.087R` | `-0.606R` | `14.3%` | `71.4%` |
| `AAVEUSDT` | `6` | `+0.142R` | `+0.854R` | `33.3%` | `50.0%` |
| `NEARUSDT` | `8` | `+0.310R` | `+2.476R` | `50.0%` | `12.5%` |
| `XRPUSDT` | `17` | `+0.174R` | `+2.958R` | `29.4%` | `47.1%` |
| `SOLUSDT` | `14` | `+0.267R` | `+3.742R` | `21.4%` | `28.6%` |
| `DOGEUSDT` | `17` | `+0.233R` | `+3.967R` | `29.4%` | `52.9%` |
| `SUIUSDT` | `5` | `+0.853R` | `+4.266R` | `0.0%` | `60.0%` |
| `WLDUSDT` | `4` | `+1.366R` | `+5.462R` | `0.0%` | `25.0%` |
| `LINKUSDT` | `11` | `+0.508R` | `+5.592R` | `9.1%` | `54.5%` |
| `1000PEPEUSDT` | `13` | `+0.575R` | `+7.478R` | `15.4%` | `69.2%` |
| `ETHUSDT` | `18` | `+0.454R` | `+8.174R` | `11.1%` | `55.6%` |

## Judgment

- Proven in-sample: combining late-US short and London long improves basket frequency and keeps DD below `2%` at `0.20%` risk/trade.
- Proven in-sample: daytime is not dead. London long contributed more accepted trades and more total R than the late-US short benchmark.
- Not proven: holdout robustness, live execution quality, or per-symbol daily tradeability.
- Failure mode: forcing daily trades per asset will likely dilute edge. Frequency should come from more validated modules, not looser filters.
- Next test: run rolling/discovery-holdout validation on module definitions, then add Asia short only if it survives the same gates.
