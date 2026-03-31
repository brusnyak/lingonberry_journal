#!/bin/bash
# Install or update systemd units for Lingonberry Journal.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

APP_DIR="${APP_DIR:-$PROJECT_ROOT}"
APP_USER="${APP_USER:-$(id -un)}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
ENABLE_SERVICES=0
RESTART_SERVICES=0
CLEANUP_LEGACY=1

usage() {
    cat <<'EOF'
Usage: scripts/install_systemd.sh [--enable] [--restart] [--no-cleanup]

Options:
  --enable      Enable services to start on boot
  --restart     Restart services after installing unit files
  --no-cleanup  Do not stop legacy nohup/screen processes before restart
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --enable)
            ENABLE_SERVICES=1
            ;;
        --restart)
            RESTART_SERVICES=1
            ;;
        --no-cleanup)
            CLEANUP_LEGACY=0
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1"
            usage
            exit 1
            ;;
    esac
    shift
done

if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl not found. This script is for Linux hosts with systemd."
    exit 1
fi

run_systemctl() {
    if [ "$(id -u)" -eq 0 ]; then
        systemctl "$@"
    else
        sudo systemctl "$@"
    fi
}

install_template() {
    local template_path=$1
    local unit_name
    unit_name=$(basename "${template_path%.template}")
    local tmp_file
    tmp_file=$(mktemp)
    sed \
        -e "s|@APP_DIR@|$APP_DIR|g" \
        -e "s|@APP_USER@|$APP_USER|g" \
        "$template_path" > "$tmp_file"
    sudo install -m 0644 "$tmp_file" "$SYSTEMD_DIR/$unit_name"
    rm -f "$tmp_file"
    echo "Installed $SYSTEMD_DIR/$unit_name"
}

cleanup_legacy_processes() {
    echo "Cleaning up legacy processes..."
    pkill -f "python3 bot/journal_daemon.py" || true
    pkill -f "python3 webapp/app.py" || true
    pkill -f "python3 jobs/ctrader_sync.py continuous" || true
    pkill -f "python3 jobs/sltp_poller.py continuous" || true
    screen -S journal_bot -X quit || true
    rm -f data/.bot.pid data/.webapp.pid data/.ctrader_sync.pid data/.sltp_poller.pid
}

mkdir -p data/logs

for template in deploy/systemd/*.template; do
    install_template "$template"
done

run_systemctl daemon-reload

if [ "$ENABLE_SERVICES" -eq 1 ]; then
    run_systemctl enable \
        journal-bot.service \
        journal-webapp.service \
        journal-ctrader-sync.service \
        journal-sltp-poller.service
fi

if [ "$RESTART_SERVICES" -eq 1 ]; then
    if [ "$CLEANUP_LEGACY" -eq 1 ]; then
        cleanup_legacy_processes
    fi
    run_systemctl restart \
        journal-bot.service \
        journal-webapp.service \
        journal-ctrader-sync.service \
        journal-sltp-poller.service
fi

run_systemctl --no-pager --full status \
    journal-bot.service \
    journal-webapp.service \
    journal-ctrader-sync.service \
    journal-sltp-poller.service | sed -n '1,120p'
