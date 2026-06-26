# Crypto Scaling Engine Plan

Goal: grow a $20 USDT futures account to $100 in 20 trading days.

## Hard Math

$20 → $100 = **400% return** in ~20 trading days.

### Daily compounding required

| Compounding | Daily return | Path |
|---|:-:|---|
| None (linear) | 20.0% | $4/day |
| Compounding | 8.4% | $20 → $21.68 → ... → $100 @ day 20 |
| Weekly targets | 47.6%/wk | $20 → $29.52 → $43.58 → $64.35 → $95.00 → $100 |

### What 8.4%/day actually means with leverage

At 50x leverage on Binance/Bybit, a 0.17% price move in your direction = 8.4% return on margin. That's:

| Pair | Price | 0.17% move | Required direction |
|------|-------|-----------|-------------------|
| BTC | $65,000 | $110 | 1 tick on 15m |
| ETH | $3,500 | $6 | 1-2 ticks |
| SOL | $140 | $0.24 | 3-4 ticks |
| DOGE | $0.12 | $0.0002 | 1 tick |
| PEPE | $0.00001 | $0.000000017 | 1-2 ticks |

The daily move does not need to be large. The constraint is not price movement — it is **min notional**, **execution friction**, and **drawdown survival**.

### The real constraint: min notional

With $20 and 50x leverage:
- Buying power = $1,000
- If min notional = $5 per order → each trade uses $0.10 margin (0.5% of capital)
- To use meaningful capital per trade, we need pairs with min notional < $1

Trading pairs sorted by min notional + volatility:

| Pair | Min notional (est.) | Daily vol% | $20 usability |
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

**Verdict**: Small-cap alts (PEPE, DOGE, WLD, SUI) are the only viable path for $20 accounts because min notional on BTC/ETH eats too much capital per trade.

### Drawdown math

If you lose 3 trades in a row at risk_pct each:

| Risk/trade | After 3 losses | Recovery needed |
|:-:|---:|---:|
| 2% | $18.82 | 6.3% |
| 5% | $17.15 | 16.6% |
| 10% | $14.58 | 37.1% |
| 15% | $12.28 | 62.8% |
| 20% | $10.24 | 95.3% |

Max recommendable risk for this goal: **5% per trade** (survive 3 losses, still recoverable).

### Strategy requirement

For 5% risk/trade at 8.4% daily target:
- Need ~1.7 winning trades per day (or 1 winner at RR 3.0+)
- OR a high-frequency scalper doing 5-10 trades/day with WR > 55%

Win rate / RR combinations that work:

| WR | RR | EV/trade | Trades needed/day |
|:-:|:-:|:-:|:-:|
| 40% | 2.5 | +0.40R | 2.1 |
| 45% | 2.0 | +0.35R | 2.4 |
| 50% | 1.5 | +0.25R | 3.4 |
| 55% | 1.5 | +0.375R | 2.2 |
| 60% | 1.2 | +0.32R | 2.6 |
| 65% | 1.0 | +0.30R | 2.8 |

At 5% risk/trade, EV of +0.35R = +1.75% per trade. Need 5 trades/day to hit 8.4% target.

## Engine Requirements

The scaling engine must:

1. **Respect exchange constraints** — min notional, qty step, tick size
2. **Choose the right pair** — based on volatility, liquidity, and min notional
3. **Size dynamically** — compound profits into larger positions
4. **Track drawdown budget** — never exceed survival thresholds
5. **Estimate path probability** — given strategy metrics (WR, RR, frequency), show how likely $100 is

## Acceptance Gates

- [ ] Can simulate $20 → $100 in < 30 calendar days with WR 55%+ and RR 1.5+
- [ ] Max drawdown stays under 30% at any point
- [ ] Min notional never prevents a valid trade from opening
- [ ] Strategy backtests on at least 3 alt pairs show PF > 1.3
- [ ] The engine can run on both Binance and Bybit
