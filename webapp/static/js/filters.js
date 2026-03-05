/**
 * Date Range Filter Component
 * Provides quick date range selection
 */

class DateRangeFilter {
    constructor(containerId, onFilterChange) {
        this.containerId = containerId;
        this.onFilterChange = onFilterChange;
        this.currentRange = 'all';
        this.render();
    }

    render() {
        const container = document.getElementById(this.containerId);
        if (!container) return;

        container.innerHTML = `
            <div class="date-filter">
                <button class="filter-btn active" data-range="all">All Time</button>
                <button class="filter-btn" data-range="today">Today</button>
                <button class="filter-btn" data-range="week">This Week</button>
                <button class="filter-btn" data-range="month">This Month</button>
                <button class="filter-btn" data-range="quarter">This Quarter</button>
                <button class="filter-btn" data-range="year">This Year</button>
            </div>
        `;

        this.addStyles();
        this.attachEventListeners();
    }

    addStyles() {
        if (document.getElementById('filter-styles')) return;

        const style = document.createElement('style');
        style.id = 'filter-styles';
        style.textContent = `
            .date-filter {
                display: flex;
                gap: 8px;
                margin-bottom: 16px;
                overflow-x: auto;
                padding: 4px 0;
                -webkit-overflow-scrolling: touch;
            }

            .date-filter::-webkit-scrollbar {
                height: 4px;
            }

            .date-filter::-webkit-scrollbar-track {
                background: var(--panel-light);
                border-radius: 2px;
            }

            .date-filter::-webkit-scrollbar-thumb {
                background: var(--border);
                border-radius: 2px;
            }

            .filter-btn {
                background: var(--panel-light);
                border: 1px solid var(--border);
                color: var(--text-muted);
                padding: 8px 16px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                cursor: pointer;
                white-space: nowrap;
                transition: all 0.2s;
            }

            .filter-btn:hover {
                background: var(--panel);
                border-color: var(--accent);
                color: var(--text);
            }

            .filter-btn.active {
                background: var(--accent);
                border-color: var(--accent);
                color: white;
            }

            .filter-btn:active {
                transform: scale(0.95);
            }
        `;
        document.head.appendChild(style);
    }

    attachEventListeners() {
        const buttons = document.querySelectorAll(`#${this.containerId} .filter-btn`);
        buttons.forEach(btn => {
            btn.addEventListener('click', () => {
                const range = btn.dataset.range;
                this.setRange(range);
            });
        });
    }

    setRange(range) {
        this.currentRange = range;

        // Update active state
        const buttons = document.querySelectorAll(`#${this.containerId} .filter-btn`);
        buttons.forEach(btn => {
            if (btn.dataset.range === range) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Calculate date range
        const dateRange = this.calculateDateRange(range);

        // Trigger callback
        if (this.onFilterChange) {
            this.onFilterChange(dateRange);
        }
    }

    calculateDateRange(range) {
        const now = new Date();
        let startDate = null;
        let endDate = now;

        switch (range) {
            case 'today':
                startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                break;

            case 'week':
                // Start of current week (Monday)
                const dayOfWeek = now.getDay();
                const diff = dayOfWeek === 0 ? -6 : 1 - dayOfWeek; // Adjust for Sunday
                startDate = new Date(now);
                startDate.setDate(now.getDate() + diff);
                startDate.setHours(0, 0, 0, 0);
                break;

            case 'month':
                startDate = new Date(now.getFullYear(), now.getMonth(), 1);
                break;

            case 'quarter':
                const quarter = Math.floor(now.getMonth() / 3);
                startDate = new Date(now.getFullYear(), quarter * 3, 1);
                break;

            case 'year':
                startDate = new Date(now.getFullYear(), 0, 1);
                break;

            case 'all':
            default:
                return {}; // No date filter
        }

        // Format dates as YYYY-MM-DD HH:MM:SS for backend
        const formatDate = (date) => {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        };

        return {
            from: formatDate(startDate) + ' 00:00:00',
            to: formatDate(endDate) + ' 23:59:59'
        };
    }

    getCurrentRange() {
        return this.currentRange;
    }

    reset() {
        this.setRange('all');
    }
}
