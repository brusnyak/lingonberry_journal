# Prop Firm Engine — Development Plan

Last updated: 2026-06-26

## Goal

Build a mechanical trading engine that can pass Goat Funded Trader challenges:

- 25k 2 Step GOAT account.
- 100k 1 Step account.

The target is not a pretty full-period backtest. The target is repeated 30-day challenge windows with enough return, low drawdown, and no rule breaches.

## Data Summary (Manual Trades)

| Trigger | Wins | Losses | WR |
|---------|------|--------|----|
| CHoCH/BOS | 52 | 4 | 93% |
| Liquidity sweep | 27 | 4 | 87% |
| FVG 50% entry | 13 | 2 | 87% |
| OB retest | 55 | 20 | 73% |

**Session breakdown**: London dominates (91W/23L), NY has better WR (89%). Balanced long/short.

**Key insight**: These are actual trades with notes like "entry after choch/bos to collect asia liquidity aiming at 50% of order block accumulation." The strategy is in your head — we codify it.

## Core Philosophy

Structure is the operating model, but structure is not magic. The engine must prove:

1. Direction filter: higher-timeframe state gives enough directional accuracy.
2. Entry quality: sweep/MSS/FVG/OB sequence beats random intraday noise.
3. Risk control: if structure changes against the trade, the trade is cut or reduced before a full stop whenever possible.
4. Re-entry logic: one failed entry does not invalidate the daily thesis, but re-entry requires a fresh structure state.
5. Challenge fit: every result is judged by 30-day windows and GFT drawdown rules.

Bullshit failure mode: calling a discretionary chart idea an "engine" before it survives rolling OOS windows.

Current evidence: structure direction is not globally correct. It is asset/session/regime-specific. XAU short Asia and GBPAUD short NY have useful pockets; XAU HTF-bull London/NY and NAS100 HTF-bear are anti-edge in the latest 120D direction test.

Direction fix: use strict ICT sequencing, not loose regime labels. Bullish direction requires HH/HL plus bullish BOS. Bearish direction requires bearish CHoCH, new LL/LH, then bearish BOS. CHoCH alone is transition/no-trade.

## Strategy Architecture

```
4H (240m) ──► HH/HL/LH/LL labels ──► macro bias (bullish/bearish)
1H (60m)   ──► HH/HL/LH/LL labels ──► intermediate bias (confluence)
15m        ──► HH/HL/LH/LL labels ──► sweep + MSS detection + structural SL
1m (or 5m) ──► HH/HL/LH/LL labels ──► FVG detection + entry + trailing SL
```

Structure (HH/HL = bullish, LH/LL = bearish) everywhere. Labels are consistent across all timeframes using the same algorithm with different swing lengths.

### Entry Sequence (Mandatory — all 6 steps must pass)

```
1. 4H structure bullish/bearish → bias set
2. 1H structure same direction → confluence (TEST: both vs either vs 4H only)
3. 15m sweep: price wicks beyond a swing point (LL for longs, HH for shorts)
   AND body closes back inside → sweep confirmed
4. 15m MSS: after the sweep, price breaks a swing point in the bias direction
   with displacement (aggressive body close, often with FVG)
5. 1m/5m FVG forms in the bias direction during MSS displacement
6. 1m/5m price retraces into the FVG → entry on limit at FVG CE (50% level)
```

Sweep detection rules (from ICT methodology):
- **Wick-rejection**: wick extends beyond the swing, body closes inside
- **Close-reclaim**: body briefly closes beyond, next bar reverses inside
- **No sweep = no setup** — price drifting to a level without stop-hunt is not an ICT reversal setup
- **MSS required** (not just CHoCH) — CHoCH without sweep context is a warning, not a trade signal
- All signals use `close[1]` (confirmed previous bar), never `close[0]`

### Stop Loss

Structural — placed beyond the swept level with ATR buffer:

- **Long**: stop below the swept LL + 0.5× ATR(14) buffer
- **Short**: stop above the swept HH + 0.5× ATR(14) buffer

If price returns to re-sweep the level, the stop holds. If structure breaks against us (new LL below for longs, new HH above for shorts), we exit.

### Exit System (Hybrid — Partial Scale-Out)

| Level | Allocation | Trigger | Action |
|-------|-----------|---------|--------|
| TP1 | **50%** | Nearest target | Close, move stop to BE |
| TP2 | **30%** | Further target | Close |
| Runner | **20%** | Structure trailing | Trail on 1m HL/LH until stopped |

Also testing: 50/50, 30/30/40, 100 (single exit).

**Targets evaluated** (trade hits the nearest one first):
1. Previous daily high/low
2. Previous 1H session high/low
3. 50% FVG level (consequent encroachment)
4. Fib extension: 1.0× / 1.272× / 1.618× of the MSS swing range

**Trailing method for runner (20%)**: 1m structure labels. New 1m HL = raise trailing stop for longs. New 1m LH = lower trailing stop for shorts. Exit when 1m CHoCH fires — structure has shifted, we're done.

### Fibonacci for TP

```
Long setup (example):
  15m MSS sweep low = L, MSS swing high = H
  Range = H - L
  TP1: H + 1.0 × Range
  TP2: H + 1.272 × Range
  TP3: H + 1.618 × Range
```

This adapts to current volatility automatically. In high-volatility periods the swing range is wider → TPs are further apart. In low-volatility periods TPs are tighter.

## Cost Model

- **Spread**: random uniform 1-3 pips on entry + 0.5-1.5 pips on exit
- **SL slippage**: random 0-1 pip extra on stop hits
- **Commission**: $0.75 per side ($1.50 round-trip)
- **Minimum stop rule**: stop distance must be ≥ 5× average spread

This matches the industry-standard cost model. Previously in strategy_v2.py.

## Prop Firm Rules (Non-Negotiable)

Primary source: Goat Funded Trader FAQ, checked 2026-06-26.

| Account | Model | Target | Daily DD | Max Loss | Min Trading Days | Leverage Eval |
|---------|-------|--------|----------|----------|------------------|---------------|
| 25k | 2 Step GOAT | Phase 1: 8%, Phase 2: 6% | 4% | 10% static | 3 days each phase | FX 1:100, indices/commodities 1:20 |
| 100k | 1 Step | 10% | 4% | 6% static | 3 days | FX 1:100, indices/commodities 1:20 |

Internal pass gate is stricter than the firm:

| Gate | Requirement |
|------|-------------|
| Rolling window | Every 30D test window reported separately |
| Max DD | Prefer <2%; reject >3% unless return is exceptional |
| Daily loss | Prefer <1.5%; hard reject near 4% |
| Return | 25k 2-step phase target: 8% and 6%; 100k 1-step target: 10% |
| Trades | Zero-trade days allowed; forced activity is a bug |
| Risk/trade search | 0.10%, 0.15%, 0.20%, 0.25%, 0.30%, 0.40%, 0.50% |

Binding constraint: 100k 1-step has only 6% static max loss, so it controls the portfolio risk design.

## Realistic Expectations

| Metric | Manual | Mechanical (Expected) |
|--------|--------|----------------------|
| Win rate | 83% | 55-65% |
| Risk:Reward | 1:1.5-1:2 | 1:1.5-1:2 |
| 30D return | — | 6-10% only after OOS proof |
| Max DD | — | <2-3% preferred |
| Trades/day | — | 1-3 |

**Why the drop**: Discretionary + hindsight vs. mechanical rules. The edge is real, but execution won't be perfect.

## Test Matrix — First Sweep

| Variable | Values | Purpose |
|----------|--------|---------|
| Assets | XAUUSD, NAS100, GBPJPY, GBPUSD, EURUSD, GBPAUD | Gold and NAS are allowed; FX remains the structure thesis |
| Bias TF | 4H only, 1H only, 4H+1H same | Test all |
| Entry TF | 1m, 5m | Compare noise vs precision |
| Sweep | Required, Not required | Test filter impact |
| Partials | 50/30/20, 50/50, 30/30/40, 100 (single) | Test all |
| Targets | Daily, Session, 50% FVG, Fib exts, ALL | Test individually |
| Trade management | fixed SL, structure-cut, scale-down-on-CHoCH, re-entry allowed once | Test whether structure monitoring reduces DD |
| Data window | rolling 30D + 7-14D structure warmup | Challenge-realistic comparison |

First target is not max return. First target is a stable profile: positive 30D return, DD below 2-3%, no daily breach, and no obvious lookahead.

## Data Sources

| Asset class | State |
|-------------|-------|
| FX majors/crosses | 21 symbols with 5m/15m/30m/60m/240m coverage to 2026-06-23; 1m is shorter, roughly from 2026-03-16 |
| Gold | XAUUSD available and currently produces the most TrIct trades |
| NAS100 | CSV exists, but format/history must be normalized before serious tests |
| Crypto | Useful architecture from `feature/crypto-scaling-engine`, but not part of this GFT forex/index/commodity challenge engine |

## Obsidian Vault

The existing `/Trading/` directory in Obsidian contains previous V2 work that is known to have issues (overfitting, missing spread model, flawed rolling analysis). This data is **not relied upon** for Prop Firm Engine decisions.

Action: archive old content, rebuild with only validated results from our own sweep runs.

## Work Plan

### Phase 1: Correctness + Review Surface
- [x] Review UI can run TrFvg and TrIct without crypto leverage controls.
- [x] TrIct review API uses structure warmup before the selected test window.
- [x] Remove hardcoded cTrader credentials from data fetch script.
- [x] Normalize NAS100 data into standard `ts/open/high/low/close/volume` schema.
- [x] Add GFT account presets to reporting: 25k 2-step GOAT and 100k 1-step.
- [ ] Add rule-breach columns to every result: return target hit, max daily loss, static max loss, min valid days.

### Phase 2: Engine Candidate
- [x] Build first `backtesting/strategies/prop_firm_structure_v1.py` candidate.
- [ ] Implement state machine: HTF bias -> liquidity sweep -> MSS/ChoCH -> FVG/OB retest -> entry.
- [ ] Add active structure monitor: exit/reduce if 1m/5m structure flips against the trade.
- [x] Add direction/session/no-structure-cut controls to the V1 runner.
- [x] Add direction accuracy test for causal structure predictors.
- [x] Add target-before-stop study for 0.5R/1R/1.5R/2R/3R.
- [x] Add strict ICT structure module: HH/HL -> CHoCH -> LL/LH -> BOS down, and mirror for bullish.
- [x] Add SMC/zigzag audit script for structure sanity checks.
- [x] Add strict ICT triple-barrier direction accuracy script.
- [ ] Add intraday re-entry: max 1-2 attempts per thesis, only after fresh sweep/MSS.
- [ ] Add target hierarchy: opposing liquidity first, then partials, then structure runner.
- [ ] Run first sweep on XAUUSD, then NAS100 after normalization, then FX basket.

### Phase 3: Validate (This Week)
- [ ] Review sweep results, fix bugs
- [ ] Run rolling 30D windows with 7-14D structure warmup.
- [x] Add first online parity check for causal structure features.
- [ ] Expand parity checks across all target assets/timeframes before trusting any result.
- [ ] Test account sizes/rules separately: 25k 2-step GOAT, 100k 1-step
- [ ] Archive deprecated Obsidian content
- [ ] Document validated configs

### Phase 4: Deploy (Next Week)
- [ ] cTrader demo adapter: read account, quotes, positions, and orders.
- [ ] cTrader demo paper execution only: place/modify/close micro trades behind a hard safety flag.
- [ ] Run 2-4 weeks on cTrader demo with full audit logs.
- [ ] Only after cTrader demo stability: wire TradeLocker demo.
- [ ] Only after TradeLocker demo stability: consider GFT live account interaction.
- [ ] Obsidian trade journal from validated data.
- [ ] LLM-assisted post-trade review pipeline.

## Non-Goals (Removed from Scope)

- VWAP/EMA bias (replaced with pure structure)
- ATR-only stops (ATR buffer is allowed around structural stops)
- Session filters as blind optimization (sessions are context, not edge by themselves)
- Telegram scraper (visual content not reliably extractable)
- Fixed R:R-only exits (adaptive hybrid exit remains in scope)
- ML before OOS-stable structure rules

## Latest Structure Findings

Test date: 2026-06-26. Data window: latest 120D unless stated.

Direction accuracy says structure is a filter candidate, not a complete strategy:

| Slice | Sample | Direction Read |
|-------|-------:|----------------|
| XAUUSD HTF-bull long NY/London | 36 each | Strong anti-edge in forward 24 bars |
| XAUUSD bear/short Asia/NY | 2,628+ HTF-bear NY, 5,627 entry-bear Asia | Positive but not enough alone |
| GBPAUD entry+HTF bear short NY | 2,140 | Best high-sample FX pocket |
| NAS100 HTF-bear short | 5,477+ | Anti-edge; do not short NAS just because structure says bear |

Target-before-stop study:

| Slice | n | Best Read |
|-------|--:|-----------|
| EURUSD HTF-bull long London | 36 | Strong 1.5R/2R math, but V1 sweep/MSS produced 0 trades in latest 30D |
| GBPAUD entry+HTF bear short NY | 2,140 | Positive but modest: `exp_1.5R +0.11R`, `exp_2R +0.14R` |
| XAUUSD BOS-down short NY | 88 | Positive: `exp_1R +0.22R`, `exp_2R +0.28R` |
| XAUUSD entry+HTF bear short | 2,201 NY / 4,698 Asia | 1R weak, 1.5R/2R slightly positive |

V1 strategy results:

| Config | Window | Trades | Return | Max DD | Verdict |
|--------|--------|-------:|-------:|-------:|---------|
| GBPAUD short NY, HTF, 2R, no structure-cut | 2026-05-24..2026-06-23 | 7 | +0.92% | 0.63% | Clean but too few trades and too low return |
| GBPAUD short NY, HTF, 2R, no structure-cut | 2026-02-24..2026-06-23 | 28 | -1.45% | 3.27% | Reject: 30D slice was noise |
| XAUUSD short Asia, 2R, no structure-cut | 2026-02-24..2026-06-23 | 61 | +4.21% | 3.57% | Research-only: return decent, DD too high, misses target |

Conclusion: if direction is right, target selection matters. But V1 proves the stronger point: direction is only right in specific pockets, and the current sweep/MSS entry does not harvest enough of those pockets to pass GFT rules.

Strict ICT audit:

| Test | Result |
|------|--------|
| XAUUSD 5m latest 30D strict ICT | 1,298 swings, 43 bullish BOS, 42 bearish BOS, 42 bullish CHoCH, 42 bearish CHoCH |
| SMC reference on same sample | 1,536 swings, 378 BOS, 203 CHoCH |
| Verdict | SMC is useful for cross-checking definitions, but too noisy/permissive as the production direction engine without causal filtering |

Strict ICT 120D triple-barrier direction result:

| Slice | n | Hit 1R | Exp 1R | Exp 2R | Verdict |
|-------|--:|-------:|-------:|-------:|---------|
| XAUUSD bearish BOS NY | 24 | 58.3% | +0.38R | +0.52R | Best pocket, needs more sample |
| EURUSD bearish BOS Asia | 59 | 55.9% | +0.30R | +0.25R | Useful candidate |
| NAS100 bullish BOS Asia | 49 | 46.9% | +0.19R | +0.24R | Long-only candidate; avoids bearish anti-edge |
| GBPAUD bearish state NY | 58 | 46.6% | +0.14R | +0.14R | Modest, not enough alone |

## Code Locations

| Component | Path |
|-----------|------|
| Structure lib | `backtesting/structure_lib/` |
| Engine | `backtesting/engine/` |
| Forex V1 | `backtesting/forex_v1.py` |
| Webapp | `webapp/app.py` |
| Structure overlay JS | `webapp/static/js/structure-overlay.js` |
| TradeLocker client | `infra/tradelocker_client.py` |

## Obsidian References

- [[Strategy/Prop-Firm-Engine]] — Development plan
- [[Strategy/V2-ICT-SMC-Overview]] — Previous strategy architecture
- [[Strategy/Sweep-Results-Jun2026]] — First sweep results
- [[Strategy/Rolling-Analysis-Jun2026]] — Rolling window validation
- [[Goals]] — Trading goals and milestones
