/**
 * Analytics Page Logic
 * Renders advanced trading analytics
 */

let dateFilter;
let currentDateRange = { from_ts: null, to_ts: null };
let currentAccountId = null;

// Listen for account changes
document.addEventListener('accountChanged', (e) => {
    console.log('Account changed event received:', e.detail);
    currentAccountId = e.detail.accountId;
    loadAnalytics(currentDateRange);
});

// Also listen for the window event (for compatibility)
window.addEventListener('accountChanged', (e) => {
    console.log('Account changed (window event):', e.detail);
    currentAccountId = e.detail.accountId;
    loadAnalytics(currentDateRange);
});

async function loadAnalytics(dateRange = {}) {
    try {
        currentDateRange = dateRange;
        const params = new URLSearchParams();

        // Add date range params
        if (dateRange.from) params.append('from', dateRange.from);
        if (dateRange.to) params.append('to', dateRange.to);

        // Add account filter
        if (currentAccountId) {
            params.append('account_id', currentAccountId);
            console.log('Loading analytics for account:', currentAccountId);
        }

        const queryString = params.toString();
        const dashboardUrl = `/api/dashboard${queryString ? '?' + queryString : ''}`;
        const tradesUrl = `/api/trades${queryString ? '?' + queryString : ''}`;

        console.log('Fetching:', dashboardUrl);

        const [data, trades] = await Promise.all([
            fetch(dashboardUrl).then(r => r.json()),
            fetch(tradesUrl).then(r => r.json())
        ]);

        // Store trades globally for heatmap
        window.currentTrades = trades;

        renderAnalyticsPage(data, trades);
    } catch (err) {
        console.error('Error loading analytics:', err);
        document.getElementById('content').innerHTML = `
            <div class="panel">
                <div class="panel-title">⚠️ Error Loading Analytics</div>
                <p style="color: var(--muted);">
                    ${err.message}
                </p>
            </div>
        `;
    }
}

// Initialize date filter and load analytics
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        dateFilter = new DateRangeFilter('dateFilter', (range) => {
            loadAnalytics(range);
        });
        loadAnalytics();
    });
} else {
    dateFilter = new DateRangeFilter('dateFilter', (range) => {
        loadAnalytics(range);
    });
    loadAnalytics();
}

function renderAnalyticsPage(data, trades) {
    const stats = data.stats || {};
    const analytics = data.analytics || {};
    const distributions = data.distributions || {};

    document.getElementById('content').innerHTML = `
        <!-- Date Filter -->
        <div id="analyticsDateFilter"></div>

        <!-- Quick Stats -->
        <div class="grid grid-3">
            <div class="panel">
                <div class="panel-title">Total Trades</div>
                <div class="stat-value">${stats.total_trades || 0}</div>
            </div>
            <div class="panel">
                <div class="panel-title">Win Rate</div>
                <div class="stat-value ${(stats.win_rate || 0) >= 50 ? 'positive' : 'negative'}">
                    ${(stats.win_rate || 0).toFixed(1)}%
                </div>
            </div>
            <div class="panel">
                <div class="panel-title">Profit Factor</div>
                <div class="stat-value ${(stats.profit_factor || 0) >= 1.5 ? 'positive' : 'negative'}">
                    ${(stats.profit_factor || 0).toFixed(2)}
                </div>
            </div>
        </div>

        <!-- Time Heatmap -->
        <div class="panel">
            <div class="panel-title">⏰ Time-Based Performance Heatmap</div>
            <div class="panel-subtitle">Profitability by day of week and hour</div>
            <div id="timeHeatmap" style="margin-top: 20px;"></div>
        </div>

        <!-- Two Column Layout -->
        <div class="grid grid-2">
            <!-- Win/Loss Distribution -->
            <div class="panel">
                <div class="panel-title">📊 Win/Loss Distribution</div>
                <div class="chart-container">
                    <canvas id="winLossChart"></canvas>
                </div>
            </div>

            <!-- Risk-Reward Distribution -->
            <div class="panel">
                <div class="panel-title">🎯 Risk-Reward Distribution</div>
                <div class="chart-container">
                    <canvas id="rrDistChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Directional Deep Dive -->
        <div class="panel">
            <div class="panel-title">🎯 Directional Analysis</div>
            <div class="panel-subtitle">Long vs Short performance comparison</div>
            <div id="directionalAnalysis"></div>
        </div>

        <!-- Two Column Layout -->
        <div class="grid grid-2">
            <!-- Session Performance -->
            <div class="panel">
                <div class="panel-title">🌍 Session Performance</div>
                <div class="panel-subtitle">Asian, London, NY sessions</div>
                <div id="sessionPerformance"></div>
            </div>

            <!-- Symbol Performance -->
            <div class="panel">
                <div class="panel-title">📈 Symbol Performance</div>
                <div class="panel-subtitle">Top and bottom performers</div>
                <div id="symbolPerformance"></div>
            </div>
        </div>

        <!-- Outcome Analysis -->
        <div class="panel">
            <div class="panel-title">🎲 Outcome Analysis</div>
            <div class="panel-subtitle">TP, SL, and Manual exits</div>
            <div class="chart-container">
                <canvas id="outcomeChart"></canvas>
            </div>
        </div>

        <!-- Monte Carlo Projections -->
        <div class="panel">
            <div class="panel-title">🎰 Monte Carlo Projections</div>
            <div class="panel-subtitle">Probabilistic future outcomes based on your trading history</div>
            <div class="chart-container" style="height: 320px;">
                <canvas id="monteCarloChart"></canvas>
            </div>
            <div id="monteCarlo"></div>
        </div>
    `;

    // Render visualizations
    renderTimeHeatmap(analytics.by_hour, analytics.by_weekday);
    renderWinLossDistribution(stats);
    renderRRDistribution(trades);
    renderDirectionalAnalysis(analytics.by_direction);
    renderSessionPerformance(distributions.session, trades);
    renderSymbolPerformance(distributions.symbol_pnl, trades);
    renderOutcomeAnalysis(distributions.outcome);
    renderMonteCarloProjections();
}

/**
 * Render time-based heatmap
 */
function renderTimeHeatmap(byHour, byWeekday) {
    const container = document.getElementById('timeHeatmap');
    if (!container) return;

    // Get trades to build actual heatmap
    const trades = window.currentTrades || [];

    if (trades.length === 0) {
        container.innerHTML =
            '<p style="color: var(--muted); text-align: center; padding: 40px;">No time-based data available</p>';
        return;
    }

    // Build data structure: [day][hour] = pnl
    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    const dayShort = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const hours = Array.from({ length: 24 }, (_, i) => i);

    // Initialize heatmap data
    const heatmapData = {};
    const heatmapCounts = {};
    days.forEach(day => {
        heatmapData[day] = {};
        heatmapCounts[day] = {};
        hours.forEach(hour => {
            heatmapData[day][hour] = 0;
            heatmapCounts[day][hour] = 0;
        });
    });

    // Fill in data from actual trades
    trades.forEach(trade => {
        if (!trade.ts_open || !trade.pnl_usd) return;

        try {
            const date = new Date(trade.ts_open);
            const dayOfWeek = date.getDay(); // 0 = Sunday, 1 = Monday, etc.
            const hour = date.getHours();

            // Convert Sunday (0) to index 6, Monday (1) to index 0, etc.
            const dayIndex = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
            const dayName = days[dayIndex];

            heatmapData[dayName][hour] += trade.pnl_usd;
            heatmapCounts[dayName][hour] += 1;
        } catch (e) {
            console.warn('Error parsing trade timestamp:', trade.ts_open, e);
        }
    });

    // Find max value for color scaling
    let maxValue = 1; // Minimum to avoid division by zero
    days.forEach(day => {
        hours.forEach(hour => {
            maxValue = Math.max(maxValue, Math.abs(heatmapData[day][hour]));
        });
    });

    // Build HTML
    let html = '<div class="heatmap-grid" style="overflow-x: auto;">';

    // Header row
    html += '<div class="heatmap-row"><div class="heatmap-cell heatmap-header"></div>';
    hours.forEach(h => {
        html += `<div class="heatmap-cell heatmap-header">${h}</div>`;
    });
    html += '</div>';

    // Data rows
    days.forEach((day, dayIdx) => {
        html += `<div class="heatmap-row"><div class="heatmap-cell heatmap-header">${dayShort[dayIdx]}</div>`;
        hours.forEach(hour => {
            const value = heatmapData[day][hour];
            const count = heatmapCounts[day][hour];
            const intensity = Math.min(Math.abs(value) / maxValue, 1) * 0.7 + 0.1; // Min 0.1, max 0.8
            const color = value > 0.01
                ? `rgba(16, 185, 129, ${intensity})`
                : value < -0.01
                    ? `rgba(239, 68, 68, ${intensity})`
                    : 'rgba(139, 146, 168, 0.1)';

            html += `<div class="heatmap-cell" style="background-color: ${color}" 
                     title="${day} ${hour}:00 - ${value >= 0 ? '+' : ''}${value.toFixed(2)} (${count} trades)"></div>`;
        });
        html += '</div>';
    });

    html += '</div>';

    // Add legend
    html += `
        <div style="display: flex; justify-content: center; gap: 20px; margin-top: 20px; font-size: 12px; color: var(--muted);">
            <div style="display: flex; align-items: center; gap: 8px;">
                <div style="width: 20px; height: 20px; background: rgba(239, 68, 68, 0.7); border-radius: 4px;"></div>
                <span>Losses</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <div style="width: 20px; height: 20px; background: rgba(139, 146, 168, 0.1); border-radius: 4px;"></div>
                <span>Neutral</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
                <div style="width: 20px; height: 20px; background: rgba(16, 185, 129, 0.7); border-radius: 4px;"></div>
                <span>Profits</span>
            </div>
        </div>
    `;

    container.innerHTML = html;
}

/**
 * Render win/loss distribution chart
 */
function renderWinLossDistribution(stats) {
    const wins = stats.wins || 0;
    const losses = stats.losses || 0;
    const avgWin = stats.avg_win_usd || 0;
    const avgLoss = Math.abs(stats.avg_loss_usd || 0);
    const largestWin = stats.largest_win || 0;
    const largestLoss = Math.abs(stats.largest_loss || 0);

    createBarChart('winLossChart',
        ['Wins', 'Losses', 'Avg Win', 'Avg Loss', 'Best Win', 'Worst Loss'],
        [wins, losses, avgWin, avgLoss, largestWin, largestLoss],
        {
            label: 'Value',
            colors: [
                CHART_COLORS.green,
                CHART_COLORS.red,
                CHART_COLORS.green,
                CHART_COLORS.red,
                CHART_COLORS.green,
                CHART_COLORS.red
            ]
        }
    );
}

/**
 * Render risk-reward distribution histogram
 */
function renderRRDistribution(trades) {
    if (!trades || trades.length === 0) {
        return;
    }

    // Calculate RR buckets
    const buckets = {
        '<1': 0,
        '1-1.5': 0,
        '1.5-2': 0,
        '2-3': 0,
        '3+': 0
    };

    const winsByBucket = {
        '<1': 0,
        '1-1.5': 0,
        '1.5-2': 0,
        '2-3': 0,
        '3+': 0
    };

    trades.forEach(trade => {
        const rr = trade.rr_ratio || 0;
        const isWin = (trade.pnl_usd || 0) > 0;

        if (rr < 1) {
            buckets['<1']++;
            if (isWin) winsByBucket['<1']++;
        } else if (rr < 1.5) {
            buckets['1-1.5']++;
            if (isWin) winsByBucket['1-1.5']++;
        } else if (rr < 2) {
            buckets['1.5-2']++;
            if (isWin) winsByBucket['1.5-2']++;
        } else if (rr < 3) {
            buckets['2-3']++;
            if (isWin) winsByBucket['2-3']++;
        } else {
            buckets['3+']++;
            if (isWin) winsByBucket['3+']++;
        }
    });

    const labels = Object.keys(buckets);
    const data = Object.values(buckets);
    const colors = labels.map(label => {
        const bucket = buckets[label];
        const wins = winsByBucket[label];
        const winRate = bucket > 0 ? (wins / bucket) : 0;
        return winRate >= 0.5 ? CHART_COLORS.green : CHART_COLORS.red;
    });

    createBarChart('rrDistChart', labels, data, {
        label: 'Trade Count',
        colors: colors
    });
}

/**
 * Render directional analysis (Long vs Short)
 */
function renderDirectionalAnalysis(byDirection) {
    const container = document.getElementById('directionalAnalysis');
    if (!container) return;

    if (!byDirection || Object.keys(byDirection).length === 0) {
        container.innerHTML = '<p style="color: var(--muted); text-align: center; padding: 20px;">No directional data available</p>';
        return;
    }

    const longStats = byDirection.long || { count: 0, total_pnl: 0, win_rate: 0, avg_pnl: 0 };
    const shortStats = byDirection.short || { count: 0, total_pnl: 0, win_rate: 0, avg_pnl: 0 };

    container.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px;">
            <!-- Long Stats -->
            <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 16px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                    <div style="font-size: 24px;">🟢</div>
                    <div style="font-size: 16px; font-weight: 700;">LONG</div>
                </div>
                <div style="display: grid; gap: 8px;">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: var(--muted); font-size: 12px;">Total P&L</span>
                        <span style="font-weight: 700; color: ${longStats.total_pnl >= 0 ? 'var(--green)' : 'var(--red)'};">
                            ${longStats.total_pnl >= 0 ? '+' : ''}${(longStats.total_pnl || 0).toFixed(2)}
                        </span>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: var(--muted); font-size: 12px;">Win Rate</span>
                        <span style="font-weight: 700;">${(longStats.win_rate || 0).toFixed(1)}%</span>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: var(--muted); font-size: 12px;">Avg P&L</span>
                        <span style="font-weight: 700; color: ${longStats.avg_pnl >= 0 ? 'var(--green)' : 'var(--red)'};">
                            ${longStats.avg_pnl >= 0 ? '+' : ''}${(longStats.avg_pnl || 0).toFixed(2)}
                        </span>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: var(--muted); font-size: 12px;">Trade Count</span>
                        <span style="font-weight: 700;">${longStats.count || 0}</span>
                    </div>
                </div>
            </div>

            <!-- Short Stats -->
            <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px; padding: 16px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                    <div style="font-size: 24px;">🔴</div>
                    <div style="font-size: 16px; font-weight: 700;">SHORT</div>
                </div>
                <div style="display: grid; gap: 8px;">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: var(--muted); font-size: 12px;">Total P&L</span>
                        <span style="font-weight: 700; color: ${shortStats.total_pnl >= 0 ? 'var(--green)' : 'var(--red)'};">
                            ${shortStats.total_pnl >= 0 ? '+' : ''}${(shortStats.total_pnl || 0).toFixed(2)}
                        </span>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: var(--muted); font-size: 12px;">Win Rate</span>
                        <span style="font-weight: 700;">${(shortStats.win_rate || 0).toFixed(1)}%</span>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: var(--muted); font-size: 12px;">Avg P&L</span>
                        <span style="font-weight: 700; color: ${shortStats.avg_pnl >= 0 ? 'var(--green)' : 'var(--red)'};">
                            ${shortStats.avg_pnl >= 0 ? '+' : ''}${(shortStats.avg_pnl || 0).toFixed(2)}
                        </span>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: var(--muted); font-size: 12px;">Trade Count</span>
                        <span style="font-weight: 700;">${shortStats.count || 0}</span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Render session performance
 */
function renderSessionPerformance(sessionDist, trades) {
    const container = document.getElementById('sessionPerformance');
    if (!container) return;

    if (!trades || trades.length === 0) {
        container.innerHTML = '<p style="color: var(--muted); text-align: center; padding: 20px;">No session data available</p>';
        return;
    }

    // Calculate session stats
    const sessionStats = {};
    trades.forEach(trade => {
        const session = trade.session || 'Unknown';
        if (!sessionStats[session]) {
            sessionStats[session] = { count: 0, pnl: 0, wins: 0 };
        }
        sessionStats[session].count++;
        sessionStats[session].pnl += trade.pnl_usd || 0;
        if ((trade.pnl_usd || 0) > 0) sessionStats[session].wins++;
    });

    const sessions = ['Asian', 'London', 'NY'];
    const sessionEmojis = { 'Asian': '🌏', 'London': '🇬🇧', 'NY': '🇺🇸' };

    let html = '<div style="display: grid; gap: 12px;">';

    sessions.forEach(session => {
        const stats = sessionStats[session] || { count: 0, pnl: 0, wins: 0 };
        const winRate = stats.count > 0 ? (stats.wins / stats.count * 100) : 0;
        const avgPnl = stats.count > 0 ? (stats.pnl / stats.count) : 0;

        html += `
            <div style="background: var(--panel-light); border: 1px solid var(--border); border-radius: 8px; padding: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 20px;">${sessionEmojis[session] || '🌍'}</span>
                        <span style="font-weight: 700;">${session}</span>
                    </div>
                    <span style="font-weight: 700; color: ${stats.pnl >= 0 ? 'var(--green)' : 'var(--red)'};">
                        ${stats.pnl >= 0 ? '+' : ''}${stats.pnl.toFixed(2)}
                    </span>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--muted);">
                    <span>${stats.count} trades</span>
                    <span>${winRate.toFixed(1)}% WR</span>
                    <span>Avg: ${avgPnl >= 0 ? '+' : ''}${avgPnl.toFixed(2)}</span>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

/**
 * Render symbol performance
 */
function renderSymbolPerformance(symbolPnl, trades) {
    const container = document.getElementById('symbolPerformance');
    if (!container) return;

    if (!trades || trades.length === 0) {
        container.innerHTML = '<p style="color: var(--muted); text-align: center; padding: 20px;">No symbol data available</p>';
        return;
    }

    // Calculate symbol stats
    const symbolStats = {};
    trades.forEach(trade => {
        const symbol = trade.symbol || 'Unknown';
        if (!symbolStats[symbol]) {
            symbolStats[symbol] = { count: 0, pnl: 0, wins: 0 };
        }
        symbolStats[symbol].count++;
        symbolStats[symbol].pnl += trade.pnl_usd || 0;
        if ((trade.pnl_usd || 0) > 0) symbolStats[symbol].wins++;
    });

    // Sort by P&L
    const sortedSymbols = Object.entries(symbolStats)
        .sort((a, b) => b[1].pnl - a[1].pnl);

    // Get top 5 and bottom 3
    const topSymbols = sortedSymbols.slice(0, 5);
    const bottomSymbols = sortedSymbols.slice(-3).reverse();

    let html = '<div style="display: grid; gap: 8px;">';

    // Top performers
    html += '<div style="font-size: 12px; font-weight: 700; color: var(--green); margin-bottom: 4px;">TOP PERFORMERS</div>';
    topSymbols.forEach(([symbol, stats]) => {
        const winRate = stats.count > 0 ? (stats.wins / stats.count * 100) : 0;
        html += `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px; background: var(--panel-light); border-radius: 6px;">
                <div>
                    <div style="font-weight: 700; font-size: 13px;">${symbol}</div>
                    <div style="font-size: 11px; color: var(--muted);">${stats.count} trades • ${winRate.toFixed(1)}% WR</div>
                </div>
                <div style="font-weight: 700; color: ${stats.pnl >= 0 ? 'var(--green)' : 'var(--red)'};">
                    ${stats.pnl >= 0 ? '+' : ''}${stats.pnl.toFixed(2)}
                </div>
            </div>
        `;
    });

    // Bottom performers
    if (bottomSymbols.length > 0 && bottomSymbols[0][1].pnl < 0) {
        html += '<div style="font-size: 12px; font-weight: 700; color: var(--red); margin-top: 12px; margin-bottom: 4px;">NEEDS IMPROVEMENT</div>';
        bottomSymbols.forEach(([symbol, stats]) => {
            const winRate = stats.count > 0 ? (stats.wins / stats.count * 100) : 0;
            html += `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px; background: var(--panel-light); border-radius: 6px;">
                    <div>
                        <div style="font-weight: 700; font-size: 13px;">${symbol}</div>
                        <div style="font-size: 11px; color: var(--muted);">${stats.count} trades • ${winRate.toFixed(1)}% WR</div>
                    </div>
                    <div style="font-weight: 700; color: var(--red);">
                        ${stats.pnl.toFixed(2)}
                    </div>
                </div>
            `;
        });
    }

    html += '</div>';
    container.innerHTML = html;
}

/**
 * Render outcome analysis (TP, SL, Manual)
 */
function renderOutcomeAnalysis(outcomeDist) {
    if (!outcomeDist || Object.keys(outcomeDist).length === 0) {
        return;
    }

    const outcomes = ['TP', 'SL', 'Manual'];
    const labels = [];
    const data = [];
    const colors = [];

    outcomes.forEach(outcome => {
        const count = outcomeDist[outcome] || 0;
        if (count > 0) {
            labels.push(outcome);
            data.push(count);
            colors.push(
                outcome === 'TP' ? CHART_COLORS.green :
                    outcome === 'SL' ? CHART_COLORS.red :
                        CHART_COLORS.accent
            );
        }
    });

    createDoughnutChart('outcomeChart', labels, data, colors);
}


/**
 * Render Monte Carlo projections
 */
async function renderMonteCarloProjections() {
    const container = document.getElementById('monteCarlo');
    if (!container) {
        console.error('Monte Carlo container not found');
        return;
    }

    // Show loading state
    container.innerHTML = '<p style="color: var(--muted); text-align: center; padding: 20px;">Loading Monte Carlo simulation...</p>';

    try {
        console.log('Fetching Monte Carlo data for account:', currentAccountId);

        // Build params with account filter
        const params = new URLSearchParams();
        if (currentAccountId) {
            params.append('account_id', currentAccountId);
        }
        if (currentDateRange.from) {
            params.append('from', currentDateRange.from);
        }
        if (currentDateRange.to) {
            params.append('to', currentDateRange.to);
        }

        const queryString = params.toString();
        const url = `/api/analytics/monte-carlo${queryString ? '?' + queryString : ''}`;
        console.log('Monte Carlo URL:', url);

        const response = await fetch(url);
        const mcData = await response.json();
        console.log('Monte Carlo data received:', mcData);

        if (mcData.error) {
            container.innerHTML = `<p style="color: var(--muted); text-align: center; padding: 20px;">${mcData.error}</p>`;
            return;
        }

        if (!mcData || !mcData.simulations || mcData.simulations.length === 0) {
            container.innerHTML = '<p style="color: var(--muted); text-align: center; padding: 20px;">Not enough trade data for Monte Carlo simulation (need at least 5 closed trades)</p>';
            return;
        }

        // Prepare data for fan chart
        const simulations = mcData.simulations;
        const steps = simulations[0].length;
        const labels = Array.from({ length: steps }, (_, i) => `Trade ${i + 1}`);

        // Calculate percentiles
        const p25 = [];
        const p50 = [];
        const p75 = [];

        for (let step = 0; step < steps; step++) {
            const values = simulations.map(sim => sim[step]).sort((a, b) => a - b);
            p25.push(values[Math.floor(values.length * 0.25)]);
            p50.push(values[Math.floor(values.length * 0.50)]);
            p75.push(values[Math.floor(values.length * 0.75)]);
        }

        // Create fan chart
        console.log('Creating fan chart...');
        createFanChart('monteCarloChart', labels, {
            p25,
            p50,
            p75,
            stats: mcData.stats
        });

        // Add statistics
        const stats = mcData.stats || {};
        const statsHtml = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-top: 20px;">
                <div style="background: var(--panel-light); padding: 12px; border-radius: 8px;">
                    <div style="font-size: 11px; color: var(--muted); margin-bottom: 4px;">MEDIAN OUTCOME</div>
                    <div style="font-size: 20px; font-weight: 700; color: ${stats.median_final >= 0 ? 'var(--green)' : 'var(--red)'};">
                        ${stats.median_final >= 0 ? '+' : ''}${(stats.median_final || 0).toFixed(2)}
                    </div>
                </div>
                <div style="background: var(--panel-light); padding: 12px; border-radius: 8px;">
                    <div style="font-size: 11px; color: var(--muted); margin-bottom: 4px;">BEST CASE (75th)</div>
                    <div style="font-size: 20px; font-weight: 700; color: var(--green);">
                        +${(stats.p75_final || 0).toFixed(2)}
                    </div>
                </div>
                <div style="background: var(--panel-light); padding: 12px; border-radius: 8px;">
                    <div style="font-size: 11px; color: var(--muted); margin-bottom: 4px;">WORST CASE (25th)</div>
                    <div style="font-size: 20px; font-weight: 700; color: ${stats.p25_final >= 0 ? 'var(--green)' : 'var(--red)'};">
                        ${stats.p25_final >= 0 ? '+' : ''}${(stats.p25_final || 0).toFixed(2)}
                    </div>
                </div>
                <div style="background: var(--panel-light); padding: 12px; border-radius: 8px;">
                    <div style="font-size: 11px; color: var(--muted); margin-bottom: 4px;">PROFIT PROBABILITY</div>
                    <div style="font-size: 20px; font-weight: 700;">
                        ${((stats.prob_profit || 0) * 100).toFixed(1)}%
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = statsHtml;
        console.log('Monte Carlo rendered successfully');

    } catch (err) {
        console.error('Error loading Monte Carlo:', err);
        container.innerHTML = '<p style="color: var(--red); text-align: center; padding: 20px;">Error loading Monte Carlo projections. Check console for details.</p>';
    }
}
