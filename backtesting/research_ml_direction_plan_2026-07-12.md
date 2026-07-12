# ML And Direction Research Plan

Date: 2026-07-12.

## Verdict

Do not replace the layered price-action engine with black-box ML.

Use ML only after the causal layers define a trade candidate:

1. direction/context state;
2. entry model;
3. stop geometry;
4. target model;
5. portfolio throttle.

Then ML can answer a smaller question:

> Given this candidate exists, should we take it, reduce risk, or skip it?

That is a meta-labeling/ranking problem, not a raw price prediction problem.

## Why

Current best bucket already has an interpretable edge:

- entry: `structure_confirmed_fvg_top_retest`;
- target: `fixed_1_5r`;
- management: `partial_1r_be`;
- PF: about `2.5-2.9` after portfolio throttles;
- low-DD research profile: about `+7.7%` to `+8.2%` with `~1.2%-1.3%` DD
  proxy under the current 60-day sample.

The bottleneck is not raw feature search. The bottlenecks are:

1. high expiry rate;
2. clustered trades;
3. whether execution buckets survive walk-forward;
4. whether rejected trades are rejected for visually correct reasons.

## What ML Is Allowed To Do

Allowed:

- predict `P(hit target before stop)` for an already-valid setup;
- predict `P(expiry)` to avoid dead trades;
- rank accepted setup quality;
- reduce risk size for lower-quality candidates;
- identify feature importance for human-auditable filters.

Not allowed yet:

- train directly on candles to emit buy/sell;
- optimize across hundreds of unstructured indicators;
- use random K-fold CV;
- use future candle-derived features;
- deploy a model before walk-forward and paper/demo validation.

## Candidate Feature Set

All features must be known at entry time.

Structure:

- HTF regime;
- LTF regime;
- latest BOS/CHoCH direction and age;
- swing sequence state;
- distance to protected high/low;
- sweep/rejection flags.

Entry quality:

- bars from FVG signal to retest;
- retest depth: top/CE/full fill;
- FVG size in ATR;
- entry distance to stop;
- opposing spike flag;
- candle close location around retest.

Target quality:

- target R;
- distance to last swing low/high;
- distance to round number;
- ATR-normalized room to target;
- expected obstruction before target.

Market state:

- ATR percentile;
- session;
- symbol;
- exchange;
- recent trend slope / EMA distance if added causally;
- funding/open interest later, if data quality passes.

Portfolio state:

- active correlated trades;
- symbol cooldown;
- daily realized PnL;
- open risk.

## Labels

Primary labels:

- `hit_target_before_stop`;
- `net_r > 0`;
- `net_r >= 0.5`;
- `expiry_without_1r`;
- `bad_trade = stop OR expiry_without_1r`.

Use separate models for:

- entry acceptance;
- target/expiry risk;
- sizing/risk scalar.

## Validation Rules

Minimum validation rules:

1. chronological walk-forward only;
2. purged/embargoed splits for overlapping labels;
3. no feature generated after `entry_ts`;
4. all multi-timeframe features merged by `known_after_ts <= entry_ts`;
5. report performance by fold, not only aggregate;
6. reject if fold concentration is high;
7. compare against the current rule-only portfolio baseline.

## Research References

- Marcos Lopez de Prado's financial ML framework emphasizes purging/embargo
  because ordinary K-fold validation leaks information in overlapping time-series
  labels: https://www.quantresearch.org/Innovations.htm
- Bailey, Borwein, Lopez de Prado, and Zhu propose Probability of Backtest
  Overfitting for investment simulations: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
- Bailey and Lopez de Prado's Deflated Sharpe Ratio corrects for selection bias,
  non-normal returns, and backtest overfitting:
  https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2460551_code87814.pdf?abstractid=2460551
- Recent validation research also points toward strict walk-forward testing and
  overfit-aware evaluation for algorithmic trading:
  https://arxiv.org/html/2512.12924v1

## Next Implementation

1. Finish UI review packet review.
2. Add execution walk-forward validation for the current bucket.
3. Build a feature table for accepted and rejected candidates.
4. Train only a simple baseline first:
   - logistic regression;
   - shallow tree / gradient boosting only after the baseline works;
   - feature importance report required.
5. Compare ML-gated portfolio to the rule-only portfolio.

If ML does not improve return/DD and reduce expiry across folds, delete it.
