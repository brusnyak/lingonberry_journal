# External Crypto Research Resources

Purpose: decide what to reuse from external open-source trading stacks without turning this repo into a framework graveyard.

## Verdict

Do not migrate to another framework. Borrow the audit patterns and execution abstractions.

| Project | Use | Verdict |
|---|---|---|
| [Freqtrade](https://github.com/freqtrade/freqtrade) | Lookahead checks, recursive-analysis checks, hyperopt/backtest workflow shape | Strong reference. Copy validation ideas, not the framework. |
| [Hummingbot](https://github.com/hummingbot/hummingbot) | Exchange connector model, CEX perpetual abstraction, paper/live deployment separation | Strong execution reference. Too heavy for research engine internals. |
| [OpenBB](https://github.com/OpenBB-finance/OpenBB) | Data integration surface, REST/API-first data access, analyst dashboard model | Useful later for external macro/equity/context data. Not needed for perp OHLCV/OI/funding. |
| [QuantDinger](https://github.com/brokermr810/QuantDinger) | Agent gateway, audit logging, dual vector/event strategy runtime idea | Interesting product architecture. Too broad to adopt now. |
| [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) | Skill/MCP/agent workflow ideas and swarm research UX | Research-agent inspiration only. Not a trading-engine dependency. |

## Concrete Ideas To Import

1. Add a `lookahead-analysis` command equivalent: rerun a strategy with delayed/shifted feature columns and fail if results improve suspiciously.
2. Add a `recursive-analysis` command equivalent: compare full-run indicators against rolling/online recomputation.
3. Split exchange execution from research logic: `ExchangeSpec`, `DataFeed`, `ExecutionAdapter`, `BacktestAdapter`.
4. Keep all agent/AI-generated strategy work paper-only by default and audit-logged before any live execution path.
5. Use resource-backed features first: mark price, index price, funding, open interest, premium/basis. Skip L2/orderbook until a Level 1 strategy survives OOS.

## Current Local Implementation

Added downloader support:

```bash
python -m backtesting.data_pipeline.crypto \
  --days 90 \
  --exchange both \
  --symbols DOGEUSDT,XRPUSDT,SUIUSDT \
  --tfs 1,15,60 \
  --resources mark,index,open_interest
```

Output paths:

- `data/market_data/crypto/{exchange}/resources/{SYMBOL}_mark{TF}.parquet`
- `data/market_data/crypto/{exchange}/resources/{SYMBOL}_index{TF}.parquet`
- `data/market_data/crypto/{exchange}/resources/{SYMBOL}_open_interest.parquet`

## Rejection Notes

- Do not use AI-agent projects to justify live trading. They help workflow, not edge.
- Do not adopt OpenBB just to fetch data already available from exchange APIs.
- Do not use Hummingbot for backtesting this strategy. Its value is connector/execution design.
- Do not trust any framework's result unless our local engine passes no-lookahead, cost, funding, min-notional, liquidation, and rolling-window checks.
