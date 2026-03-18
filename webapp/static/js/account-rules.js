// Account Rules Display - FTMO-style risk management display
class AccountRulesDisplay {
    constructor(containerId) {
        this.containerId = containerId;
        this.account = null;
        this.stats = null;
        this.ruleProgress = null;
        this.isExpanded = false; // Hidden by default
    }

    update(account, stats, ruleProgress = null) {
        this.account = account;
        this.stats = stats;
        this.ruleProgress = ruleProgress;
        this.render();
    }

    toggle() {
        this.isExpanded = !this.isExpanded;
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
        const progress = this.ruleProgress || {};

        const accountName = this.account.firm_name || 'Account';
        
        container.innerHTML = `
            <div class="rules-card ${this.isExpanded ? 'expanded' : 'collapsed'}">
                <div class="rules-header" id="rules-toggle-btn" style="cursor: pointer; user-select: none;">
                    <div class="rules-title">
                        <i data-lucide="target" class="rules-icon"></i>
                        <span>${accountName} Rules</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <div class="rules-status ${rules.status}">
                            ${rules.status === 'safe' ? '✓' : rules.status === 'warning' ? '⚠' : '❌'}
                        </div>
                        <i data-lucide="${this.isExpanded ? 'chevron-up' : 'chevron-down'}" style="width: 16px; height: 16px; color: var(--muted);"></i>
                    </div>
                </div>

                <div class="rules-content" style="${this.isExpanded ? 'display: block;' : 'display: none;'}">
                    <div class="rules-vertical-list">
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

                        ${progress.min_trading_days ? `
                        <div class="rule-item">
                            <div class="rule-label">
                                <span>Trading Days</span>
                                <span class="rule-value">
                                    ${progress.trading_days || 0} / ${progress.min_trading_days}
                                </span>
                            </div>
                        </div>
                        ` : ''}

                        ${progress.min_profitable_days ? `
                        <div class="rule-item">
                            <div class="rule-label">
                                <span>Profitable Days</span>
                                <span class="rule-value">
                                    ${progress.profitable_days || 0} / ${progress.min_profitable_days}
                                </span>
                            </div>
                            <div class="progress-label">
                                <span>Threshold: ${(progress.profitable_day_threshold_pct || 0).toFixed(1)}%</span>
                                <span>${(progress.profitable_day_threshold_usd || 0).toFixed(2)} ${this.account.currency}</span>
                            </div>
                        </div>
                        ` : ''}

                        ${progress.consistency_pct ? `
                        <div class="rule-item">
                            <div class="rule-label">
                                <span>Consistency Rule</span>
                                <span class="rule-value">
                                    ${(progress.consistency_pct || 0).toFixed(1)}%
                                </span>
                            </div>
                            <div class="progress-label">
                                <span>Best day: ${(progress.best_day_profit || 0).toFixed(2)} ${this.account.currency}</span>
                                <span>Min profit: ${(progress.minimum_required_profit || 0).toFixed(2)} ${this.account.currency}</span>
                            </div>
                        </div>
                        ` : ''}

                        ${progress.static_drawdown_floor ? `
                        <div class="rule-item">
                            <div class="rule-label">
                                <span>Static DD Floor</span>
                                <span class="rule-value">
                                    ${(progress.static_drawdown_floor || 0).toFixed(2)} ${this.account.currency}
                                </span>
                            </div>
                        </div>
                        ` : ''}

                        ${progress.inactivity_limit_days ? `
                        <div class="rule-item">
                            <div class="rule-label">
                                <span>Inactivity Limit</span>
                                <span class="rule-value">
                                    ${progress.inactive_days ?? 0} / ${progress.inactivity_limit_days} days
                                </span>
                            </div>
                        </div>
                        ` : ''}

                        ${progress.is_ptb_lightning_funded ? `
                        <div class="rule-item ${progress.payout_readiness?.eligible ? 'achieved' : 'warning'}">
                            <div class="rule-label">
                                <span>Payout Readiness</span>
                                <span class="rule-value ${progress.payout_readiness?.eligible ? 'positive' : 'negative'}">
                                    ${progress.payout_readiness?.eligible ? 'Eligible' : 'Not eligible'}
                                </span>
                            </div>
                            <div class="progress-label">
                                <span>${progress.current_profit?.toFixed(2) || '0.00'} ${this.account.currency} profit</span>
                                <span>${progress.payout_progress_pct?.toFixed(0) || 0}% to target</span>
                            </div>
                            ${progress.payout_readiness?.missing_requirements?.length ? `
                            <div class="progress-label" style="display: block; margin-top: 8px;">
                                ${progress.payout_readiness.missing_requirements.map(item => `
                                    <div style="color: var(--danger, #ef4444); margin-top: 4px;">• ${item}</div>
                                `).join('')}
                            </div>
                            ` : ''}
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
            </div>
        `;

        // Bind toggle event
        const btn = document.getElementById('rules-toggle-btn');
        if (btn) {
            btn.onclick = () => this.toggle();
        }

        // Initialize icons if lucide is available
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    calculateRules() {
        const balance = this.stats?.balance || this.account.initial_balance;
        const initialBalance = this.account.initial_balance;
        const growth = ((balance - initialBalance) / initialBalance) * 100;
        const progress = this.ruleProgress || {};

        const violations = [];
        let overallStatus = 'safe';

        const dailyLossUsed = progress.daily_loss_used_account_pct || 0;
        const dailyLossRemaining = (this.account.max_daily_loss_pct || 0) - dailyLossUsed;
        const dailyLossPercentage = this.account.max_daily_loss_pct
            ? (dailyLossUsed / this.account.max_daily_loss_pct) * 100
            : 0;

        let dailyLossStatus = 'safe';
        if (progress.historical_daily_loss_breached || dailyLossPercentage >= 100) {
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
        if (progress.static_drawdown_breached || totalLossPercentage >= 100) {
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
