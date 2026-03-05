/**
 * Chart Utilities
 * Wrapper functions for Chart.js with consistent styling
 */

const CHART_COLORS = {
    bg: '#0a0e1a',
    panel: '#141824',
    border: 'rgba(255, 255, 255, 0.08)',
    text: '#ffffff',
    textMuted: '#8b92a8',
    green: '#10b981',
    red: '#ef4444',
    accent: '#6366f1',
    grid: 'rgba(255, 255, 255, 0.05)'
};

/**
 * Create equity curve chart
 */
function createEquityChart(canvasId, equityData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 220);
    gradient.addColorStop(0, 'rgba(16, 185, 129, 0.3)');
    gradient.addColorStop(1, 'rgba(16, 185, 129, 0)');

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: equityData.map(p => p.ts ? p.ts.slice(5, 10) : 'Start'),
            datasets: [{
                label: 'Balance',
                data: equityData.map(p => p.balance),
                borderColor: CHART_COLORS.green,
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: CHART_COLORS.panel,
                    titleColor: CHART_COLORS.text,
                    bodyColor: CHART_COLORS.textMuted,
                    borderColor: CHART_COLORS.border,
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: CHART_COLORS.textMuted,
                        maxTicksLimit: 6,
                        font: { size: 11 }
                    }
                },
                y: {
                    grid: {
                        color: CHART_COLORS.grid,
                        drawBorder: false
                    },
                    ticks: {
                        color: CHART_COLORS.textMuted,
                        font: { size: 11 }
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

/**
 * Create bar chart (for win/loss, directional breakdown, etc.)
 */
function createBarChart(canvasId, labels, data, options = {}) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const colors = options.colors || data.map(v => v >= 0 ? CHART_COLORS.green : CHART_COLORS.red);

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: options.label || 'Value',
                data: data,
                backgroundColor: colors,
                borderColor: colors,
                borderWidth: 0,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: CHART_COLORS.panel,
                    titleColor: CHART_COLORS.text,
                    bodyColor: CHART_COLORS.textMuted,
                    borderColor: CHART_COLORS.border,
                    borderWidth: 1,
                    padding: 12
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: CHART_COLORS.textMuted,
                        font: { size: 11 }
                    }
                },
                y: {
                    grid: {
                        color: CHART_COLORS.grid,
                        drawBorder: false
                    },
                    ticks: {
                        color: CHART_COLORS.textMuted,
                        font: { size: 11 }
                    }
                }
            }
        }
    });
}

/**
 * Create doughnut chart (for win rate, etc.)
 */
function createDoughnutChart(canvasId, labels, data, colors) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors || [CHART_COLORS.green, CHART_COLORS.red],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        color: CHART_COLORS.text,
                        padding: 15,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    backgroundColor: CHART_COLORS.panel,
                    titleColor: CHART_COLORS.text,
                    bodyColor: CHART_COLORS.textMuted,
                    borderColor: CHART_COLORS.border,
                    borderWidth: 1,
                    padding: 12
                }
            }
        }
    });
}

/**
 * Create heatmap using Chart.js matrix (requires chartjs-chart-matrix plugin)
 * Fallback to simple grid if plugin not available
 */
function createHeatmap(containerId, data, options = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Simple HTML grid heatmap (no external plugin needed)
    const days = options.days || ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
    const hours = options.hours || Array.from({ length: 24 }, (_, i) => i);

    let html = '<div class="heatmap-grid">';

    // Header row
    html += '<div class="heatmap-row"><div class="heatmap-cell heatmap-header"></div>';
    hours.forEach(h => {
        html += `<div class="heatmap-cell heatmap-header">${h}</div>`;
    });
    html += '</div>';

    // Data rows
    days.forEach((day, dayIdx) => {
        html += `<div class="heatmap-row"><div class="heatmap-cell heatmap-header">${day}</div>`;
        hours.forEach((hour, hourIdx) => {
            const value = data[dayIdx]?.[hourIdx] || 0;
            const intensity = Math.min(Math.abs(value) / (options.maxValue || 100), 1);
            const color = value >= 0
                ? `rgba(16, 185, 129, ${intensity})`
                : `rgba(239, 68, 68, ${intensity})`;
            html += `<div class="heatmap-cell" style="background-color: ${color}" title="${day} ${hour}:00 - ${value.toFixed(2)}"></div>`;
        });
        html += '</div>';
    });

    html += '</div>';
    container.innerHTML = html;
}

/**
 * Create histogram chart
 */
function createHistogram(canvasId, labels, data, options = {}) {
    return createBarChart(canvasId, labels, data, options);
}


/**
 * Create fan chart for Monte Carlo projections
 */
function createFanChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const { p25, p50, p75 } = data;

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '75th Percentile (Optimistic)',
                    data: p75,
                    borderColor: 'rgba(16, 185, 129, 0.8)',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: '+1',
                    tension: 0.4,
                    pointRadius: 0
                },
                {
                    label: '50th Percentile (Median)',
                    data: p50,
                    borderColor: CHART_COLORS.accent,
                    backgroundColor: 'rgba(99, 102, 241, 0.2)',
                    borderWidth: 3,
                    fill: '+1',
                    tension: 0.4,
                    pointRadius: 0
                },
                {
                    label: '25th Percentile (Pessimistic)',
                    data: p25,
                    borderColor: 'rgba(239, 68, 68, 0.8)',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: CHART_COLORS.text,
                        padding: 15,
                        font: { size: 11 },
                        usePointStyle: true
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: CHART_COLORS.panel,
                    titleColor: CHART_COLORS.text,
                    bodyColor: CHART_COLORS.textMuted,
                    borderColor: CHART_COLORS.border,
                    borderWidth: 1,
                    padding: 12
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: CHART_COLORS.textMuted,
                        maxTicksLimit: 10,
                        font: { size: 10 }
                    }
                },
                y: {
                    grid: {
                        color: CHART_COLORS.grid,
                        drawBorder: false
                    },
                    ticks: {
                        color: CHART_COLORS.textMuted,
                        font: { size: 11 },
                        callback: function (value) {
                            return (value >= 0 ? '+' : '') + value.toFixed(0);
                        }
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}
