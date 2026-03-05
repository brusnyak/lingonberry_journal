// Account Rules Display - FTMO-style risk management display
class AccountRulesDisplay {
    constructor(containerId) {
        this.containerId = containerId;
        this.account = null;
        this.stats = null;
    }

    update(account, stats) {
        this.account = account;
        this.stats = stats;
        this.render();
    }

    render() {
        const container = document.getElementById(this.containerId);
        if (!container || !this.account) return;

        const balance = this.stats?.balance || this.account.initial_balance;
        const initialBalance = this.account.initial_balance;
        const growth = ((balance - initialBalance) / initialBalance) * 100;

        // Calculate rule violations
        const rules = this.calculateRules();

        container.innerHTML = `
            <div class="rules-card">
                <div class="rules-header">
                    <div class="rules-title">
                        <span class="rules-icon">🎯</span>
                        <span>${this.account.firm_name || 'Account'} Rules</span>
                    </div>
                    <div class="rules-status ${rules.status}">
                        ${rules.status === 'safe' ? '✓ Safe' : rules.status === 'warning' ? '⚠ Warning' : '❌ Danger'}
                    </div>
                </div>

                <div class="rules-grid">
                    <!-- Balance Progress -->
                    <div class="rule-item">
                        <div class="rule-label">
                            <span>Current Balance</span>
                            <span class="rule-value ${growth >= 0 ? 'positive' : 'negative'}">
                                ${balance.toFixed(2)} ${this.account.currency}
                            </span>
                        </div>
                        <div class="rule-progress">
                            <div class="progress-bar">
                                <div class="progress-fill ${growth >= 0 ? 'positive' : 'negative'}" 
                                     style="width: ${Math.min(Math.abs(growth), 100)}%"></div>
                            </div>
                            <div class="progress-label">
                                <span>Initial: ${initialBalance.toFixed(2)}</span>
                                <span class="${growth >= 0 ? 'positive' : 'negative'}">
                                    ${growth >= 0 ? '+' : ''}${growth.toFixed(2)}%
                                </span>
                            </div>
                        </div>
                    </div>

                    ${this.account.max_daily_loss_pct ? `
                    <!-- Daily Loss -->
                    <div class="rule-item ${rules.dailyLoss.status}">
                        <div class="rule-label">
                            <span>Daily Loss Limit</span>
                            <span class="rule-value">
                                ${rules.dailyLoss.used.toFixed(2)}% / ${this.account.max_daily_loss_pct.toFixed(2)}%
                            </span>
                        </div>
                        <div class="rule-progress">
                            <div class="progress-bar">
                                <div class="progress-fill ${rules.dailyLoss.status}" 
                                     style="width: ${rules.dailyLoss.percentage}%"></div>
                            </div>
                            <div class="progress-label">
                                <span>${rules.dailyLoss.remaining.toFixed(2)}% remaining</span>
                                <span>${rules.dailyLoss.percentage.toFixed(0)}% used</span>
                            </div>
                        </div>
                    </div>
                    ` : ''}

                    ${this.account.max_total_loss_pct ? `
                    <!-- Total Loss -->
                    <div class="rule-item ${rules.totalLoss.status}">
                        <div class="rule-label">
                            <span>Max Drawdown Limit</span>
                            <span class="rule-value">
                                ${rules.totalLoss.used.toFixed(2)}% / ${this.account.max_total_loss_pct.toFixed(2)}%
                            </span>
                        </div>
                        <div class="rule-progress">
                            <div class="progress-bar">
                                <div class="progress-fill ${rules.totalLoss.status}" 
                                     style="width: ${rules.totalLoss.percentage}%"></div>
                            </div>
                            <div class="progress-label">
                                <span>${rules.totalLoss.remaining.toFixed(2)}% remaining</span>
                                <span>${rules.totalLoss.percentage.toFixed(0)}% used</span>
                            </div>
                        </div>
                    </div>
                    ` : ''}

                    ${this.account.profit_target_pct ? `
                    <!-- Profit Target -->
                    <div class="rule-item ${rules.profitTarget.status}">
                        <div class="rule-label">
                            <span>Profit Target</span>
                            <span class="rule-value">
                                ${rules.profitTarget.achieved.toFixed(2)}% / ${this.account.profit_target_pct.toFixed(2)}%
                            </span>
                        </div>
                        <div class="rule-progress">
                            <div class="progress-bar">
                                <div class="progress-fill positive" 
                                     style="width: ${rules.profitTarget.percentage}%"></div>
                            </div>
                            <div class="progress-label">
                                <span>${rules.profitTarget.remaining.toFixed(2)}% to go</span>
                                <span>${rules.profitTarget.percentage.toFixed(0)}% achieved</span>
                            </div>
                        </div>
                    </div>
                    ` : ''}
                </div>

                ${rules.violations.length > 0 ? `
                <div class="rules-violations">
                    <div class="violation-title">⚠️ Violations</div>
                    ${rules.violations.map(v => `
                        <div class="violation-item">${v}</div>
                    `).join('')}
                </div>
                ` : ''}
            </div>
        `;
    }

    calculateRules() {
        const balance = this.stats?.balance || this.account.initial_balance;
        const initialBalance = this.account.initial_balance;
        const growth = ((balance - initialBalance) / initialBalance) * 100;

        const violations = [];
        let overallStatus = 'safe';

        // Daily loss calculation (simplified - would need today's trades)
        const dailyPnl = this.stats?.daily_pnl || 0;
        const dailyLossPct = (dailyPnl / initialBalance) * 100;
        const dailyLossUsed = Math.abs(Math.min(dailyLossPct, 0));
        const dailyLossRemaining = (this.account.max_daily_loss_pct || 0) - dailyLossUsed;
        const dailyLossPercentage = this.account.max_daily_loss_pct
            ? (dailyLossUsed / this.account.max_daily_loss_pct) * 100
            : 0;

        let dailyLossStatus = 'safe';
        if (dailyLossPercentage >= 100) {
            dailyLossStatus = 'danger';
            violations.push('Daily loss limit exceeded');
            overallStatus = 'danger';
        } else if (dailyLossPercentage >= 80) {
            dailyLossStatus = 'warning';
            if (overallStatus === 'safe') overallStatus = 'warning';
        }

        // Total loss calculation
        const totalLossPct = Math.abs(Math.min(growth, 0));
        const totalLossRemaining = (this.account.max_total_loss_pct || 0) - totalLossPct;
        const totalLossPercentage = this.account.max_total_loss_pct
            ? (totalLossPct / this.account.max_total_loss_pct) * 100
            : 0;

        let totalLossStatus = 'safe';
        if (totalLossPercentage >= 100) {
            totalLossStatus = 'danger';
            violations.push('Maximum drawdown exceeded');
            overallStatus = 'danger';
        } else if (totalLossPercentage >= 80) {
            totalLossStatus = 'warning';
            if (overallStatus === 'safe') overallStatus = 'warning';
        }

        // Profit target calculation
        const profitAchieved = Math.max(growth, 0);
        const profitRemaining = (this.account.profit_target_pct || 0) - profitAchieved;
        const profitPercentage = this.account.profit_target_pct
            ? (profitAchieved / this.account.profit_target_pct) * 100
            : 0;

        let profitStatus = 'safe';
        if (profitPercentage >= 100) {
            profitStatus = 'achieved';
        } else if (profitPercentage >= 80) {
            profitStatus = 'near';
        }

        return {
            status: overallStatus,
            violations,
            dailyLoss: {
                used: dailyLossUsed,
                remaining: dailyLossRemaining,
                percentage: dailyLossPercentage,
                status: dailyLossStatus
            },
            totalLoss: {
                used: totalLossPct,
                remaining: totalLossRemaining,
                percentage: totalLossPercentage,
                status: totalLossStatus
            },
            profitTarget: {
                achieved: profitAchieved,
                remaining: profitRemaining,
                percentage: profitPercentage,
                status: profitStatus
            }
        };
    }
}
