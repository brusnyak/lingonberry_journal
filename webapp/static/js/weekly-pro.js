/**
 * Weekly Pro - Charting and Drawing for Weekly Review
 */

class WeeklyPro {
  constructor() {
    this.container = document.getElementById("chartContainer");
    this.canvas = document.getElementById("drawLayer");
    this.symbolSelect = document.getElementById("symbolSelect");
    this.timeframeSelect = document.getElementById("timeframeSelect");
    this.weekDisplay = document.getElementById("weekRangeDisplay");

    this.currentWeekStart = this.getMonday(new Date());
    this.chart = null;
    this.series = null;
    this.engine = null;
    this.showPerfectTrades = false; // Toggle between real and perfect trades
    this.weekTrades = [];
    this.weekStats = {};
    this.starredTools = JSON.parse(localStorage.getItem("starredTools") || '["trendline", "long", "short"]');

    this.init();
  }

  getMonday(d) {
    const date = new Date(d);
    const day = date.getDay();
    const diff = date.getDate() - day + (day === 0 ? -6 : 1); // adjust when day is sunday
    const monday = new Date(date.setDate(diff));
    monday.setHours(0, 0, 0, 0);
    return monday;
  }

  async init() {
    this.initChart();
    this.setupEventListeners();
    this.setupFavorites();
    await this.loadData();
    await this.loadWeekTrades();
    await this.loadWeekStats();
  }

  getActiveAccountId() {
    const idFromManager = window.accountManager?.getCurrentAccountId?.();
    if (idFromManager) return idFromManager;
    const stored = localStorage.getItem("currentAccountId");
    if (stored && stored !== "null" && stored !== "undefined") return parseInt(stored, 10);
    return 1;
  }

  initChart() {
    this.chart = LightweightCharts.createChart(this.container, {
      layout: {
        background: { color: "#070b13" },
        textColor: "#94a3b8",
        fontSize: 12,
        fontFamily: "'Inter', sans-serif",
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.05)" },
        horzLines: { color: "rgba(255, 255, 255, 0.05)" },
      },
      rightPriceScale: { borderColor: "rgba(255, 255, 255, 0.1)" },
      timeScale: {
        borderColor: "rgba(255, 255, 255, 0.1)",
        timeVisible: true,
      },
      crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: { color: "#00a3ff", labelBackgroundColor: "#00a3ff" },
        horzLine: { color: "#00a3ff", labelBackgroundColor: "#00a3ff" },
      }
    });

    this.series = this.chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
      borderVisible: false,
      priceFormat: {
        type: 'price',
        precision: 5,
        minMove: 0.00001,
      },
    });

    // Drawing Engine
    this.engine = new DrawingEngine(this.chart, this.series, this.container, this.canvas);
    this.engine.setSessionBreaks(true, { color: "rgba(56, 189, 248, 0.45)", dash: [3, 6], width: 1 });
  }

  setupEventListeners() {
    // Toolbar
    document.querySelectorAll(".tool-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        if (e.target.closest(".tool-star")) {
          this.toggleFavorite(btn.dataset.tool);
          return;
        }
        document.querySelectorAll(".tool-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        this.engine.setTool(btn.dataset.tool);
      });
    });

    // Filters
    this.symbolSelect.addEventListener("change", () => this.loadData());
    this.timeframeSelect.addEventListener("change", () => this.loadData());

    // Account change reload
    document.addEventListener("accountChanged", () => {
      this.loadData();
      this.loadWeekTrades();
      this.loadWeekStats();
    });

    // Toggle between real and perfect trades
    const toggleBtn = document.getElementById("toggleTradeSource");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        this.showPerfectTrades = !this.showPerfectTrades;
        toggleBtn.textContent = this.showPerfectTrades ? "Show Manual" : "Show Perfect";
        this.loadWeekTrades();
        this.loadWeekStats();
      });
    }

    // Save reflection button
    const saveReflectionBtn = document.getElementById("saveReflection");
    if (saveReflectionBtn) {
      saveReflectionBtn.addEventListener("click", () => this.saveWeeklyReflection());
    }

    // Trade Entry Form Trigger
    const logPerfectBtn = document.getElementById("logPerfectTrade");
    if (logPerfectBtn) {
      logPerfectBtn.onclick = () => {
        document.getElementById("perfectTradeLogger").style.display = "block";
        document.getElementById("addBtnContainer").style.display = "none";
        this.syncFormWithDrawing();
      };
    }

    const form = document.getElementById("perfectTradeForm");
    if (form) form.onsubmit = (e) => this.handlePerfectTradeSubmit(e);

    // Week navigation
    document.getElementById("prevWeek").addEventListener("click", () => {
      this.currentWeekStart.setDate(this.currentWeekStart.getDate() - 7);
      this.loadData();
      this.loadWeekTrades();
      this.loadWeekStats();
    });

    document.getElementById("nextWeek").addEventListener("click", () => {
      this.currentWeekStart.setDate(this.currentWeekStart.getDate() + 7);
      this.loadData();
      this.loadWeekTrades();
      this.loadWeekStats();
    });

    // Risk Calculation
    const riskInput = document.getElementById("mRiskPct");
    if (riskInput) {
      ["input", "change"].forEach(ev => {
        riskInput.addEventListener(ev, () => this.calculateLots());
      });
    }
    ["mEntry", "mSL"].forEach(id => {
      document.getElementById(id)?.addEventListener("input", () => this.calculateLots());
    });

    // Drawing Engine Updates sync
    this.container.addEventListener("drawing-updated", (e) => {
      if (e.detail.type === "riskreward") this.syncFormWithDrawing();
    });
    this.container.addEventListener("drawing-added", (e) => {
      if (e.detail.tool === "long" || e.detail.tool === "short") this.syncFormWithDrawing();
    });
  }

  syncFormWithDrawing() {
    const rr = this.engine.state.drawings.find(d => d.type === "riskreward");
    if (rr && document.getElementById("perfectTradeLogger").style.display !== "none") {
      document.getElementById("mEntry").value = rr.points[0].price.toFixed(5);
      document.getElementById("mSL").value = rr.points[1].price.toFixed(5);
      if (rr.points[2]) document.getElementById("mTP").value = rr.points[2].price.toFixed(5);
      this.calculateLots();
    }
  }

  calculateLots() {
    const entry = parseFloat(document.getElementById("mEntry").value);
    const sl = parseFloat(document.getElementById("mSL").value);
    const riskPct = parseFloat(document.getElementById("mRiskPct").value);
    const lotsInput = document.getElementById("mLots");

    if (!entry || !sl || !riskPct || entry === sl) return;

    // Fetch account balance from localStorage or default
    const account = JSON.parse(localStorage.getItem("selectedAccount") || '{"initial_balance": 50000}');
    const balance = account.initial_balance;
    const riskUsd = balance * (riskPct / 100);

    // Simple Lot Calculation (assuming 100,000 unit standard lot for Forex)
    // Pip value calculation is complex, but for EURUSD 0.0001 is 1 pip = $10 per lot.
    const pips = Math.abs(entry - sl) * 10000;
    if (pips > 0) {
      const lots = riskUsd / (pips * 10);
      lotsInput.value = lots.toFixed(2);
    }
  }

  async handlePerfectTradeSubmit(e) {
    e.preventDefault();
    const payload = {
      symbol: this.symbolSelect.value,
      entry_price: parseFloat(document.getElementById("mEntry").value),
      exit_price: parseFloat(document.getElementById("mTP").value),
      ts_open: Math.floor(this.currentWeekStart.getTime() / 1000) + 86400, // Monday 
      ts_close: Math.floor(this.currentWeekStart.getTime() / 1000) + 86400 * 2,
      is_perfect: true,
      week_start: this.currentWeekStart.toISOString().split('T')[0],
      notes: document.getElementById("mNotes").value,
      drawings: this.engine.state.drawings,
      lots: parseFloat(document.getElementById("mLots").value) || 0.1
    };

    try {
      const accId = localStorage.getItem("selectedAccountId") || 1;
      const res = await fetch(`/api/trades/manual?account_id=${accId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (res.ok) {
        if (window.notify) {
          window.notify.success(`Perfect trade #${data.trade_id} logged!`);
        } else {
          alert("Ideal Trade Logged! ✨");
        }
        document.getElementById("perfectTradeLogger").style.display = "none";
        document.getElementById("addBtnContainer").style.display = "block";
        document.getElementById("perfectTradeForm").reset();
        // Reload trades and stats
        this.loadWeekTrades();
        this.loadWeekStats();
      } else {
        console.error("Error response:", data);
        const errorMsg = data.error || "Unknown error";
        const details = data.message || data.details || "";
        if (window.notify) {
          window.notify.error(`${errorMsg}${details ? ': ' + details : ''}`);
        } else {
          alert(`Error logging trade: ${errorMsg}\n${details}`);
        }
      }
    } catch (err) {
      console.error("Request failed:", err);
      if (window.notify) {
        window.notify.error("Error logging trade: " + err.message);
      } else {
        alert("Error logging trade: " + err.message);
      }
    }
  }

  async loadWeekTrades() {
    try {
      const weekStart = this.currentWeekStart.toISOString().split('T')[0];
      const accId = this.getActiveAccountId();
      const isPerfect = this.showPerfectTrades ? 'true' : 'false';

      const res = await fetch(`/api/trades/week?account_id=${accId}&week_start=${weekStart}&is_perfect=${isPerfect}`);
      this.weekTrades = await res.json();

      this.renderWeekTrades(this.weekTrades);
      this.displayTradesOnChart(this.weekTrades);
    } catch (err) {
      console.error("Failed to load week trades:", err);
    }
  }

  async loadWeekStats() {
    try {
      const weekStart = this.currentWeekStart.toISOString().split('T')[0];
      const accId = this.getActiveAccountId();
      const isPerfect = this.showPerfectTrades ? 'true' : 'false';

      const res = await fetch(`/api/trades/week/stats?account_id=${accId}&week_start=${weekStart}&is_perfect=${isPerfect}`);
      this.weekStats = await res.json();

      this.renderWeekStats(this.weekStats);
    } catch (err) {
      console.error("Failed to load week stats:", err);
    }
  }

  displayTradesOnChart(trades) {
    // Clear existing trade drawings
    if (this.tradeDrawingIds && this.tradeDrawingIds.length) {
      const remove = new Set(this.tradeDrawingIds);
      this.engine.state.drawings = this.engine.state.drawings.filter(d => !remove.has(d.id));
      this.tradeDrawingIds = [];
    }

    const toEpochSeconds = (value) => {
      if (!value) return null;
      if (typeof value === "number") return value;
      const ms = Date.parse(value);
      return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
    };

    const defaultEndSeconds = 3600 * 4;

    this.tradeDrawingIds = [];
    const activeSymbol = this.symbolSelect?.value;
    trades.forEach(trade => {
      if (activeSymbol && trade.symbol && trade.symbol !== activeSymbol) return;
      if (!trade.ts_open) return;
      const entryTime = toEpochSeconds(trade.ts_open);
      const exitTime = toEpochSeconds(trade.ts_close);
      const entryPrice = parseFloat(trade.entry_price);
      const sl = parseFloat(trade.sl_price || trade.sl);
      const tp = parseFloat(trade.tp_price || trade.tp);

      if (!entryTime || !entryPrice || !sl || !tp) return;

      const side = String(trade.direction || "").toLowerCase() === "short" ? "short" : "long";
      const endTime = exitTime || (entryTime + defaultEndSeconds);

      const drawing = this.engine.addDrawing({
        type: "riskreward",
        points: [
          { time: entryTime, price: entryPrice },
          { time: entryTime, price: sl },
          { time: entryTime, price: tp },
          { time: endTime, price: entryPrice },
        ],
        side,
        source: "trade",
        select: false,
      });

      if (drawing?.id) this.tradeDrawingIds.push(drawing.id);
    });
  }

  renderWeekTrades(trades) {
    const container = document.getElementById("perfectTradesList");
    const header = document.querySelector("#perfectTradesDisplay h3");

    if (!container) return;

    // Update header
    if (header) {
      const label = this.showPerfectTrades ? "Perfect Trades" : "Manual Trades";
      header.textContent = `${label} (${trades.length})`;
    }

    if (trades.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📭</div>
          <div>No ${this.showPerfectTrades ? 'perfect' : 'manual'} trades yet</div>
        </div>
      `;
      return;
    }

    container.innerHTML = trades.map(trade => {
      const pnl = trade.pnl_usd || 0;
      const isWin = pnl > 0;
      const outcome = trade.outcome || 'OPEN';

      return `
        <div class="trade-item" style="cursor: pointer;" onclick="weeklyPro.highlightTrade(${trade.id})">
          <div class="trade-header">
            <span>${trade.direction === 'LONG' ? '🟢' : '🔴'} ${trade.symbol}</span>
            <span class="badge ${isWin ? 'success' : outcome === 'OPEN' ? 'warning' : 'danger'}">
              ${outcome === 'OPEN' ? 'OPEN' : (isWin ? '+' : '') + pnl.toFixed(2)}
            </span>
          </div>
          <div class="trade-details" style="font-size: 11px; color: var(--muted); margin-top: 4px;">
            Entry: ${trade.entry_price?.toFixed(5)} | ${outcome !== 'OPEN' ? `Exit: ${trade.exit_price?.toFixed(5)}` : 'Running'}
          </div>
          ${trade.notes ? `<div style="font-size: 10px; color: var(--muted); margin-top: 4px; font-style: italic;">${trade.notes}</div>` : ''}
        </div>
      `;
    }).join('');
  }

  renderWeekStats(stats) {
    // Update the weekly reflection card with stats
    const reflectionCard = document.querySelector('.review-card');
    if (!reflectionCard) return;

    // Check if stats summary already exists
    let statsSummary = reflectionCard.querySelector('.week-stats-summary');
    if (!statsSummary) {
      statsSummary = document.createElement('div');
      statsSummary.className = 'week-stats-summary';
      statsSummary.style.cssText = 'margin-bottom: 16px; padding: 12px; background: var(--panel-solid); border-radius: 8px; border: 1px solid var(--border);';
      reflectionCard.insertBefore(statsSummary, reflectionCard.firstChild.nextSibling);
    }

    const profitFactor = stats.profit_factor === null ? '∞' : stats.profit_factor;

    statsSummary.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; font-size: 12px;">
        <div>
          <div style="color: var(--muted);">Trades</div>
          <div style="font-weight: 600; font-size: 16px;">${stats.total_trades}</div>
        </div>
        <div>
          <div style="color: var(--muted);">Win Rate</div>
          <div style="font-weight: 600; font-size: 16px; color: ${stats.win_rate >= 50 ? '#22c55e' : '#ef4444'};">${stats.win_rate}%</div>
        </div>
        <div>
          <div style="color: var(--muted);">Net P&L</div>
          <div style="font-weight: 600; font-size: 16px; color: ${stats.net_pnl >= 0 ? '#22c55e' : '#ef4444'};">${stats.net_pnl >= 0 ? '+' : ''}$${stats.net_pnl}</div>
        </div>
        <div>
          <div style="color: var(--muted);">Profit Factor</div>
          <div style="font-weight: 600; font-size: 16px;">${profitFactor}</div>
        </div>
        <div>
          <div style="color: var(--muted);">Avg R:R</div>
          <div style="font-weight: 600; font-size: 16px;">${stats.avg_rr}</div>
        </div>
        <div>
          <div style="color: var(--muted);">Best Trade</div>
          <div style="font-weight: 600; font-size: 16px; color: #22c55e;">$${stats.best_trade}</div>
        </div>
      </div>
    `;
  }

  async highlightTrade(tradeId) {
    const trade = this.weekTrades.find(t => t.id === tradeId);
    if (!trade || !trade.ts_open) return;

    // Switch chart symbol to trade symbol if needed
    if (this.symbolSelect && trade.symbol && this.symbolSelect.value !== trade.symbol) {
      const optionExists = Array.from(this.symbolSelect.options).some(o => o.value === trade.symbol);
      if (optionExists) {
        this.symbolSelect.value = trade.symbol;
        await this.loadData();
        this.displayTradesOnChart(this.weekTrades);
      }
    }

    // Scroll chart to trade time
    const entryTime = new Date(trade.ts_open).getTime() / 1000;
    this.chart.timeScale().scrollToPosition(5, true);

    // Flash notification
    if (window.notify) {
      window.notify.info(`${trade.symbol} ${trade.direction} @ ${trade.entry_price?.toFixed(5)}`);
    }
  }
  async saveWeeklyReflection() {
    const weekStart = this.currentWeekStart.toISOString().split('T')[0];
    const accId = localStorage.getItem("selectedAccountId") || 1;
    const notes = document.getElementById("weeklyNotes")?.value || '';

    try {
      const res = await fetch('/api/review/week', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_id: parseInt(accId),
          week_start: weekStart,
          summary: notes,
        })
      });

      if (res.ok) {
        if (window.notify) {
          window.notify.success('Weekly reflection saved!');
        } else {
          alert('Weekly reflection saved!');
        }
      } else {
        throw new Error('Failed to save reflection');
      }
    } catch (err) {
      console.error('Failed to save reflection:', err);
      if (window.notify) {
        window.notify.error('Failed to save reflection');
      } else {
        alert('Failed to save reflection');
      }
    }
  }


  setupFavorites() {
    const bar = document.getElementById("favoritesBar");
    if (!bar) return;

    bar.innerHTML = "";
    if (this.starredTools.length > 0) {
      bar.style.display = "flex";
      this.starredTools.forEach(tool => {
        const btn = document.createElement("button");
        btn.className = "tool-btn";
        btn.dataset.tool = tool;
        const mainBtn = document.querySelector(`#mainToolbar .tool-btn[data-tool="${tool}"]`);
        if (mainBtn) {
          btn.innerHTML = mainBtn.innerHTML;
          btn.onclick = () => {
            document.querySelectorAll(".tool-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            this.engine.setTool(tool);
          };
          bar.appendChild(btn);
        }
      });
      if (window.lucide) window.lucide.createIcons();
    } else {
      bar.style.display = "none";
    }

    // Sync stars
    document.querySelectorAll("#mainToolbar .tool-star").forEach(star => {
      const tool = star.parentElement.dataset.tool;
      star.classList.toggle("active", this.starredTools.includes(tool));
    });
  }

  toggleFavorite(tool) {
    if (this.starredTools.includes(tool)) {
      this.starredTools = this.starredTools.filter(t => t !== tool);
    } else {
      this.starredTools.push(tool);
    }
    localStorage.setItem("starredTools", JSON.stringify(this.starredTools));
    this.setupFavorites();
  }

  async loadData() {
    const symbol = this.symbolSelect.value;
    const tf = this.timeframeSelect.value;

    // Show loading notification
    let loadingToast = null;
    if (window.notify) {
      loadingToast = window.notify.info(`Loading ${symbol} ${tf}...`, 0);
    }

    // Friday end
    const end = new Date(this.currentWeekStart);
    end.setDate(end.getDate() + 5);
    end.setHours(23, 59, 59, 999);

    this.updateWeekDisplay(this.currentWeekStart, end);

    try {
      const url = `/api/candles?symbol=${symbol}&timeframe=${tf}&start=${this.currentWeekStart.toISOString()}&end=${end.toISOString()}`;
      const res = await fetch(url);
      const data = await res.json();

      if (data && data.length) {
        this.series.setData(data);
        this.engine.setCandles(data);
        this.chart.timeScale().fitContent();
        this.engine.redraw();
        if (this.weekTrades && this.weekTrades.length) {
          this.displayTradesOnChart(this.weekTrades);
        }

        if (window.notify && loadingToast) {
          window.notify.dismiss(loadingToast);
          window.notify.success(`${symbol} ${tf} loaded`);
        }
      } else {
        this.series.setData([]);
        this.engine.setCandles([]);
        this.engine.redraw();

        if (window.notify && loadingToast) {
          window.notify.dismiss(loadingToast);
          window.notify.warning(`No data for ${symbol} ${tf}`);
        }
      }
    } catch (err) {
      console.error("Failed to load candles:", err);
      if (window.notify && loadingToast) {
        window.notify.dismiss(loadingToast);
        window.notify.error("Failed to load chart data");
      }
    }
  }

  updateWeekDisplay(start, end) {
    const options = { month: 'short', day: 'numeric' };
    this.weekDisplay.textContent = `${start.toLocaleDateString(undefined, options)} - ${end.toLocaleDateString(undefined, options)}, ${start.getFullYear()}`;
  }
}

window.WeeklyPro = WeeklyPro;
