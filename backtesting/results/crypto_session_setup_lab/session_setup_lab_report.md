# Crypto Session Setup Lab

Date: 2026-07-13.

## Verdict

- Tested candle/setup filters on London-long `fixed_2r + be_after_half_target` candidates.
- The goal is frequency expansion without accepting the whole noisy London-long universe.
- Candle patterns are treated as confirmation features, not standalone signals.

## Variant Summary

| variant | candidates | accepted | symbols | candidate_per_symbol_day | accepted_per_symbol_day | avg_r | profit_factor | gross_return_pct | max_dd_pct | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| middle_local_bull | 627 | 78 | 10 | +1.226 | +0.152 | +0.350 | +2.262 | 5.45% | 1.82% | 19.23% | 46.15% |
| middle_local_bull_any_entry_confirm | 267 | 73 | 10 | +0.522 | +0.143 | +0.373 | +2.417 | 5.45% | 1.35% | 17.81% | 46.58% |
| middle_local_bull_no_exhaustion | 616 | 78 | 10 | +1.204 | +0.152 | +0.286 | +2.020 | 4.47% | 1.83% | 19.23% | 47.44% |
| middle_local_bull_rejection_or_break | 118 | 35 | 10 | +0.231 | +0.068 | +0.634 | +5.628 | 4.44% | 0.69% | 8.57% | 45.71% |
| middle_local_bull_candle_confirm | 120 | 33 | 10 | +0.235 | +0.065 | +0.632 | +4.603 | 4.17% | 0.91% | 12.12% | 45.45% |
| early_london_middle_local_bull | 243 | 46 | 10 | +0.476 | +0.090 | +0.304 | +2.185 | 2.80% | 0.95% | 17.39% | 54.35% |
| middle_local_bull_compression_break | 2 | 1 | 1 | +2.000 | +1.000 | -0.061 | +0.000 | -0.01% | 0.01% | 0.00% | 0.00% |
| all_london_long | 5147 | 355 | 11 | +8.043 | +0.555 | -0.017 | +0.960 | -1.21% | 6.42% | 32.11% | 42.54% |

## Middle/Local Bullish By Symbol

| symbol | candidates | avg_r | profit_factor | candle_confirm_share | compression_break_share | rejection_or_break_share | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOGEUSDT | 106 | +0.474 | +2.818 | 16.98% | 0.00% | 20.75% | 20.75% | 44.34% |
| 1000PEPEUSDT | 56 | +0.454 | +4.654 | 35.71% | 0.00% | 35.71% | 10.71% | 75.00% |
| SUIUSDT | 55 | +0.447 | +4.731 | 25.45% | 3.64% | 25.45% | 9.09% | 61.82% |
| XRPUSDT | 75 | +0.400 | +3.716 | 8.00% | 0.00% | 10.67% | 12.00% | 70.67% |
| ETHUSDT | 74 | +0.375 | +2.524 | 18.92% | 0.00% | 18.92% | 13.51% | 51.35% |
| LINKUSDT | 67 | +0.208 | +1.542 | 20.90% | 0.00% | 20.90% | 32.84% | 43.28% |
| AAVEUSDT | 42 | +0.085 | +1.237 | 14.29% | 0.00% | 14.29% | 26.19% | 66.67% |
| AVAXUSDT | 60 | -0.040 | +0.905 | 16.67% | 0.00% | 16.67% | 33.33% | 35.00% |
| SOLUSDT | 68 | -0.149 | +0.638 | 23.53% | 0.00% | 11.76% | 35.29% | 36.76% |
| NEARUSDT | 24 | -0.620 | +0.210 | 8.33% | 0.00% | 8.33% | 75.00% | 0.00% |

## Review Packet

- UI packet: `backtesting/results/review_samples/crypto_london_setup_lab_review_samples.csv`.
- Review `setup_confirm_loser` and `no_confirm_winner` first. Those decide whether candle/setup features are causal.

## Next Implementation Rule

- Do not loosen London to all long FVGs. That already fails.
- If candle/setup filters do not improve holdout, the right answer is another module, not more permissive London entries.
