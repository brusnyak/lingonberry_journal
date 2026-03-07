// Weekly Review - BacktestingMax-style with Drawing Tools & cTrader Integration
class WeeklyReview {
    constructor() {
        this.currentWeekStart = '2026-02-23'; // Feb 23-27 for testing
        this.trades = [];
        this.selectedTrade = null;
        this.chart = null;
        this.candles = [];
        this.drawingTools = null;
        this.perfectTrades = [];
        this.init();
    }

    getWeekStart(date) {
        const d = new Date(date);
        const day = d.getDay();
        const diff = d.getDate() - day + (day === 0 ? -6 : 1);
        const monday = new Date(d.setDate(diff));
        monday.setHours(0, 0, 0, 0);
        return monday.toISOString().split('T')[0];
    }

    async init() {
        await this.loadWeekData();
        this.render();
    }

    async loadWeekData() {
        try {
            // Load EURUSD data from cTrader for Feb 23-27
            await this.loadCTraderData('EURUSD', 'H1');

            // Load perfect trades from localStorage
            this.loadPerfectTrades();

            this.stats = {
                total_trades: this.perfectTrades.length,
                win_rate: 0,
                net_pnl: 0,
                growth_pct: 0
            };
        } catch (err) {
            console.error('Failed to load week data:', err);
        }
    }

    async loadCTraderData(symbol, timeframe) {
        try {
            // For now, generate sample data - you'll wire up real cTrader API
            this.candles = this.generateSampleCandles();
            console.log(`Loaded ${this.candles.length} candles for ${symbol} ${timeframe}`);
        } catch (err) {
            console.error('Failed to load cTrader data:', err);
        }
    }

    generateSampleCandles() {
        // Generate sample EURUSD data for Feb 23-27
        const candles = [];
        const startPrice = 1.0850;
        let price = startPrice;
        const startDate = new Date('2026-02-23T00:00:00');

        for (let i = 0; i < 120; i++) { // 5 days * 24 hours
            const date = new Date(startDate.getTime() + i * 3600000);
            const change = (Math.random() - 0.5) * 0.002;
            price += change;

            candles.push({
                ts: date.toISOString(),
                open: price,
                high: price + Math.random() * 0.001,
                low: price - Math.random() * 0.001,
                close: price,
                volume: Math.random() * 1000
            });
        }

        return candles;
    }

    loadPerfectTrades() {
        const stored = localStorage.getItem(`perfectTrades_${this.currentWeekStart}`);
        this.perfectTrades = stored ? JSON.parse(stored) : [];
    }

    savePerfectTrades() {
        localStorage.setItem(`perfectTrades_${this.currentWeekStart}`, JSON.stringify(this.perfectTrades));
    }

    addPerfectTrade() {
        const entry = prompt('Enter entry price:');
        const exit = prompt('Enter exit price:');
        const direction = prompt('Direction (LONG/SHORT):').toUpperCase();

        if (!entry || !exit || !direction) return;

        const trade = {
            id: Date.now(),
            entry: parseFloat(entry),
            exit: parseFloat(exit),
            direction,
            pnl: direction === 'LONG' ?
                (parseFloat(exit) - parseFloat(entry)) * 10000 :
                (parseFloat(entry) - parseFloat(exit)) * 10000,
            timestamp: new Date().toISOString()
        };

        this.perfectTrades.push(trade);
        this.savePerfectTrades();
        this.render();
        this.showToast('Perfect trade added!');
    }

    render() {
        const container = document.getElementById('weeklyContent');
        if (!container) return;

        container.innerHTML = `
            <div class="weekly-review-container">
                <!-- Week Navigation -->
                <div class="week-nav">
                    <button class="week-nav-btn" onclick="weeklyReview.previousWeek()">
                        ← Previous Week
                    </button>
                    <div class="week-current">
                        Week of ${this.formatDate(this.currentWeekStart)} (EURUSD)
                    </div>
                    <button class="week-nav-btn" onclick="weeklyReview.nextWeek()">
                        Next Week →
                    </button>
                </div>

                <!-- Week Stats -->
                <div class="week-stats-grid">
                    <div class="week-stat-card">
                        <div class="week-stat-label">Perfect Trades</div>
                        <div class="week-stat-value">${this.perfectTrades.length}</div>
                    </div>
                    <div class="week-stat-card">
                        <div class="week-stat-label">Win Rate</div>
                        <div class="week-stat-value">-</div>
                    </div>
                    <div class="week-stat-card">
                        <div class="week-stat-label">Net P&L</div>
                        <div class="week-stat-value">-</div>
                    </div>
                    <div class="week-stat-card">
                        <div class="week-stat-label">Growth</div>
                        <div class="week-stat-value">-</div>
                    </div>
                </div>

                <!-- Main Content: Chart + Trade List -->
                <div class="weekly-main-grid">
                    <!-- Chart Section -->
                    <div class="weekly-chart-section">
                        <div class="chart-header">
                            <div class="chart-title">EURUSD H1 - Feb 23-27, 2026</div>
                            <div class="chart-tools">
                                <button class="chart-tool-btn" onclick="weeklyReview.setDrawingTool('line')" title="Draw Line">
                                    📏
                                </button>
                                <button class="chart-tool-btn" onclick="weeklyReview.setDrawingTool('rect')" title="Draw Rectangle">
                                    ▭
                                </button>
                                <button class="chart-tool-btn" onclick="weeklyReview.setDrawingTool('horizontal')" title="Horizontal Line">
                                    ─
                                </button>
                                <button class="chart-tool-btn" onclick="weeklyReview.undoDrawing()" title="Undo">
                                    ↶
                                </button>
                                <button class="chart-tool-btn" onclick="weeklyReview.clearDrawings()" title="Clear All">
                                    🗑️
                                </button>
                            </div>
                        </div>
                        <div class="chart-canvas-wrapper">
                            <canvas id="weeklyChart"></canvas>
                            <canvas id="drawingCanvas" style="position: absolute; top: 0; left: 0; pointer-events: none;"></canvas>
                        </div>
                        
                        <button class="add-perfect-trade-btn" onclick="weeklyReview.addPerfectTrade()">
                            ➕ Add Perfect Trade
                        </button>
                    </div>

                    <!-- Trade List Section -->
                    <div class="weekly-trades-section">
                        <div class="trades-header">
                            <div class="trades-title">Perfect Trades (${this.perfectTrades.length})</div>
                        </div>
                        <div class="trades-list">
                            ${this.perfectTrades.length === 0 ? `
                                <div class="empty-state">
                                    <div class="empty-icon">📭</div>
                                    <div>No perfect trades yet</div>
                                    <div style="font-size: 12px; margin-top: 8px;">
                                        Click "Add Perfect Trade" to log what you should have done
                                    </div>
                                </div>
                            ` : this.perfectTrades.map(trade => this.renderPerfectTradeItem(trade)).join('')}
                        </div>
                    </div>
                </div>

                <!-- Weekly Reflection -->
                <div class="weekly-reflection">
                    <div class="reflection-header">
                        <div class="reflection-title">📝 Weekly Reflection</div>
                        <button class="btn-primary" onclick="weeklyReview.saveReflection()">
                            Save Reflection
                        </button>
                    </div>
                    <div class="reflection-grid">
                        <div class="reflection-box">
                            <label>Market Summary</label>
                            <textarea id="reflectionSummary" rows="4" 
                                      placeholder="What happened in the markets this week?"></textarea>
                        </div>
                        <div class="reflection-box">
                            <label>Key Wins & Good Habits</label>
                            <textarea id="reflectionWins" rows="4" 
                                      placeholder="What went well?"></textarea>
                        </div>
                        <div class="reflection-box">
                            <label>Mistakes & Lessons</label>
                            <textarea id="reflectionMistakes" rows="4" 
                                      placeholder="What can be improved?"></textarea>
                        </div>
                        <div class="reflection-box">
                            <label>Next Week Focus</label>
                            <textarea id="reflectionFocus" rows="4" 
                                      placeholder="What to focus on next week?"></textarea>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.renderChart();
    }

    renderPerfectTradeItem(trade) {
        const pnl = trade.pnl || 0;

        return `
            <div class="trade-list-item">
                <div class="trade-item-header">
                    <div class="trade-symbol">
                        ${trade.direction === 'LONG' ? '🟢' : '🔴'} EURUSD
                    </div>
                    <div class="trade-pnl ${pnl >= 0 ? 'positive' : 'negative'}">
                        ${pnl >= 0 ? '+' : ''}${pnl.toFixed(1)} pips
                    </div>
                </div>
                <div class="trade-item-details">
                    <span>${trade.direction}</span>
                    <span>•</span>
                    <span>Entry: ${trade.entry.toFixed(5)}</span>
                    <span>•</span>
                    <span>Exit: ${trade.exit.toFixed(5)}</span>
                </div>
            </div>
        `;
    }

    renderChart() {
        const canvas = document.getElementById('weeklyChart');
        const drawingCanvas = document.getElementById('drawingCanvas');
        if (!canvas || this.candles.length === 0) return;

        const ctx = canvas.getContext('2d');

        // Destroy existing chart
        if (this.chart) {
            this.chart.destroy();
        }

        // Set canvas size
        const container = canvas.parentElement;
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;
        drawingCanvas.width = canvas.width;
        drawingCanvas.height = canvas.height;

        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: this.candles.map(c => this.formatDateTime(c.ts)),
                datasets: [
                    {
                        label: 'EURUSD',
                        data: this.candles.map(c => c.close),
                        borderColor: '#ff8c00',
                        backgroundColor: 'rgba(255, 140, 0, 0.1)',
                        borderWidth: 2,
                        pointRadius: 0,
                        fill: true,
                        tension: 0.1
                    }
                ]
            },
            options: {
                responsive: false,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.9)',
                        titleColor: '#ff8c00',
                        bodyColor: '#ffffff',
                        borderColor: '#ff8c00',
                        borderWidth: 1
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: '#999999',
                            font: { size: 10 },
                            maxTicksLimit: 12
                        },
                        grid: {
                            color: 'rgba(255, 140, 0, 0.1)'
                        }
                    },
                    y: {
                        position: 'right',
                        ticks: {
                            color: '#999999',
                            font: { size: 10 }
                        },
                        grid: {
                            color: 'rgba(255, 140, 0, 0.1)'
                        }
                    }
                }
            }
        });

        // Initialize drawing tools
        this.drawingTools = new DrawingTools(drawingCanvas, this.chart);
    }

    setDrawingTool(tool) {
        if (this.drawingTools) {
            this.drawingTools.setTool(tool);
            this.showToast(`Drawing tool: ${tool}`);
        }
    }

    undoDrawing() {
        if (this.drawingTools) {
            this.drawingTools.removeLastDrawing();
        }
    }

    clearDrawings() {
        if (this.drawingTools) {
            this.drawingTools.clearAll();
            this.showToast('Drawings cleared');
        }
    }

    async saveReflection() {
        const data = {
            week_start: this.currentWeekStart,
            summary: document.getElementById('reflectionSummary')?.value || '',
            key_wins: document.getElementById('reflectionWins')?.value || '',
            key_mistakes: document.getElementById('reflectionMistakes')?.value || '',
            next_week_focus: document.getElementById('reflectionFocus')?.value || ''
        };

        localStorage.setItem(`reflection_${this.currentWeekStart}`, JSON.stringify(data));
        this.showToast('Weekly reflection saved!');
    }

    async previousWeek() {
        const date = new Date(this.currentWeekStart);
        date.setDate(date.getDate() - 7);
        this.currentWeekStart = this.getWeekStart(date);
        await this.loadWeekData();
        this.render();
    }

    async nextWeek() {
        const date = new Date(this.currentWeekStart);
        date.setDate(date.getDate() + 7);
        this.currentWeekStart = this.getWeekStart(date);
        await this.loadWeekData();
        this.render();
    }

    formatDate(dateStr) {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }

    formatDateTime(dateStr) {
        if (!dateStr) return '';
        return dateStr.slice(5, 16).replace('T', ' ');
    }

    showToast(message) {
        if (window.notify) {
            window.notify.success(message);
        } else {
            const toast = document.createElement('div');
            toast.className = 'toast';
            toast.textContent = message;
            toast.style.cssText = `
                position: fixed;
                bottom: 24px;
                right: 24px;
                background: #1a1a1a;
                border: 1px solid #ff8c00;
                padding: 14px 20px;
                border-radius: 8px;
                color: #ffffff;
                z-index: 10000;
                animation: slideIn 0.3s ease;
            `;
            document.body.appendChild(toast);

            setTimeout(() => {
                toast.style.animation = 'slideOut 0.3s ease';
                setTimeout(() => toast.remove(), 300);
            }, 2000);
        }
    }
}

// Global instance
let weeklyReview;
