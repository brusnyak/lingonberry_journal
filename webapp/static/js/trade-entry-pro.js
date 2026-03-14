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
    this.accountBadge = document.getElementById("selectedAccountBadge");

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
    this.updateAccountBadge();
    await this.loadData();
  }

  updateAccountBadge() {
    if (!this.accountBadge) return;

    const account = window.accountManager?.currentAccount;
    if (account) {
      this.accountBadge.innerHTML = `<span style="color: var(--accent);">●</span> ${account.name}`;
      this.accountBadge.title = `Logging to: ${account.name}`;
    } else {
      this.accountBadge.textContent = 'No account selected';
    }
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
    this.engine.setSessionBreaks(true, { color: "rgba(56, 189, 248, 0.45)", dash: [3, 6], width: 1 });
  }

  setupEventListeners() {
    // Drawing Engine Events
    this.container.addEventListener("drawing-added", (e) => this.handleDrawing(e.detail));
    this.container.addEventListener("drawing-updated", (e) => {
      if (e.detail.type === "riskreward") this.syncFormWithDrawing(e.detail);
    });

    // Account change listener
    document.addEventListener('accountChanged', () => {
      this.updateAccountBadge();
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

    // Show loading notification
    let loadingToast = null;
    if (window.notify) {
      loadingToast = window.notify.info(`Loading ${symbol} ${tf}...`, 0);
    }

    try {
      const res = await fetch(`/api/candles?symbol=${symbol}&timeframe=${tf}`);
      const data = await res.json();
      if (data && data.length) {
        this.currentData = data;
        this.series.setData(data);
        this.engine.setCandles(data);
        this.chart.timeScale().fitContent();

        if (window.notify && loadingToast) {
          window.notify.dismiss(loadingToast);
          window.notify.success(`${symbol} ${tf} loaded`);
        }
      } else {
        if (window.notify && loadingToast) {
          window.notify.dismiss(loadingToast);
          window.notify.warning(`No data for ${symbol} ${tf}`);
        }
      }
    } catch (err) {
      console.error("Load failed", err);
      if (window.notify && loadingToast) {
        window.notify.dismiss(loadingToast);
        window.notify.error("Failed to load chart data");
      }
    }

    // Redraw to ensure drawings are visible
    if (this.engine) {
      this.engine.redraw();
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

  findExitTime(entryTime, exitPrice, direction, sl, tp) {
    // Scan through candles after entry to find when price hit SL or TP
    if (!this.currentData || this.currentData.length === 0) {
      return { time: null, outcome: null, exitPrice: null };
    }

    // Find candles after entry time
    const candlesAfterEntry = this.currentData.filter(c => c.time >= entryTime);

    for (const candle of candlesAfterEntry) {
      // Skip the entry candle
      if (candle.time === entryTime) continue;

      // Check which was hit first
      if (direction === 'LONG') {
        // For LONG: check if SL hit first (price went down)
        if (candle.low <= sl) {
          return { time: candle.time, outcome: 'SL', exitPrice: sl };
        }
        // Then check if TP hit (price went up)
        if (candle.high >= tp) {
          return { time: candle.time, outcome: 'TP', exitPrice: tp };
        }
      } else { // SHORT
        // For SHORT: check if SL hit first (price went up)
        if (candle.high >= sl) {
          return { time: candle.time, outcome: 'SL', exitPrice: sl };
        }
        // Then check if TP hit (price went down)
        if (candle.low <= tp) {
          return { time: candle.time, outcome: 'TP', exitPrice: tp };
        }
      }
    }

    return { time: null, outcome: null, exitPrice: null }; // Exit not found in available data
  }


  async captureChartScreenshot() {
    return new Promise(async (resolve, reject) => {
      try {
        const captureArea = document.querySelector('.chart-center') || document.getElementById('chartContainer');
        if (!captureArea) {
          reject(new Error('Capture area not found'));
          return;
        }

        console.log('📸 Capturing full chart area...');
        
        if (typeof html2canvas === 'undefined') {
          await new Promise((res, rej) => {
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
            script.onload = res;
            script.onerror = rej;
            document.head.appendChild(script);
          });
        }

        const canvas = await html2canvas(captureArea, {
          backgroundColor: '#131722',
          useCORS: true,
          scale: 2
        });

        const dataUrl = canvas.toDataURL('image/jpeg', 0.95);
        console.log('✅ Screenshot captured:', (dataUrl.length / 1024).toFixed(1), 'KB');
        resolve(dataUrl);
      } catch (err) {
        console.error('❌ Screenshot capture failed:', err);
        reject(err);
      }
    });
  }

  async handleSubmit(e) {
    e.preventDefault();
    const btn = this.form.querySelector("button[type='submit']");
    btn.disabled = true;

    // Get current account ID with debugging
    const accountId = window.accountManager?.getCurrentAccountId();
    console.log('📝 Submitting trade to account:', accountId);

    if (!accountId) {
      console.error('❌ No account selected!');
      if (window.notify) {
        window.notify.error('Please select an account first');
      }
      btn.disabled = false;
      return;
    }

    // Determine direction from entry/sl/tp
    const entry = parseFloat(this.inputs.entry.value);
    const sl = parseFloat(this.inputs.sl.value);
    const tp = parseFloat(this.inputs.tp.value);

    // Direction logic: if TP > entry, it's LONG; if TP < entry, it's SHORT
    const direction = tp > entry ? 'LONG' : 'SHORT';
    console.log('   Direction:', direction, '(TP:', tp, 'Entry:', entry, ')');

    // Extract trade time from drawing (if available) or use current time
    let ts_open = Math.floor(Date.now() / 1000);
    let ts_close = null;
    let outcome = null;
    let exit_price = null;

    const rrDrawing = this.engine.state.drawings.find(d => d.type === "riskreward");
    if (rrDrawing && rrDrawing.points && rrDrawing.points.length > 0) {
      // Chart timestamps are already in Unix seconds
      ts_open = Math.floor(rrDrawing.points[0].time);

      // Find when price hit SL or TP by scanning candles
      const exitInfo = this.findExitTime(ts_open, null, direction, sl, tp);

      if (exitInfo.time) {
        ts_close = exitInfo.time;
        outcome = exitInfo.outcome;
        exit_price = exitInfo.exitPrice;

        const openDate = new Date(ts_open * 1000);
        const closeDate = new Date(ts_close * 1000);
        console.log('   Using trade time from chart:');
        console.log('   Entry:', openDate.toISOString(), '(', ts_open, ')');
        console.log('   Exit:', closeDate.toISOString(), '(', ts_close, ')');
        console.log('   Outcome:', outcome, 'at price:', exit_price);
      } else {
        console.log('   Exit: Not found in chart data - trade still open');
        ts_close = ts_open; // Use entry time as placeholder
        outcome = 'OPEN';
      }
    } else {
      console.log('   No drawing found, using current time');
    }

    const payload = {
      account_id: accountId,
      symbol: this.symbolSelect.value,
      direction: direction,
      entry_price: entry,
      exit_price: exit_price, // Set the actual exit price
      sl: sl,
      tp: tp,
      ts_open: ts_open,
      ts_close: ts_close || ts_open,
      outcome: outcome, // Set the outcome (TP/SL/OPEN)
      timeframe: this.tfSelect.value,
      risk: parseFloat(this.inputs.risk.value),
      lots: parseFloat(this.inputs.lots.value),
      mindset: this.inputs.mindset.value,
      setup: this.inputs.setup.value,
      notes: this.inputs.notes.value,
      drawings: this.engine.state.drawings,
      indicator_data: {
        mindset: this.inputs.mindset.value,
        setup: this.inputs.setup.value,
        risk_pct: parseFloat(this.inputs.risk.value),
        lots: parseFloat(this.inputs.lots.value)
      }
    };

    try {
      // Capture chart screenshot before submitting
      let chartScreenshot = null;
      try {
        chartScreenshot = await this.captureChartScreenshot();
        console.log('📸 Chart screenshot captured');
      } catch (err) {
        console.warn('Failed to capture screenshot:', err);
      }

      const res = await fetch("/api/trades/manual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...payload,
          chart_screenshot: chartScreenshot
        })
      });

      const data = await res.json();

      if (res.ok) {
        const accountName = window.accountManager?.currentAccount?.name || 'Account';
        if (window.notify) {
          window.notify.success(`✅ Trade logged to ${accountName}!`);
        } else {
          alert(`Trade logged to ${accountName}!`);
        }
        // Reset form instead of redirecting
        this.form.reset();
        this.inputs.risk.value = "1.0";
        if (this.engine && typeof this.engine.clear === 'function') {
          this.engine.clear();
        }
      } else {
        console.error("Error response:", data);
        const errorMsg = data.error || "Unknown error";
        const details = data.message || data.details || "";
        if (window.notify) {
          window.notify.error(`${errorMsg}${details ? ': ' + details : ''}`);
        } else {
          alert(`Error: ${errorMsg}\n${details}`);
        }
      }
    } catch (err) {
      console.error("Request failed:", err);
      if (window.notify) {
        window.notify.error("System Error: " + err.message);
      } else {
        alert("System Error: " + err.message);
      }
    } finally {
      btn.disabled = false;
    }
  }
}

window.TradeEntryPro = TradeEntryPro;
