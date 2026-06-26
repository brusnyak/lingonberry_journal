# Crypto Scaling Engine Plan

Goal: research whether a small USDT futures account can scale without hiding behind unrealistic leverage, fees, funding, liquidation, or min-notional assumptions.

Development assumption: **$70 account, 10x leverage**. Higher leverage can be studied later as an offshore/regulatory-risk variant, not the default.

## Hard Math

$70 → $100 = **42.9% return**. The old $20 → $100 path is a 400% moonshot and should not be the default EU-realistic target.

### Daily compounding required

| Target | Required return | Path |
|---|:-:|---|
| $70 → $100 in 20 days | 1.81% compounded/day | $70 → $100 |
| $70 → $100 in 30 days | 1.20% compounded/day | $70 → $100 |
| $20 → $100 in 20 days | 8.38% compounded/day | research-only stress case |

### What 8.4%/day actually means with leverage

At 10x leverage, a 0.84% price move in your direction = 8.4% gross return on margin before fees/funding. For the new $70 → $100 target, the daily gross move requirement is closer to 0.12-0.18% account-equivalent if compounded over 20-30 days.

| Pair | Price | 0.84% move | Notes |
|------|-------|-----------|-------------------|
| BTC | $65,000 | $546 | liquid but min-notional heavy for tiny accounts |
| ETH | $3,500 | $29 | liquid, lower noise than alts |
| SOL | $140 | $1.18 | useful middle ground |
| DOGE | $0.12 | $0.0010 | small-account viable |
| 1000PEPE | $0.01 | $0.000084 | volatile, overfit risk high |

The daily move does not need to be large. The constraint is not price movement — it is **min notional**, **execution friction**, and **drawdown survival**.

### The real constraint: min notional

With $70 and 10x leverage:
- Buying power = $700.
- If min notional = $5 per order, minimum margin is $0.50 before fees.
- Small alts still matter, but BTC/ETH are no longer automatically impossible.

Trading pairs sorted by min notional + volatility:

| Pair | Min notional (est.) | Daily vol% | $70 / 10x usability |
|------|:-:|:-:|---|
| PEPE/USDT | ~$1 | 8-15% | Best |
| DOGE/USDT | ~$1 | 5-10% | Best |
| 1000PEPE/USDT | ~$1 | 8-20% | Best |
| WLD/USDT | ~$1 | 6-12% | Great |
| SUI/USDT | ~$1 | 5-10% | Great |
| SOL/USDT | ~$5 | 4-8% | OK |
| XRP/USDT | ~$5 | 3-6% | OK |
| ETH/USDT | ~$10 | 3-5% | Marginal |
| BTC/USDT | ~$65 | 2-4% | No |

**Verdict**: DOGE/XRP/SUI/SOL are better first candidates than BTC/ETH for growth rate, but BTC/ETH remain useful control symbols for data/engine validation.

### Drawdown math

If you lose 3 trades in a row at risk_pct each:

| Risk/trade | After 3 losses | Recovery needed |
|:-:|---:|---:|
| 1% | $67.92 | 3.1% |
| 2% | $65.88 | 6.3% |
| 5% | $60.02 | 16.6% |
| 10% | $51.03 | 37.1% |
| 15% | $42.98 | 62.8% |

Max research risk: **1-2% per trade**. Use 5% only for explicit stress tests.

### Strategy requirement

For 1-2% risk/trade, the engine needs positive expectancy plus enough frequency. Forced daily trades are a failure mode, not a requirement.

Win rate / RR combinations that work:

| WR | RR | EV/trade | Trades needed/day |
|:-:|:-:|:-:|:-:|
| 40% | 2.5 | +0.40R | 2.1 |
| 45% | 2.0 | +0.35R | 2.4 |
| 50% | 1.5 | +0.25R | 3.4 |
| 55% | 1.5 | +0.375R | 2.2 |
| 60% | 1.2 | +0.32R | 2.6 |
| 65% | 1.0 | +0.30R | 2.8 |

At 1% risk/trade, EV of +0.35R = +0.35% per trade. At 2% risk/trade, EV of +0.35R = +0.70% per trade.

## Engine Requirements

The scaling engine must:

1. **Respect exchange constraints** — min notional, qty step, tick size
2. **Choose the right pair** — based on volatility, liquidity, and min notional
3. **Size dynamically** — compound profits into larger positions
4. **Track drawdown budget** — never exceed survival thresholds
5. **Estimate path probability** — given strategy metrics (WR, RR, frequency), show how likely $100 is
6. **Use exchange-derived context** — funding, mark/index price, basis, and open interest before any ML work

## Acceptance Gates

- [ ] Can simulate $70 → $100 with 10x leverage and no liquidation exits
- [ ] Max drawdown stays under 20% at any point
- [ ] Min notional never prevents a valid trade from opening
- [ ] Strategy backtests on at least 3 alt pairs show PF > 1.3
- [ ] The engine can run on both Binance and Bybit
- [ ] Edge survives rolling windows, not just the latest bull period

## Latest Test Verdict - 2026-06-26

The current capped `TrFvg` test does **not** pass deployment gates yet.

What was fixed:

- Removed 50x default assumptions from crypto research runners.
- Added min/max stop gates so SL/TP are intraday-sized.
- Fixed crypto R-multiple math to use actual linear-perp PnL risk.
- Review UI now uses `$70`, `10x`, exchange-specific data, funding, and specs.

What passed:

- `AVAXUSDT 15m bull`: useful 30D and rolling signal.
  - 30D: `39 trades`, `44% WR`, `PF 1.98`, `+37.3%`, `9.2% DD`.
  - Rolling: `5/8` valid windows, mean `PF 3.79`, mean `DD 5.6%`, mean `24 trades`.
- `XRPUSDT 15m bull`: strong but under-sampled.
  - Rolling: `8/8` valid windows, mean `PF 5.70`, mean `6 trades`.

What failed:

- `DOGEUSDT` is rejected for now.
  - 30D top row looked good.
  - Rolling bull: mean `PF 0.30`, only `6/8` valid windows.
- `SUIUSDT` is unstable.
  - Rolling both: mean `PF 1.05`, high drawdown, negative mean return.
- Bear direction remains weak.

Current stronger hypothesis:

> Use capped structure-FVG as an event generator, then add mark/index basis and open-interest filters before considering any live/paper route.

Do not transfer funds for this engine yet. The next step is feature-filter validation, not live deployment.

## Resource Fetch

```bash
# Core OHLCV/funding/spec data
python -m backtesting.data_pipeline.crypto --days 90 --exchange both --tfs 1,3,5,15,30,60,240,1440

# Exchange-derived resources for liquidation/basis/OI filters
python -m backtesting.data_pipeline.crypto --days 90 --exchange both --symbols DOGEUSDT,XRPUSDT,SUIUSDT --tfs 1,15,60 --resources mark,index,open_interest
```
