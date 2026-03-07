/**
 * Trade Detail Modal
 * Shows full trade details with charts and edit capabilities
 */

class TradeModal {
    constructor() {
        this.currentTradeId = null;
        this.createModal();
    }

    createModal() {
        // Create modal HTML
        const modalHTML = `
            <div id="tradeModal" class="modal">
                <div class="modal-overlay"></div>
                <div class="modal-content">
                    <div class="modal-header">
                        <h2 id="modalTitle">Trade Details</h2>
                        <button class="modal-close" onclick="tradeModal.close()">&times;</button>
                    </div>
                    <div class="modal-body" id="modalBody">
                        <div class="loading">
                            <div class="loading-spinner"></div>
                            <div>Loading trade details...</div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Add to body
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Add styles
        this.addStyles();

        // Close on overlay click
        document.querySelector('.modal-overlay').addEventListener('click', () => this.close());

        // Close on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen()) {
                this.close();
            }
        });
    }

    addStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .modal {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                z-index: 1000;
                animation: fadeIn 0.2s ease-out;
            }

            .modal.active {
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .modal-overlay {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.8);
                backdrop-filter: blur(4px);
            }

            .modal-content {
                position: relative;
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 16px;
                max-width: 800px;
                width: 90%;
                max-height: 90vh;
                overflow: hidden;
                display: flex;
                flex-direction: column;
                animation: slideUp 0.3s ease-out;
            }

            .modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 20px;
                border-bottom: 1px solid var(--border);
            }

            .modal-header h2 {
                font-size: 20px;
                font-weight: 700;
                margin: 0;
            }

            .modal-close {
                background: none;
                border: none;
                color: var(--text-muted);
                font-size: 32px;
                cursor: pointer;
                padding: 0;
                width: 32px;
                height: 32px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 8px;
                transition: background 0.2s, color 0.2s;
            }

            .modal-close:hover {
                background: var(--panel-light);
                color: var(--text);
            }

            .modal-body {
                padding: 20px;
                overflow-y: auto;
                flex: 1;
            }

            .trade-detail-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
                margin-bottom: 20px;
            }

            .trade-detail-item {
                background: var(--panel-light);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 12px;
            }

            .trade-detail-label {
                font-size: 11px;
                color: var(--text-muted);
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 6px;
            }

            .trade-detail-value {
                font-size: 16px;
                font-weight: 600;
            }

            .trade-charts {
                margin: 20px 0;
            }

            .trade-chart-item {
                margin-bottom: 16px;
            }

            .trade-chart-item img {
                width: 100%;
                border-radius: 8px;
                border: 1px solid var(--border);
            }

            .trade-chart-label {
                font-size: 12px;
                font-weight: 600;
                color: var(--text-muted);
                margin-bottom: 8px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            .trade-notes-section {
                background: var(--panel-light);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 16px;
                margin-top: 20px;
            }

            .trade-notes-title {
                font-size: 14px;
                font-weight: 700;
                margin-bottom: 12px;
            }

            .trade-notes-content {
                font-size: 14px;
                line-height: 1.6;
                color: var(--text-muted);
            }

            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }

            @keyframes slideUp {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            @media (max-width: 768px) {
                .modal-content {
                    width: 100%;
                    max-width: 100%;
                    height: 100%;
                    max-height: 100%;
                    border-radius: 0;
                }

                .trade-detail-grid {
                    grid-template-columns: 1fr;
                }
            }

            .indicator-snapshot {
                margin: 20px 0;
                background: var(--panel-light);
                border: 1px solid var(--border);
                border-radius: 8px;
                overflow: hidden;
            }

            .indicator-table {
                width: 100%;
                border-collapse: collapse;
                font-size: 12px;
            }

            .indicator-table th, .indicator-table td {
                padding: 10px;
                text-align: left;
                border: 1px solid var(--border);
            }

            .indicator-table th {
                background: var(--panel);
                color: var(--text-muted);
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            .indicator-val {
                font-family: monospace;
                font-weight: 600;
            }

            .indicator-offset {
                font-size: 10px;
                margin-left: 4px;
            }

            .indicator-offset.positive { color: var(--green); }
            .indicator-offset.negative { color: var(--red); }
        `;
        document.head.appendChild(style);
    }

    async open(tradeId) {
        this.currentTradeId = tradeId;
        const modal = document.getElementById('tradeModal');
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Load trade data
        await this.loadTradeData(tradeId);
    }

    close() {
        const modal = document.getElementById('tradeModal');
        modal.classList.remove('active');
        document.body.style.overflow = '';
        this.currentTradeId = null;
    }

    isOpen() {
        return document.getElementById('tradeModal').classList.contains('active');
    }

    async loadTradeData(tradeId) {
        const modalBody = document.getElementById('modalBody');
        const modalTitle = document.getElementById('modalTitle');

        try {
            const trade = await api.getTrade(tradeId);

            if (!trade) {
                throw new Error('Trade not found');
            }

            // Update title
            const direction = String(trade.direction || '').toUpperCase();
            const directionEmoji = direction === 'LONG' ? '🟢' : '🔴';
            modalTitle.textContent = `${directionEmoji} ${trade.symbol} ${direction}`;

            // Render trade details
            this.renderTradeDetails(trade, modalBody);

        } catch (err) {
            console.error('Error loading trade:', err);
            modalBody.innerHTML = `
                <div class="error">
                    <div class="error-title">⚠️ Error Loading Trade</div>
                    <p>${err.message}</p>
                </div>
            `;
        }
    }

    renderTradeDetails(trade, container) {
        const pnl = trade.pnl_usd || 0;
        const pnlClass = pnl >= 0 ? 'positive' : 'negative';
        const outcome = trade.outcome || 'OPEN';
        const outcomeEmoji = outcome === 'TP' ? '✅' : outcome === 'SL' ? '❌' : outcome === 'OPEN' ? '🔓' : '⚪';

        // Format dates
        const openDate = trade.ts_open ? new Date(trade.ts_open).toLocaleString() : 'N/A';
        const closeDate = trade.ts_close ? new Date(trade.ts_close).toLocaleString() : 'Still open';

        // Calculate duration
        let duration = 'N/A';
        if (trade.ts_open && trade.ts_close) {
            const ms = new Date(trade.ts_close) - new Date(trade.ts_open);
            const hours = Math.floor(ms / 3600000);
            const minutes = Math.floor((ms % 3600000) / 60000);
            duration = `${hours}h ${minutes}m`;
        }

        container.innerHTML = `
            <!-- Key Metrics -->
            <div class="trade-detail-grid">
                <div class="trade-detail-item">
                    <div class="trade-detail-label">P&L</div>
                    <div class="trade-detail-value ${pnlClass}">
                        ${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)} USD
                    </div>
                    ${trade.pnl_pct ? `<div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                        ${trade.pnl_pct >= 0 ? '+' : ''}${trade.pnl_pct.toFixed(2)}%
                    </div>` : ''}
                </div>

                <div class="trade-detail-item">
                    <div class="trade-detail-label">Outcome</div>
                    <div class="trade-detail-value">${outcomeEmoji} ${outcome}</div>
                </div>

                <div class="trade-detail-item">
                    <div class="trade-detail-label">Entry Price</div>
                    <div class="trade-detail-value">${(trade.entry_price || trade.entry || 0).toFixed(5)}</div>
                </div>

                <div class="trade-detail-item">
                    <div class="trade-detail-label">Exit Price</div>
                    <div class="trade-detail-value">${trade.exit_price ? trade.exit_price.toFixed(5) : 'N/A'}</div>
                </div>

                <div class="trade-detail-item">
                    <div class="trade-detail-label">Stop Loss</div>
                    <div class="trade-detail-value">${(trade.sl_price || trade.sl || 0).toFixed(5)}</div>
                </div>

                <div class="trade-detail-item">
                    <div class="trade-detail-label">Take Profit</div>
                    <div class="trade-detail-value">${(trade.tp_price || trade.tp || 0).toFixed(5)}</div>
                </div>

                <div class="trade-detail-item">
                    <div class="trade-detail-label">Risk/Reward</div>
                    <div class="trade-detail-value">${trade.rr_ratio ? trade.rr_ratio.toFixed(2) : 'N/A'}</div>
                </div>

                <div class="trade-detail-item">
                    <div class="trade-detail-label">Lot Size</div>
                    <div class="trade-detail-value">${trade.lot_size || 'N/A'}</div>
                </div>

                <div class="trade-detail-item">
                    <div class="trade-detail-label">Session</div>
                    <div class="trade-detail-value">
                        ${trade.session === 'Asian' ? '🌏' : trade.session === 'London' ? '🇬🇧' : trade.session === 'NY' ? '🇺🇸' : ''}
                        ${trade.session || 'N/A'}
                    </div>
                </div>

                <div class="trade-detail-item">
                    <div class="trade-detail-label">Duration</div>
                    <div class="trade-detail-value">${duration}</div>
                </div>

                <div class="trade-detail-item">
                    <div class="trade-detail-label">Opened</div>
                    <div class="trade-detail-value" style="font-size: 13px;">${openDate}</div>
                </div>

                <div class="trade-detail-item">
                    <div class="trade-detail-label">Closed</div>
                    <div class="trade-detail-value" style="font-size: 13px;">${closeDate}</div>
                </div>
            </div>

            <!-- Technical Snapshot -->
            ${this.renderIndicatorSnapshot(trade)}

            <!-- Charts -->
            ${this.renderCharts(trade)}

            <!-- Notes -->
            ${trade.notes || trade.mood || trade.market_condition ? `
                <div class="trade-notes-section">
                    <div class="trade-notes-title">📝 Trade Notes</div>
                    ${trade.notes ? `
                        <div class="trade-notes-content">
                            <strong>Notes:</strong><br>
                            ${trade.notes}
                        </div>
                    ` : ''}
                    ${trade.mood ? `
                        <div class="trade-notes-content" style="margin-top: 12px;">
                            <strong>Mood:</strong> ${trade.mood}
                        </div>
                    ` : ''}
                    ${trade.market_condition ? `
                        <div class="trade-notes-content" style="margin-top: 12px;">
                            <strong>Market Condition:</strong> ${trade.market_condition}
                        </div>
                    ` : ''}
                </div>
            ` : ''}
        `;
    }

    renderIndicatorSnapshot(trade) {
        if (!trade.indicator_data) return '';

        let data = {};
        try {
            data = typeof trade.indicator_data === 'string'
                ? JSON.parse(trade.indicator_data)
                : trade.indicator_data;
        } catch (e) {
            console.warn('Failed to parse indicator data:', e);
            return '';
        }

        const entry = data.entry || {};
        const exit = data.exit || {};

        const rows = [
            { label: 'EMA 9', key: 'ema_9', offset: 'offset_ema_9' },
            { label: 'EMA 21', key: 'ema_21', offset: 'offset_ema_21' },
            { label: 'EMA 50', key: 'ema_50', offset: 'offset_ema_50' },
            { label: 'EMA 200', key: 'ema_200', offset: 'offset_ema_200' },
            { label: 'VWAP', key: 'vwap', offset: 'offset_vwap' }
        ];

        const formatCell = (val, offset) => {
            if (val === undefined || val === null) return '-';
            const offsetNum = parseFloat(offset);
            const offsetClass = offsetNum >= 0 ? 'positive' : 'negative';
            const offsetSign = offsetNum >= 0 ? '+' : '';
            return `
                <span class="indicator-val">${parseFloat(val).toFixed(5)}</span>
                ${offset !== undefined ? `<span class="indicator-offset ${offsetClass}">${offsetSign}${offset}%</span>` : ''}
            `;
        };

        return `
            <div class="indicator-snapshot">
                <div class="trade-notes-title" style="padding: 16px 16px 0 16px;">📐 Technical Context</div>
                <div style="padding: 16px;">
                    <table class="indicator-table">
                        <thead>
                            <tr>
                                <th>Indicator</th>
                                <th>At Entry</th>
                                <th>At Exit</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rows.map(row => `
                                <tr>
                                    <td><strong>${row.label}</strong></td>
                                    <td>${formatCell(entry[row.key], entry[row.offset])}</td>
                                    <td>${formatCell(exit[row.key], exit[row.offset])}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }

    renderCharts(trade) {
        // Use chart_path from database if available
        if (trade.chart_path) {
            const paths = trade.chart_path.split(',').filter(p => p.trim() !== '');
            if (paths.length > 0) {
                return `
                    <div class="trade-charts">
                        <div class="trade-notes-title">📊 Multi-Timeframe Analysis</div>
                        ${paths.map(path => {
                    const filename = path.split('/').pop();
                    const tf = filename.split('_')[3] || 'Chart';
                    return `
                                <div class="trade-chart-item">
                                    <div class="trade-chart-label">${tf} Chart</div>
                                    <img 
                                        src="/charts/${filename}" 
                                        alt="${tf} chart"
                                        onerror="this.parentElement.style.display='none'"
                                    />
                                </div>
                            `;
                }).join('')}
                    </div>
                `;
            }
        }

        // Fallback to legacy timestamp guessing if no chart_path
        const symbol = trade.symbol;
        const direction = String(trade.direction || '').toUpperCase();
        const timestamp = trade.ts_open ? trade.ts_open.replace(/[:\-\s]/g, '').slice(0, 14) : '';

        if (!timestamp) {
            return '<p style="color: var(--text-muted); text-align: center; padding: 20px;">No charts available</p>';
        }

        const baseFilename = `trade_${symbol}_${direction}`;
        const timeframes = ['H4', 'M30', 'M5'];

        return `
            <div class="trade-charts">
                <div class="trade-notes-title">📊 Multi-Timeframe Analysis (Legacy)</div>
                ${timeframes.map(tf => `
                    <div class="trade-chart-item">
                        <div class="trade-chart-label">${tf} Chart</div>
                        <img 
                            src="/charts/${baseFilename}_${tf}_${timestamp}.png" 
                            alt="${tf} chart"
                            onerror="this.parentElement.innerHTML='<p style=\\'color: var(--text-muted); text-align: center; padding: 20px;\\'>Chart not available</p>'"
                        />
                    </div>
                `).join('')}
            </div>
        `;
    }
}

// Initialize modal
const tradeModal = new TradeModal();
