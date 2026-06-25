const signalsState = {
  backtests: [],
  backtest: null,
  candles: [],
  chart: null,
  series: null,
  overlayCanvas: null,
  overlayCtx: null,
  techSeries: {
    ema20: null,
    ema50: null,
    vwap: null,
  },
  selectedTradeId: null,
  showTech: true,
};

function signalsFormatPrice(value) {
  if (value == null || Number.isNaN(Number(value))) return "-";
  return Number(value).toFixed(2);
}

async function signalsApi(url, opts = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function signalsQueryParam(name) {
  const url = new URL(window.location.href);
  return url.searchParams.get(name);
}

function initSignalsChart() {
  const container = document.getElementById("signalsChartContainer");
  signalsState.chart = LightweightCharts.createChart(container, {
    layout: { background: { color: "#131722" }, textColor: "#d1d4dc" },
    grid: {
      vertLines: { color: "#2a2e39" },
      horzLines: { color: "#2a2e39" },
    },
    rightPriceScale: { borderColor: "#2a2e39" },
    timeScale: { borderColor: "#2a2e39", timeVisible: true, secondsVisible: false },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  });

  signalsState.series = signalsState.chart.addCandlestickSeries({
    upColor: "#089981",
    downColor: "#f23645",
    wickUpColor: "#089981",
    wickDownColor: "#f23645",
    borderVisible: false,
  });

  signalsState.techSeries.ema20 = signalsState.chart.addLineSeries({
    color: "#f5d400",
    lineWidth: 1,
    visible: true,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  signalsState.techSeries.ema50 = signalsState.chart.addLineSeries({
    color: "#7b61ff",
    lineWidth: 1,
    visible: true,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  signalsState.techSeries.vwap = signalsState.chart.addLineSeries({
    color: "#1ec8a5",
    lineWidth: 1,
    visible: true,
    priceLineVisible: false,
    lastValueVisible: false,
  });

  const canvas = document.getElementById("signalsDrawLayer");
  signalsState.overlayCanvas = canvas;
  signalsState.overlayCtx = canvas.getContext("2d");

  const resize = () => {
    const rect = container.getBoundingClientRect();
    signalsState.chart.applyOptions({ width: rect.width, height: rect.height });
    canvas.width = rect.width;
    canvas.height = rect.height;
    drawTradeOverlay();
  };
  window.addEventListener("resize", resize);
  signalsState.chart.timeScale().subscribeVisibleTimeRangeChange(() => drawTradeOverlay());
  resize();
}

function computeEma(values, period) {
  const k = 2 / (period + 1);
  const out = [];
  let ema = null;
  for (const item of values) {
    const price = Number(item.close);
    ema = ema == null ? price : (price * k) + (ema * (1 - k));
    out.push({ time: item.time, value: ema });
  }
  return out;
}

function computeSessionVwap(values) {
  const out = [];
  let currentDay = null;
  let cumPv = 0;
  let cumVol = 0;
  for (const item of values) {
    const day = new Date(item.time * 1000).toISOString().slice(0, 10);
    if (day !== currentDay) {
      currentDay = day;
      cumPv = 0;
      cumVol = 0;
    }
    const vol = Number(item.volume || 1);
    cumPv += Number(item.close) * vol;
    cumVol += vol;
    out.push({ time: item.time, value: cumPv / Math.max(cumVol, 1) });
  }
  return out;
}

function drawTradeBox(x1, x2, y1, y2, color, alpha) {
  const ctx = signalsState.overlayCtx;
  const left = Math.min(x1, x2);
  const top = Math.min(y1, y2);
  const width = Math.abs(x2 - x1);
  const height = Math.abs(y2 - y1);
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.fillStyle = color;
  ctx.fillRect(left, top, width, height);
  ctx.globalAlpha = 1;
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.strokeRect(left, top, width, height);
  ctx.restore();
}

function drawKillZoneBands() {
  const ctx = signalsState.overlayCtx;
  const visible = signalsState.chart.timeScale().getVisibleRange();
  if (!visible || !signalsState.candles.length) return;
  const zones = [
    { start: 8, end: 10, color: "rgba(41, 98, 255, 0.08)" },
    { start: 13, end: 15, color: "rgba(245, 212, 0, 0.08)" },
  ];

  const candles = signalsState.candles.filter((c) => c.time >= visible.from && c.time <= visible.to);
  if (!candles.length) return;

  for (const zone of zones) {
    let bandStart = null;
    let prevTime = null;
    for (const candle of candles) {
      const date = new Date(candle.time * 1000);
      const hour = date.getUTCHours();
      const inZone = hour >= zone.start && hour < zone.end;
      if (inZone && bandStart == null) bandStart = candle.time;
      if (!inZone && bandStart != null && prevTime != null) {
        const x1 = signalsState.chart.timeScale().timeToCoordinate(bandStart);
        const x2 = signalsState.chart.timeScale().timeToCoordinate(prevTime);
        if (x1 != null && x2 != null) {
          ctx.save();
          ctx.fillStyle = zone.color;
          ctx.fillRect(Math.min(x1, x2), 0, Math.abs(x2 - x1), signalsState.overlayCanvas.height);
          ctx.restore();
        }
        bandStart = null;
      }
      prevTime = candle.time;
    }
    if (bandStart != null && prevTime != null) {
      const x1 = signalsState.chart.timeScale().timeToCoordinate(bandStart);
      const x2 = signalsState.chart.timeScale().timeToCoordinate(prevTime);
      if (x1 != null && x2 != null) {
        ctx.save();
        ctx.fillStyle = zone.color;
        ctx.fillRect(Math.min(x1, x2), 0, Math.abs(x2 - x1), signalsState.overlayCanvas.height);
        ctx.restore();
      }
    }
  }
}

function drawTradeOverlay() {
  const ctx = signalsState.overlayCtx;
  if (!ctx || !signalsState.backtest?.trades?.length) return;
  ctx.clearRect(0, 0, signalsState.overlayCanvas.width, signalsState.overlayCanvas.height);
  drawKillZoneBands();

  for (const trade of signalsState.backtest.trades) {
    const entryTime = Math.floor(new Date(trade.entry_time).getTime() / 1000);
    const exitTime = trade.exit_time
      ? Math.floor(new Date(trade.exit_time).getTime() / 1000)
      : entryTime + (30 * 60);
    const entry = Number(trade.entry_price);
    const stop = Number(trade.stop_loss);
    const tp = Number(trade.take_profit);

    const x1 = signalsState.chart.timeScale().timeToCoordinate(entryTime);
    const x2 = signalsState.chart.timeScale().timeToCoordinate(exitTime);
    const yEntry = signalsState.series.priceToCoordinate(entry);
    const yStop = signalsState.series.priceToCoordinate(stop);
    const yTp = signalsState.series.priceToCoordinate(tp);
    if ([x1, x2, yEntry, yStop, yTp].some((v) => v == null)) continue;

    const selected = trade.id === signalsState.selectedTradeId;
    const profitColor = trade.direction === "long" ? "#089981" : "#f23645";
    const riskColor = trade.direction === "long" ? "#f23645" : "#089981";
    drawTradeBox(x1, x2, yEntry, yTp, profitColor, selected ? 0.22 : 0.12);
    drawTradeBox(x1, x2, yEntry, yStop, riskColor, selected ? 0.18 : 0.08);

    ctx.save();
    ctx.fillStyle = "#d1d4dc";
    ctx.font = "12px Trebuchet MS";
    ctx.fillText(
      `${trade.direction.toUpperCase()} ${signalsFormatPrice(entry)}`,
      Math.min(x1, x2) + 6,
      yEntry - 6,
    );
    ctx.restore();
  }
}

function renderSignalsSummary() {
  const host = document.getElementById("signalsSummary");
  const backtest = signalsState.backtest;
  if (!backtest) {
    host.innerHTML = "";
    return;
  }
  const summary = backtest.summary || {};
  host.innerHTML = `
    <div class="signal-card">
      <span class="muted">Strategy</span>
      <strong>${backtest.name || "-"}</strong>
    </div>
    <div class="signal-card">
      <span class="muted">Symbol</span>
      <strong>${backtest.symbol || "-"}</strong>
    </div>
    <div class="signal-card">
      <span class="muted">Trades</span>
      <strong>${summary.total_trades ?? backtest.trades?.length ?? 0}</strong>
    </div>
    <div class="signal-card">
      <span class="muted">Win Rate</span>
      <strong>${Number(summary.win_rate || 0).toFixed(1)}%</strong>
    </div>
    <div class="signal-card">
      <span class="muted">Return</span>
      <strong>${Number(summary.return_pct || 0).toFixed(2)}%</strong>
    </div>
    <div class="signal-card">
      <span class="muted">Max DD</span>
      <strong>${Number(summary.max_drawdown || 0).toFixed(2)}%</strong>
    </div>
    <div class="signal-card">
      <span class="muted">MC Prob Profit</span>
      <strong>${Number(backtest.monte_carlo?.prob_profit || 0).toFixed(1)}%</strong>
    </div>
  `;
}

function renderSignalsTradeList() {
  const host = document.getElementById("signalsTradeList");
  host.innerHTML = "";
  const trades = signalsState.backtest?.trades || [];
  document.getElementById("signalsTradeCount").textContent = trades.length;

  trades.forEach((trade) => {
    const div = document.createElement("div");
    div.className = `trade-item ${trade.id === signalsState.selectedTradeId ? "active" : ""}`;
    const meta = trade.meta || {};
    div.innerHTML = `
      <div class="title"><strong>${trade.direction.toUpperCase()}</strong> ${meta.level_name || "level"}</div>
      <div class="meta">Entry ${signalsFormatPrice(trade.entry_price)} | SL ${signalsFormatPrice(trade.stop_loss)} | TP ${signalsFormatPrice(trade.take_profit)}</div>
      <div class="meta">${trade.notes || ""}</div>
    `;
    div.addEventListener("click", () => {
      signalsState.selectedTradeId = trade.id;
      focusTrade(trade);
      renderSignalsTradeList();
      drawTradeOverlay();
    });
    host.appendChild(div);
  });
}

function focusTrade(trade) {
  const entryTime = Math.floor(new Date(trade.entry_time).getTime() / 1000);
  const exitTime = trade.exit_time
    ? Math.floor(new Date(trade.exit_time).getTime() / 1000)
    : entryTime + 60 * 30;
  signalsState.chart.timeScale().setVisibleRange({
    from: entryTime - 60 * 90,
    to: exitTime + 60 * 120,
  });
}

async function loadSignalsBacktests() {
  const resp = await signalsApi("/api/backtests");
  signalsState.backtests = resp.backtests || [];
  const select = document.getElementById("signalsBacktestSelect");
  select.innerHTML = "";
  for (const bt of signalsState.backtests) {
    const opt = document.createElement("option");
    opt.value = bt.id;
    opt.textContent = bt.name;
    select.appendChild(opt);
  }
}

async function loadSelectedBacktest(backtestId) {
  const backtest = await signalsApi(`/api/backtests/${encodeURIComponent(backtestId)}`);
  signalsState.backtest = backtest;

  const candlesResp = await signalsApi(
    `/api/candles?symbol=${encodeURIComponent(backtest.symbol)}&timeframe=${encodeURIComponent(backtest.timeframe)}&asset_type=${encodeURIComponent(backtest.asset_type || "")}&limit=140000`,
  );
  signalsState.candles = candlesResp.candles || [];
  signalsState.series.setData(signalsState.candles);

  const ema20 = computeEma(signalsState.candles, 20);
  const ema50 = computeEma(signalsState.candles, 50);
  const vwap = computeSessionVwap(signalsState.candles);
  signalsState.techSeries.ema20.setData(ema20);
  signalsState.techSeries.ema50.setData(ema50);
  signalsState.techSeries.vwap.setData(vwap);
  signalsState.techSeries.ema20.applyOptions({ visible: !!signalsState.showTech });
  signalsState.techSeries.ema50.applyOptions({ visible: !!signalsState.showTech });
  signalsState.techSeries.vwap.applyOptions({ visible: !!signalsState.showTech });

  signalsState.selectedTradeId = backtest.trades?.[0]?.id || null;
  renderSignalsSummary();
  renderSignalsTradeList();
  signalsState.chart.timeScale().fitContent();
  if (backtest.trades?.length) focusTrade(backtest.trades[0]);
  drawTradeOverlay();
}

async function openReviewSessionForBacktest() {
  const backtestId = document.getElementById("signalsBacktestSelect").value;
  if (!backtestId) return;
  const backtest = signalsState.backtest;
  const payload = await signalsApi("/api/sessions", {
    method: "POST",
    body: JSON.stringify({
      symbol: backtest.symbol,
      asset_type: backtest.asset_type,
      timeframe: String(backtest.timeframe),
      name: `${backtest.symbol}-${backtest.timeframe} Signals`,
      backtest_id: backtestId,
      metadata: {
        review_origin: "signals",
        playback_mode: "full",
        show_tech: true,
        tech_overlay: "vwap_ema20",
        show_ict: false,
      },
    }),
  });
  window.location.href = `/?session=${encodeURIComponent(payload.session_id)}`;
}

function bindSignalsEvents() {
  document.getElementById("signalsBacktestSelect").addEventListener("change", async (event) => {
    await loadSelectedBacktest(event.target.value);
  });
  document.getElementById("signalsRefreshBtn").addEventListener("click", async () => {
    await loadSignalsBacktests();
    const selected = document.getElementById("signalsBacktestSelect").value || signalsState.backtests[0]?.id;
    if (selected) await loadSelectedBacktest(selected);
  });
  document.getElementById("signalsShowTech").addEventListener("change", (event) => {
    signalsState.showTech = !!event.target.checked;
    signalsState.techSeries.ema20.applyOptions({ visible: signalsState.showTech });
    signalsState.techSeries.ema50.applyOptions({ visible: signalsState.showTech });
    signalsState.techSeries.vwap.applyOptions({ visible: signalsState.showTech });
  });
  document.getElementById("openReviewFromSignalsBtn").addEventListener("click", () => {
    openReviewSessionForBacktest().catch(console.error);
  });
  document.getElementById("openAnalyticsFromSignalsBtn").addEventListener("click", () => {
    window.location.href = "/analytics";
  });
}

async function signalsMain() {
  initSignalsChart();
  bindSignalsEvents();
  await loadSignalsBacktests();
  const requested = signalsQueryParam("backtest");
  const initial = requested && signalsState.backtests.some((item) => item.id === requested)
    ? requested
    : signalsState.backtests[0]?.id;
  if (!initial) return;
  document.getElementById("signalsBacktestSelect").value = initial;
  await loadSelectedBacktest(initial);
}

signalsMain().catch(console.error);
