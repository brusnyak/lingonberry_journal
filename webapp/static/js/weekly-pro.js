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
        alert("Ideal Trade Logged! ✨");
        document.getElementById("perfectTradeLogger").style.display = "none";
        document.getElementById("addBtnContainer").style.display = "block";
      } else {
        console.error("Error response:", data);
        const errorMsg = data.error || "Unknown error";
        const details = data.message || data.details || "";
        alert(`Error logging trade: ${errorMsg}\n${details}`);
      }
    } catch (err) {
      console.error("Request failed:", err);
      alert("Error logging trade: " + err.message);
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

    document.getElementById("prevWeek").addEventListener("click", () => {
      this.currentWeekStart.setDate(this.currentWeekStart.getDate() - 7);
      this.loadData();
    });

    document.getElementById("nextWeek").addEventListener("click", () => {
      this.currentWeekStart.setDate(this.currentWeekStart.getDate() + 7);
      this.loadData();
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
      } else {
        this.series.setData([]);
        this.engine.setCandles([]);
      }
    } catch (err) {
      console.error("Failed to load candles:", err);
    }
  }

  updateWeekDisplay(start, end) {
    const options = { month: 'short', day: 'numeric' };
    this.weekDisplay.textContent = `${start.toLocaleDateString(undefined, options)} - ${end.toLocaleDateString(undefined, options)}, ${start.getFullYear()}`;
  }
}

window.WeeklyPro = WeeklyPro;
