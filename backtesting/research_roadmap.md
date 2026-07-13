# Multi-Asset Research Roadmap

Last updated: 2026-07-13.

## Objective

Build this repository into a multi-asset research lab first, and a strategy
factory second.

Assets in scope now:

- Crypto perpetuals: Binance and Bybit now; BingX later as an explicit exchange
  namespace.
- Forex.
- Metals.
- Indices.

Assets in scope later:

- Stocks, if they enter through the same loader, data-quality, and event-labeling
  contracts.

## Short-Term Goal

Make the research substrate trustworthy enough that a result can be rejected or
promoted without arguing about data leakage.

Done or implemented:

1. Asset-specific pair discovery.
2. Exchange-pure crypto loading by default when `exchange=` is explicit.
3. Rerunnable data freshness/source audit.
4. Funding/OHLCV alignment guardrails for funding-aware crypto tests.
5. Structure cache refresh path.
6. First event-outcome atlas for crypto price action.
7. Direction/stop/target plan variants inside the atlas.
8. Rolling-window validation for event-plan-context buckets.
9. Discovery/holdout walk-forward validation for selected buckets.
10. First causal direction/entry-quality layer for the crypto survivor branch:
    structure-confirmed entry variants and opposing-spike rejection.
11. First target/risk layer for the crypto survivor branch: explicit target
    models, stale-retest filtering, duplicate-zone suppression, and sizing
    proxy.
12. First shock-aware execution layer: causal large-displacement state,
    half-target breakeven management, and optional EMA research variants.
13. First trade-level forensic audit for the promoted shock-aware bucket,
    including UI review packet generation and exchange-specific review loading.
14. First single-exchange trend/session matrix for crypto `15m`, separating
    raw event frequency from execution-filter scarcity.
15. First executable FVG session matrix for crypto `15m`, testing actual retest
    entries/exits across all sessions instead of raw event drift.
16. First promoted daytime module: London long with `1H+15m` bullish EMA,
    structure confirmation, fixed `2R`, and breakeven after half-target.
17. First two-module crypto stack combining late-US short and London long.
18. First London session frequency audit separating UI sampling scarcity,
    strategy-filter scarcity, and raw executable-event frequency.
19. First London setup lab testing candle/setup confirmation features as
    frequency-quality gates.

Still needed:

1. Context-bucket validation over event rows.
2. FX/metals/index refresh before current cross-asset claims.
3. BingX namespace and data pipeline if BingX becomes active scope.

## Middle-Term Goal

Turn the repo into a repeatable strategy factory:

1. Ingest asset/exchange data.
2. Validate quality, freshness, gaps, and provenance.
3. Generate causal structure and price-action events.
4. Label forward outcomes with mechanical R-based rules.
5. Search for robust event buckets across rolling windows.
6. Build execution strategies only from event buckets that survive validation.

## Non-Goals

- Do not build a monolithic ICT/SMC mega-engine.
- Do not optimize one equity curve and call it edge.
- Do not mix Binance, Bybit, BingX, or legacy crypto data unless the research
  explicitly asks for merged history.
- Do not treat crypto evidence as FX evidence.
- Do not treat intraday evidence as swing evidence.

## Current State

Known good:

- Explicit crypto `exchange=` loads default to exchange-scoped data.
- Legacy crypto history is still available with `crypto_source="merged"`.
- `list_pairs(asset_type=...)` separates crypto, forex, commodity, and index symbols.
- Index symbols with digits such as `NAS100` and `SPX500` are preserved.
- Active Binance/Bybit crypto OHLCV, funding, market specs, and `L2_R2`
  structure cache were refreshed on 2026-07-12 for 14 symbols.
- Crypto batch runs now fail on stale/incomplete funding coverage unless
  `--allow-stale-funding` is passed.
- First crypto event-atlas module exists at `backtesting/crypto/event_atlas.py`.
- Event bucket rolling validator exists at `backtesting/crypto/event_validation.py`.
- Walk-forward bucket validation selects on discovery and scores the same bucket
  on holdout without re-selecting.
- `backtesting/crypto/direction_layer.py` now enforces direction confirmation
  through `known_after_ts <= entry_ts`, so multi-timeframe or structure features
  are joined by availability time, not pivot/reference time.
- Event rows now score competing stop models:
  - event extreme;
  - prior swing;
  - ATR stop.
- Event rows now score competing target models:
  - fixed `1R`;
  - fixed `2R`;
  - prior opposite range level;
  - next round number.

Known gaps:

- Legacy crypto is still stale and should not be used for exchange-specific
  research.
- FX, metals, and indices are still stale relative to the current date.
- BingX is not yet implemented as a crypto exchange namespace.
- Raw event labels are not tradeable edge without context filters.
- Structure confirmation improves stop/adverse-excursion quality but does not
  solve target/expiry quality by itself.
- The first decent target/risk bucket exists, but still needs portfolio
  throttling and walk-forward validation before strategy promotion.
- The first portfolio-throttled candidate survived, but live/funded deployment
  is still blocked by execution walk-forward and demo/paper validation.
- EMA is implemented as an optional research feature, not a promoted direction
  gate. The first EMA-inclusive run reduced sample size and did not beat the
  structure-confirmed FVG top-retest bucket.

## Event Atlas

Run example:

```bash
python -m backtesting.crypto.event_atlas --symbols BTCUSDT,ETHUSDT --exchange both --tfs 5,15 --days 120
```

Current event families:

- Sweep and reclaim of prior high/low.
- Failed breakout back into range.
- Displacement candle.
- Inside-bar compression.
- FVG formation.

Outcome columns:

- `+1R`, `+2R`, and `-1R` hits.
- MFE/MAE.
- Expiration result.
- Cost-adjusted `net_r`.
- Stop model, target model, and target R.
- UTC session and volatility bucket.

Smoke result on `BTCUSDT,ETHUSDT`, Binance+Bybit, `5m/15m`, `60d`:

- `39,417` event rows.
- Overall average `net_r=-0.4178`.
- Overall median `net_r=-1.2014`.
- Best symbol-level bucket was only about `+0.02R` average and still had
  negative median R.

Verdict: raw price-action labels alone are not an edge. The next useful test is
context filtering by HTF regime, volatility, session/time, distance to structure,
symbol agreement, and exchange agreement.

Plan-variant smoke on `BTCUSDT,ETHUSDT`, Binance+Bybit, `5m/15m`, `30d`:

- `225,366` scored event-plan rows.
- Overall average `net_r=-0.3944`.
- Overall median `net_r=-1.0438`.
- No raw symbol-level plan bucket passed even loose robustness gates with
  `events >= 200` and `PF >= 1.05`.
- Context buckets produced a few hypotheses across both BTC/ETH and both
  exchanges:
  - `bullish_fvg_formation`, long, `prior_swing` stop, `fixed_2r`, HTF bear,
    Asia, normal vol: `204` events, avg `+0.1551R`, PF `1.64`.
  - `bearish_fvg_formation`, short, `prior_swing` stop, `fixed_2r`, HTF bull,
    late US, normal vol: `298` events, avg `+0.1103R`, PF `1.41`.
  - Smaller but stronger bucket: `bearish_fvg_formation`, short,
    `prior_swing` stop, prior-opposite target, HTF bear, London, normal vol:
    `112` events, avg `+0.3030R`, PF `2.93`.

Interpretation: direction appears to matter more than entry pattern naming.
FVG formation may be useful only when paired with HTF/session/volatility
context and prior-swing stops. Event-extreme stops still look fragile in many
buckets.

Rolling validation over the same `30d` smoke using `7d` windows and `3d` step:

- `642` event-plan-context buckets evaluated after minimum event filtering.
- `6` buckets passed loose research gates.
- Every passed bucket was FVG formation.
- No sweep/reclaim, failed breakout, displacement, or compression bucket passed.
- Passed buckets:
  - Bearish FVG, short, prior-swing stop, prior-opposite target, HTF bear,
    London, normal vol: `112` events, PF `2.93`, avg `+0.303R`, `75%`
    positive windows.
  - Bearish FVG, short, prior-swing stop, fixed `2R`, HTF bear, London,
    normal vol: `130` events, PF `1.81`, avg `+0.262R`, `75%` positive
    windows.
  - Bullish FVG, long, prior-swing stop, fixed `2R`, HTF bear, Asia,
    normal vol: `204` events, PF `1.64`, avg `+0.155R`, `80%` positive
    windows.
  - Bearish FVG, short, ATR stop, prior-opposite target, HTF bear, London,
    normal vol: `112` events, PF `1.27`, avg `+0.150R`, `75%` positive
    windows.
  - Bullish FVG, long, prior-swing stop, fixed `1R`, HTF bear, Asia,
    normal vol: `204` events, PF `1.48`, avg `+0.113R`, `80%` positive
    windows.
  - Bullish FVG, long, prior-swing stop, round-number target, HTF bear,
    Asia, normal vol: `204` events, PF `1.45`, avg `+0.105R`, `60%`
    positive windows.

Current research verdict:

- Keep FVG formation as the active chemistry branch.
- Drop raw sweep/reclaim, failed breakout, displacement, and compression from
  strategy work until they show up as useful context filters rather than entry
  triggers.
- Prior-swing stops are currently stronger than event-extreme stops.
- Direction should be treated as a context-dependent output, not assumed from
  the event name alone.

Manual UI review checkpoint on 2026-07-12:

- Saved labels existed for `11` crypto review trades across `LINKUSDT` and
  `XRPUSDT`.
- Label split: `4` good, `4` bad, `3` note-only.
- Good labels were all winners, about `+1.46R` average.
- Bad labels were all losers, about `-1.09R` average.
- Human notes repeatedly flagged late entries, no confirmation, wrong structure
  context, and big spike/rejection handling. Human notes did not primarily blame
  stop placement.

Structure-layer execution checkpoint on 2026-07-12:

- Scope: `11` reviewed/strong symbols, Binance+Bybit, `15m`, `60d`.
- Rows: `28,680`.
- Raw entries: `18,828` rows, avg bucket R `+0.241`, best avg R `+0.353`,
  best PF `2.41`, mean stop rate `18.2%`, mean median MAE `-0.445R`.
- Structure-confirmed entries: `9,852` rows, avg bucket R `+0.223`, best avg R
  `+0.355`, best PF `2.67`, mean stop rate `14.3%`, mean median MAE `-0.339R`.
- Verdict: structure confirmation improves risk quality but is not enough. The
  next failure is target/expiry and stale-retest behavior, not raw stop geometry.

Target/risk execution checkpoint on 2026-07-12:

- Scope: same `11` symbols, Binance+Bybit, `15m`, `60d`.
- Rows: `58,584`.
- Raw layer aggregate: `41,334` rows, avg bucket R `+0.167`, best avg R
  `+0.344`, best PF `2.53`, mean stop rate `23.2%`.
- Structure-confirmed layer aggregate: `17,250` rows, avg bucket R `+0.226`,
  best avg R `+0.576`, best PF `2.70`, mean stop rate `17.9%`.
- Best practical bucket after sample/quality filters:
  - entry: `structure_confirmed_fvg_top_retest`;
  - target: `fixed_1_5r`;
  - management: `partial_1r_be`;
  - events: `185`;
  - symbols/exchanges: `11` symbols, Binance+Bybit;
  - avg R: `+0.378`;
  - median R: `+0.510`;
  - PF: `2.69`;
  - target rate: `31.4%`;
  - stop rate: `17.3%`;
  - expiry rate: `40.0%`.
- Position-risk proxy for that bucket:
  - `0.10%` risk/trade: about `+6.99%` gross return, `1.06%-1.14%` DD proxy.
  - `0.15%` risk/trade: about `+10.49%` gross return, `1.58%-1.71%` DD proxy.
  - `0.25%` risk/trade: about `+17.49%` gross return, `2.64%-2.85%` DD proxy.
- Verdict: first decent candidate. Not deployable yet. Use `0.10%-0.15%`
  risk/trade for low-DD research; `0.25%` is too aggressive for the stated
  drawdown target.

Portfolio-layer checkpoint on 2026-07-12:

- Bucket tested:
  - entry: `structure_confirmed_fvg_top_retest`;
  - target: `fixed_1_5r`;
  - management: `partial_1r_be`;
  - candidates: `185`.
- Conservative setting:
  - risk/trade: `0.15%`;
  - max open: `3`;
  - max open per symbol: `1`;
  - daily loss cap: `0.75%`;
  - accepted trades: `78`;
  - return: `+4.17%`;
  - max DD: `0.65%`;
  - daily max DD: `0.59%`;
  - PF: `2.50`.
- Better research setting under `2%` DD:
  - risk/trade: `0.20%`;
  - max open: `6` or uncapped after symbol cap;
  - max open per symbol: `1`;
  - daily loss cap: `0.50%`;
  - accepted trades: `96-98`;
  - return: about `+7.7%` to `+8.2%`;
  - max DD: about `1.26%`;
  - PF: about `2.8-2.9`.
- Verdict: candidate survives portfolio throttling. It is now worth manual
  review plus execution walk-forward. It is still not ready for live cTrader or
  funded-account deployment.

Manual portfolio-candidate review checkpoint on 2026-07-12:

- Reviewed labels so far: `17` across `LINKUSDT` and `XRPUSDT`.
- Labels: `9` good, `4` bad, `1` skip, `3` note-only.
- Accepted winners reviewed so far are visually credible: `4/4` good.
- Rejected no-confirmation examples are correctly rejected so far: `3/3` bad.
- Stale-retest filter is too blunt: several stale rejects were marked good or
  note-only.
- Portfolio throttle is also blunt: `2` reviewed throttle rejects were marked
  good.
- Accepted losers show the next missing layer:
  - some are real direction/confirmation failures;
  - some need better management once price has moved about `50%` toward target.
- Screenshot/review finding: large displacement or price shock must become an
  explicit market-state feature. The engine must not treat violent moves as if
  normal FVG retest logic still applies unchanged.
- Next priority: implement causal displacement/follow-through state, then test
  BE-after-`0.5R` / runner management variants before ML.

Full active crypto universe validation on 2026-07-12:

- Scope: 14 symbols, Binance+Bybit, `15m`, `60d`.
- Symbols: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `XRPUSDT`, `DOGEUSDT`, `BNBUSDT`,
  `HYPEUSDT`, `AAVEUSDT`, `WLDUSDT`, `1000PEPEUSDT`, `AVAXUSDT`,
  `LINKUSDT`, `NEARUSDT`, `SUIUSDT`.
- Atlas rows: `729,528` scored event-plan rows.
- Validation gates:
  - `target_r >= 1.5`;
  - median target R `>= 1.8`;
  - median stop distance `>= 0.15%`;
  - `events >= 300`;
  - `PF >= 1.20`;
  - average net R `>= +0.05`;
  - positive rolling-window rate `>= 60%`;
  - max symbol/exchange concentration `<= 60%`.
- Buckets evaluated after filters: `352`.
- Buckets passed: `6`.

Passed full-universe buckets:

| Event | Direction | Stop | Target | HTF | Session | Vol | Events | Avg R | PF | Positive windows |
|---|---|---|---|---|---|---|---:|---:|---:|---:|
| bearish FVG | short | prior swing | fixed 2R | bull | late US | high | 1170 | +0.173 | 1.58 | 71% |
| bearish FVG | short | ATR | round number | bull | late US | high | 539 | +0.170 | 1.28 | 71% |
| bearish FVG | short | prior swing | prior opposite | bull | NY | high | 326 | +0.162 | 1.34 | 71% |
| bearish FVG | short | prior swing | fixed 2R | neutral | late US | high | 478 | +0.141 | 1.50 | 71% |
| bearish FVG | short | ATR | fixed 2R | neutral | Asia | high | 701 | +0.132 | 1.21 | 71% |
| inside compression | short | prior swing | fixed 2R | bull | NY | high | 495 | +0.093 | 1.22 | 86% |

Full-universe interpretation:

- The earlier BTC/ETH long FVG buckets did not generalize to the 14-symbol
  universe.
- The surviving chemistry is short-side, high-volatility, mostly bearish FVG.
- The broad direction filter is: do not assume bull HTF means long. In this
  sample, shorts inside bull/neutral HTF during high volatility performed
  better, probably because bearish FVGs are capturing pullback/flush behavior
  after expansion.
- This is still research, not deployment. The worst rolling window remains
  negative for every passed bucket, so sizing and frequency control matter.

Discovery/holdout test over the same `60d` full-universe sample:

- Discovery: first `30d`.
- Holdout: next `30d`.
- Discovery-selected rows: `14`.
- Holdout-passed rows: `1`.
- Only survivor:
  - Event: bearish FVG formation.
  - Direction: short.
  - Stop: prior swing.
  - Target: fixed `2R`.
  - Context: HTF bull, late US session, high volatility.
  - Discovery: `566` events, avg `+0.229R`, PF `1.85`.
  - Holdout: `602` events, avg `+0.121R`, median `+0.054R`, PF `1.38`.
  - Holdout coverage: `14` symbols, `2` exchanges.

Holdout interpretation:

- Most apparent chemistry failed outside discovery.
- The current strongest candidate is one short-side bearish-FVG bucket:
  `bearish_fvg_formation + short + prior_swing stop + fixed 2R + HTF bull +
  late US + high volatility`.
- Do not promote any other bucket yet.

Shock/EMA execution checkpoint on 2026-07-13:

- Scope: reviewed `11`-symbol crypto basket, Binance+Bybit, `15m`, `60d`.
- Shock-aware execution rows with EMA off by default: `78,744`.
- Exploratory EMA-inclusive rows: `89,640`.
- Best practical shock-aware bucket:
  - entry: `structure_confirmed_fvg_top_retest`;
  - target: `fixed_1_5r`;
  - management: `partial_1r_be_after_half_target`;
  - events: `192`;
  - symbols/exchanges: `11` symbols, Binance+Bybit;
  - avg R: `+0.371`;
  - median R: `+0.466`;
  - PF: `2.99`;
  - target rate: `27.6%`;
  - stop rate: `13.0%`;
  - expiry rate: `39.6%`.
- Prior comparable bucket without half-target shock management:
  - entry: `structure_confirmed_fvg_top_retest`;
  - target: `fixed_1_5r`;
  - management: `partial_1r_be`;
  - events: `192`;
  - avg R: `+0.358`;
  - PF: `2.56`;
  - stop rate: `17.7%`.
- Portfolio proxy for the new bucket with `max_open_trades=6`,
  `max_open_per_symbol=1`, daily loss cap `0.50%`:
  - `0.20%` risk/trade: `101` accepted, `+7.51%` return, `0.90%` max DD,
    return/DD `8.33`, PF `2.82`;
  - `0.25%` risk/trade: `97` accepted, `+9.21%` return, `1.13%` max DD,
    return/DD `8.17`, PF `2.85`.
- EMA verdict:
  - structure-confirmed top-retest weighted avg R: `+0.326`;
  - EMA+structure-confirmed top-retest weighted avg R: `+0.262`;
  - EMA remains optional behind `--include-ema-confirmed`.

Shock/EMA interpretation:

- The manual UI review was correct: violent movement must change market state.
- The stop model was not the main bug; entry state and management were.
- Shock-aware management improves risk quality more than EMA improves direction.
- The current promoted research bucket is shock-aware
  `structure_confirmed_fvg_top_retest + fixed_1_5r +
  partial_1r_be_after_half_target`.
- This is still not deployable until shock-aware discovery/holdout and UI sample
  review pass.

Trade-level forensic checkpoint on 2026-07-13:

- Scope: promoted shock-aware bucket with `0.20%` risk/trade, max `6` open
  trades, max `1` per symbol, daily loss cap `0.50%`.
- Accepted trades inspected: `101`.
- Candle windows reconstructed: `101/101`.
- Portfolio proxy: `+7.51%` return, `0.90%` max DD, PF `2.82`.
- Winner rate among accepted trades: `67.3%`.
- Median entry MAE: `-0.448R`.
- Stop exits: `14.9%`.
- Target exits: `27.7%`.
- Expiry exits: `40.6%`.
- Reached `1R`: `61.4%`.
- Reached half-target: `68.3%`.

Forensic failure split:

- Working: `68` trades, avg `+0.856R`.
- Direction/entry failure: `18` trades, avg `-0.684R`.
- Management/target failure: `5` trades, avg `-0.687R`.
- Entry/stop failure: `3` trades, avg `-1.055R`.
- Target/time-exit failure: `3` trades, avg `-0.480R`.
- Unknown: `4` trades, avg `-0.071R`.

Forensic path split:

- No follow-through: `32` trades, avg `-0.427R`.
- Clean target path: `31` trades, avg `+1.043R`.
- Expiry after progress: `20` trades, avg `+0.840R`.
- Partial follow-through: `8` trades, avg `+0.374R`.
- Gave back after `1R`: `6` trades, avg `+0.068R`.
- Gave back after half-target: `4` trades, avg `-0.321R`.

Forensic verdict:

- Still not a stop-placement problem.
- Biggest remaining failure is direction/entry: trades that never get even
  half-target follow-through.
- Management is improved but not finished. There are still giveback and expiry
  cases worth manual review.
- Weak accepted symbols in this portfolio sample: `1000PEPEUSDT`, `WLDUSDT`,
  `NEARUSDT`, `AVAXUSDT`.
- Stronger accepted symbols in this sample: `DOGEUSDT`, `ETHUSDT`, `XRPUSDT`,
  `LINKUSDT`, `SUIUSDT`.
- Generated UI packet:
  `backtesting/results/review_samples/crypto_shock_forensics_review_samples.csv`.
- The review UI now has exchange-specific loading for Binance/Bybit so manual
  labels do not mix exchange candles.

Trend/session matrix checkpoint on 2026-07-13:

- Scope: Binance only, reviewed `11`-symbol crypto basket, `15m`, `60d`.
- Reason for Binance-only: Binance and Bybit price action is similar enough for
  first-pass direction/session research. Exchange split should be reserved for
  robustness, fees, liquidity, and execution validation after a viable bucket is
  found.
- Total event rows: `278,770`.
- FVG event rows: `134,850`.
- Summary rows: `4,953`.
- Research-ready rows after single-exchange gates: `432`.
- Raw FVG event flow is not scarce. The low trade count in the promoted bucket
  comes from execution-selection filters: session, direction, structure,
  retest, duplicate suppression, and portfolio throttles.

Top event-level buckets from the matrix:

| Session | Direction | Context | EMA/trend state | Stop | Target | Events | Symbols | Avg R | PF | Stop |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|
| late US | short | 4H bull | counter global/structure | ATR | fixed 2R | 131 | 11 | +0.602 | 2.31 | 40.5% |
| late US | short | 4H bull | counter global/structure | event extreme | fixed 2R | 131 | 11 | +0.598 | 2.40 | 36.6% |
| late US | short | 4H bull | counter global/structure | prior swing | fixed 2R | 131 | 11 | +0.425 | 3.21 | 12.2% |
| Asia | short | 4H bull | 1H+15m bearish EMA | event extreme | fixed 2R | 117 | 11 | +0.387 | 1.86 | 37.6% |
| Asia | short | 4H bull | 1H+15m bearish EMA | prior swing | fixed 2R | 117 | 11 | +0.320 | 2.33 | 17.1% |
| London | long | 4H bull | 1H+15m bullish EMA | prior swing | fixed 2R | 181 | 10 | +0.240 | 1.82 | 22.7% |

Matrix interpretation:

- The current late-US short idea still appears in the best event-level rows, but
  it is explicitly a countertrend/flush bucket, not a general trend engine.
- Asia short with 1H+15m bearish EMA alignment is the first non-late-US short
  candidate.
- London long with 1H+15m bullish EMA alignment is the first cleaner
  trend-following candidate.
- Full all-timeframe trend alignment was not best at the raw event level. The
  useful helper appears to be middle/local EMA alignment, not blindly requiring
  4H EMA plus 4H structure to agree.
- Next step is not another broad backtest. It is execution-path validation for
  three candidates:
  1. late-US short countertrend, kept as benchmark;
  2. Asia short with middle/local bearish EMA;
  3. London long with middle/local bullish EMA.

Executable FVG session matrix checkpoint on 2026-07-13:

- Scope: Binance only, reviewed `11`-symbol crypto basket, `15m`, `60d`.
- Execution rows: `226,356`.
- Unique executable signals: `10,311`.
- Unique executable signal frequency:
  - about `15.6` executable signals per symbol over `60d`;
  - about `0.26` executable signals per symbol per day before final quality
    filters.
- Conclusion: the engine does not lack executable FVG retests. The scarcity is
  created by final strategy filters.

Top executable session/direction aggregates:

| Session | Direction | Trend state | Rows | Weighted avg R | Weighted stop | Max avg R | Max PF |
|---|---|---|---:|---:|---:|---:|---:|
| late US | short | counter global/structure | 1,524 | +0.294 | 18.6% | +0.473 | 3.67 |
| late US | short | global+middle bearish EMA | 3,186 | +0.262 | 18.5% | +0.533 | 3.04 |
| London | long | middle+local bullish EMA | 3,180 | +0.196 | 25.2% | +0.297 | 2.14 |
| Asia | short | middle+local bearish EMA | 960 | +0.168 | 21.1% | +0.216 | 1.82 |
| London | long | full trend | 3,990 | +0.127 | 32.1% | +0.290 | 1.65 |

Best non-late-US executable bucket:

- session: `London`;
- direction: `long`;
- context: `4H bull`;
- trend helper: `1H+15m bullish EMA`, global/4H EMA mixed;
- entry: `structure_confirmed_next_open`;
- confirmation: `latest_bull_regime`;
- target: `fixed_2r`;
- management: `be_after_half_target`;
- events: `134`;
- symbols: `10`;
- frequency: `0.262` events per symbol per day;
- avg R: `+0.297`;
- PF: `2.14`;
- target rate: `16.4%`;
- stop rate: `20.1%`;
- expiry rate: `54.5%`.

Best Asia candidate:

- session: `Asia`;
- direction: `short`;
- context: `4H bull`;
- trend helper: `1H+15m bearish EMA`;
- entry: `FVG CE retest` or `next open`;
- events: `60-100`;
- symbols: `11`;
- avg R: `+0.18R` to `+0.22R`;
- PF: `1.5-1.8`;
- verdict: weaker than London long and late-US short, but not dead.

Executable matrix interpretation:

- The current late-US short module remains the strongest executable bucket.
- Daytime is not dead. London long with middle/local EMA alignment is the first
  credible daytime module.
- Asia short is a secondary candidate, but lower edge and lower frequency.
- Full 4H/1H/15m trend alignment is not automatically best. The useful helper
  remains middle/local EMA alignment plus structure context.
- If the goal is one tradeable engine per asset per day, a single setup will not
  do it. The engine should become a module stack:
  - late-US short countertrend/flush module;
  - London long trend-continuation module;
  - optional Asia short pullback/flush module;
  - later, non-FVG event families if they survive execution testing.

Execution-path review:

- The survivor is not a clean `2R` target strategy.
- In the full `60d` sample it had `1170` observations:
  - target hit rate: `9.2%`;
  - stop hit rate: `19.7%`;
  - expiry exits: `71.0%`;
  - current net average: `+0.173R`;
  - current median: `+0.107R`.
- If expiry exits are forced flat after costs, expectancy drops to about
  `-0.053R`, PF `0.77`.
- If expiry exits are set to zero, expectancy is still negative at about
  `-0.029R`, PF `0.86`.
- A harsher expiry-exit haircut shows fragility:
  - `0.05R` haircut: avg `+0.132R`, PF `1.42`;
  - `0.10R` haircut: avg `+0.096R`, PF `1.29`;
  - `0.20R` haircut: avg `+0.025R`, PF `1.07`;
  - `0.30R` haircut: avg `-0.046R`, PF `0.88`.
- Approximate management variants:
  - breakeven after `+1R`: avg `+0.188R`, PF `1.67`;
  - `50%` partial at `+1R` plus current remainder: avg `+0.162R`, PF `1.59`;
  - `50%` partial at `+1R` plus breakeven remainder: avg `+0.169R`, PF `1.62`.

Execution verdict:

- The bucket is worth researching further, but not worth building as a normal
  fixed-TP strategy yet.
- The real hypothesis is: bearish FVG short in high-volatility late-US context
  has favorable short-horizon drift/continuation, not reliable `2R` target
  completion.
- Before a paper strategy, build an execution-path lab that tests:
  - market-vs-limit entry;
  - expiry close realism;
  - breakeven after `+1R`;
  - partial at `+1R`;
  - max adverse excursion before `+1R`;
  - no-trade filters for symbols where the bucket is negative.

Execution-path lab result:

- Lab file: `backtesting/crypto/execution_path_lab.py`.
- Scope: 14 symbols, Binance+Bybit, `15m`, `60d`.
- Bucket: bearish FVG, short, HTF bull, late US, high volatility, prior-swing
  stop, fixed `2R`.

| Entry model | Events | Avg R | Median R | PF | Target | Stop | Expiry |
|---|---:|---:|---:|---:|---:|---:|---:|
| FVG CE retest | 849 | +0.278 | +0.225 | 1.85 | 18.0% | 25.8% | 56.2% |
| FVG top retest | 761 | +0.269 | +0.214 | 1.80 | 17.5% | 26.8% | 55.7% |
| Next open | 1170 | +0.174 | +0.107 | 1.59 | 9.2% | 19.7% | 71.0% |
| Break continuation | 947 | +0.089 | +0.081 | 1.32 | 4.5% | 18.1% | 77.4% |

Discovery/holdout for CE retest:

- Discovery: `405` rows, avg `+0.330R`, PF `2.02`, target `23.2%`,
  stop `24.9%`, expiry `51.9%`.
- Holdout: `444` rows, avg `+0.230R`, PF `1.69`, target `13.3%`,
  stop `26.6%`, expiry `60.1%`.

Execution-path interpretation:

- The user concern was correct: next-open entry was weak.
- Waiting for FVG CE/top retest materially improves target rate and expectancy.
- Continuation-break entry is worse; it enters late and still mostly expires.
- This remains expiry-heavy, but less broken than next-open.
- Symbol filtering matters. Strong CE retest symbols included `LINK`, `XRP`,
  `DOGE`, `ETH`, `AAVE`, `SUI`, `AVAX`, `WLD`; weak/negative symbols included
  `BTC`, `BNB`, `HYPE`, and `SOL`.

Management and symbol-filter review:

- Added management variants:
  - hold to `2R` or expiry;
  - breakeven after `+1R`;
  - `50%` partial at `+1R`, hold remainder;
  - `50%` partial at `+1R`, breakeven remainder;
  - time stop;
  - market-expiry haircut.
- With `0.10R` expiry haircut, full-universe best rows:
  - CE retest + BE after `+1R`: `849` rows, avg `+0.291R`, PF `2.05`.
  - CE retest + hold `2R`: `849` rows, avg `+0.278R`, PF `1.85`.
  - Top retest + hold `2R`: `761` rows, avg `+0.269R`, PF `1.80`.
  - Top retest + partial `1R` hold: `761` rows, avg `+0.260R`, PF `1.94`.
  - Top retest + partial `1R` + BE: `761` rows, avg `+0.252R`,
    median `+0.387R`, PF `1.94`.
- Symbol-filtered best holdout candidates:
  - CE retest + BE after `+1R`, filtered to 11 symbols:
    holdout `372` rows, avg `+0.289R`, median `+0.240R`, PF `2.10`.
  - CE retest + `0.10R` expiry haircut, filtered to 10 symbols:
    holdout `333` rows, avg `+0.242R`, median `+0.177R`, PF `1.75`.
  - Top retest + partial `1R` + BE, filtered to 11 symbols:
    holdout `334` rows, avg `+0.282R`, median `+0.408R`, PF `2.09`.
  - Top retest + `0.10R` expiry haircut, filtered to 9 symbols:
    holdout `261` rows, avg `+0.285R`, median `+0.272R`, PF `1.85`.

Current strongest implementation hypothesis:

- Entry: bearish FVG top or CE retest.
- Direction/context: short only, HTF bull, late-US session, high volatility.
- Stop: prior swing high.
- Management: partial at `+1R` plus breakeven remainder, or CE retest with
  breakeven after `+1R`.
- Avoid weak symbols unless a later walk-forward promotion proves them:
  `BTC`, `BNB`, `HYPE`; possibly `SOL` depending on management model.

UI review threshold:

- UI review is now useful, but only for a small sample:
  - 10 winners and 10 losers from top retest + partial/BE;
  - 10 winners and 10 losers from CE retest + BE;
  - focus on whether the retest is visually real and whether prior-swing stop
    placement is structurally valid.

Session-module promotion checkpoint on 2026-07-13:

- Scope: Binance only, reviewed `11`-symbol crypto basket, `15m`, `60d`.
- Reason for single exchange: Binance/Bybit price action is similar enough for
  first-pass session/module research; exchange split is a later robustness and
  execution-cost check.

London long candidate:

- Filters:
  - session: `london`;
  - direction: `long`;
  - `4H` structure context: `bull`;
  - trend helper: `1H+15m bullish EMA`;
  - entry: `structure_confirmed_next_open`;
  - confirmation: `latest_bull_regime`;
  - target: `fixed_2r`;
  - management: `be_after_half_target`.
- Candidate trades: `143`.
- Portfolio-accepted trades: `69`.
- Symbols: `10`.
- Gross return at `0.20%` risk/trade: `+4.78%`.
- Max DD: `1.75%`.
- Return/DD: `2.73`.
- PF: `2.26`.
- Avg R: `+0.347`.
- Win rate: `56.5%`.
- Stop rate: `18.8%`.
- Expiry rate: `46.4%`.
- Forensic split:
  - working: `39` trades, avg `+1.100R`;
  - direction/entry failure: `15` trades, avg `-0.865R`;
  - management/target failure: `10` trades, avg `-0.098R`;
  - entry/stop failure: `4` trades, avg `-1.077R`;
  - target/time-exit failure: `1` trade, avg `-0.702R`.

Two-module stack:

- Modules:
  - late-US short benchmark: `53` accepted trades, avg `+0.355R`,
    total `+18.815R`, stop `22.6%`, expiry `54.7%`;
  - London long: `67` accepted trades, avg `+0.381R`,
    total `+25.548R`, stop `19.4%`, expiry `44.8%`.
- Combined candidate trades: `217`.
- Combined accepted trades: `120`.
- Symbols: `11`.
- Gross return at `0.20%` risk/trade: `+8.87%`.
- Max DD: `1.81%`.
- Daily max DD: `1.47%`.
- Return/DD: `4.91`.
- PF: `2.28`.
- Avg R: `+0.370`.
- Median R: `+0.271`.
- Win rate: `56.7%`.
- Stop rate: `20.8%`.
- Expiry rate: `49.2%`.

Session-module interpretation:

- The earlier user observation was directionally right: relying on one late-US
  short module leaves too much of the day unused.
- The engine is not missing raw FVG retests. The final strategy filters create
  low per-symbol frequency.
- Daytime is not dead. London long is the first credible daytime module and
  contributed more total R than the late-US benchmark in this in-sample stack.
- Still not enough for one trade per asset per day. Current frequency is about
  `2` accepted trades per day across the basket, but only about `0.18` accepted
  trades per symbol per day.
- Forcing daily trades per asset is a bad strategy unless new modules survive
  validation. Frequency should come from validated session modules, not looser
  filters.
- Next research target: rolling/discovery-holdout validation for the two-module
  stack, then optional Asia short promotion under the same gates.

London frequency and setup checkpoint on 2026-07-13:

- User review of the London-long sample was mostly positive:
  - `11` saved London labels across `LINKUSDT`, `SOLUSDT`, and `XRPUSDT`;
  - `7` explicit good labels;
  - recurring notes: targets sometimes too far for intraday, entries sometimes
    late, and consolidation/accumulation after big movement is not modeled.
- Frequency problem split:
  - UI sample scarcity: the prior London review packet was intentionally small.
  - Engine scarcity: current module filters produce only `143` candidates and
    `69` portfolio-accepted trades.
  - Raw opportunity is not scarce: broad London-long `fixed_2r +
    be_after_half_target` has `5,147` rows, but it loses money as a module.

London filter funnel:

| Stage | Candidates | Accepted | Avg R | PF | Return | Max DD | Stop | Expiry |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all London long `2R` + BE half | `5,147` | `355` | `-0.017R` | `0.96` | `-1.21%` | `6.42%` | `32.1%` | `42.5%` |
| + `4H` bull | `3,720` | `315` | `-0.004R` | `0.99` | `-0.25%` | `6.13%` | `33.0%` | `38.4%` |
| + `1H+15m` bullish EMA | `627` | `78` | `+0.350R` | `2.26` | `+5.45%` | `1.82%` | `19.2%` | `46.2%` |
| + structure-confirmed next open | `146` | `70` | `+0.345R` | `2.27` | `+4.83%` | `1.75%` | `18.6%` | `47.1%` |
| current latest-bull-regime | `143` | `69` | `+0.347R` | `2.26` | `+4.78%` | `1.75%` | `18.8%` | `46.4%` |

London setup lab:

- Research file: `backtesting/crypto/session_setup_lab.py`.
- Review packet:
  `backtesting/results/review_samples/crypto_london_setup_lab_review_samples.csv`.
- Tested causal entry-bar setup features:
  - bullish body close near high;
  - bullish engulfing;
  - lower-wick rejection;
  - micro-range break;
  - pre-entry compression;
  - early London timing;
  - entry exhaustion filter.

Setup-lab result:

| Variant | Candidates | Accepted | Avg R | PF | Return | Max DD | Stop | Accepted/symbol/day |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `1H+15m` bullish EMA | `627` | `78` | `+0.350R` | `2.26` | `+5.45%` | `1.82%` | `19.2%` | `0.152` |
| + any structure entry confirmation | `267` | `73` | `+0.373R` | `2.42` | `+5.45%` | `1.35%` | `17.8%` | `0.143` |
| + rejection or micro-break | `118` | `35` | `+0.634R` | `5.63` | `+4.44%` | `0.69%` | `8.6%` | `0.068` |
| + candle confirmation | `120` | `33` | `+0.632R` | `4.60` | `+4.17%` | `0.91%` | `12.1%` | `0.065` |
| early London only | `243` | `46` | `+0.304R` | `2.18` | `+2.80%` | `0.95%` | `17.4%` | `0.090` |
| all London long | `5,147` | `355` | `-0.017R` | `0.96` | `-1.21%` | `6.42%` | `32.1%` | `0.555` |

Setup-lab interpretation:

- Your frequency complaint is correct, but the fix is not simply allowing every
  visible London entry. Broad London-long entries are low-quality.
- Best current direction: use `1H+15m` bullish EMA as the core daytime direction
  gate, then test candle/rejection/micro-break confirmation for quality.
- Candle/setup confirmation improves trade quality sharply but lowers accepted
  frequency to about `0.065-0.068` trades per symbol per day.
- The frequency-quality compromise is currently `1H+15m` bullish EMA plus any
  structure entry confirmation: `267` candidates, `73` accepted, `+0.373R`, PF
  `2.42`, DD `1.35%`.
- Weak symbols under the middle/local bullish London setup: `NEARUSDT`,
  `SOLUSDT`, `AVAXUSDT`. Do not exclude them permanently yet; validate with
  walk-forward symbol promotion.

Research notes from external literature:

- Bitcoin activity and volatility are not uniform through the day; European and
  US daytime hours show higher volume/volatility in published intraday Bitcoin
  research.
- Crypto intraday predictability can flip between momentum and reversal, and
  large jumps change the pattern. This supports explicit shock/consolidation
  state instead of fixed SMC rules.
- Candlestick evidence is mixed, but Bitcoin-specific work found engulfing
  fertile among classical patterns. Treat this as a confirmation feature, not a
  standalone strategy.
- Opening-range/breakout literature supports testing range breakout as a
  mechanical setup, but crypto needs session-defined pseudo-opens because it
  trades `24/7`.

## Validation Gates

Minimum gates before strategy construction:

- `200+` events before trusting a bucket.
- Net `avg_r > 0`.
- Profit factor `>= 1.20` as a research minimum.
- Rolling windows positive enough to avoid one lucky month.
- No single symbol, exchange, or window contributes more than about half the result.

## Current Recommendation

Do not code another strategy yet.

Next concrete work:

1. Run rolling/discovery-holdout validation for the late-US short + London long
   module stack.
2. UI-review London setup lab samples using
   `backtesting/results/review_samples/crypto_london_setup_lab_review_samples.csv`,
   especially `setup_confirm_loser` and `no_confirm_winner`.
3. Run holdout validation for London setup variants:
   - `middle_local_bull_any_entry_confirm`;
   - `middle_local_bull_rejection_or_break`;
   - `middle_local_bull_candle_confirm`.
4. Promote Asia short only if it survives the same execution, portfolio, and
   holdout gates.
5. Add walk-forward symbol filtering to session modules instead of static
   symbol exclusions.
6. Add trade-frequency, overlap/correlation, and drawdown controls before
   judging returns.
7. Add multi-asset refresh for FX/metals/indices before comparing asset classes.
