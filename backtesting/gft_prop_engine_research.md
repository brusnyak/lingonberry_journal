# GFT Prop Engine Research Notes

Last updated: 2026-06-26

## Target Accounts

Primary firm: Goat Funded Trader.

| Account | Model | Target | Daily DD | Max Loss | Notes |
|---|---:|---:|---:|---:|---|
| 25k | 2 Step GOAT | 8% then 6% | 4% | 10% static | 3 valid trading days per phase |
| 100k | 1 Step | 10% | 4% | 6% static | 3 valid trading days |

Source notes:

- GFT 2 Step GOAT FAQ says 8% and 6% phase targets, 4% daily drawdown, 10% static max loss.
- GFT 1 Step FAQ says 10% target, 4% daily drawdown, 6% static max overall loss.
- GFT leverage in evaluation: forex 1:100, indices/commodities 1:20, crypto 1:2.

## Current Verdict

The current branch is directionally correct but not deployment-ready.

Proven locally:

- Review UI/API now runs `TrFvg` and `TrIct` on the ICT branch.
- FX data coverage is broad on 5m+ timeframes.
- XAUUSD currently produces the only meaningful TrIct sample among GBPAUD/EURUSD/XAUUSD.
- Prior portfolio-style FX results looked good in-sample, then failed walk-forward.
- Causal structure parity passed first sampled online/full-history checks for XAUUSD and NAS100 5m.
- Direction accuracy and target-before-stop studies now exist under `backtesting/scripts/`.
- V1 can be sliced by direction, session, HTF requirement, RR, and structure-cut behavior.

Assumed:

- Gold and NAS100 are allowed for the target accounts.
- Structure-based logic is still the best candidate because it can define invalidation, partial exits, and re-entry.

Unknown:

- Whether structure labels are stable enough online versus full-data computation.
- Whether structure labels are stable enough across all target symbols/timeframes.
- Whether NAS100 has a tradable structure edge; current direction tests show multiple NAS bearish anti-edge pockets.
- Whether FX pairs can produce enough quality trades without forcing activity; GBPAUD short NY has a directional pocket, but V1 failed the 120D strategy check.

## Engine Direction

Build one market-state engine, not a pile of entry scripts.

State stack:

1. Macro state: 4H/1H HH-HL or LH-LL bias.
2. Session state: Asian range, London/NY open, prior day high/low.
3. Trigger state: liquidity sweep into discount/premium.
4. Confirmation state: MSS/ChoCH with displacement.
5. Entry state: FVG CE or OB retest.
6. Management state: partials, structure trailing, reduce/exit on adverse structure flip.
7. Re-entry state: allow one fresh intraday re-entry only if the thesis rebuilds.

Failure mode to avoid:

- Holding a losing trade until fixed SL when 1m/5m structure has already invalidated the setup.
- Re-entering because price is "still near the level" instead of requiring a fresh sweep/MSS.
- Optimizing a single month into a fake pass.

## Research Resources

Use these as references, not dependencies to blindly adopt.

| Resource | What to borrow | What not to do |
|---|---|---|
| cTrader Open API Python SDK | Demo execution adapter and market-data fetch path; official Spotware SDK uses Twisted async callbacks | Do not connect this to GFT live accounts until demo gate is passed |
| Freqtrade lookahead analysis | Bias-check command concept: perturb/delay features and fail suspicious results | Do not migrate to Freqtrade |
| Freqtrade recursive analysis | Online-vs-full-data indicator stability checks | Do not trust full-data indicators until checked |
| smartmoneyconcepts Python package | Cross-check FVG, swing, BOS/ChoCH, OB, liquidity definitions | Do not outsource our engine edge to a package |
| vectorbt | Fast parameter grid and walk-forward result inspection ideas | Do not replace event-based trade management with pure vectorization |
| Crypto branch `feature/crypto-scaling-engine` | Walk-forward helper, challenge-style reporting, data audit style, explicit exchange/resource separation | Do not import leverage/funding/liquidation UI into GFT forex/index review |

## Execution Gate

No code should interact with TradeLocker or GFT-funded accounts until these gates pass:

1. Backtest gate
   - Rolling 30D windows with GFT rule reporting.
   - Lookahead/recursive checks passed.
   - Review UI confirms representative winners and losers.

2. cTrader demo gate
   - Official cTrader Open API SDK only.
   - Demo account only.
   - Read account, symbols, quotes, positions, orders.
   - Place/modify/close tiny demo trades behind `CTRADER_DEMO_EXECUTION_ENABLED=true`.
   - Full audit log for every signal, decision, order, modification, and close.

3. TradeLocker demo gate
   - Same adapter contract as cTrader.
   - No live credentials loaded by default.
   - Same audit log and kill-switch behavior.

4. GFT live gate
   - Manual approval per release.
   - Daily loss guard enforced locally before every order.
   - Max loss guard enforced locally before every order.
   - No overnight position unless explicitly configured.

## Domain and OAuth Callback

Current check on 2026-06-26:

- `recareo.uk` uses Cloudflare nameservers.
- Local Wrangler is logged in and can read the Cloudflare account.
- Local `cloudflared` is installed, but no origin cert is configured.
- `recareo.uk` and `www.recareo.uk` currently resolve to Vercel IPs and return `DEPLOYMENT_NOT_FOUND`.
- The registered cTrader redirect URL `https://recareo.uk/callback` will not work until the domain points to a valid deployment or Worker.

Recommended options:

1. Cloudflare Worker callback
   - Fastest for OAuth testing.
   - Route `recareo.uk/callback*` to a Worker that displays the short-lived `code`.
   - Do not exchange/store tokens in the Worker until secrets handling is designed.

2. Webapp callback
   - Deploy this Flask app behind the domain.
   - `/callback` already displays the short-lived auth code.
   - Better once the journal app is actually hosted.

3. Temporary Playground only
   - Use `https://openapi.ctrader.com/apps/{client_id}/playground` for manual token generation.
   - Good for immediate data fetch tests.
   - Not a real app callback.

cTrader auth flow:

1. User grants access through the Open API URL with `client_id`, `redirect_uri`, and `scope`.
2. cTrader redirects to `redirect_uri?code=...`.
3. App exchanges the short-lived code for access/refresh tokens using `/apps/token`.
4. App sends `ProtoOAApplicationAuthReq`.
5. App sends `ProtoOAGetAccountListByAccessTokenReq`.
6. App sends `ProtoOAAccountAuthReq` for the chosen `ctidTraderAccountId`.

For this project, default scope should be `accounts` until demo execution testing starts. Use `trading` only for cTrader demo execution gate.

## Next Tests

Run these before adding complexity:

1. `structure_online_parity`
   - Compare full-run structure labels against online incremental recomputation.
   - Fail if BOS/ChoCH/FVG timestamps shift materially.

2. `xauusd_structure_manager_v1`
   - XAUUSD 5m/30m/240m.
   - Risk search: 0.10-0.50%.
   - Measure fixed SL versus structure-cut exits.
   - Required output: rolling 30D return, max DD, max daily loss, WR, avg R, trades/day.

3. `nas100_data_normalization`
   - Convert `USATECHIDXUSD*.csv` to standard schema.
   - Verify date ranges and session gaps.
   - Only then run structure tests.

4. `fx_basket_starvation_check`
   - GBPJPY, GBPUSD, EURUSD, GBPAUD.
   - Goal: prove whether FX has enough quality setups.
   - If most windows have fewer than 10 trades, do not force FX.

5. `gft_account_report`
   - Same trades evaluated on 25k 2-step GOAT and 100k 1-step.
   - Include pass/fail per 30D window, not aggregate totals.

## First Structure Candidate Result

Command:

```bash
python3 -m backtesting.scripts.run_prop_structure_v1 --symbol XAUUSD --start 2026-05-24 --end 2026-06-23 --risk-pct 0.25
python3 -m backtesting.scripts.run_prop_structure_v1 --symbol NAS100 --start 2026-05-24 --end 2026-06-23 --risk-pct 0.25
```

Result:

| Symbol | Trades | WR | PF | Return | Max DD | Verdict |
|---|---:|---:|---:|---:|---:|---|
| XAUUSD | 42 | 30.9% | 1.00 | -0.02% | 4.17% | Reject: DD too high, no edge |
| NAS100 | 39 | 41.0% | 0.84 | -1.01% | 2.09% | Reject: negative edge |

This is useful because it proves raw sweep -> structure break -> structural SL is not enough. Next version needs better direction filter, entry quality filter, and active structure-cut management.

## Direction and Target Study Result

Commands:

```bash
python3 -m backtesting.scripts.structure_direction_accuracy --days 120 --symbols XAUUSD,NAS100,GBPJPY,GBPUSD,EURUSD,GBPAUD --tag structure_direction_accuracy_120d
python3 -m backtesting.scripts.structure_target_study --days 120 --symbols XAUUSD,NAS100,GBPJPY,GBPUSD,EURUSD,GBPAUD --tag structure_target_study_120d --min-n 30
python3 -m backtesting.scripts.structure_target_study --days 120 --symbols GBPAUD,XAUUSD,EURUSD,NAS100 --predictors entry_plus_htf_bear,htf_regime_bull,bos_down,entry_regime_bull --sessions ny_open,london_open,asia --tag structure_target_study_focus_120d --min-n 30
```

Key reads:

| Slice | n | Read |
|---|---:|---|
| EURUSD HTF-bull long London | 36 | Good target math, but latest 30D V1 produced 0 trades |
| GBPAUD entry+HTF bear short NY | 2,140 | Positive but modest: `exp_1.5R +0.11R`, `exp_2R +0.14R` |
| XAUUSD BOS-down short NY | 88 | Better target quality: `exp_1R +0.22R`, `exp_2R +0.28R` |
| NAS100 HTF/entry bear short | 5,000+ | Multiple anti-edge pockets; do not assume bearish structure means short edge |

V1 focused strategy checks:

| Config | Window | Trades | WR | PF | Return | Max DD | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| GBPAUD short NY, HTF, 1.5R, no structure-cut | 2026-05-24..2026-06-23 | 7 | 57.1% | 1.52 | +0.46% | 0.61% | Too small |
| GBPAUD short NY, HTF, 2R, no structure-cut | 2026-05-24..2026-06-23 | 7 | 57.1% | 2.02 | +0.92% | 0.63% | Best 30D slice, still too low |
| GBPAUD short NY, HTF, 2R, no structure-cut | 2026-02-24..2026-06-23 | 28 | 32.1% | 0.74 | -1.45% | 3.27% | Reject |
| XAUUSD short Asia, 2R, no structure-cut | 2026-02-24..2026-06-23 | 61 | 39.3% | 1.23 | +4.21% | 3.57% | Research-only |

Plain conclusion: target choice matters after direction is right, but direction is not reliably right globally. V2 must select directional pockets first, then test entry/target construction. Optimizing V1 targets without that filter is bullshit curve fitting.

## Strict ICT Structure Direction

Simplified ICT sequence now used for direction research:

```text
bullish: HH/HL + bullish BOS
bearish warning: bearish CHoCH below protected HL
bearish setup: new LL + LH
bearish confirmed: bearish BOS below new LL

bearish: LL/LH + bearish BOS
bullish warning: bullish CHoCH above protected LH
bullish setup: new HH + HL
bullish confirmed: bullish BOS above new HH
```

CHoCH alone is not direction. It is transition/no-trade until the opposite structure confirms with BOS.

External source checks:

- Just2Trade's forex market-structure guide defines bullish structure as higher highs plus higher lows, bearish structure as lower highs plus lower lows, BOS as a break in the trend direction, and CHOCH as breaking the structural level against the trend. It explicitly warns that CHOCH does not guarantee reversal; it means continuation is uncertain.
- Rosemary Ekong's Medium notes define a swing high/low using surrounding candles, explain that fractal swing detection lags by several candles, and anchor BOS/CHOCH to protective swing points. This supports our causal `left/right` pivot confirmation and the rule that CHOCH is transition, not automatic reversal.
- Additional reference checks agree on the same mechanical interpretation: BOS is trend-continuation through a prior swing level, CHOCH is a break against current structure, and higher highs/higher lows versus lower highs/lower lows define the trend state. Investopedia's pivot/fractal references also support the idea that confirmed pivots are lagging, not predictive, so they must be used causally.
- Practical implication for code: default to confirmed pivots, require candle-close BOS, use protected HL/LH as invalidation, and label range/transition as no-trade.

New files:

- `backtesting/features/ict_structure.py`
- `backtesting/scripts/ict_structure_audit.py`
- `backtesting/scripts/ict_direction_accuracy.py`
- `backtesting/tests/test_ict_structure.py`

SMC reference check:

```bash
python3 -m pip install --no-deps smartmoneyconcepts==0.0.27
python3 -m backtesting.scripts.ict_structure_audit --symbol XAUUSD --tf 5 --days 30 --events 20
```

XAUUSD latest 30D result:

| Engine | Swings | BOS | CHoCH | Read |
|---|---:|---:|---:|---|
| Strict ICT local | 1,298 | 85 | 84 | Controlled enough for direction testing |
| `smartmoneyconcepts` reference | 1,536 | 378 | 203 | Useful reference, too noisy/permissive for production direction without causal filtering |

Strict ICT 120D triple-barrier direction:

```bash
python3 -m backtesting.scripts.ict_direction_accuracy --days 120 --symbols XAUUSD,NAS100,GBPJPY,GBPUSD,EURUSD,GBPAUD --tag ict_direction_accuracy_120d --min-n 20
```

| Slice | n | Hit 1R | Exp 1R | Exp 1.5R | Exp 2R |
|---|---:|---:|---:|---:|---:|
| XAUUSD bearish BOS NY | 24 | 58.3% | +0.38R | +0.40R | +0.52R |
| EURUSD bearish BOS Asia | 59 | 55.9% | +0.30R | +0.27R | +0.25R |
| GBPAUD bullish BOS NY | 23 | 47.8% | +0.24R | +0.29R | +0.40R |
| NAS100 bullish BOS Asia | 49 | 46.9% | +0.19R | +0.22R | +0.24R |

This is a better direction framework than the loose regime test. Next test should widen sample with rolling windows and review UI screenshots for the top/bottom 50 events.

Swing sensitivity check:

```bash
python3 -m backtesting.scripts.ict_direction_accuracy --days 120 --symbols XAUUSD,NAS100,GBPJPY,GBPUSD,EURUSD,GBPAUD --left 3 --right 3 --tag ict_direction_accuracy_120d_l3r3 --min-n 15
```

`left=3/right=3` is cleaner than `2/2` for current research:

| Slice | n | Hit 1R | Exp 1R | Exp 2R | Read |
|---|---:|---:|---:|---:|---|
| XAUUSD bearish BOS Asia | 35 | 62.9% | +0.39R | +0.36R | Best strict ICT pocket |
| XAUUSD bearish BOS NY | 15 | 53.3% | +0.35R | +0.43R | Good but small |
| EURUSD bearish BOS Asia | 45 | 48.9% | +0.30R | +0.34R | Candidate |
| GBPAUD bearish BOS NY | 25 | 40.0% | +0.21R | +0.43R | Better at 1.5R/2R than 1R |

Default candidate for strict direction research: `left=3/right=3`, not `2/2`.

Rolling 30D stability over 180D:

```bash
python3 -m backtesting.scripts.ict_direction_rolling --days 180 --symbols XAUUSD,NAS100,GBPJPY,GBPUSD,EURUSD,GBPAUD --tag ict_direction_rolling_180d_l3r3 --min-n 5 --min-windows 4 --target 1r
python3 -m backtesting.scripts.ict_direction_rolling --days 180 --symbols XAUUSD,NAS100,GBPJPY,GBPUSD,EURUSD,GBPAUD --tag ict_direction_rolling_180d_l3r3_15r --min-n 5 --min-windows 4 --target 1.5r
python3 -m backtesting.scripts.ict_direction_rolling --days 180 --symbols XAUUSD,NAS100,GBPJPY,GBPUSD,EURUSD,GBPAUD --tag ict_direction_rolling_180d_l3r3_2r --min-n 5 --min-windows 4 --target 2r
```

Lead direction candidates:

| Slice | Target | Windows | Positive | Median Exp | Worst Exp | Read |
|---|---:|---:|---:|---:|---:|---|
| XAUUSD bearish BOS Asia | 1R | 11 | 9 | +0.33R | -0.22R | Best stable lead |
| XAUUSD bearish BOS Asia | 1.5R | 11 | 9 | +0.41R | -0.16R | Better target profile |
| XAUUSD bearish BOS Asia | 2R | 11 | 8 | +0.38R | -0.25R | Still holds |
| GBPUSD bearish BOS NY | 1.5R | 7 | 7 | +0.43R | +0.05R | Clean but small sample |
| NAS100 bullish BOS London | 1.5R | 6 | 5 | +0.51R | -0.28R | Interesting, sample too small |

Manual review sample:

```bash
python3 -m backtesting.scripts.ict_review_samples --events backtesting/results/ict_direction_rolling_180d_l3r3_events.csv --symbol XAUUSD --predictor bearish_bos --session asia --direction short --target 1.5r --n 10 --tag ict_review_samples
```

Output: `backtesting/results/ict_review_samples_XAUUSD_bearish_bos_asia_1.5r.csv`.

Next review task: load the top 10 and worst 10 XAUUSD Asia bearish BOS events into the review UI and inspect whether the BOS line, protected LH/HL, and transition state are visually correct.

## Next Build Step

Build Prop Firm Structure V2 as an event-to-trade engine:

1. Start from proven directional pockets only:
   - XAUUSD short Asia/NY after bearish BOS or confirmed bear regime.
   - GBPAUD short NY only when entry and HTF regimes agree.
   - EURUSD long London HTF-bull as a separate candidate because V1 does not currently generate entries there.
2. Replace blunt structure-cut with staged management:
   - cut only on adverse BOS/ChoCH after entry plus failure to reclaim;
   - otherwise reduce risk or move stop to BE after 0.75R/1R.
3. Add target candidates from the target study:
   - fixed 1R/1.5R/2R;
   - opposing liquidity/session high-low;
   - hybrid: first partial at 1R, runner to 2R or structure trail.
4. Report rolling 30D windows, not one 120D aggregate.

## Decision Rule

Promote a candidate only if:

- At least 6 rolling 30D OOS windows.
- 5/6 windows positive.
- Worst 30D return not worse than -1%.
- Max DD mostly below 2%, hard cap 3%.
- No daily loss above 1.5%.
- No lookahead/recursive structure failure.

Anything weaker is research-only.
