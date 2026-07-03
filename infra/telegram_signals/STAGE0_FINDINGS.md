# Stage 0 — "just trade it" channel verification (2026-07-02)

## CORRECTION (same day, later pass) — original cost-adjusted result was wrong

The `+0.09R gross / +0.03R net` result below was produced by a bug in
`backtest_signals.py`'s `simulate()`: the stop-hit check used the ORIGINAL
stop price for the entire bar-walk (`stop_hit = lo <= stop`, never updated),
while the breakeven-adjusted exit price was only applied *after the fact* to
compute a nicer R-multiple. This let trades "ride" all the way to their far
original stop even after the channel's own stated rule says they'd already
be flat at breakeven — silently crediting TP touches a real account would
never see, because a real breakeven-managed position exits the moment price
returns to entry.

`trade_manager.py`'s `simulate_managed_trade(..., be_rule="tp1_only")`
enforces breakeven as a real exit condition during the walk (matches the
channel's stated rule exactly). Same 216 signals, same cost model, corrected
enforcement:

```
Mean net R: -0.082   Sum net R: -17.6   Win rate: 58.3%
```

**The text-verifiable era is a net loser, not a thin winner.** The
"worth building" conclusion from the original pass is retracted. See the
bottom of this doc for the updated recommendation.

---

## Original Stage 0 pass (kept for record, superseded by correction above)

Goal: check the channel's actual track record against real price data before
risking any capital, per the staged plan (verify -> paper -> human-confirm ->
auto). Read-only Telethon session, full history pulled (1,804 messages,
2025-11-06 to 2026-07-02).

## Format changed mid-history — two eras, different confidence

- **Nov 2025 – ~Apr 2026**: fully text-templated (`Плечо:`, `Take:`, `Stop:`,
  `PM:`). No OCR/vision needed. 227 self-contained signals parsed, 219
  matched to a Binance USDT-M futures symbol.
- **~May 2026 – present**: shifted to short captions + "Тейки и стоп на
  скрине/графике" (levels are chart-image-only). Includes the WLDUSDT and
  VELVETUSDT trades referenced as the motivating example. **Not covered by
  this backtest** — would need vision parsing, which is a separate, lower-
  confidence problem (see PLAN.md's prior rejection of chart-OCR for this
  exact reason). The shift away from auditable text right around the hyped
  trades is itself a mark against verifiability, not evidence of anything
  worse, but it means the trades that sold the idea are the ones we can't
  independently check yet.

## Text-era backtest (n=219 real-data-matched signals, 5m bars, Binance futures)

Methodology: entry = first 5m close at/after signal post time (matches
channel's stated "Вход: по рынку"). Walk forward up to 52 days per signal
(extended after an initial 3.5-day window left 36% of trades unresolved —
do not trust short-window backtests on swing-holding-time strategies).
Partial closes 50/25/25 at TP1/TP2/TP3 per the channel's own stated rule;
stop moves to breakeven after TP1 (also per their stated rule). Same-bar
stop+TP ties resolved conservatively (assume stop first) since OHLC can't
show intrabar order.

- Unresolved within 52-day window: 6/219 (3%) — window is adequate now.
- Stop eventually hit: 168/219 (77%) — note this includes breakeven-stops
  after TP1, not all losses.
- TP1+ hit at some point: 129/219 (59%)
- **Mean weighted R (216 signals, 3 excluded as parser artifacts): +0.09.
  Sum: +19.4R.**

This is a real, modest positive read on the DIRECTION/LEVEL calls themselves
in the verifiable era — before any cost model. It is not the "high win rate,
1000%+ trades" impression from the highlight reel; it's closer to a
small-edge signal system.

### Cost-adjusted result (`apply_cost_model.py`)

Applied round-trip fee+slippage (0.20% combined) and actual historical
funding rate over each trade's real holding period (fetched per-symbol from
Binance, not assumed):

```
n = 216, mean hold 6.71 days
Mean cost (fee+slip+funding), in R units: 0.060
Mean weighted R gross (price-only):  +0.090
Mean weighted R net (after costs):   +0.030
Sum net R: +6.5
Only 3/216 trades flipped from win to loss by costs alone
```

**The edge survives costs, but it's thin: +0.03R/trade net.** At $300 and
1.5% risk/trade, ~45 signals/month, that's roughly $0.13 expected profit per
trade — low-single-digit %/month territory, not "300%/month." This number
already assumes safe, self-computed leverage (see liquidation finding below)
— copying his posted leverage directly would likely be worse.

## CRITICAL finding — stated stop distances are mostly unreachable at the stated leverage

For 176/216 clean signals (81%), the posted stop-loss distance is WIDER than
the naive isolated-margin liquidation distance implied by the channel's own
posted leverage (`liq_distance ≈ 1/leverage`, before maintenance-margin
buffer, which only makes real liquidation distance tighter still).

Example: `TRADOOR SHORT lev=10x` — stop 31% away, liquidation ~10% away.
`FIL LONG lev=50x` — stop 14% away, liquidation ~2% away.

**Implication**: if a follower opens a position at the posted leverage with
the posted stop, on isolated margin sized to the posted "PM: 1-3% of depo,"
the EXCHANGE will very likely force-liquidate the position before the
stop-loss order ever executes. The posted stop is not the real worst case —
it's aspirational. Either:
(a) the channel operator is actually running cross-margin with much more
    backing capital than "1-3% of depo" implies (meaning his real $ risk
    per trade is understated to followers), or
(b) he is also getting liquidated before his own stated stop on a majority
    of trades, and the "Stop:" line is more of a mental exit target than an
    executable order.

**This breaks the "copy his leverage + stop, risk 1-2%" plan as stated.**
To keep the "defined stop, bounded % risk" property the user wants, ANY
execution system must independently compute leverage/margin from OUR
account size and the posted stop distance (target: stop distance should be
comfortably inside the liquidation buffer, e.g. leverage <= 0.5x of what
`1/stop_distance` allows), not copy his posted leverage number directly.
This is a hard engineering constraint, not a tuning knob.

## Honest verdict

- The verifiable era shows a real, small, cost-surviving edge (+0.03R/trade
  net) — better than "gambling," far below the "300%/month" framing that
  motivated this. Roughly low-single-digit %/month at realistic sizing.
- The recent, most-cited trades (WLD, VELVET) are in the unverified,
  screenshot-only era and are not covered here (user decision 2026-07-02:
  write this era off as unverifiable rather than build vision parsing).
- The stated leverage/stop combination, if copied literally, does not
  deliver the bounded risk it appears to promise — liquidation would
  usually happen first. Any execution layer must size leverage from our own
  stop distance, not his. The +0.03R net figure already assumes this fix.

## Decisions made (2026-07-02)

- Cost model: applied. Original pass showed a surviving thin edge; that
  result is RETRACTED (see correction at top of doc) — corrected result is
  -0.082R net, a loser.
- Screenshot era (May 2026+): written off as unverifiable, excluded from
  go/no-go. Not building vision/OCR parsing for it — vision extraction was
  also pilot-tested separately (2/2 seed images, 6 repeat calls) and got
  1/6 fully correct, 1/6 dangerously wrong (swapped entry/stop). Manual
  entry by the user is the plan going forward, not automated OCR.
- Trade-management pilot on the two motivating examples (VELVETUSDT,
  WLDUSDT): both were REAL winners (full TP ladder or near it) under the
  channel's own BE rule. A stricter "move to breakeven at 50% progress
  toward TP1" rule was tested and would have converted both to $0 — round
  numbers +1.99R and +2.00R (channel's rule) vs +0.00R (stricter rule) on
  the exact trades that motivated this project. Rejected as default.
  Broader test across all 216 signals: EVERY breakeven variant tested
  (tp1_only, progress 50%/25%, progress-with-hold 30min/2h) has negative
  mean R. None fixes the channel's underlying loss; they only change how
  much is lost.

## Updated recommendation (supersedes the earlier "worth building" call)

The rigorous, corrected result: this channel's real, verifiable track
record is a net loser (-0.08R/trade average) across the one 6-month sample
we can check, under every trade-management variant tested. The two trades
that motivated this whole investigation (VELVET, WLD) were real winners,
but two anecdotes were never a track record — that was the entire point of
doing Stage 0 instead of trusting the highlight reel, and the full-sample
result does not back them up.

I do not recommend building Stage 2/3 (live execution, position management,
monitoring) around this specific channel's signals. Building automation
around a demonstrated negative-expectancy signal source makes losing money
faster and more consistent, not less.

If there's still interest in a Telegram-copy-trading system generally, the
tooling built here (Telethon ingestion, backtest-against-real-price
verification, cost model, safe leverage sizing, breakeven-rule testing) is
reusable against any other channel cheaply -- that's the actual asset this
exercise produced, not this specific channel's signals.

## Next steps (pending user decision)

1. Decide whether to point this same verification pipeline at a different
   channel, or stop here.
2. Do NOT build live execution / position management / monitoring for
   "just trade it" specifically -- the evidence doesn't support it.
