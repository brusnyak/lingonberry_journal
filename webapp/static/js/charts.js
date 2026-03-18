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
function createEquityChart(canvasId, equityData, overlayLines = []) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const chart = Chart.getChart(ctx);
    if (chart) {
        chart.destroy();
    }

    const renderingContext = ctx.getContext('2d');
    const gradient = renderingContext.createLinearGradient(0, 0, 0, 320);
    gradient.addColorStop(0, 'rgba(16, 185, 129, 0.34)');
    gradient.addColorStop(1, 'rgba(16, 185, 129, 0)');

    const labels = equityData.map((point, index) => {
        if (!point.ts) return 'Start';
        const date = new Date(point.ts);
        if (Number.isNaN(date.getTime())) {
            return point.ts.slice(5, 10);
        }
        return date.toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric'
        });
    });

    const balanceValues = equityData.map(p => Number(p.balance || 0));
    const overlayValues = overlayLines
        .filter(line => line?.value != null)
        .map(line => Number(line.value));
    const allValues = [...balanceValues, ...overlayValues].filter(value => Number.isFinite(value));
    const minValue = allValues.length ? Math.min(...allValues) : 0;
    const maxValue = allValues.length ? Math.max(...allValues) : 0;
    const range = Math.max(1, maxValue - minValue);
    const yPadding = Math.max(range * 0.12, Math.abs(maxValue) * 0.01, 50);

    const datasets = [{
        label: 'Balance',
        data: balanceValues,
        borderColor: CHART_COLORS.green,
        backgroundColor: gradient,
        borderWidth: 3,
        fill: true,
        tension: 0.25,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHitRadius: 18
    }];

    overlayLines.forEach((line) => {
        if (line?.value == null) return;
        datasets.push({
            label: line.label,
            data: labels.map(() => line.value),
            borderColor: line.color || CHART_COLORS.accent,
            borderWidth: line.width || 1.25,
            borderDash: line.dash || [5, 5],
            pointRadius: 0,
            pointHoverRadius: 0,
            fill: false,
            tension: 0
        });
    });

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: datasets.length > 1,
                    labels: {
                        color: CHART_COLORS.textMuted,
                        boxWidth: 18,
                        boxHeight: 8,
                        padding: 16,
                        font: { size: 11 }
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
                    padding: 12,
                    callbacks: {
                        label: (context) => `${context.dataset.label}: ${Number(context.parsed.y || 0).toLocaleString()}`
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: CHART_COLORS.textMuted,
                        maxTicksLimit: 5,
                        font: { size: 11 }
                    }
                },
                y: {
                    min: minValue - yPadding,
                    max: maxValue + yPadding,
                    grid: {
                        color: CHART_COLORS.grid,
                        drawBorder: false
                    },
                    ticks: {
                        color: CHART_COLORS.textMuted,
                        font: { size: 11 },
                        callback: (value) => Number(value).toLocaleString()
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            },
            elements: {
                line: {
                    capBezierPoints: true
                }
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
