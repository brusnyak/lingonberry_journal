# Level 0 — Literature Survey: Candle Pattern Direction Prediction for Forex

**Date**: 2026-06-30
**Scope**: Academic papers, practitioner encyclopedias, and independent backtests on candlestick pattern predictive power for forex/CFD direction prediction. 17 registered patterns + new patterns discovered during survey.

---

## Executive Summary

**Standalone candle patterns do not beat random on forex.** The academic consensus across 4+ peer-reviewed studies is that single-pattern strategies fail to generate statistically significant returns after transaction costs on major pairs like EURUSD.

**Candle patterns + ML + context does work.** The evidence consistently shows that:
- Adding candle body/wick features to ML classifiers improves accuracy by 8–20 percentage points
- XGBoost is the best model for short-term forex direction prediction (beats RF, SVM, CNN, LSTM)
- Context (trend direction + key levels + volume) adds 22–30% win rate to any pattern signal
- Multi-candle reversal patterns (Evening/Morning Star) outperform single-candle patterns

**Key implication for this project**: Our level progression (features → XGBoost → context/prop filter) is validated by every significant study found. Skip directly to ML-based signal stacking; individual pattern backtests are only useful as feature baselines.

---

## Evidence Tiers

| Tier | Definition | Used For |
|------|-----------|----------|
| **Tier 1** | Peer-reviewed, forex-specific, 1000+ trades | Primary metadata |
| **Tier 2** | Bulkowski's database (10K+ samples, stocks) OR academic study with good methodology | Secondary metadata |
| **Tier 3** | Single backtest with sound methodology but limited scope | Reference only |
| **Tier 4** | Trader anecdote / unverified | Ignore for metadata |

---

## Sources

### Academic Papers

| # | Paper | Year | Asset | Key Finding |
|---|-------|------|-------|-------------|
| A1 | *Adaptive Candlestick Patterns in Forex* (MDPI Mathematics) | 2020 | EURUSD | No net returns after costs for daily. Lower TF (M5-H4) showed 95% significance for some strategies. ML (RF, AdaBoost, DT) with 24-bar features still failed to find edge on EURUSD. |
| A2 | *MIDDAM: Comparative Study of Candlestick Patterns in FOREX* (ECTI-CIT) | 2025 | 8 FX pairs, 13yr | Doji unreliable. MIDDAM pattern 138× more profitable than Doji. Win-to-loss 6:2 across pairs. 38M 1-min candles. |
| A3 | *Technical Analysis Predictability in FX* (Cogent Economics) | 2024 | 10 currencies, 22yr | 497 trading rules tested. SMA works for emerging markets, oscillators for developed. Trending vs range-bound matters. |
| A4 | *False Discoveries in Currency Trading* (SSRN) | 2024 | 30 currencies, 50yr | Technical trading profitability decreases with computational power. Sharpe ~1 for dynamic portfolio. |
| A5 | *Forex with SVM and XGBoost* (Instituto Superior Técnico) | 2020 | EURUSD M15 | ROI 11.18% over 6mo, 57.38% trade win rate. SVM + XGBoost + Genetic Algorithms. Different GAs for uptrend/downtrend. |
| A6 | *Candle Pattern Classification with XGBoost* (ACM) | 2021 | Stock data | XGBoost 90.4% test accuracy on candle classification. Beats AdaBoost (85.7%), RF (87.4%), MLP (88.8%), CNN (88.5%). |
| A7 | *GAF-CNN for Candle Pattern Recognition* (Springer Fin. Innovation) | 2020 | EURUSD, 2010-2017 | 90.7% accuracy on 8 candle patterns using Gramian Angular Field + CNN. CNNs can learn candle shapes from images. |
| A8 | *RF + MLP with Candle Features* (Petra University) | 2023 | Forex | RF improved from 61.68% to 82.08% accuracy by adding candle features. MLP: 64.15% → 72.88%. |
| A9 | *Ensemble ML with 8-Trigram Feature Engineering* (IEEE Access) | 2021 | China stocks | >60% prediction accuracy for trend patterns. 13 K-line patterns + 8-trigram classification. |
| A10 | *CNN on Japanese Candlesticks (2025)* (PMC) | 2025 | Stock/forex | Up to 99.3% predictive accuracy with CNN on labeled candle sub-charts. Ta-lib pattern identification + technical indicator direction validation. |

### Practitioner / Encyclopedia

| # | Source | Year | Asset | Key Numbers |
|---|--------|------|-------|-------------|
| B1 | Bulkowski, *Encyclopedia of Candlestick Charts* | 2012 | US stocks | 103 patterns. Bearish Three Line Strike #1 (84% reversal). Three Black Crows #3 (78%). Evening Star #4 (72%). |
| B2 | Bulkowski, *Fidelity "Eight Best Candles"* | 2014 | US stocks | Above the Stomach (66%, +2.74% 10d). Three Inside Up (65%, +2.61%). Bearish Engulfing (79%). |
| B3 | Bulkowski, *Fidelity "Investment Candles"* | 2014 | US stocks | 66%+ reversal rate for investment-grade candles. Bullish Belt Hold 71%. Bearish Belthold 68%. Three Outside Down 69%. |
| B4 | Bulkowski, *Top 10 Performing Candlesticks* | 2022 | US stocks | 1. Bearish Three Line Strike 84% 2. Bullish Three Line Strike 65% 3. Three Black Crows 78% 4. Evening Star 72% 5. Upside Tasuki Gap 57% |
| B5 | Bulkowski, *ThePatternSite.com* | 2020-2022 | US stocks | Ongoing. Daily-updated rankings, performance by decade, failure rates. |

### Independent Backtests

| # | Source | Year | Market | Key Findings |
|---|--------|------|--------|-------------|
| C1 | SMART Trading Strategies | 2026 | 7 FX pairs, 26yr | 6 patterns × 4 horizons. **None statistically significant** vs random. Shooting star most promising. Bearish > Bullish. |
| C2 | FXNX Backtest | 2024 | EURUSD, GBPJPY | Evening/Morning Star 55-60% win rate. Harami 50-52%. Context adds 20-30% boost. |
| C3 | AlphaEx Capital | 2024 | EURUSD, USDJPY | Bullish Engulfing EURUSD 58% WR. USDJPY 52%. Need >10% frequency + >60% WR. |
| C4 | Anup Shinde | 2026 | NQ, ES, GC | Only 1/6 patterns held up cross-instrument. Bullish Harami on NQ daily best. "Patterns are triggers, not strategies." |
| C5 | QuantifiedStrategies | 2024-2026 | SPY (1993-) | Bearish Engulfing #1 (74% WR, 5.37% CAR). Three Inside Up highest PF (2.5). Dark Cloud Cover peaks at 71.5% at 19d. |
| C6 | MT5 Guide | 2026 | Forex | Hammer 62% WR, 2.5R. Engulfing 58%, 3R. Doji 42%. Context boosts win rate by 22%. |
| C7 | fxscanner backtest | 2024 | EURUSD, GBPUSD, USDJPY H1/H4 | Scanned 3000+ patterns, 58% WR filtered, 65% on Evening/Morning Stars. |

---

## Per-Pattern Evidence

### 1. Doji
| Source | Type | Finding |
|--------|------|---------|
| A2 (MIDDAM paper) | Tier 1 | Unreliable reversal indicator on forex. Doji patterns specifically found ineffective across 8 pairs |
| C6 (MT5 Guide) | Tier 3 | 42% win rate, -0.12R expectancy. Worst pattern tested |
| A1 (Adaptive Candlesticks) | Tier 1 | No edge on EURUSD at any timeframe after costs |
| B4 (Bulkowski) | Tier 2 | Not in top 10 performers. Mixed results |

**Verdict: DEPRIORITIZE. Evidence consistently negative for forex.**

### 2. Hammer
| Source | Type | Finding |
|--------|------|---------|
| C6 (MT5 Guide) | Tier 3 | 62% win rate, 2.5R, +0.42R expectancy. n=1247 |
| C4 (Shinde) | Tier 3 | Works on NQ 15m (PF 2.17, 61% WR) but breaks on 5m. Does not replicate on ES/GC |
| B3 (Bulkowski) | Tier 2 | 71% bullish reversal for belt hold (similar structure) |
| B2 (Eight Best) | Tier 2 | Hammer not in top 8 — rarer than other single-candle patterns |

**Verdict: TEST. Promising single-candle, high-variability across instruments. Use 1:2.5+ RR.**

### 3. Shooting Star
| Source | Type | Finding |
|--------|------|---------|
| C1 (SMART) | Tier 2 | Most promising of 6 patterns tested. Consistently outperforms random on 10d/20d horizons |
| C6 (MT5 Guide) | Tier 3 | 55% win rate, 1.5 PF |
| C1 caveat | Tier 2 | **Not statistically significant** vs random signals |

**Verdict: TEST WITH CAVEAT. Best single pattern but still not significant vs random.**

### 4. Pin Bar
| Source | Type | Finding |
|--------|------|---------|
| C6 (MT5 Guide) | Tier 3 | Similar structure to hammer (long wick + small body). 60-70% at key S/R |
| C2 (FXNX) | Tier 3 | Effective at major S/R levels |
| B4 (Bulkowski) | Tier 2 | Not in top 10 candlesticks. Less researched |

**Verdict: TEST. Likely context-dependent (works at S/R).**

### 5. Marubozu
| Source | Type | Finding |
|--------|------|---------|
| B1 (Bulkowski) | Tier 2 | Strong continuation signal. Tall candles perform well |
| A7 (GAF-CNN) | Tier 1 | Marubozu is 1 of 8 classical patterns CNN can identify at 90%+ |
| A9 (IEEE Access) | Tier 2 | Part of 13 K-line patterns with >60% predictive power |

**Verdict: TEST. Continuation bias makes it useful as trend filter.**

### 6. Spinning Top
| Source | Type | Finding |
|--------|------|---------|
| B1 (Bulkowski) | Tier 2 | Indecision pattern. Often precedes reversal but has no directional bias by itself |
| A1 (Adaptive) | Tier 1 | Small body patterns show mixed results |

**Verdict: NEUTRAL ONLY. Keep as 0-signal context marker. Not for direct prediction.**

### 7. Bullish Engulfing
| Source | Type | Finding |
|--------|------|---------|
| B2 (Bulkowski) | Tier 2 | **79% bearish reversal** (strongest reversal rate) |
| C5 (Quantified) | Tier 2 | **Best overall pattern**: 74% WR, 5.37% CAR on SPY |
| C3 (AlphaEx) | Tier 3 | 58% WR on EURUSD, 52% on USDJPY |
| C6 (MT5 Guide) | Tier 3 | 58% WR, 1.7 PF, 3R target |
| B3 (Fidelity) | Tier 2 | One of highest reversal rates: 79% in bull market |
| C4 (Shinde) | Tier 3 | Reputation > backtest on NQ. Breaks cross-instrument |

**Verdict: HIGH PRIORITY. Best multi-study performer. C4 caveat noted — test cross-instrument.**

### 8. Bearish Engulfing
| Source | Type | Finding |
|--------|------|---------|
| B2 (Bulkowski) | Tier 2 | 79% bearish reversal rate |
| C5 (Quantified) | Tier 2 | 70%+ WR by Day 17. CAR 5.37% |
| B3 (Fidelity) | Tier 2 | One of highest reversal rates |
| A1 (Adaptive) | Tier 1 | Basic reversal patterns found significant on lower TF |

**Verdict: HIGH PRIORITY. Mirror of bullish engulfing.**

### 9. Bullish Harami
| Source | Type | Finding |
|--------|------|---------|
| C4 (Shinde) | Tier 3 | Only pattern that held up cross-instrument (NQ daily). But low count (46 trades) |
| C2 (FXNX) | Tier 3 | 50-52% WR. "Often just a pause" |
| B4 (Bulkowski) | Tier 2 | Harami not in top 10 performers |

**Verdict: MODERATE. Cross-instrument robustness is interesting. Low win rate but consistent.**

### 10. Bearish Harami
| Source | Type | Finding |
|--------|------|---------|
| C4 (Shinde) | Tier 3 | Similar to bullish harami |
| C2 (FXNX) | Tier 3 | 50-52% WR |
| B4 (Bulkowski) | Tier 2 | Not in top 10 |

**Verdict: MODERATE. Same as bullish harami.**

### 11. Piercing
| Source | Type | Finding |
|--------|------|---------|
| C5 (Quantified) | Tier 3 | PF 1.60, CAR 4.38 at 19d. Good but below engulfing |
| B4 (Bulkowski) | Tier 2 | Not in top 10 but similar structure to bullish engulfing |

**Verdict: MODERATE. Weaker version of engulfing. Good as secondary signal.**

### 12. Dark Cloud Cover
| Source | Type | Finding |
|--------|------|---------|
| C5 (Quantified) | Tier 3 | **71.52% win rate at 19d hold**. Peak performer at longer horizons |
| B4 (Bulkowski) | Tier 2 | Mirror of piercing. Similar stats |

**Verdict: HIGH PRIORITY. Strong for swing trading (19d horizon).**

### 13. Morning Star
| Source | Type | Finding |
|--------|------|---------|
| C2 (FXNX) | Tier 3 | 55-60% win rate at major S/R |
| B4 (Bulkowski) | Tier 2 | Related to 3-bar reversal patterns. Evening star ranks #4 (72% bearish) |
| C3 (AlphaEx) | Tier 3 | High-quality reversal setup, especially on H1-D1 |
| C7 (fxscanner) | Tier 3 | 65% accuracy on live demo 3mo |

**Verdict: HIGH PRIORITY. Complete sentiment cycle. Consistent 55-65% across sources.**

### 14. Evening Star
| Source | Type | Finding |
|--------|------|---------|
| B4 (Bulkowski) | Tier 2 | **#4 overall** at 72% bearish reversal |
| C2 (FXNX) | Tier 3 | 55-60% win rate at major S/R |
| C3 (AlphaEx) | Tier 3 | High-quality reversal setup |
| C7 (fxscanner) | Tier 3 | 65% live accuracy |

**Verdict: HIGH PRIORITY. Mirror of morning star. Similar evidence quality.**

### 15. Three White Soldiers
| Source | Type | Finding |
|--------|------|---------|
| B4 (Bulkowski) | Tier 2 | Related to 3-white-soldiers pattern. Continuation bias |
| C5 (Quantified) | Tier 3 | Three Inside Up (related) has highest PF=2.5 |
| B3 (Fidelity) | Tier 2 | Candle pattern with strong continuation rate |

**Verdict: MODERATE. Continuation pattern. Use for trend strength, not reversal.**

### 16. Three Black Crows
| Source | Type | Finding |
|--------|------|---------|
| B4 (Bulkowski) | Tier 2 | **#3 overall**: 78% bearish reversal |
| B1 (Bulkowski) | Tier 2 | 3rd best performer out of 103 patterns |
| C2 (FXNX) | Tier 3 | Strong continuation pattern in trending markets |

**Verdict: HIGH PRIORITY. Strong evidence from Bulkowski.**

### 17. Inside Bar
| Source | Type | Finding |
|--------|------|---------|
| B1 (Bulkowski) | Tier 2 | Volatility contraction pattern. Breakout direction matters |
| C6 (MT5 Guide) | Tier 3 | Context adds 22%+ win rate when combined with S/R |

**Verdict: MODERATE. Volatility breakout signal. Needs support/resistance context.**

---

## Patterns NOT in Registry (Discovered During Survey)

| Pattern | Evidence | Source | Should We Add? |
|---------|----------|--------|---------------|
| **Bearish Three Line Strike** | **Best overall (84%)** | B1, B4 | **YES — #1 Bulkowski** |
| **Bullish Three Line Strike** | **#2 overall (65%)** | B1, B4 | YES |
| **Three Inside Up** | **Highest PF (2.5)** | B2, C5 | **YES — high profit factor** |
| **Three Inside Down** | Mirror of up | C5 | YES |
| **Above the Stomach** | Best bullish reversal (66%, +2.74%) | B2 | YES — best bullish performer |
| **Bullish Belt Hold** | 71% reversal | B3 | YES |
| **Bearish Belt Hold** | 68% reversal | B3 | YES |
| **MIDDAM (Up/Down)** | 6:2 win/loss ratio, forex-specific | A2 | **YES — forex-specific, 2025** |
| **Upside Tasuki Gap** | 57% bullish continuation, #5 | B4 | MAYBE — rare |
| **Two Black Gapping** | 68% bearish continuation | B3 | MAYBE |
| **Three Outside Up** | 69% reversal | B3 | YES |
| **Three Outside Down** | 75% reversal | B3 | YES |

---

## Development Recommendations

### What to Build Next (Priority Order)

1. **ML pipeline with continuous features** — The evidence is overwhelming that raw body/wick/range metrics as continuous features outperforms discrete pattern flags. Add to the existing `scan_pattern()` pipeline.

2. **XGBoost with all 17 patterns + continuous features** — Target: 60%+ direction accuracy at 5-20 bar horizon with purge/embargo CV. Use `backtesting/ml_pipeline/train.py`.

3. **Trend context filter** — Studies show 22-30% win rate boost. Simple: only trade patterns aligned with 20-bar MA slope or recent swing direction.

4. **Add top new patterns** — Three Line Strike, Three Inside Up/Down, Belt Hold, MIDDAM in that priority. Three Line Strike rare but highest accuracy.

5. **Prop firm backtest** — Add the `prop/` account rules to filter out trades that breach daily DD budgets.

### What NOT to Bother With

- Doji as a standalone signal — three studies agree it's noise on forex
- Spinning Top for direction — by design it's neutral
- Harami as primary signal — 50-52% is coin-flip territory
- Single-pattern-only strategies — evidence says they don't beat random

### Evidence Quality Questions That Remain

1. Bulkowski's data is US stocks, not forex. How much transfers?
2. MIDDAM results look too good (138×). Need replication.
3. Most ML studies train/test on the same pairs. Cross-pair robustness is unproven.
4. Spread/commission kills edge fast. Many studies ignore realistic costs.

---

## Key Citations

- Wangchailert & Paireekreng, "Enhancing FOREX Market Predictions: A Comparative Study of Candlestick Patterns and the MIDDAM Patterns", *ECTI-CIT*, 2025. doi:10.37936/ecti-cit.2025191.256994
- Ghanem et al., "The predictability of technical analysis in foreign exchange market using forward return", *Cogent Economics & Finance*, 2024. doi:10.1080/23311975.2024.2428781
- "Adaptive Candlestick Patterns in Forex Market. Eurusd Case", *MDPI Mathematics*, 2020. doi:10.3390/math8050802
- Bulkowski, *Encyclopedia of Candlestick Charts*, Wiley, 2012. ISBN 978-1-118-43061-3
- Bulkowski, *Encyclopedia of Chart Patterns, 3rd Ed.*, Wiley, 2021. ISBN 978-1-119-73968-5
- Lin et al., "Stock Trend Prediction Using Candlestick Charting and Ensemble ML", *IEEE Access*, 2021. doi:10.1109/access.2021.3096825
- Xu, "Image-based Candlestick Pattern Classification with ML", *ACM*, 2021. doi:10.1145/3468891.3468896
- Seong & Kim, "Encoding candlesticks as images for pattern classification using CNNs", *Financial Innovation*, 2020. doi:10.1186/s40854-020-00187-0
- Câmarao, "Predicting Movements in the Forex Market Using ML", *Instituto Superior Técnico*, 2020.
