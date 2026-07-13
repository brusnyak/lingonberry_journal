# Crypto Session Setup Research Notes

Date: 2026-07-13.

## External Research Takeaways

- Session effects are real. FX and crypto both show intraday time-of-day patterns, so session should be a first-class context variable, not an afterthought.
- Crypto has 24/7 trading, but activity still clusters around traditional market hours. London/NY windows are valid pseudo-sessions to test.
- NY reversal and opening-range breakout are hypotheses, not rules. They need mechanical definitions and holdout tests.
- Candle patterns are weak as standalone predictors. Use them only as entry confirmation after direction/session context is already valid.

## Session Setup Hypotheses

| Setup | Mechanical Definition | First Test | Current Status |
| --- | --- | --- | --- |
| London continuation | 15m London, 4H bull, 1H+15m bullish, long FVG/retest/next-open | canonical harness | Best current daytime setup |
| London sweep then continuation | London takes prior Asia/session low, reclaims, then long retest | not implemented | next candidate |
| London swing to NY reversal | London directional expansion, NY fails continuation and breaks micro-structure opposite | not implemented | research candidate |
| NY continuation | NY overlap follows London trend after range break/retest | not implemented | research candidate |
| Late-US flush | late-US short after bull/neutral context, bearish FVG/CE retest | canonical harness | strongest 60d module |
| Asia pullback/flush | Asia short in bearish local/middle EMA | matrix only | secondary candidate |
| Compression breakout | narrow pre-session range, displacement breakout, retest/engulfing | partial setup lab | needs proper range module |

## Canonical Harness Results

### binance_15m_30d

| setup_name | candidates | accepted | avg_r | median_r | profit_factor | gross_return_pct | max_dd_pct | return_to_dd | win_rate | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| london_long_middle_local_next_open | 94 | 42 | +0.796 | +0.784 | +5.991 | 6.69% | 0.44% | +15.324 | 76.19% | 9.52% | 47.62% |
| london_long_middle_local_retest | 94 | 43 | +0.758 | +0.702 | +5.582 | 6.52% | 0.44% | +14.934 | 74.42% | 9.30% | 46.51% |
| late_us_short_bull_flush_ce | 115 | 63 | +0.510 | +0.451 | +3.068 | 6.43% | 0.89% | +7.260 | 61.90% | 17.46% | 52.38% |
| ny_long_neutral_reversal_ce | 125 | 65 | +0.161 | -0.043 | +1.520 | 2.09% | 1.86% | +1.128 | 46.15% | 21.54% | 53.85% |
| late_us_short_bearish_trend_ce | 28 | 18 | -0.244 | -1.039 | +0.605 | -0.88% | 1.26% | -0.698 | 33.33% | 55.56% | 27.78% |

### binance_15m_60d

| setup_name | candidates | accepted | avg_r | median_r | profit_factor | gross_return_pct | max_dd_pct | return_to_dd | win_rate | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| late_us_short_bull_flush_ce | 152 | 85 | +0.493 | +0.386 | +3.226 | 8.38% | 0.92% | +9.080 | 60.00% | 15.29% | 52.94% |
| london_long_middle_local_retest | 163 | 76 | +0.320 | +0.246 | +2.158 | 4.86% | 1.59% | +3.051 | 55.26% | 18.42% | 44.74% |
| london_long_middle_local_next_open | 163 | 75 | +0.291 | +0.137 | +2.003 | 4.36% | 2.20% | +1.982 | 54.67% | 20.00% | 45.33% |
| late_us_short_bearish_trend_ce | 97 | 56 | +0.248 | +0.168 | +1.799 | 2.77% | 1.57% | +1.764 | 58.93% | 25.00% | 60.71% |
| ny_long_neutral_reversal_ce | 322 | 147 | +0.090 | -0.051 | +1.291 | 2.65% | 3.23% | +0.820 | 45.58% | 21.09% | 57.14% |

### binance_5m_30d

| setup_name | candidates | accepted | avg_r | median_r | profit_factor | gross_return_pct | max_dd_pct | return_to_dd | win_rate | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| late_us_short_bull_flush_ce | 343 | 70 | +0.073 | -0.088 | +1.220 | 1.03% | 2.94% | +0.349 | 45.71% | 24.29% | 52.86% |
| london_long_middle_local_retest | 223 | 45 | +0.042 | -0.146 | +1.109 | 0.38% | 1.76% | +0.214 | 40.00% | 24.44% | 46.67% |
| london_long_middle_local_next_open | 223 | 44 | +0.020 | -0.172 | +1.051 | 0.18% | 1.79% | +0.098 | 38.64% | 25.00% | 45.45% |
| ny_long_neutral_reversal_ce | 396 | 81 | -0.023 | -0.132 | +0.945 | -0.37% | 1.84% | -0.199 | 37.04% | 30.86% | 39.51% |
| late_us_short_bearish_trend_ce | 47 | 19 | -0.205 | -0.201 | +0.562 | -0.78% | 1.16% | -0.673 | 31.58% | 31.58% | 63.16% |

## Verdict

- Do not use `5m` as the primary search interval. Canonical `5m/30d` results are weak after de-duplication and one-execution-per-signal selection.
- Use `15m` for direction/session/setup selection. Add `5m` only later as an entry-refinement confirmation layer.
- Current best short-term build target: canonical `15m` London continuation plus late-US flush, then holdout/rolling validation.
- Next implementation should add missing setup families: London sweep-continuation, London-to-NY reversal, and session opening-range breakout.
