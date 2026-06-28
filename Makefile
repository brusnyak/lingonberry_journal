SHELL := /bin/bash
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help venv install run-web run-bot run-copy copy-status test clean nas100 nas100-sweep nas100-monthly
.PHONY: run-ctrader-mirror ctrader-mirror-status ctrader-mirror-dry
.PHONY: run-strategy strategy-dry strategy-test strategy-list
.PHONY: run-pm pm-dry pm-test trades-summary deploy-to-oracle

help:
	@echo "Available targets:"
	@echo "  make venv          - create virtual environment"
	@echo "  make install       - install dependencies"
	@echo "  make run-web       - start Flask web app (port 5000)"
	@echo "  make run-bot       - start Telegram bot"
	@echo "  make run-copy      - start Copy Trader (25K→100K) [legacy TradeLocker]"
	@echo "  make copy-status   - print copy trader account status"
	@echo "  make copy-dry      - start Copy Trader in dry-run mode"
	@echo ""
	@echo "  cTrader services:"
	@echo "  make run-ctrader-mirror  - start cTrader Mirror (25K→100K)"
	@echo "  make ctrader-mirror-status - print cTrader account status"
	@echo "  make ctrader-mirror-dry  - start cTrader Mirror in dry-run mode"
	@echo ""
	@echo "  Trend Strategy:"
	@echo "  make run-strategy       - start MA trend strategy"
	@echo "  make strategy-dry       - start strategy in dry-run mode"
	@echo "  make strategy-test      - one eval cycle, then exit"
	@echo "  make strategy-list      - list available strategy types"
	@echo ""
	@echo "  Position Manager:"
	@echo "  make run-pm             - start Position Manager (trailing SL)"
	@echo "  make pm-dry             - start PM in dry-run mode"
	@echo "  make pm-test            - run one PM eval cycle and exit"
	@echo ""
	@echo "  Analytics:"
	@echo "  make trades-summary     - show recent trade log entries"
	@echo ""
	@echo ""
	@echo "  Deployment:"
	@echo "  make deploy-to-oracle   - rsync + install + restart on Oracle VM"
	@echo ""
	@echo "  Other:"
	@echo "  make test          - run test suite"
	@echo "  make clean         - clean cache files"
	@echo "  make nas100        - NAS100 backtest (30d, single run)"
	@echo "  make nas100-sweep  - NAS100 backtest (full config sweep)"
	@echo "  make nas100-monthly - NAS100 backtest (rolling monthly)"

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

run-web:
	$(PY) webapp/app.py

run-bot:
	$(PY) bot/journal_daemon.py

run-copy:
	$(PY) infra/copy_trader.py

copy-status:
	$(PY) infra/copy_trader.py --status

copy-dry:
	COPY_DRY_RUN=true $(PY) infra/copy_trader.py

# ── cTrader services ──

run-ctrader-mirror:
	$(PY) infra/ctrader_mirror.py

ctrader-mirror-status:
	$(PY) infra/ctrader_mirror.py --status

ctrader-mirror-dry:
	COPY_DRY_RUN=true $(PY) infra/ctrader_mirror.py

# Trend Strategy
run-strategy:
	$(PY) infra/ctrader_strategy.py

strategy-dry:
	TREND_DRY_RUN=true $(PY) infra/ctrader_strategy.py

strategy-test:
	TREND_DRY_RUN=true $(PY) infra/ctrader_strategy.py --test

strategy-list:
	$(PY) infra/ctrader_strategy.py --list-strategies

# Position Manager
run-pm:
	$(PY) infra/position_manager.py

pm-dry:
	PM_DRY_RUN=true $(PY) infra/position_manager.py

pm-test:
	$(PY) infra/position_manager.py --test

# Trade Logger
trades-summary:
	@echo "=== Recent trade log entries ==="
	@ls -t data/trades/*.jsonl 2>/dev/null | head -3 | xargs -I{} tail -5 {} || echo "No trade logs found"
	@echo "=== Summary ==="
	@cat data/trades/*.jsonl 2>/dev/null | python3 -c "
import sys, json
events = [json.loads(l) for l in sys.stdin if l.strip()]
if not events:
    print('No trades recorded')
    sys.exit(0)
opens = [e for e in events if e['event']=='open']
closes = [e for e in events if e['event']=='close']
signals = [e for e in events if e['event']=='signal']
print(f'  Signals: {len(signals)}  Opens: {len(opens)}  Closes: {len(closes)}')
for e in opens:
    print(f'  {e[\"ts\"][:19]}  {e[\"side\"].upper():4s} {e[\"symbol\"]:6s} {e[\"qty\"]:.4f} @ {e[\"price\"]:.2f}  SL={e[\"sl\"]:.2f} TP={e[\"tp\"]:.2f}')
" || true

# ── Deployment ──

deploy-to-oracle:
	bash deploy/deploy.sh

test:
	$(PY) -m pytest -q

clean:
	rm -rf __pycache__ .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".DS_Store" -delete

nas100:
	$(PY) backtesting/nas100_test.py --days 30

nas100-sweep:
	$(PY) backtesting/nas100_test.py --sweep --days 30

nas100-monthly:
	$(PY) backtesting/nas100_test.py --monthly --days 60
