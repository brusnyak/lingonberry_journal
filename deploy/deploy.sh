#!/usr/bin/env bash
# Deploy services to Oracle VM (cTrader + TradeLocker)
set -euo pipefail

APP_USER="${APP_USER:-ubuntu}"
APP_DIR="${APP_DIR:-/home/ubuntu/lingonberry_journal}"
REMOTE_HOST="${REMOTE_HOST:-84.8.249.139}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/ssh-key-2026-02-21.key}"
RSYNC_OPTS="-avz --delete --exclude=.venv --exclude=.git --exclude=.gitignore --exclude=.claude --exclude=.codegraph --exclude=.DS_Store --exclude=__pycache__ --exclude=.pytest_cache --exclude=data --exclude='*.parquet' --exclude='*.zip' --exclude=.env"

echo "=== Deploying to $REMOTE_HOST ==="

# 1. Rsync codebase (skip venv, git, caches)
echo "--- Syncing code ---"
rsync $RSYNC_OPTS \
    -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
    "$(dirname "$0")/../" \
    "$APP_USER@$REMOTE_HOST:$APP_DIR/"

# 2. Install/update Python deps
echo "--- Installing dependencies ---"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$APP_USER@$REMOTE_HOST" \
    "cd $APP_DIR && .venv/bin/pip install -q -r requirements.txt"

# 3. Inject cTrader credentials + bundle vars from local .env into VM's .env
echo "--- Injecting required env vars ---"
LOCAL_ENV="$(dirname "$0")/../.env"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$APP_USER@$REMOTE_HOST" \
    "grep -q '^CTRADER_CLIENT_ID=' $APP_DIR/.env 2>/dev/null || echo 'CTRADER_CLIENT_ID=$(grep ^CTRADER_CLIENT_ID= "$LOCAL_ENV" | cut -d= -f2-)' >> $APP_DIR/.env && \
     grep -q '^CTRADER_SECRET=' $APP_DIR/.env 2>/dev/null || echo 'CTRADER_SECRET=$(grep ^CTRADER_SECRET= "$LOCAL_ENV" | cut -d= -f2-)' >> $APP_DIR/.env && \
     grep -q '^CTRADER_ACCESS_TOKEN=' $APP_DIR/.env 2>/dev/null || echo 'CTRADER_ACCESS_TOKEN=$(grep ^CTRADER_ACCESS_TOKEN= "$LOCAL_ENV" | cut -d= -f2-)' >> $APP_DIR/.env && \
     grep -q '^CTRADER_REFRESH_TOKEN=' $APP_DIR/.env 2>/dev/null || echo 'CTRADER_REFRESH_TOKEN=$(grep ^CTRADER_REFRESH_TOKEN= "$LOCAL_ENV" | cut -d= -f2-)' >> $APP_DIR/.env && \
     grep -q '^CTRADER_ACCOUNT_ID=' $APP_DIR/.env 2>/dev/null || echo 'CTRADER_ACCOUNT_ID=44798689' >> $APP_DIR/.env && \
     grep -q '^CTRADER_ACC_NUM_MASTER=' $APP_DIR/.env 2>/dev/null || echo 'CTRADER_ACC_NUM_MASTER=47747207' >> $APP_DIR/.env && \
     grep -q '^CTRADER_ACC_NUM_SLAVE=' $APP_DIR/.env 2>/dev/null || echo 'CTRADER_ACC_NUM_SLAVE=47747211' >> $APP_DIR/.env && \
     grep -q '^PM_ACCOUNT_IDS=' $APP_DIR/.env 2>/dev/null || echo 'PM_ACCOUNT_IDS=47747207,47747211' >> $APP_DIR/.env && \
     grep -q '^TREND_DRY_RUN=' $APP_DIR/.env 2>/dev/null || echo 'TREND_DRY_RUN=true' >> $APP_DIR/.env && \
     grep -q '^TREND_POSITION_SIZE=' $APP_DIR/.env 2>/dev/null || echo 'TREND_POSITION_SIZE=0.001' >> $APP_DIR/.env && \
     echo '  Done: cTrader creds + bundle vars injected'"

# 3b. Inject TradeLocker trading env vars (conditional — won't overwrite existing)
echo "--- Injecting TradeLocker env vars ---"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$APP_USER@$REMOTE_HOST" \
    "grep -q '^TL_ACC_NUM_MASTER=' $APP_DIR/.env 2>/dev/null || echo 'TL_ACC_NUM_MASTER=2165806' >> $APP_DIR/.env && \
     grep -q '^TL_ACC_NUM_SLAVE=' $APP_DIR/.env 2>/dev/null || echo 'TL_ACC_NUM_SLAVE=2165807' >> $APP_DIR/.env && \
     grep -q '^TL_MASTER_ACCOUNT=' $APP_DIR/.env 2>/dev/null || echo 'TL_MASTER_ACCOUNT=2165806' >> $APP_DIR/.env && \
     grep -q '^TL_SLAVE_ACCOUNT=' $APP_DIR/.env 2>/dev/null || echo 'TL_SLAVE_ACCOUNT=2165807' >> $APP_DIR/.env && \
     grep -q '^COPY_RISK_PCT=' $APP_DIR/.env 2>/dev/null || echo 'COPY_RISK_PCT=0.005' >> $APP_DIR/.env && \
     grep -q '^COPY_DRY_RUN=' $APP_DIR/.env 2>/dev/null || echo 'COPY_DRY_RUN=true' >> $APP_DIR/.env && \
     grep -q '^TL_ACTIVE_ENV=' $APP_DIR/.env 2>/dev/null || echo 'TL_ACTIVE_ENV=demo' >> $APP_DIR/.env && \
     grep -q '^PM_DRY_RUN=' $APP_DIR/.env 2>/dev/null || echo 'PM_DRY_RUN=true' >> $APP_DIR/.env && \
     echo '  Done: TL trading vars injected'"

# 4. Create data directories for trade logs
echo "--- Creating data directories ---"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$APP_USER@$REMOTE_HOST" \
    "mkdir -p $APP_DIR/data/trades"

# 5. Install systemd unit files (replace placeholders)
echo "--- Installing systemd units ---"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$APP_USER@$REMOTE_HOST" \
    "cd $APP_DIR && \
     for tmpl in deploy/systemd/*.template; do
        svc=\$(basename "\$tmpl" .template)
        sed -e 's|@APP_USER@|$APP_USER|g' \
            -e 's|@APP_DIR@|$APP_DIR|g' \
            "\$tmpl" | sudo tee /etc/systemd/system/\$svc > /dev/null
        echo \"  Installed \$svc\"
     done && \
     sudo systemctl daemon-reload"

# 6. Restart cTrader services (webapp stays running)
echo "--- Restarting cTrader services ---"
for svc in ctrader-strategy.service ctrader-mirror.service position-manager.service; do
    echo "  Enabling/restarting $svc..."
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$APP_USER@$REMOTE_HOST" \
        "sudo systemctl enable $svc && sudo systemctl restart $svc" 2>&1 || \
        echo "  WARNING: $svc restart failed (might not exist yet)"
done

# 6b. Restart TradeLocker services (if templates exist)
echo "--- Restarting TradeLocker services ---"
for svc in tl-copy-trader.service tl-position-manager.service; do
    echo "  Enabling/restarting $svc..."
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$APP_USER@$REMOTE_HOST" \
        "sudo systemctl enable $svc && sudo systemctl restart $svc" 2>&1 || \
        echo "  WARNING: $svc restart failed (might not exist yet)"
done

# 7. Status check
echo "--- Service status ---"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$APP_USER@$REMOTE_HOST" \
    "systemctl status ctrader-strategy.service ctrader-mirror.service position-manager.service \
                 tl-copy-trader.service tl-position-manager.service --no-pager 2>&1 \
     | grep -E '(●|Active:)' || true"

echo ""
echo "=== Deploy complete ==="
echo "Monitor:"
echo "  journalctl -u ctrader-strategy.service -f --no-pager -n 50"
echo "  journalctl -u ctrader-mirror.service -f --no-pager -n 50"
echo "  journalctl -u position-manager.service -f --no-pager -n 50"
echo "  journalctl -u tl-copy-trader.service -f --no-pager -n 50"
echo "  journalctl -u tl-position-manager.service -f --no-pager -n 50"
