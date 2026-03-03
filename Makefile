SHELL := /bin/zsh
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help venv install env-check run-web run-bot run-all stop-all status test sltp-check export-ml import-csv deploy-prep ctrader-sync ctrader-test ctrader-fetch ctrader-viz git-init deploy setup-mini-app bot webapp clean daily-reminder setup-daily-reminder

help:
	@echo "Targets:"
	@echo "  make venv           - create virtualenv"
	@echo "  make install        - install dependencies"
	@echo "  make env-check      - verify .env exists"
	@echo "  make bot            - start Telegram bot"
	@echo "  make webapp         - start Flask web app"
	@echo "  make run-all        - start all services (bot, webapp, ctrader, sltp)"
	@echo "  make stop-all       - stop all running services"
	@echo "  make status         - check status of all services"
	@echo "  make test           - run test suite"
	@echo "  make sltp-check     - trigger SL/TP poll endpoint"
	@echo "  make export-ml      - trigger ML export endpoint"
	@echo "  make import-csv     - import sample trades CSV"
	@echo "  make ctrader-test   - test cTrader API connection"
	@echo "  make ctrader-fetch  - fetch trades and save to CSV/Parquet"
	@echo "  make ctrader-viz    - visualize trades on charts"
	@echo "  make ctrader-sync   - sync trades from cTrader to database"
	@echo "  make daily-reminder - test daily reminder (send now)"
	@echo "  make setup-daily-reminder - install cron job for daily reminders"
	@echo "  make git-init       - initialize git repository"
	@echo "  make deploy         - deploy to GitHub"
	@echo "  make setup-mini-app - setup Telegram Mini App"
	@echo "  make clean          - clean cache files"
	@echo "  make deploy-prep    - run local pre-push gate"

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

env-check:
	@test -f .env || (echo ".env missing. Copy .env.example to .env" && exit 1)

run-web: env-check
	$(PY) webapp/app.py

run-bot: env-check
	$(PY) bot/journal_daemon.py

run-all: env-check
	bash scripts/manage.sh start all

stop-all:
	bash scripts/manage.sh stop all

status:
	bash scripts/manage.sh status

test:
	$(PY) -m pytest -q

sltp-check:
	curl -s -X POST http://localhost:5000/api/jobs/sltp-check -H 'Content-Type: application/json' -d '{}' | cat

export-ml:
	curl -s -X POST http://localhost:5000/api/export/ml -H 'Content-Type: application/json' -d '{"account_id":1}' | cat

import-csv:
	$(PY) scripts/import_trades_csv.py /Users/yegor/Downloads/2nd_trades.csv --account-id 1 --asset-type forex --symbol GBPUSD

ctrader-test: env-check
	$(PY) infra/ctrader_client.py

ctrader-fetch: env-check
	$(PY) scripts/test_ctrader.py

ctrader-viz: env-check
	$(PY) scripts/visualize_trades.py

ctrader-sync: env-check
	$(PY) jobs/ctrader_sync.py

daily-reminder: env-check
	$(PY) jobs/daily_reminder.py

setup-daily-reminder: env-check
	@bash scripts/setup_daily_reminder.sh

deploy-prep: env-check
	$(PY) -m py_compile bot/journal_db.py infra/market_data.py infra/pine_bridge.py jobs/sltp_poller.py core/exporter.py webapp/app.py bot/journal_daemon.py infra/ctrader_client.py jobs/ctrader_sync.py
	$(PY) -m pytest -q
	@echo "deploy-prep: PASS"

bot: run-bot

webapp: run-web

clean:
	rm -rf __pycache__ .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

git-init:
	@bash scripts/init_git.sh

deploy:
	@bash scripts/deploy_to_github.sh

setup-mini-app:
	@bash scripts/setup_mini_app.sh
