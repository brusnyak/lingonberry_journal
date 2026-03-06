/**
 * Trade Entry Pro - Visual Logger using Drawing Engine
 */

class TradeEntryPro {
  constructor() {
    this.container = document.getElementById("chartContainer");
    this.canvas = document.getElementById("drawLayer");
    this.symbolSelect = document.getElementById("symbolSelect");
    this.tfSelect = document.getElementById("timeframeSelect");
    this.form = document.getElementById("tradeForm");

    // Form Inputs
    this.inputs = {
      entry: document.getElementById("entryPrice"),
      tp: document.getElementById("tpPrice"),
      sl: document.getElementById("slPrice"),
      risk: document.getElementById("riskPct"),
      lots: document.getElementById("lots"),
      mindset: document.getElementById("mindset"),
      setup: document.getElementById("setup"),
      notes: document.getElementById("notes")
    };

    this.chart = null;
    this.series = null;
    this.engine = null;
    this.currentData = [];
    this.starredTools = JSON.parse(localStorage.getItem("starredTools") || '["trendline", "long", "short"]');

    this.init();
  }

  async init() {
    this.initChart();
    this.setupEventListeners();
    this.setupFavorites();
    await this.loadData();
  }

  initChart() {
    this.chart = LightweightCharts.createChart(this.container, {
      layout: { background: { color: "#070b13" }, textColor: "#94a3b8", fontFamily: "'Inter', sans-serif" },
      grid: { vertLines: { color: "rgba(255, 255, 255, 0.05)" }, horzLines: { color: "rgba(255, 255, 255, 0.05)" } },
      rightPriceScale: { borderColor: "rgba(255, 255, 255, 0.1)" },
      timeScale: { borderColor: "rgba(255, 255, 255, 0.1)", timeVisible: true },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal }
    });

    this.series = this.chart.addCandlestickSeries({
      upColor: "#22c55e", downColor: "#ef4444", borderVisible: false,
      wickUpColor: "#22c55e", wickDownColor: "#ef4444",
      priceFormat: {
        type: 'price',
        precision: 5,
        minMove: 0.00001,
      },
    });

    this.engine = new DrawingEngine(this.chart, this.series, this.container, this.canvas);
  }

  setupEventListeners() {
    // Drawing Engine Events
    this.container.addEventListener("drawing-added", (e) => this.handleDrawing(e.detail));
    this.container.addEventListener("drawing-updated", (e) => {
      if (e.detail.type === "riskreward") this.syncFormWithDrawing(e.detail);
    });

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

    // Form Auto-Calc
    this.inputs.risk.addEventListener("input", () => this.calculateLots());

    // Filters
    this.symbolSelect.addEventListener("change", () => this.loadData());
    this.tfSelect.addEventListener("change", () => this.loadData());

    this.form.addEventListener("submit", (e) => this.handleSubmit(e));
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
    const tf = this.tfSelect.value;
    try {
      const res = await fetch(`/api/candles?symbol=${symbol}&timeframe=${tf}`);
      const data = await res.json();
      if (data && data.length) {
        this.currentData = data;
        this.series.setData(data);
        this.engine.setCandles(data);
        this.chart.timeScale().fitContent();
      }
    } catch (err) {
      console.error("Load failed", err);
    }
  }

  handleDrawing(detail) {
    // If it's a long/short tool, we wait for it to be fully placed
    // The engine dispatches drawing-added after both points are set
    const drawing = this.engine.state.drawings.find(d => d.type === "riskreward");
    // Usually we only care about the most recent one for entry
    if (drawing) this.syncFormWithDrawing(drawing);
  }

  syncFormWithDrawing(d) {
    if (d.type !== "riskreward") return;
    const entry = d.points[0].price;
    const sl = d.points[1].price;
    const tp = d.points[2] ? d.points[2].price : (entry + (entry - sl));

    this.inputs.entry.value = entry.toFixed(5);
    this.inputs.sl.value = sl.toFixed(5);
    this.inputs.tp.value = tp.toFixed(5);

    this.calculateLots();
  }

  calculateLots() {
    const entry = parseFloat(this.inputs.entry.value);
    const sl = parseFloat(this.inputs.sl.value);
    const riskPct = parseFloat(this.inputs.risk.value);

    if (isNaN(entry) || isNaN(sl) || isNaN(riskPct) || entry === sl) return;

    // Fetch account balance from localStorage or default
    const account = JSON.parse(localStorage.getItem("selectedAccount") || '{"initial_balance": 50000}');
    const balance = account.initial_balance;
    const riskUsd = balance * (riskPct / 100);

    const pips = Math.abs(entry - sl) * 10000; // Simplified for Forex
    if (pips === 0) return;

    // Basic Forex Lot Calc: Risk / (Pips * PipValueFor1Lot)
    // Assuming 1 Lot = 100k, so 1 Pip = $10 approx for EURUSD
    const lots = riskUsd / (pips * 10);
    this.inputs.lots.value = lots.toFixed(2);
  }

  async handleSubmit(e) {
    e.preventDefault();
    const btn = this.form.querySelector("button[type='submit']");
    btn.disabled = true;

    const payload = {
      symbol: this.symbolSelect.value,
      entry_price: parseFloat(this.inputs.entry.value),
      exit_price: parseFloat(this.inputs.tp.value), // Usually we log the target or leave open
      sl: parseFloat(this.inputs.sl.value),
      tp: parseFloat(this.inputs.tp.value),
      ts_open: Math.floor(Date.now() / 1000), // Current time for manual entry
      ts_close: Math.floor(Date.now() / 1000) + 3600, // +1 hour as default for manual entry if missing
      risk: parseFloat(this.inputs.risk.value),
      lots: parseFloat(this.inputs.lots.value),
      mindset: this.inputs.mindset.value,
      setup: this.inputs.setup.value,
      notes: this.inputs.notes.value,
      drawings: this.engine.state.drawings // Save drawings with the trade!
    };

    try {
      const res = await fetch("/api/trades/manual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (res.ok) {
        alert("Trade Logged!");
        window.location.href = "/mini";
      } else {
        console.error("Error response:", data);
        const errorMsg = data.error || "Unknown error";
        const details = data.message || data.details || "";
        alert(`Error: ${errorMsg}\n${details}`);
      }
    } catch (err) {
      console.error("Request failed:", err);
      alert("System Error: " + err.message);
    } finally {
      btn.disabled = false;
    }
  }
}

window.TradeEntryPro = TradeEntryPro;
