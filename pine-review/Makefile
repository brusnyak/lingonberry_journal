.PHONY: install run-backend run-frontend run-all clean

# Install dependencies for both backend and frontend
install:
	@echo "Installing Backend Dependencies..."
	cd backend && python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt
	@echo "Installing Frontend Dependencies..."
	cd frontend && npm install

# Run Backend (FastAPI)
run-backend:
	@echo "Starting Backend..."
	PYTHONPATH=./backend uvicorn backend.app.main:app --reload --port 8000


back: run-backend

# Run Backend Tests
test-backend:
	@echo "Running Backend Tests..."
	cd backend && . venv/bin/activate && pytest tests/

# Run Multi-Pair Batch Backtest (Monte Carlo)
backtest:
	@echo "Running Random Interval Batch Backtest..."
	PYTHONPATH=./backend python3 -m backend.app.core.batch_tester


# Run Frontend (Vite)
run-frontend:
	@echo "Starting Frontend..."
	cd frontend && npm run dev

front: run-frontend

# Run Both Backend + Frontend (requires parallel execution)
# Usage: make -j2 run
run: run-backend run-frontend

# Run Telegram Signal Monitor (background signal monitoring)
tele:
	@echo "Starting Telegram Signal Monitor..."
	cd backend && python3 signal_monitor.py

# Run Telegram Bot (interactive mode)
tele-bot:
	@echo "Starting Telegram Bot (interactive)..."
	cd backend && python3 telegram_bot.py

# Test Telegram Bot
tele-test:
	@echo "Testing Telegram Bot..."
	cd backend && python3 test_telegram_bot.py

# End-to-end Telegram test (requires backend running)
tele-e2e:
	@echo "Running E2E Telegram Test..."
	@echo "Make sure backend is running: make back"
	cd backend && python3 test_telegram_e2e.py

# Run Backend + Telegram Monitor together
monitor:
	@echo "Starting Backend + Telegram Monitor..."
	./start_monitor.sh

# Check for trading inactivity (run daily via cron)
check-inactivity:
	@echo "Checking for trading inactivity..."
	cd backend && . venv/bin/activate && python3 check_inactivity.py

# Clean up venv and node_modules
clean:
	rm -rf backend/venv
	rm -rf frontend/node_modules


# Run Review App
review:
	@echo "Starting Review App..."
	uvicorn backend.src.review_app.main:app --port 8000 --reload

