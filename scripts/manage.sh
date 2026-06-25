#!/bin/bash
# Trading Journal Process Management Script
# Uses systemd when journal services are installed, otherwise falls back to local nohup processes.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

BOT_PID_FILE="data/.bot.pid"
WEBAPP_PID_FILE="data/.webapp.pid"
SLTP_POLLER_PID_FILE="data/.sltp_poller.pid"
COPY_PID_FILE="data/.copy.pid"

LOG_DIR="data/logs"
mkdir -p "$LOG_DIR"

BOT_LOG="$LOG_DIR/bot.log"
WEBAPP_LOG="$LOG_DIR/webapp.log"
SLTP_POLLER_LOG="$LOG_DIR/sltp_poller.log"
COPY_LOG="$LOG_DIR/copy_trader.log"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

systemd_unit_for() {
    case "$1" in
        bot) echo "journal-bot.service" ;;
        webapp) echo "journal-webapp.service" ;;
        sltp) echo "journal-sltp-poller.service" ;;
        copy) echo "journal-copy-trader.service" ;;
        *) return 1 ;;
    esac
}

run_systemctl() {
    if [ "$(id -u)" -eq 0 ]; then
        systemctl "$@"
    else
        sudo systemctl "$@"
    fi
}

has_all_systemd_units() {
    command -v systemctl >/dev/null 2>&1 || return 1
    local unit
    for unit in \
        journal-bot.service \
        journal-webapp.service \
        journal-sltp-poller.service \
        journal-copy-trader.service
    do
        systemctl cat "$unit" >/dev/null 2>&1 || return 1
    done
    return 0
}

use_systemd() {
    [ "${JOURNAL_MANAGE_MODE:-auto}" != "local" ] && has_all_systemd_units
}

is_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
        rm -f "$pid_file"
    fi
    return 1
}

find_webapp_pid() {
    pgrep -f "[Pp]ython3 .*webapp/app.py" | head -n 1
}

start_bot_local() {
    echo -e "${YELLOW}Starting Telegram bot...${NC}"

    if is_running "$BOT_PID_FILE"; then
        echo -e "${RED}Bot is already running${NC}"
        return 1
    fi

    nohup python3 bot/journal_daemon.py > "$BOT_LOG" 2>&1 &
    echo $! > "$BOT_PID_FILE"

    echo -e "${GREEN}Bot started (PID: $(cat "$BOT_PID_FILE"))${NC}"
    echo "Logs: $BOT_LOG"
}

stop_bot_local() {
    echo -e "${YELLOW}Stopping Telegram bot...${NC}"

    if ! is_running "$BOT_PID_FILE"; then
        echo -e "${RED}Bot is not running${NC}"
        return 1
    fi

    kill "$(cat "$BOT_PID_FILE")"
    rm -f "$BOT_PID_FILE"
    echo -e "${GREEN}Bot stopped${NC}"
}

start_webapp_local() {
    echo -e "${YELLOW}Starting webapp...${NC}"

    if is_running "$WEBAPP_PID_FILE"; then
        echo -e "${RED}Webapp is already running${NC}"
        return 1
    fi

    local existing_pid
    existing_pid=$(find_webapp_pid || true)
    if [ -n "$existing_pid" ]; then
        echo "$existing_pid" > "$WEBAPP_PID_FILE"
        echo -e "${YELLOW}Webapp was already running without a PID file. Recovered PID: $existing_pid${NC}"
        return 0
    fi

    nohup python3 webapp/app.py > "$WEBAPP_LOG" 2>&1 &
    echo $! > "$WEBAPP_PID_FILE"

    echo -e "${GREEN}Webapp started (PID: $(cat "$WEBAPP_PID_FILE"))${NC}"
    echo "Logs: $WEBAPP_LOG"
    echo "URL: http://localhost:${WEBAPP_PORT:-5000}"
}

stop_webapp_local() {
    echo -e "${YELLOW}Stopping webapp...${NC}"

    local pid=""
    if is_running "$WEBAPP_PID_FILE"; then
        pid=$(cat "$WEBAPP_PID_FILE")
    else
        pid=$(find_webapp_pid || true)
        if [ -z "$pid" ]; then
            echo -e "${RED}Webapp is not running${NC}"
            return 1
        fi
    fi

    kill "$pid"
    rm -f "$WEBAPP_PID_FILE"
    echo -e "${GREEN}Webapp stopped${NC}"
}

start_sltp_poller_local() {
    echo -e "${YELLOW}Starting SL/TP poller...${NC}"

    if is_running "$SLTP_POLLER_PID_FILE"; then
        echo -e "${RED}SL/TP poller is already running${NC}"
        return 1
    fi

    nohup python3 jobs/sltp_poller.py continuous > "$SLTP_POLLER_LOG" 2>&1 &
    echo $! > "$SLTP_POLLER_PID_FILE"

    echo -e "${GREEN}SL/TP poller started (PID: $(cat "$SLTP_POLLER_PID_FILE"))${NC}"
    echo "Logs: $SLTP_POLLER_LOG"
}

stop_sltp_poller_local() {
    echo -e "${YELLOW}Stopping SL/TP poller...${NC}"

    if ! is_running "$SLTP_POLLER_PID_FILE"; then
        echo -e "${RED}SL/TP poller is not running${NC}"
        return 1
    fi

    kill "$(cat "$SLTP_POLLER_PID_FILE")"
    rm -f "$SLTP_POLLER_PID_FILE"
    echo -e "${GREEN}SL/TP poller stopped${NC}"
}

start_copy_local() {
    echo -e "${YELLOW}Starting Copy Trader...${NC}"

    if is_running "$COPY_PID_FILE"; then
        echo -e "${RED}Copy Trader is already running${NC}"
        return 1
    fi

    nohup python3 infra/copy_trader.py > "$COPY_LOG" 2>&1 &
    echo $! > "$COPY_PID_FILE"

    echo -e "${GREEN}Copy Trader started (PID: $(cat "$COPY_PID_FILE"))${NC}"
    echo "Logs: $COPY_LOG"
}

stop_copy_local() {
    echo -e "${YELLOW}Stopping Copy Trader...${NC}"

    if ! is_running "$COPY_PID_FILE"; then
        echo -e "${RED}Copy Trader is not running${NC}"
        return 1
    fi

    kill "$(cat "$COPY_PID_FILE")"
    rm -f "$COPY_PID_FILE"
    echo -e "${GREEN}Copy Trader stopped${NC}"
}

print_systemd_status_line() {
    local label=$1
    local unit=$2
    echo -n "$label: "
    if systemctl is-active --quiet "$unit"; then
        local main_pid
        main_pid=$(systemctl show -p MainPID --value "$unit")
        echo -e "${GREEN}Running (PID: ${main_pid:-n/a})${NC}"
    else
        echo -e "${RED}Stopped${NC}"
    fi
}

run_service_action() {
    local action=$1
    local service=$2

    if use_systemd; then
        local unit
        unit=$(systemd_unit_for "$service")
        echo -e "${YELLOW}${action^}ing ${service} via systemd...${NC}"
        run_systemctl "$action" "$unit"
        return
    fi

    case "${action}:${service}" in
        start:bot) start_bot_local ;;
        stop:bot) stop_bot_local ;;
        restart:bot) stop_bot_local || true; sleep 1; start_bot_local ;;
        start:webapp) start_webapp_local ;;
        stop:webapp) stop_webapp_local ;;
        restart:webapp) stop_webapp_local || true; sleep 1; start_webapp_local ;;
        start:sltp) start_sltp_poller_local ;;
        stop:sltp) stop_sltp_poller_local ;;
        restart:sltp) stop_sltp_poller_local || true; sleep 1; start_sltp_poller_local ;;
        start:copy) start_copy_local ;;
        stop:copy) stop_copy_local ;;
        restart:copy) stop_copy_local || true; sleep 1; start_copy_local ;;
        *) echo "Unknown action/service: ${action} ${service}"; exit 1 ;;
    esac
}

status_all() {
    echo -e "${YELLOW}=== Service Status ===${NC}"

    if use_systemd; then
        print_systemd_status_line "Bot" "journal-bot.service"
        print_systemd_status_line "Webapp" "journal-webapp.service"
        print_systemd_status_line "SL/TP Poller" "journal-sltp-poller.service"
        print_systemd_status_line "Copy Trader" "journal-copy-trader.service"
        return
    fi

    echo -n "Bot: "
    if is_running "$BOT_PID_FILE"; then
        echo -e "${GREEN}Running (PID: $(cat "$BOT_PID_FILE"))${NC}"
    else
        echo -e "${RED}Stopped${NC}"
    fi

    echo -n "Webapp: "
    if is_running "$WEBAPP_PID_FILE"; then
        echo -e "${GREEN}Running (PID: $(cat "$WEBAPP_PID_FILE"))${NC}"
    elif [ -n "$(find_webapp_pid || true)" ]; then
        local pid
        pid=$(find_webapp_pid)
        echo "$pid" > "$WEBAPP_PID_FILE"
        echo -e "${YELLOW}Running (recovered PID: $pid)${NC}"
    else
        echo -e "${RED}Stopped${NC}"
    fi

    echo -n "SL/TP Poller: "
    if is_running "$SLTP_POLLER_PID_FILE"; then
        echo -e "${GREEN}Running (PID: $(cat "$SLTP_POLLER_PID_FILE"))${NC}"
    else
        echo -e "${RED}Stopped${NC}"
    fi

    echo -n "Copy Trader: "
    if is_running "$COPY_PID_FILE"; then
        echo -e "${GREEN}Running (PID: $(cat "$COPY_PID_FILE"))${NC}"
    else
        echo -e "${RED}Stopped${NC}"
    fi
}

logs_for_service() {
    local service=$1

    if use_systemd; then
        local unit
        unit=$(systemd_unit_for "$service")
        if [ "$(id -u)" -eq 0 ]; then
            journalctl -u "$unit" -f -n 100
        else
            sudo journalctl -u "$unit" -f -n 100
        fi
        return
    fi

    case "$service" in
        bot) tail -f "$BOT_LOG" ;;
        webapp) tail -f "$WEBAPP_LOG" ;;
        sltp) tail -f "$SLTP_POLLER_LOG" ;;
        copy) tail -f "$COPY_LOG" ;;
        *)
            echo "Usage: $0 logs {bot|webapp|sltp|copy}"
            exit 1
            ;;
    esac
}

run_all_action() {
    local action=$1
    local past_tense="started"
    case "$action" in
        stop) past_tense="stopped" ;;
        restart) past_tense="restarted" ;;
    esac
    if use_systemd; then
        echo -e "${YELLOW}${action^}ing all services via systemd...${NC}"
    else
        echo -e "${YELLOW}${action^}ing all services...${NC}"
    fi
    run_service_action "$action" bot
    run_service_action "$action" webapp
    run_service_action "$action" sltp
    run_service_action "$action" copy
    echo -e "${GREEN}All services ${past_tense}${NC}"
}

case "${1:-}" in
    start)
        case "${2:-all}" in
            bot|webapp|sltp) run_service_action start "${2}" ;;
            all) run_all_action start ;;
            *) echo "Unknown service: $2"; exit 1 ;;
        esac
        ;;
    stop)
        case "${2:-all}" in
            bot|webapp|sltp) run_service_action stop "${2}" ;;
            all) run_all_action stop ;;
            *) echo "Unknown service: $2"; exit 1 ;;
        esac
        ;;
    restart)
        case "${2:-all}" in
            bot|webapp|sltp) run_service_action restart "${2}" ;;
            all) run_all_action restart ;;
            *) echo "Unknown service: $2"; exit 1 ;;
        esac
        ;;
    status)
        status_all
        ;;
    logs)
        logs_for_service "${2:-}"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs} [service]"
        echo ""
        echo "Services: bot, webapp, sltp, all"
        echo ""
        echo "Environment:"
        echo "  JOURNAL_MANAGE_MODE=local  Force local nohup mode even if systemd units exist"
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
