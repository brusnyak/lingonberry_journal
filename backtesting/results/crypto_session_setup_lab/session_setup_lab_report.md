# Crypto Session Setup Lab

Date: 2026-07-13.

## Verdict

- Tested candle/setup filters on London-long `fixed_2r + be_after_half_target` candidates.
- The goal is frequency expansion without accepting the whole noisy London-long universe.
- Candle patterns are treated as confirmation features, not standalone signals.

## Variant Summary

| variant | candidates | accepted | symbols | candidate_per_symbol_day | accepted_per_symbol_day | avg_r | profit_factor | gross_return_pct | max_dd_pct | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| middle_local_bull_any_entry_confirm | 267 | 73 | 10 | +0.522 | +0.143 | +0.396 | +2.513 | 5.79% | 1.33% | 17.81% | 46.58% |
| middle_local_bull_rejection_or_break | 61 | 34 | 10 | +0.119 | +0.066 | +0.660 | +5.665 | 4.49% | 0.69% | 8.82% | 44.12% |
| middle_local_bull_no_exhaustion | 346 | 78 | 10 | +0.676 | +0.152 | +0.283 | +2.000 | 4.42% | 1.81% | 19.23% | 46.15% |
| middle_local_bull | 355 | 78 | 10 | +0.694 | +0.152 | +0.278 | +1.975 | 4.34% | 2.21% | 19.23% | 44.87% |
| middle_local_bull_candle_confirm | 62 | 33 | 10 | +0.121 | +0.065 | +0.633 | +4.609 | 4.17% | 0.91% | 12.12% | 45.45% |
| early_london_middle_local_bull | 135 | 46 | 10 | +0.264 | +0.090 | +0.312 | +2.216 | 2.87% | 0.94% | 17.39% | 54.35% |
| all_london_long | 3057 | 361 | 11 | +4.777 | +0.564 | +0.017 | +1.042 | 1.23% | 5.70% | 29.92% | 42.38% |
| middle_local_bull_compression_break | 1 | 1 | 1 | +1.000 | +1.000 | -0.061 | +0.000 | -0.01% | 0.01% | 0.00% | 0.00% |

## Middle/Local Bullish By Symbol

| symbol | candidates | avg_r | profit_factor | candle_confirm_share | compression_break_share | rejection_or_break_share | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOGEUSDT | 59 | +0.479 | +2.762 | 15.25% | 0.00% | 18.64% | 22.03% | 42.37% |
| 1000PEPEUSDT | 32 | +0.450 | +5.125 | 31.25% | 0.00% | 31.25% | 9.38% | 78.12% |
| XRPUSDT | 41 | +0.428 | +3.882 | 7.32% | 0.00% | 9.76% | 12.20% | 70.73% |
| SUIUSDT | 33 | +0.361 | +3.691 | 21.21% | 3.03% | 21.21% | 9.09% | 60.61% |
| ETHUSDT | 39 | +0.334 | +2.263 | 17.95% | 0.00% | 17.95% | 15.38% | 51.28% |
| LINKUSDT | 38 | +0.139 | +1.324 | 21.05% | 0.00% | 21.05% | 36.84% | 42.11% |
| AAVEUSDT | 28 | +0.129 | +1.350 | 14.29% | 0.00% | 14.29% | 28.57% | 60.71% |
| AVAXUSDT | 34 | -0.112 | +0.754 | 14.71% | 0.00% | 14.71% | 35.29% | 32.35% |
| SOLUSDT | 39 | -0.130 | +0.669 | 20.51% | 0.00% | 10.26% | 33.33% | 38.46% |
| NEARUSDT | 12 | -0.620 | +0.210 | 8.33% | 0.00% | 8.33% | 75.00% | 0.00% |

## Review Packet

- UI packet: `backtesting/results/review_samples/crypto_london_setup_lab_review_samples.csv`.
- Review `setup_confirm_loser` and `no_confirm_winner` first. Those decide whether candle/setup features are causal.

## Next Implementation Rule

- Do not loosen London to all long FVGs. That already fails.
- If candle/setup filters do not improve holdout, the right answer is another module, not more permissive London entries.
