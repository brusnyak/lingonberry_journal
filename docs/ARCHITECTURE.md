# System Architecture

## Overview

Three microservices running on Oracle Cloud Free Tier (84.8.249.139),
communicating with cTrader OpenAPI (protobuf) over WebSocket.

```
┌─────────────────────────────────────────────────────┐
│                    Oracle VM                          │
│                                                       │
│  ┌─────────────────┐    ┌──────────────────────────┐ │
│  │ ctrader-strategy │───▶│     ctrader-mirror       │ │
│  │ (15s poll)       │   │ (3s poll, COPY_DRY_RUN)   │ │
│  │                  │   │ 25K master → 100K slave   │ │
│  └────────┬────────┘    └───────────┬──────────────┘ │
│           │                         │                 │
│           │     ┌──────────────────┐│                 │
│           │     │ position-manager  ││                 │
│           │     │ (5s poll)         ││                 │
│           │     │ trailing SL       ││                 │
│           │     └────────┬─────────┘│                 │
│           │              │           │                 │
│           ▼              ▼           ▼                 │
│  ┌──────────────────────────────────────────────────┐ │
│  │              cTrader OpenAPI WebSocket             │ │
│  │        (infra/ctrader_client.py — protobuf)       │ │
│  └──────────────────────┬───────────────────────────┘ │
│                         │                              │
└─────────────────────────┼──────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
        47747207 (25K)          47747211 (100K)
        master                  slave
        Spotware demo           Spotware demo
        $24,926                 $99,778
```

## Services

### ctrader-strategy (ctrader_strategy.py)

- **Symbol**: BTCUSD
- **Timeframe**: M5
- **Signal**: EMA20/50 crossover
- **Poll**: 15s
- **Risk**: 0.001 lots (~$60 at current BTC price)
- **SL**: ATR × 1.5
- **TP**: ATR × 1.5 × 1.5 (2.25R)
- **Cooldown**: 3 bars between signals

Connects to master account (47747207). Writes signals and trade events
to `data/trades/YYYY-MM-DD.jsonl`.

Supports `TREND_DRY_RUN=true` to log signals without executing.

### ctrader-mirror (ctrader_mirror.py)

Copies positions from master → slave with risk-based position sizing.

- **Poll**: 3s
- **Risk**: 0.5% of slave equity per trade
- **Method**: Two-phase (market order → modify_sltp)
- **Tracking**: Maintains position ID map between accounts

Risk scaling formula:
```
lots = equity * RISK_PCT / stop_distance
```

Supports `COPY_DRY_RUN=true`.

### position-manager (position_manager.py)

Manages trailing stop loss on open positions across both accounts.

- **Poll**: 5s
- **BE**: 1.0R (moves SL to breakeven)
- **Trail**: 1.5R (trails SL via swing point structure)
- **Fallback**: Simple distance-based trailing when swing data unavailable
- **News filter**: Checks economic calendar before close actions

Supports `PM_DRY_RUN=true`.

## Shared Infrastructure

### ctrader_client.py

Synchronous cTrader OpenAPI protobuf client over Twisted/WebSocket.

Capabilities:
- Application auth + account auth (JWT-based)
- Symbol cache (by ID and name, per account)
- OHLC history (get_trendbars)
- Order placement (market, limit, stop)
- Position management (close, modify SL/TP)
- Balance/equity queries

Key implementation details:
- Singleton pattern with `get_ctrader()`
- Single WebSocket connection, multi-account
- Marketplace orders: SL/TP sent as **relative distances in points**
  via `relativeStopLoss`/`relativeTakeProfit` protobuf fields
- Limit/stop orders: SL/TP sent as absolute prices rounded to symbol digits

### trade_logger.py

JSONL trade journal writer. Thread-safe. Daily rotation.

Events logged:
- `signal` — strategy detected entry condition
- `open` — position opened
- `close` — position closed
- `error` — order execution failure
- `modify` — SL/TP change

Files stored in `data/trades/YYYY-MM-DD.jsonl`.

## Deployment

`deploy/deploy.sh` rsyncs the project to the VM and reloads systemd units.

Systemd templates in `deploy/systemd/`:
- `ctrader-strategy.service.template`
- `ctrader-mirror.service.template`
- `position-manager.service.template`

Each template has Restart=on-failure with RestartSec=5.

Makefile targets:
- `deploy-to-oracle` — full deploy
- `deploy-copy-files` — file-only deploy (no restart)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CTRADER_CLIENT_ID` | — | cTrader API app ID |
| `CTRADER_SECRET` | — | cTrader API secret |
| `CTRADER_ACCESS_TOKEN` | — | cTrader access token |
| `CTRADER_ACC_NUM_MASTER` | — | Master account ID (25K) |
| `CTRADER_ACC_NUM_SLAVE` | — | Slave account ID (100K) |
| `TREND_DRY_RUN` | `true` | Strategy dry-run |
| `COPY_DRY_RUN` | `true` | Mirror dry-run |
| `PM_DRY_RUN` | `true` | Position manager dry-run |
| `TREND_POSITION_SIZE` | `0.001` | Lots per trade |
| `TREND_COOLDOWN_BARS` | `3` | Bars between signals |
| `SL_ATR_MULT` | `1.5` | ATR multiplier for SL |
| `TP_RR` | `1.5` | Risk/reward ratio |

## TradeLocker (Legacy)

Old services stopped and disabled:
- `journal-bot` — Telegram bot
- `journal-copy-trader` — TradeLocker copy trader
- `journal-mr-bot-25k` / `journal-mr-bot-100k` — Mean reversion bots
- `journal-sltp-poller` — SL/TP poller

Webapp still has read-only TradeLocker API endpoints (`/api/tradelocker/*`)
but they are unused. No TradeLocker trades execute in the current setup.

## Current State

- Strategy: live (dry_run=false), no positions, waiting for crossover
- Mirror: live (dry_run=false), polling, no positions to copy
- PM: dry_run=true, evaluating, no managed positions
- All services: active, no crashes
