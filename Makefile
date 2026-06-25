SHELL := /bin/bash
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help venv install run-web run-bot test clean nas100 nas100-sweep nas100-monthly

help:
	@echo "Available targets:"
	@echo "  make venv          - create virtual environment"
	@echo "  make install       - install dependencies"
	@echo "  make run-web       - start Flask web app (port 5000)"
	@echo "  make run-bot       - start Telegram bot"
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
