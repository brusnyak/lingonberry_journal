#!/bin/bash
# Trading Journal Process Management Script
# Manages bot, webapp, and background jobs

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# PID files
BOT_PID_FILE="data/.bot.pid"
WEBAPP_PID_FILE="data/.webapp.pid"
CTRADER_SYNC_PID_FILE="data/.ctrader_sync.pid"
SLTP_POLLER_PID_FILE="data/.sltp_poller.pid"

# Log files
LOG_DIR="data/logs"
mkdir -p "$LOG_DIR"

BOT_LOG="$LOG_DIR/bot.log"
WEBAPP_LOG="$LOG_DIR/webapp.log"
CTRADER_SYNC_LOG="$LOG_DIR/ctrader_sync.log"
SLTP_POLLER_LOG="$LOG_DIR/sltp_poller.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
is_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$pid_file"
            return 1
        fi
    fi
    return 1
}

start_bot() {
    echo -e "${YELLOW}Starting Telegram bot...${NC}"
    
    if is_running "$BOT_PID_FILE"; then
        echo -e "${RED}Bot is already running${NC}"
        return 1
    fi
    
    nohup python3 bot/journal_daemon.py > "$BOT_LOG" 2>&1 &
    echo $! > "$BOT_PID_FILE"
    
    echo -e "${GREEN}Bot started (PID: $(cat $BOT_PID_FILE))${NC}"
    echo "Logs: $BOT_LOG"
}

stop_bot() {
    echo -e "${YELLOW}Stopping Telegram bot...${NC}"
    
    if ! is_running "$BOT_PID_FILE"; then
        echo -e "${RED}Bot is not running${NC}"
        return 1
    fi
    
    local pid=$(cat "$BOT_PID_FILE")
    kill "$pid"
    rm -f "$BOT_PID_FILE"
    
    echo -e "${GREEN}Bot stopped${NC}"
}

start_webapp() {
    echo -e "${YELLOW}Starting webapp...${NC}"
    
    if is_running "$WEBAPP_PID_FILE"; then
        echo -e "${RED}Webapp is already running${NC}"
        return 1
    fi
    
    nohup python3 webapp/app.py > "$WEBAPP_LOG" 2>&1 &
    echo $! > "$WEBAPP_PID_FILE"
    
    echo -e "${GREEN}Webapp started (PID: $(cat $WEBAPP_PID_FILE))${NC}"
    echo "Logs: $WEBAPP_LOG"
    echo "URL: http://localhost:${WEBAPP_PORT:-5000}"
}

stop_webapp() {
    echo -e "${YELLOW}Stopping webapp...${NC}"
    
    if ! is_running "$WEBAPP_PID_FILE"; then
        echo -e "${RED}Webapp is not running${NC}"
        return 1
    fi
    
    local pid=$(cat "$WEBAPP_PID_FILE")
    kill "$pid"
    rm -f "$WEBAPP_PID_FILE"
    
    echo -e "${GREEN}Webapp stopped${NC}"
}

start_ctrader_sync() {
    echo -e "${YELLOW}Starting cTrader sync job...${NC}"
    
    if is_running "$CTRADER_SYNC_PID_FILE"; then
        echo -e "${RED}cTrader sync is already running${NC}"
        return 1
    fi
    
    nohup python3 jobs/ctrader_sync.py continuous > "$CTRADER_SYNC_LOG" 2>&1 &
    echo $! > "$CTRADER_SYNC_PID_FILE"
    
    echo -e "${GREEN}cTrader sync started (PID: $(cat $CTRADER_SYNC_PID_FILE))${NC}"
    echo "Logs: $CTRADER_SYNC_LOG"
}

stop_ctrader_sync() {
    echo -e "${YELLOW}Stopping cTrader sync job...${NC}"
    
    if ! is_running "$CTRADER_SYNC_PID_FILE"; then
        echo -e "${RED}cTrader sync is not running${NC}"
        return 1
    fi
    
    local pid=$(cat "$CTRADER_SYNC_PID_FILE")
    kill "$pid"
    rm -f "$CTRADER_SYNC_PID_FILE"
    
    echo -e "${GREEN}cTrader sync stopped${NC}"
}

start_sltp_poller() {
    echo -e "${YELLOW}Starting SL/TP poller...${NC}"
    
    if is_running "$SLTP_POLLER_PID_FILE"; then
        echo -e "${RED}SL/TP poller is already running${NC}"
        return 1
    fi
    
    nohup python3 jobs/sltp_poller.py continuous > "$SLTP_POLLER_LOG" 2>&1 &
    echo $! > "$SLTP_POLLER_PID_FILE"
    
    echo -e "${GREEN}SL/TP poller started (PID: $(cat $SLTP_POLLER_PID_FILE))${NC}"
    echo "Logs: $SLTP_POLLER_LOG"
}

stop_sltp_poller() {
    echo -e "${YELLOW}Stopping SL/TP poller...${NC}"
    
    if ! is_running "$SLTP_POLLER_PID_FILE"; then
        echo -e "${RED}SL/TP poller is not running${NC}"
        return 1
    fi
    
    local pid=$(cat "$SLTP_POLLER_PID_FILE")
    kill "$pid"
    rm -f "$SLTP_POLLER_PID_FILE"
    
    echo -e "${GREEN}SL/TP poller stopped${NC}"
}

status() {
    echo -e "${YELLOW}=== Service Status ===${NC}"
    
    echo -n "Bot: "
    if is_running "$BOT_PID_FILE"; then
        echo -e "${GREEN}Running (PID: $(cat $BOT_PID_FILE))${NC}"
    else
        echo -e "${RED}Stopped${NC}"
    fi
    
    echo -n "Webapp: "
    if is_running "$WEBAPP_PID_FILE"; then
        echo -e "${GREEN}Running (PID: $(cat $WEBAPP_PID_FILE))${NC}"
    else
        echo -e "${RED}Stopped${NC}"
    fi
    
    echo -n "cTrader Sync: "
    if is_running "$CTRADER_SYNC_PID_FILE"; then
        echo -e "${GREEN}Running (PID: $(cat $CTRADER_SYNC_PID_FILE))${NC}"
    else
        echo -e "${RED}Stopped${NC}"
    fi
    
    echo -n "SL/TP Poller: "
    if is_running "$SLTP_POLLER_PID_FILE"; then
        echo -e "${GREEN}Running (PID: $(cat $SLTP_POLLER_PID_FILE))${NC}"
    else
        echo -e "${RED}Stopped${NC}"
    fi
}

start_all() {
    echo -e "${YELLOW}Starting all services...${NC}"
    start_bot
    start_webapp
    start_ctrader_sync
    start_sltp_poller
    echo -e "${GREEN}All services started${NC}"
}

stop_all() {
    echo -e "${YELLOW}Stopping all services...${NC}"
    stop_bot || true
    stop_webapp || true
    stop_ctrader_sync || true
    stop_sltp_poller || true
    echo -e "${GREEN}All services stopped${NC}"
}

restart_all() {
    stop_all
    sleep 2
    start_all
}

logs() {
    local service=$1
    
    case $service in
        bot)
            tail -f "$BOT_LOG"
            ;;
        webapp)
            tail -f "$WEBAPP_LOG"
            ;;
        ctrader)
            tail -f "$CTRADER_SYNC_LOG"
            ;;
        sltp)
            tail -f "$SLTP_POLLER_LOG"
            ;;
        *)
            echo "Usage: $0 logs {bot|webapp|ctrader|sltp}"
            exit 1
            ;;
    esac
}

# Main command handler
case "${1:-}" in
    start)
        case "${2:-all}" in
            bot) start_bot ;;
            webapp) start_webapp ;;
            ctrader) start_ctrader_sync ;;
            sltp) start_sltp_poller ;;
            all) start_all ;;
            *) echo "Unknown service: $2"; exit 1 ;;
        esac
        ;;
    stop)
        case "${2:-all}" in
            bot) stop_bot ;;
            webapp) stop_webapp ;;
            ctrader) stop_ctrader_sync ;;
            sltp) stop_sltp_poller ;;
            all) stop_all ;;
            *) echo "Unknown service: $2"; exit 1 ;;
        esac
        ;;
    restart)
        case "${2:-all}" in
            bot) stop_bot; sleep 1; start_bot ;;
            webapp) stop_webapp; sleep 1; start_webapp ;;
            ctrader) stop_ctrader_sync; sleep 1; start_ctrader_sync ;;
            sltp) stop_sltp_poller; sleep 1; start_sltp_poller ;;
            all) restart_all ;;
            *) echo "Unknown service: $2"; exit 1 ;;
        esac
        ;;
    status)
        status
        ;;
    logs)
        logs "${2:-}"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs} [service]"
        echo ""
        echo "Services: bot, webapp, ctrader, sltp, all"
        echo ""
        echo "Examples:"
        echo "  $0 start all       - Start all services"
        echo "  $0 stop bot        - Stop bot only"
        echo "  $0 restart webapp  - Restart webapp"
        echo "  $0 status          - Show status of all services"
        echo "  $0 logs bot        - Tail bot logs"
        exit 1
        ;;
esac
