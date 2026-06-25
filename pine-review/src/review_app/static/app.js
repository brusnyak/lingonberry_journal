const state = {
  symbols: [],
  candles: [],
  session: null,
  sessionId: null,
  currentTool: "cursor",
  activeTradeId: null,
  selectedId: null,
  drawingDraft: null,
  dragging: null, // {id, pointIdx, offset} OR {id, rrHandle}
  chart: null,
  series: null,
  ctx: null,
  saveTimer: null,
  assetType: "crypto",
  hoveredHandle: null, // {drawingId, handle}
  backtests: [],
  ictOverlay: { fvgs: [], order_blocks: [], liquidity: [] },
  showIct: true,

  showTech: false,
  tech: { ema20: [], ema50: [], vwap: [], rsi14: [], atr14: [], byTime: {} },
  techSeries: { ema20: null, ema50: null, vwap: null },
  fullCandles: [],
  intervalCandles: [],
  playback: {
    enabled: true,
    isPlaying: false,
    timer: null,
    interval: null, // {from,to}
    currentTime: null,
  },
  saveInFlight: false,
  saveQueued: false,
  saveDirty: false,
  lastSavedJson: "",
  clipboardDrawing: null,
  lastCursorPoint: null,
  dragDirty: false,
};

const RR_FILL_ALPHA_SELECTED = 0.14;
const RR_FILL_ALPHA_UNSELECTED = 0.06;
const RR_FILL_ALPHA_DRAWING = 0.14;
const TWO_MONTHS_SEC = 60 * 24 * 3600;

const TOOLS = [
  { id: "cursor", label: "Cursor", icon: "mouse-pointer-2" },
  { id: "trendline", label: "Line", icon: "trending-up" },
  { id: "hline", label: "H-Line", icon: "minus" },
  { id: "accum", label: "Accum", icon: "copy-plus" },
  { id: "dist", label: "Dist", icon: "copy-x" },
  { id: "manip", label: "Sweep", icon: "move-up-right" },
  { id: "bos", label: "BOS", icon: "git-branch" },
  { id: "choch", label: "CHoCH", icon: "milestone" },
  { id: "rect", label: "Rect", icon: "square" },
  { id: "text", label: "Text", icon: "type" },
  { id: "long", label: "Long", icon: "arrow-up-circle" },
  { id: "short", label: "Short", icon: "arrow-down-circle" },
];

function formatPrice(val) {
  if (val == null || isNaN(val)) return "-";
  let precision = 2;
  if (state.assetType === "forex") precision = 5;
  if (state.assetType === "metal") precision = 3;
  if (state.assetType === "index") precision = 2;
  return Number(val).toFixed(precision);
}

async function api(url, opts = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

function clonePoint(p) {
  return { time: Number(p.time), price: Number(p.price) };
}

function rrFromDrawing(d) {
  if (!d || d.type !== "riskreward") return null;
  if (d.rr) return d.rr;
  if (!d.points || d.points.length < 2) return null;
  const entry = d.points[0].price;
  const stop = d.points[1].price;
  let inferredSide = d.side;
  let inferredTP = null;
  if (!inferredSide && d.trade_id && state.session?.trades?.length) {
    const linked = state.session.trades.find((t) => t.id === d.trade_id);
    if (linked) {
      inferredSide = linked.manual_direction ?? linked.direction;
      inferredTP = linked.manual_take_profit ?? linked.take_profit ?? null;
    }
  }
  const side = inferredSide === "short" ? "short" : "long";
  const risk = Math.abs(entry - stop);
  return {
    side,
    start_time: Number(d.points[0].time),
    end_time: Number(d.points[1].time),
    entry_price: Number(entry),
    stop_price: Number(stop),
    take_price: Number(inferredTP ?? (side === "long" ? entry + risk * 2 : entry - risk * 2)),
  };
}

function setRR(d, rr) {
  d.rr = rr;
  d.points = [
    { time: rr.start_time, price: rr.entry_price },
    { time: rr.end_time, price: rr.stop_price },
  ];
}

function initChart() {
  const container = document.getElementById("chartContainer");
  state.chart = LightweightCharts.createChart(container, {
    layout: { background: { color: "#131722" }, textColor: "#d1d4dc" },
    grid: {
      vertLines: { color: "#2a2e39" },
      horzLines: { color: "#2a2e39" },
    },
    rightPriceScale: { borderColor: "#2a2e39" },
    timeScale: { borderColor: "#2a2e39", timeVisible: true, secondsVisible: false },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    handleScroll: true,
    handleScale: true,
  });
  state.series = state.chart.addCandlestickSeries({
    upColor: "#089981",
    downColor: "#f23645",
    wickUpColor: "#089981",
    wickDownColor: "#f23645",
    borderVisible: false,
  });
  state.techSeries.ema20 = state.chart.addLineSeries({
    color: "#f5d400",
    lineWidth: 1,
    visible: false,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  state.techSeries.ema50 = state.chart.addLineSeries({
    color: "#7b61ff",
    lineWidth: 1,
    visible: false,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  state.techSeries.vwap = state.chart.addLineSeries({
    color: "#1ec8a5",
    lineWidth: 1,
    visible: false,
    priceLineVisible: false,
    lastValueVisible: false,
  });

  const canvas = document.getElementById("drawLayer");
  state.ctx = canvas.getContext("2d");

  const resize = () => {
    const rect = container.getBoundingClientRect();
    state.chart.applyOptions({ width: rect.width, height: rect.height });
    canvas.width = rect.width;
    canvas.height = rect.height;
    redrawOverlay();
  };
  window.addEventListener("resize", resize);
  resize();

  state.chart.timeScale().subscribeVisibleTimeRangeChange(() => redrawOverlay());
  state.chart.subscribeCrosshairMove((e) => {
    state.mouse = e;
    if (e?.point) {
      const t = state.chart.timeScale().coordinateToTime(e.point.x);
      const p = state.series.coordinateToPrice(e.point.y);
      if (t != null && p != null) {
        state.lastCursorPoint = { time: Number(t), price: Number(p) };
      }
    }
    redrawOverlay();
  });

  container.addEventListener("mousedown", handleMouseDown, true);
  window.addEventListener("mousemove", handleMouseMove, true);
  window.addEventListener("mouseup", handleMouseUp, true);
  window.addEventListener("keydown", handleKeyDown);
}

function setChartInteraction(enabled) {
  if (!state.chart) return;
  state.chart.applyOptions({
    handleScroll: enabled,
    handleScale: enabled,
  });
}

function buildToolbars() {
  const left = document.getElementById("leftTools");
  left.innerHTML = "";
  for (const tool of TOOLS) {
    const btn = document.createElement("button");
    btn.className = `tool-btn ${state.currentTool === tool.id ? "active" : ""}`;
    if (state.session?.starred_tools?.includes(tool.id)) btn.classList.add("starred");
    btn.dataset.toolId = tool.id;
    btn.title = tool.label;
    btn.innerHTML = `<i data-lucide="${tool.icon}"></i><span class="star">★</span>`;
    btn.addEventListener("click", (e) => {
      if (e.target.classList.contains("star")) toggleStar(tool.id);
      else setTool(tool.id);
    });
    left.appendChild(btn);
  }

  const floating = document.getElementById("floatingTools");
  floating.innerHTML = "";
  if (state.session?.starred_tools?.length > 0) {
    floating.classList.remove("hidden");
    for (const toolId of state.session.starred_tools) {
      const t = TOOLS.find((x) => x.id === toolId);
      if (!t) continue;
      const b = document.createElement("button");
      b.className = `btn-icon ${state.currentTool === t.id ? "active" : ""}`;
      b.innerHTML = `<i data-lucide="${t.icon}"></i>`;
      b.title = t.label;
      b.addEventListener("click", () => setTool(t.id));
      floating.appendChild(b);
    }
  } else {
    floating.classList.add("hidden");
  }
  if (window.lucide) lucide.createIcons();
}

function setTool(toolId) {
  state.currentTool = toolId;
  state.drawingDraft = null;
  state.selectedId = null;
  buildToolbars();
  redrawOverlay();
}

function toggleStar(toolId) {
  if (!state.session) return;
  const arr = state.session.starred_tools || [];
  const idx = arr.indexOf(toolId);
  if (idx >= 0) arr.splice(idx, 1);
  else arr.push(toolId);
  state.session.starred_tools = arr;
  buildToolbars();
  scheduleSave();
}

function getPointFromMouse(ev, opts = {}) {
  const { disableMagnet = false } = opts;
  const rect = document.getElementById("chartContainer").getBoundingClientRect();
  const x = ev.clientX - rect.left;
  const y = ev.clientY - rect.top;
  
  // Weak Magnet logic
  const mouseTime = state.chart.timeScale().coordinateToTime(x);
  const mousePrice = state.series.coordinateToPrice(y);
  if (mouseTime == null || mousePrice == null) return null;

  let bestPoint = { time: Number(mouseTime), price: Number(mousePrice) };
  if (disableMagnet) return bestPoint;
  let minD2 = 400; // 20px radius

  const visibleRange = state.chart.timeScale().getVisibleRange();
  if (visibleRange) {
    for (const c of state.candles) {
      if (c.time < visibleRange.from || c.time > visibleRange.to) continue;
      const cx = state.chart.timeScale().timeToCoordinate(c.time);
      const cp_o = state.series.priceToCoordinate(c.open);
      const cp_h = state.series.priceToCoordinate(c.high);
      const cp_l = state.series.priceToCoordinate(c.low);
      const cp_c = state.series.priceToCoordinate(c.close);
      
      [
        {y: cp_o, p: c.open}, {y: cp_h, p: c.high}, 
        {y: cp_l, p: c.low}, {y: cp_c, p: c.close}
      ].forEach(lvl => {
        if (lvl.y == null) return;
        const d2 = (cx - x)**2 + (lvl.y - y)**2;
        if (d2 < minD2) {
          minD2 = d2;
          bestPoint = { time: c.time, price: lvl.p };
        }
      });
    }
  }

  return bestPoint;
}

function axisLockPoint(point, anchor) {
  const ax = state.chart.timeScale().timeToCoordinate(anchor.time);
  const ay = state.series.priceToCoordinate(anchor.price);
  const px = state.chart.timeScale().timeToCoordinate(point.time);
  const py = state.series.priceToCoordinate(point.price);
  if (ax == null || ay == null || px == null || py == null) return point;
  const dx = Math.abs(px - ax);
  const dy = Math.abs(py - ay);
  if (dx >= dy) {
    // Horizontal lock
    return { time: point.time, price: anchor.price };
  }
  // Vertical lock
  return { time: anchor.time, price: point.price };
}

function getRiskRewardHandlePoints(rr) {
  if (!rr) return [];
  const xStart = timeToX(rr.start_time, true);
  const xEnd = timeToX(rr.end_time, true);
  const yEntry = priceToY(rr.entry_price, true);
  const yStop = priceToY(rr.stop_price, true);
  const yTP = priceToY(rr.take_price, true);
  if (xStart == null || xEnd == null || yEntry == null || yStop == null || yTP == null) return [];
  const leftX = Math.min(xStart, xEnd);
  return [
    { key: "entry", x: leftX, y: yEntry, cursor: "ns-resize" },
    { key: "stop", x: leftX, y: yStop, cursor: "ns-resize" },
    { key: "tp", x: leftX, y: yTP, cursor: "ns-resize" },
    { key: "time", x: xEnd, y: yEntry, cursor: "ew-resize" },
  ];
}

function computeSessionVwap(candles) {
  const out = [];
  let currentDay = null;
  let cumPv = 0;
  let cumVol = 0;
  for (const candle of candles) {
    const day = new Date(candle.time * 1000).toISOString().slice(0, 10);
    if (day !== currentDay) {
      currentDay = day;
      cumPv = 0;
      cumVol = 0;
    }
    const vol = Number(candle.volume || 1);
    cumPv += Number(candle.close) * vol;
    cumVol += vol;
    out.push({ time: candle.time, value: cumPv / Math.max(cumVol, 1) });
  }
  return out;
}

function linkedRiskRewardDrawing(tradeId) {
  if (!tradeId || !state.session?.drawings?.length) return null;
  return state.session.drawings.find((d) => d.type === "riskreward" && d.trade_id === tradeId) || null;
}

function tradeHasLinkedRiskReward(tradeId) {
  return !!linkedRiskRewardDrawing(tradeId);
}

function syncPlaybackUi() {
  const fullMode = state.session?.metadata?.playback_mode === "full";
  const playBtn = document.getElementById("playToggleBtn");
  const step1Btn = document.getElementById("step1Btn");
  const step5Btn = document.getElementById("step5Btn");
  const status = document.getElementById("playbackStatus");
  if (!playBtn || !step1Btn || !step5Btn || !status) return;
  playBtn.disabled = fullMode;
  step1Btn.disabled = fullMode;
  step5Btn.disabled = fullMode;
  if (fullMode) {
    playBtn.textContent = "Review";
    status.textContent = "Full Chart";
    return;
  }
  if (!state.playback.isPlaying) playBtn.textContent = "Play";
}

function handleMouseDown(ev) {
  if (!state.session) return;
  const p = getPointFromMouse(ev, { disableMagnet: !!ev.shiftKey });
  if (!p) return;

  // Placement mode
  if (state.currentTool !== "cursor") {
    // Prevent chart drag/pan while placing tools.
    ev.preventDefault();
    ev.stopPropagation();
    if (state.currentTool === "text") {
      const text = prompt("Text note", "note");
      if (text) addDrawing({ type: "text", points: [p], note: text });
      state.currentTool = "cursor";
      buildToolbars();
      return;
    }
    if (state.currentTool === "hline") {
      addDrawing({ type: "hline", points: [p] });
      state.currentTool = "cursor";
      buildToolbars();
      return;
    }
    if (state.currentTool === "accum" || state.currentTool === "dist") {
      if (!state.drawingDraft) {
        state.drawingDraft = { tool: state.currentTool, first: p };
      } else {
        const first = state.drawingDraft.first;
        const tool = state.drawingDraft.tool;
        state.drawingDraft = null;
        const styleByTool = {
          accum: { fill: "rgba(52, 152, 219, 0.16)", stroke: "#3498db" },
          dist: { fill: "rgba(231, 76, 60, 0.16)", stroke: "#e74c3c" },
        };
        const noteByTool = { accum: "accumulation", dist: "distribution" };
        addDrawing({
          type: "rect",
          points: [first, p],
          style: styleByTool[tool],
          note: noteByTool[tool],
        });
        state.currentTool = "cursor";
        buildToolbars();
      }
      return;
    }
    if (!state.drawingDraft) {
      state.drawingDraft = { tool: state.currentTool, first: p };
    } else {
      const first = state.drawingDraft.first;
      const tool = state.drawingDraft.tool;
      state.drawingDraft = null;
      const p2 = ev.shiftKey && (tool === "trendline" || tool === "rect") ? axisLockPoint(p, first) : p;
      if (tool === "trendline") addDrawing({ type: "trendline", points: [first, p2] });
      if (tool === "bos" || tool === "choch" || tool === "manip") {
        const styleByTool = {
          bos: { stroke: "#2b9348", label_bg: "#2b9348", label_fg: "#ffffff", arrow_head: true },
          choch: { stroke: "#c1121f", label_bg: "#c1121f", label_fg: "#ffffff", arrow_head: true },
          manip: { stroke: "#f1c40f", label_bg: "#f1c40f", label_fg: "#101418", arrow_head: true },
        };
        const noteByTool = { bos: "BS", choch: "CH", manip: "SW" };
        addDrawing({
          type: "trendline",
          points: [first, p2],
          note: noteByTool[tool],
          style: styleByTool[tool],
        });
      }
      if (tool === "rect") addDrawing({ type: "rect", points: [first, p2] });
      if (tool === "long" || tool === "short") addDrawing({ type: "riskreward", points: [first, p], side: tool });
      state.currentTool = "cursor";
      buildToolbars();
    }
    return;
  }

  // Cursor mode: Selection and Dragging
  const rect = document.getElementById("chartContainer").getBoundingClientRect();
  const mx = ev.clientX - rect.left;
  const my = ev.clientY - rect.top;

  // Check handles of selected drawing first
  if (state.selectedId) {
    const d = state.session.drawings.find(x => x.id === state.selectedId);
    if (d) {
      if (d.type === "riskreward") {
        const rr = rrFromDrawing(d);
        if (rr) {
          const handles = getRiskRewardHandlePoints(rr);
          for (const h of handles) {
            if (h.x == null || h.y == null) continue;
            const maxD2 = h.key === "time" ? 256 : 144;
            if ((h.x - mx) ** 2 + (h.y - my) ** 2 < maxD2) {
              ev.preventDefault();
              ev.stopPropagation();
              state.dragging = { id: d.id, rrHandle: h.key };
              state.dragDirty = false;
              setChartInteraction(false);
              return;
            }
          }
          ev.preventDefault();
          ev.stopPropagation();
          state.dragging = { id: d.id, pointIdx: -1, offset: { time: p.time, price: p.price } };
          state.dragDirty = false;
          setChartInteraction(false);
          return;
        }
      } else {
        for (let i = 0; i < d.points.length; i++) {
        const xy = pointToXY(d.points[i]);
        if (xy && (xy.x - mx)**2 + (xy.y - my)**2 < 100) {
          ev.preventDefault();
          ev.stopPropagation();
          state.dragging = { id: d.id, pointIdx: i };
          state.dragDirty = false;
          setChartInteraction(false);
          return;
        }
      }
      }
    }
  }

  // Hit test all drawings
  let found = null;
  for (const d of [...state.session.drawings].reverse()) {
    if (hitTest(d, mx, my)) {
      found = d.id;
      break;
    }
  }
  
  state.selectedId = found;
  if (found) {
    const selectedDrawing = state.session.drawings.find((d) => d.id === found) || null;
    if (selectedDrawing?.trade_id) {
      state.activeTradeId = selectedDrawing.trade_id;
      renderTradeList();
    }
    ev.preventDefault();
    ev.stopPropagation();
    state.dragging = { id: found, pointIdx: -1, offset: { time: p.time, price: p.price } };
    state.dragDirty = false;
    setChartInteraction(false);
  }
  redrawOverlay();
}

function handleMouseMove(ev) {
  const container = document.getElementById("chartContainer");
  const rect = container.getBoundingClientRect();
  const mx = ev.clientX - rect.left;
  const my = ev.clientY - rect.top;

  // Hover cursor feedback for risk/reward handles.
  state.hoveredHandle = null;
  if (state.selectedId && state.session) {
    const d = state.session.drawings.find(x => x.id === state.selectedId);
    if (d && d.type === "riskreward") {
      const rr = rrFromDrawing(d);
      if (rr) {
        const handles = getRiskRewardHandlePoints(rr);
        for (const h of handles) {
          if (h.x == null || h.y == null) continue;
          const maxD2 = h.key === "time" ? 256 : 144;
          if ((h.x - mx) ** 2 + (h.y - my) ** 2 < maxD2) {
            state.hoveredHandle = h;
            break;
          }
        }
      }
    }
  }

  if (state.dragging) {
    container.style.cursor = state.dragging.rrHandle === "time" ? "ew-resize" : "grabbing";
  } else if (state.hoveredHandle) {
    container.style.cursor = state.hoveredHandle.cursor;
  } else if (state.currentTool === "cursor") {
    container.style.cursor = "default";
  } else {
    container.style.cursor = "crosshair";
  }

  if (state.dragging && state.session) {
    ev.preventDefault();
    ev.stopPropagation();
    const p = getPointFromMouse(ev, { disableMagnet: !!ev.shiftKey });
    if (!p) return;
    const d = state.session.drawings.find(x => x.id === state.dragging.id);
    if (!d) return;

    if (state.dragging.rrHandle && d.type === "riskreward") {
      const rr = rrFromDrawing(d);
      if (!rr) return;
      const minDuration = 60; // 1 minute minimum in epoch seconds
      if (state.dragging.rrHandle === "entry") {
        rr.entry_price = p.price;
      } else if (state.dragging.rrHandle === "stop") {
        rr.stop_price = p.price;
      } else if (state.dragging.rrHandle === "tp") {
        rr.take_price = p.price;
      } else if (state.dragging.rrHandle === "time") {
        rr.end_time = Math.max(rr.start_time + minDuration, Math.floor(p.time));
      }
      setRR(d, rr);
      upsertTradeFromRiskReward(d);
    } else if (state.dragging.pointIdx !== -1) {
      let nextPoint = p;
      if (ev.shiftKey && (d.type === "trendline" || d.type === "rect")) {
        const anchorIdx = state.dragging.pointIdx === 0 ? 1 : 0;
        const anchor = d.points[anchorIdx];
        if (anchor) nextPoint = axisLockPoint(p, anchor);
      }
      d.points[state.dragging.pointIdx] = nextPoint;
    } else {
      // Move entire drawing
      const dt = p.time - state.dragging.offset.time;
      const dp = p.price - state.dragging.offset.price;
      d.points = d.points.map(pt => ({ time: pt.time + dt, price: pt.price + dp }));
      if (d.type === "riskreward" && d.rr) {
        d.rr.start_time += dt;
        d.rr.end_time += dt;
        d.rr.entry_price += dp;
        d.rr.stop_price += dp;
        d.rr.take_price += dp;
      }
      state.dragging.offset = p;
      if (d.type === "riskreward") {
        const rr = rrFromDrawing(d);
        if (rr) setRR(d, rr);
      }
    }
    if (d.type === "riskreward") {
      upsertTradeFromRiskReward(d);
    }
    state.dragDirty = true;
    redrawOverlay();
  }
}

function handleMouseUp() {
  state.dragging = null;
  setChartInteraction(true);
  if (state.dragDirty) {
    state.dragDirty = false;
    scheduleSave();
  }
  const container = document.getElementById("chartContainer");
  if (container) container.style.cursor = state.currentTool === "cursor" ? "default" : "crosshair";
}

function getPasteAnchorPoint() {
  if (state.lastCursorPoint) return state.lastCursorPoint;
  const vr = state.chart?.timeScale?.().getVisibleRange?.();
  if (vr && state.candles?.length) {
    const midT = Math.floor((Number(vr.from) + Number(vr.to)) / 2);
    const c = state.candles.find((x) => x.time >= midT) || state.candles[state.candles.length - 1];
    if (c) return { time: Number(c.time), price: Number(c.close) };
  }
  return null;
}

function handleKeyDown(ev) {
  const meta = ev.ctrlKey || ev.metaKey;
  if (meta && ev.key.toLowerCase() === "c" && state.selectedId && state.session) {
    const d = state.session.drawings.find((x) => x.id === state.selectedId);
    if (d) {
      state.clipboardDrawing = JSON.parse(JSON.stringify(d));
    }
    return;
  }
  if (meta && ev.key.toLowerCase() === "v" && state.clipboardDrawing) {
    ev.preventDefault();
    const base = JSON.parse(JSON.stringify(state.clipboardDrawing));
    const anchor = getPasteAnchorPoint();
    const first = Array.isArray(base.points) && base.points.length ? base.points[0] : null;
    const dt = (anchor && first) ? (Number(anchor.time) - Number(first.time)) : (Math.max(60, Number(state.session?.timeframe || 1) * 60) * 3);
    const dp = (anchor && first) ? (Number(anchor.price) - Number(first.price)) : ((state.candles?.length ? state.candles[state.candles.length - 1].close : 1) * 0.0005);
    if (Array.isArray(base.points)) {
      base.points = base.points.map((pt) => ({ time: Number(pt.time) + dt, price: Number(pt.price) + dp }));
    }
    if (base.rr) {
      base.rr.start_time = Number(base.rr.start_time) + dt;
      base.rr.end_time = Number(base.rr.end_time) + dt;
      base.rr.entry_price = Number(base.rr.entry_price) + dp;
      base.rr.stop_price = Number(base.rr.stop_price) + dp;
      base.rr.take_price = Number(base.rr.take_price) + dp;
    }
    base.trade_id = null;
    addDrawing(base);
    return;
  }
  if ((ev.key === "Delete" || ev.key === "Backspace") && state.selectedId) {
    state.session.drawings = state.session.drawings.filter(x => x.id !== state.selectedId);
    state.selectedId = null;
    redrawOverlay();
    scheduleSave();
  }
}

function hitTest(d, mx, my) {
  const pts = d.points.map(pointToXY).filter(x => x);
  if (pts.length === 0) return false;

  if (d.type === "trendline" && pts.length === 2) {
    return distToSegment(mx, my, pts[0].x, pts[0].y, pts[1].x, pts[1].y) < 8;
  }
  if (d.type === "hline") {
    return Math.abs(pts[0].y - my) < 8;
  }
  if (d.type === "rect" && pts.length === 2) {
    const minX = Math.min(pts[0].x, pts[1].x);
    const maxX = Math.max(pts[0].x, pts[1].x);
    const minY = Math.min(pts[0].y, pts[1].y);
    const maxY = Math.max(pts[0].y, pts[1].y);
    return mx >= minX && mx <= maxX && my >= minY && my <= maxY;
  }
  if (d.type === "text") {
    return Math.abs(pts[0].x - mx) < 30 && Math.abs(pts[0].y - my) < 20;
  }
  if (d.type === "riskreward" && pts.length === 2) {
    const minX = Math.min(pts[0].x, pts[1].x);
    const maxX = Math.max(pts[0].x, pts[1].x);
    const minY = Math.min(pts[0].y, pts[1].y);
    const maxY = Math.max(pts[0].y, pts[1].y);
    // Expand a bit for hit testing the full tool
    const rr_y = pts[0].y + (pts[0].y - pts[1].y); 
    const fullMinY = Math.min(pts[0].y, pts[1].y, rr_y);
    const fullMaxY = Math.max(pts[0].y, pts[1].y, rr_y);
    return mx >= minX && mx <= maxX && my >= fullMinY && my <= fullMaxY;
  }
  return false;
}

function distToSegment(px, py, x1, y1, x2, y2) {
  const l2 = (x1 - x2)**2 + (y1 - y2)**2;
  if (l2 === 0) return Math.sqrt((px - x1)**2 + (py - y1)**2);
  let t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2;
  t = Math.max(0, Math.min(1, t));
  return Math.sqrt((px - (x1 + t * (x2 - x1)))**2 + (py - (y1 + t * (y2 - y1)))**2);
}

function addDrawing(partial) {
  const drawing = {
    id: crypto.randomUUID(),
    type: partial.type,
    points: partial.points.map(clonePoint),
    style: partial.style || {},
    timeframe_created: state.session.timeframe,
    note: partial.note || "",
    side: partial.side || null,
    trade_id: partial.trade_id || null,
    rr: partial.rr || null,
  };
  if (drawing.type === "riskreward") {
    const seed = rrFromDrawing(drawing);
    if (seed) setRR(drawing, seed);
  }
  state.session.drawings.push(drawing);
  state.selectedId = drawing.id;
  if (drawing.type === "riskreward") {
    upsertTradeFromRiskReward(drawing);
  }
  redrawOverlay();
  scheduleSave();
}

function repairMissingRiskRewardDrawings() {
  if (!state.session?.trades?.length) return false;
  const timeframeSec = Math.max(300, Number(state.session.timeframe || 5) * 60);
  const existingTradeIds = new Set(
    (state.session.drawings || [])
      .filter((d) => d.type === "riskreward" && d.trade_id)
      .map((d) => d.trade_id)
  );
  let changed = false;
  for (const trade of state.session.trades) {
    if (trade.source !== "manual") continue;
    if (existingTradeIds.has(trade.id)) continue;
    const entry = trade.manual_entry_price ?? trade.entry_price;
    const stop = trade.manual_stop_loss ?? trade.stop_loss;
    const take = trade.manual_take_profit ?? trade.take_profit;
    const start = Number(trade.entry_time || 0);
    const end = Number(trade.manual_exit_time ?? trade.exit_time ?? (start + timeframeSec * 6));
    const side = (trade.manual_direction ?? trade.direction ?? "long");
    if ([entry, stop, take, start].some((v) => v == null || Number.isNaN(Number(v)))) continue;
    const drawing = {
      id: crypto.randomUUID(),
      type: "riskreward",
      points: [
        { time: Number(start), price: Number(entry) },
        { time: Number(end), price: Number(stop) },
      ],
      style: {},
      timeframe_created: state.session.timeframe,
      note: trade.notes || "Recovered from manual trade",
      side,
      trade_id: trade.id,
      rr: {
        side,
        start_time: Number(start),
        end_time: Number(end),
        entry_price: Number(entry),
        stop_price: Number(stop),
        take_price: Number(take),
      },
    };
    state.session.drawings.push(drawing);
    existingTradeIds.add(trade.id);
    changed = true;
  }
  return changed;
}

function upsertTradeFromRiskReward(drawing) {
  if (!state.session || drawing.type !== "riskreward") return;
  const rr = rrFromDrawing(drawing);
  if (!rr) return;
  const entry = rr.entry_price;
  const stop = rr.stop_price;
  const tp = rr.take_price;
  const risk = Math.abs(entry - stop);
  if (risk <= 0) return;
  const side = rr.side;

  let trade = null;
  if (drawing.trade_id) {
    trade = state.session.trades.find((t) => t.id === drawing.trade_id) || null;
  }

  if (!trade) {
    trade = {
      id: crypto.randomUUID(),
      direction: side,
      entry_time: Math.floor(rr.start_time),
      entry_price: entry,
      stop_loss: stop,
      take_profit: tp,
      exit_time: Math.floor(rr.end_time),
      exit_price: null,
      notes: "Created from long/short tool",
      tags: ["manual"],
      status: "pending",
      source: "manual",
      outcome: null,
      reason_tags: [],
      manual_entry_price: entry,
      manual_direction: side,
      manual_stop_loss: stop,
      manual_take_profit: tp,
      manual_exit_time: Math.floor(rr.end_time),
      manual_exit_price: null,
      manual_hit_reason: null,
      audit_trail: [],
    };
    state.session.trades.push(trade);
  } else {
    trade.manual_direction = side;
    trade.manual_entry_price = entry;
    trade.manual_stop_loss = stop;
    trade.manual_take_profit = tp;
    trade.manual_exit_time = Math.floor(rr.end_time);
    trade.exit_time = Math.floor(rr.end_time);
    trade.audit_trail = trade.audit_trail || [];
    trade.audit_trail.push({
      time: Date.now(),
      action: "riskreward_sync",
      details: { entry, stop, tp, end_time: Math.floor(rr.end_time) },
    });
  }

  evaluateTradeOutcomeFromPrice(trade);
  drawing.trade_id = trade.id;
  state.activeTradeId = trade.id;
  renderTradeList();
  redrawOverlay();
}

function evaluateTradeOutcomeFromPrice(trade) {
  if (!trade || !state.candles?.length) return;
  const entry = trade.manual_entry_price ?? trade.entry_price;
  const sl = trade.manual_stop_loss ?? trade.stop_loss;
  const tp = trade.manual_take_profit ?? trade.take_profit;
  const start = trade.entry_time;
  const end = trade.manual_exit_time ?? trade.exit_time ?? start;
  if (entry == null || sl == null || tp == null || !start || !end) return;

  const direction = trade.manual_direction ?? trade.direction;
  const bars = state.candles.filter((c) => c.time >= start && c.time <= end);
  if (!bars.length) {
    trade.manual_hit_reason = "unknown";
    trade.outcome = "skip";
    return;
  }

  // Conservative rule on same-candle collision: stop-loss has priority.
  for (const b of bars) {
    if (direction === "long") {
      if (b.low <= sl) {
        trade.manual_exit_price = sl;
        trade.manual_hit_reason = "stop_loss";
        trade.outcome = "loss";
        return;
      }
      if (b.high >= tp) {
        trade.manual_exit_price = tp;
        trade.manual_hit_reason = "take_profit";
        trade.outcome = "win";
        return;
      }
    } else {
      if (b.high >= sl) {
        trade.manual_exit_price = sl;
        trade.manual_hit_reason = "stop_loss";
        trade.outcome = "loss";
        return;
      }
      if (b.low <= tp) {
        trade.manual_exit_price = tp;
        trade.manual_hit_reason = "take_profit";
        trade.outcome = "win";
        return;
      }
    }
  }

  trade.manual_exit_price = bars[bars.length - 1].close;
  trade.manual_hit_reason = "timeout";
  trade.outcome = direction === "long"
    ? (trade.manual_exit_price >= entry ? "win" : "loss")
    : (trade.manual_exit_price <= entry ? "win" : "loss");
}

async function captureCurrentScreenshot() {
  redrawOverlay();
  await new Promise((resolve) => requestAnimationFrame(resolve));
  await new Promise((resolve) => requestAnimationFrame(resolve));

  if (window.html2canvas) {
    const root = document.querySelector(".app-shell");
    if (root) {
      const canvas = await window.html2canvas(root, {
        backgroundColor: null,
        useCORS: true,
        logging: false,
        scale: Math.min(window.devicePixelRatio || 1, 2),
      });
      return {
        dataUrl: canvas.toDataURL("image/png"),
        width: canvas.width,
        height: canvas.height,
        captureMode: "screen_exact",
      };
    }
  }

  const chartCanvas = state.chart.takeScreenshot();
  const drawCanvas = document.getElementById("drawLayer");
  const out = document.createElement("canvas");
  out.width = chartCanvas.width;
  out.height = chartCanvas.height;
  const ctx = out.getContext("2d");
  ctx.drawImage(chartCanvas, 0, 0);
  ctx.drawImage(drawCanvas, 0, 0);
  return {
    dataUrl: out.toDataURL("image/png"),
    width: out.width,
    height: out.height,
    captureMode: "chart_composite",
  };
}

function buildChartStateSnapshot(captureSize = null) {
  if (!state.chart || !state.candles?.length || !state.session) return null;
  const visible = state.chart.timeScale().getVisibleRange();
  const from = visible?.from ?? state.candles[0].time;
  const to = visible?.to ?? state.candles[state.candles.length - 1].time;
  const inRange = state.candles.filter((c) => c.time >= from && c.time <= to);
  const lows = inRange.map((c) => c.low);
  const highs = inRange.map((c) => c.high);
  const priceMin = lows.length ? Math.min(...lows) : null;
  const priceMax = highs.length ? Math.max(...highs) : null;
  return {
    symbol: state.session.symbol,
    timeframe: state.session.timeframe,
    asset_type: state.session.asset_type,
    visible_range: { from, to },
    price_range: { min: priceMin, max: priceMax },
    capture_size: captureSize || null,
  };
}

function buildDrawingSnapshot(tradeId = null) {
  if (!state.session?.drawings?.length) return [];
  const list = tradeId
    ? state.session.drawings.filter((d) => !d.trade_id || d.trade_id === tradeId)
    : state.session.drawings;
  return list.map((d) => ({
    id: d.id,
    type: d.type,
    points: (d.points || []).map((p) => ({ time: Number(p.time), price: Number(p.price) })),
    style: d.style || {},
    note: d.note || "",
    side: d.side || null,
    trade_id: d.trade_id || null,
    rr: d.rr || null,
    timeframe_created: d.timeframe_created || null,
  }));
}

function buildTradeSnapshot(tradeId = null) {
  if (!state.session?.trades?.length) return {};
  const t = tradeId
    ? state.session.trades.find((x) => x.id === tradeId)
    : state.session.trades.find((x) => x.id === state.activeTradeId);
  if (!t) return {};
  return {
    id: t.id,
    source: t.source,
    status: t.status,
    outcome: t.outcome,
    strategy_direction: t.direction,
    manual_direction: t.manual_direction ?? null,
    strategy_entry: t.entry_price,
    strategy_sl: t.stop_loss,
    strategy_tp: t.take_profit,
    manual_entry: t.manual_entry_price ?? null,
    manual_sl: t.manual_stop_loss ?? null,
    manual_tp: t.manual_take_profit ?? null,
    entry_time: t.entry_time,
    exit_time: t.manual_exit_time ?? t.exit_time ?? null,
    notes: t.notes || "",
  };
}

async function saveArtifact({ note = "", tradeId = null, tag = "manual_review" } = {}) {
  if (!state.sessionId) return;
  const shot = await captureCurrentScreenshot();
  const screenshot_base64 = shot.dataUrl;
  await api(`/api/sessions/${state.sessionId}/artifacts/screenshot`, {
    method: "POST",
    body: JSON.stringify({
      screenshot_base64,
      note,
      trade_id: tradeId,
      tag,
      capture_mode: shot.captureMode || "chart_composite",
      chart_state: buildChartStateSnapshot({ width: shot.width, height: shot.height }),
      drawing_snapshot: buildDrawingSnapshot(tradeId),
      trade_snapshot: buildTradeSnapshot(tradeId),
      indicator_state: buildIndicatorSnapshot(tradeId),
    }),
  });
}

function computeTechState(candles) {
  const ema = (arr, period) => {
    const out = [];
    if (!arr.length) return out;
    const k = 2 / (period + 1);
    let prev = arr[0].close;
    for (const c of arr) {
      prev = (c.close * k) + (prev * (1 - k));
      out.push({ time: c.time, value: prev });
    }
    return out;
  };
  const ema20 = ema(candles, 20);
  const ema50 = ema(candles, 50);
  const vwap = computeSessionVwap(candles);
  const rsi14 = [];
  const atr14 = [];
  let avgGain = 0;
  let avgLoss = 0;
  let prevClose = candles[0]?.close ?? 0;
  let prevAtr = 0;
  for (let i = 0; i < candles.length; i += 1) {
    const c = candles[i];
    const ch = c.close - prevClose;
    const gain = Math.max(0, ch);
    const loss = Math.max(0, -ch);
    if (i === 0) {
      avgGain = gain;
      avgLoss = loss;
    } else {
      avgGain = (avgGain * 13 + gain) / 14;
      avgLoss = (avgLoss * 13 + loss) / 14;
    }
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    const rsi = 100 - (100 / (1 + rs));
    rsi14.push({ time: c.time, value: rsi });
    const tr = i === 0
      ? (c.high - c.low)
      : Math.max(c.high - c.low, Math.abs(c.high - prevClose), Math.abs(c.low - prevClose));
    prevAtr = i === 0 ? tr : ((prevAtr * 13 + tr) / 14);
    atr14.push({ time: c.time, value: prevAtr });
    prevClose = c.close;
  }
  const byTime = {};
  for (let i = 0; i < candles.length; i += 1) {
    byTime[candles[i].time] = {
      ema20: ema20[i]?.value ?? null,
      ema50: ema50[i]?.value ?? null,
      vwap: vwap[i]?.value ?? null,
      rsi14: rsi14[i]?.value ?? null,
      atr14: atr14[i]?.value ?? null,
      close: candles[i].close,
    };
  }
  return { ema20, ema50, vwap, rsi14, atr14, byTime };
}

function indicatorStateAt(time) {
  if (!state.candles?.length) return null;
  let chosen = state.candles[0];
  for (const c of state.candles) {
    if (c.time <= time) chosen = c;
    else break;
  }
  return state.tech.byTime[chosen.time] || null;
}

function buildIndicatorSnapshot(tradeId = null) {
  const trade = tradeId
    ? state.session?.trades?.find((t) => t.id === tradeId)
    : (state.activeTradeId ? state.session?.trades?.find((t) => t.id === state.activeTradeId) : null);
  const vr = state.chart?.timeScale?.().getVisibleRange?.();
  const nowTs = vr ? Number(vr.to) : (state.candles[state.candles.length - 1]?.time || 0);
  const entryTs = trade ? Number(trade.entry_time || 0) : 0;
  return {
    at_entry: entryTs ? indicatorStateAt(entryTs) : null,
    at_capture: indicatorStateAt(nowTs),
  };
}

function timeToX(time, clamp = false) {
  let x = state.chart.timeScale().timeToCoordinate(time);
  if (x != null || !clamp) return x;
  const vr = state.chart.timeScale().getVisibleRange();
  const canvas = document.getElementById("drawLayer");
  if (!vr || !canvas) return null;
  if (time < vr.from) return 0;
  if (time > vr.to) return canvas.width;
  return null;
}

function priceToY(price, clamp = false) {
  let y = state.series.priceToCoordinate(price);
  if (y != null || !clamp) return y;
  const canvas = document.getElementById("drawLayer");
  if (!canvas) return null;
  const topPrice = state.series.coordinateToPrice(0);
  const bottomPrice = state.series.coordinateToPrice(canvas.height);
  if (topPrice == null || bottomPrice == null) return null;
  if (price > topPrice) return 0;
  if (price < bottomPrice) return canvas.height;
  return null;
}

function pointToXY(p, clamp = false) {
  const x = timeToX(p.time, clamp);
  const y = priceToY(p.price, clamp);
  if (x == null || y == null) return null;
  return { x, y };
}

function drawPriceTag(ctx, { x, y, text, bg, fg = "#ffffff", align = "right" }) {
  ctx.save();
  ctx.font = "bold 10px sans-serif";
  const padX = 6;
  const width = ctx.measureText(text).width + padX * 2;
  const height = 20;
  const boxX = align === "right" ? x - width : x;
  const boxY = y - height / 2;
  ctx.fillStyle = bg;
  ctx.fillRect(boxX, boxY, width, height);
  ctx.fillStyle = fg;
  ctx.fillText(text, boxX + padX, boxY + 13);
  ctx.restore();
}

function redrawOverlay() {
  if (!state.ctx) return;
  const c = document.getElementById("drawLayer");
  state.ctx.clearRect(0, 0, c.width, c.height);
  if (!state.session) return;

  // Optional ICT overlay layer (behind manual drawings).
  if (state.showIct && state.ictOverlay) {
    for (const f of state.ictOverlay.fvgs || []) {
      const x = state.chart.timeScale().timeToCoordinate(f.time);
      const yTop = state.series.priceToCoordinate(f.top);
      const yBot = state.series.priceToCoordinate(f.bottom);
      if (x == null || yTop == null || yBot == null) continue;
      state.ctx.globalAlpha = 0.10;
      state.ctx.fillStyle = f.type === "bullish" ? "#43aa8b" : "#f8961e";
      state.ctx.fillRect(x, Math.min(yTop, yBot), 120, Math.abs(yTop - yBot));
      state.ctx.globalAlpha = 1.0;
    }
    for (const o of state.ictOverlay.order_blocks || []) {
      const x = state.chart.timeScale().timeToCoordinate(o.time);
      const yTop = state.series.priceToCoordinate(o.top);
      const yBot = state.series.priceToCoordinate(o.bottom);
      if (x == null || yTop == null || yBot == null) continue;
      state.ctx.globalAlpha = 0.08;
      state.ctx.fillStyle = o.type === "bullish" ? "#4cc9f0" : "#ef476f";
      state.ctx.fillRect(x, Math.min(yTop, yBot), 90, Math.abs(yTop - yBot));
      state.ctx.globalAlpha = 1.0;
    }
    for (const l of state.ictOverlay.liquidity || []) {
      if (l.swept) continue;
      const y = state.series.priceToCoordinate(l.price);
      if (y == null) continue;
      state.ctx.setLineDash([4, 4]);
      state.ctx.strokeStyle = "#9d4edd";
      state.ctx.lineWidth = 1;
      state.ctx.beginPath();
      state.ctx.moveTo(0, y);
      state.ctx.lineTo(c.width, y);
      state.ctx.stroke();
      state.ctx.setLineDash([]);
    }
    for (const b of state.ictOverlay.structure_breaks || []) {
      const x = state.chart.timeScale().timeToCoordinate(b.time);
      const y = state.series.priceToCoordinate(b.price);
      if (x == null || y == null) continue;
      const label = b.type || "BRK";
      const w = 34;
      const h = 14;
      state.ctx.globalAlpha = 0.92;
      state.ctx.fillStyle = b.direction === "bullish" ? "#2b9348" : "#c1121f";
      state.ctx.fillRect(x - w / 2, y - h - 4, w, h);
      state.ctx.fillStyle = "#fff";
      state.ctx.font = "10px sans-serif";
      state.ctx.fillText(label, x - w / 2 + 4, y - 8);
      state.ctx.globalAlpha = 1.0;
    }
  }

  for (const d of state.session.drawings) {
    const isSelected = d.id === state.selectedId;
    const pts = d.points.map((pt) => pointToXY(pt, true));
    if (pts.some(p => !p)) continue;

    state.ctx.lineWidth = isSelected ? 2 : 1.5;
    state.ctx.strokeStyle = isSelected ? "#fff" : "#2962ff";
    state.ctx.fillStyle = isSelected ? "#fff" : "#2962ff";

    if (d.type === "trendline") {
      const stroke = d.style?.stroke || (isSelected ? "#fff" : "#2962ff");
      state.ctx.strokeStyle = stroke;
      state.ctx.beginPath();
      state.ctx.moveTo(pts[0].x, pts[0].y);
      state.ctx.lineTo(pts[1].x, pts[1].y);
      state.ctx.stroke();
      if (d.style?.arrow_head) {
        const angle = Math.atan2(pts[1].y - pts[0].y, pts[1].x - pts[0].x);
        const arrowLen = 10;
        const spread = Math.PI / 7;
        state.ctx.beginPath();
        state.ctx.moveTo(pts[1].x, pts[1].y);
        state.ctx.lineTo(
          pts[1].x - arrowLen * Math.cos(angle - spread),
          pts[1].y - arrowLen * Math.sin(angle - spread)
        );
        state.ctx.moveTo(pts[1].x, pts[1].y);
        state.ctx.lineTo(
          pts[1].x - arrowLen * Math.cos(angle + spread),
          pts[1].y - arrowLen * Math.sin(angle + spread)
        );
        state.ctx.stroke();
      }
      if (d.note) {
        state.ctx.font = "bold 10px sans-serif";
        const text = d.note;
        const padX = 5;
        const w = state.ctx.measureText(text).width + padX * 2;
        const h = 14;
        const bx = pts[1].x + 6;
        const by = pts[1].y - h - 6;
        state.ctx.fillStyle = d.style?.label_bg || stroke;
        state.ctx.fillRect(bx, by, w, h);
        state.ctx.fillStyle = d.style?.label_fg || "#ffffff";
        state.ctx.fillText(text, bx + padX, by + 10);
      }
    } else if (d.type === "hline") {
      state.ctx.beginPath();
      state.ctx.moveTo(0, pts[0].y);
      state.ctx.lineTo(c.width, pts[0].y);
      state.ctx.stroke();
      if (d.note) {
        state.ctx.font = "bold 10px sans-serif";
        const text = d.note;
        const padX = 5;
        const w = state.ctx.measureText(text).width + padX * 2;
        const h = 14;
        const bx = 8;
        const by = pts[0].y - h - 2;
        state.ctx.fillStyle = d.style?.label_bg || "#2a2e39";
        state.ctx.fillRect(bx, by, w, h);
        state.ctx.fillStyle = d.style?.label_fg || "#ffffff";
        state.ctx.fillText(text, bx + padX, by + 10);
      }
    } else if (d.type === "rect") {
      const fill = d.style?.fill || "rgba(41,98,255,0.15)";
      const stroke = d.style?.stroke || "#2962ff";
      state.ctx.globalAlpha = 0.15;
      state.ctx.fillStyle = fill;
      state.ctx.fillRect(Math.min(pts[0].x, pts[1].x), Math.min(pts[0].y, pts[1].y), Math.abs(pts[0].x - pts[1].x), Math.abs(pts[0].y - pts[1].y));
      state.ctx.globalAlpha = 1.0;
      state.ctx.strokeStyle = stroke;
      state.ctx.strokeRect(Math.min(pts[0].x, pts[1].x), Math.min(pts[0].y, pts[1].y), Math.abs(pts[0].x - pts[1].x), Math.abs(pts[0].y - pts[1].y));
      if (d.note) {
        state.ctx.font = "11px sans-serif";
        state.ctx.fillStyle = "#d1d4dc";
        state.ctx.fillText(d.note, Math.min(pts[0].x, pts[1].x) + 4, Math.min(pts[0].y, pts[1].y) + 14);
      }
    } else if (d.type === "text") {
      const text = d.note || "note";
      state.ctx.font = "12px sans-serif";
      const tx = pts[0].x + 4;
      const ty = pts[0].y - 4;
      if (d.style?.label_bg) {
        const padX = 5;
        const w = state.ctx.measureText(text).width + padX * 2;
        const h = 16;
        state.ctx.fillStyle = d.style.label_bg;
        state.ctx.fillRect(tx - 3, ty - 12, w, h);
      }
      state.ctx.fillStyle = d.style?.label_fg || (isSelected ? "#fff" : "#d1d4dc");
      state.ctx.fillText(text, tx, ty);
    } else if (d.type === "riskreward") {
      const rr = rrFromDrawing(d);
      if (!rr) continue;
      const xStart = timeToX(rr.start_time, true);
      const xEnd = timeToX(rr.end_time, true);
      const yEntry = state.series.priceToCoordinate(rr.entry_price);
      const yStop = state.series.priceToCoordinate(rr.stop_price);
      const yTP = state.series.priceToCoordinate(rr.take_price);
      if (xStart == null || xEnd == null || yEntry == null || yStop == null || yTP == null) continue;
      const width = Math.max(8, Math.abs(xEnd - xStart));
      const leftX = Math.min(xStart, xEnd);
      
      // Risk Box
      state.ctx.globalAlpha = RR_FILL_ALPHA_DRAWING;
      state.ctx.fillStyle = "#f23645";
      state.ctx.fillRect(leftX, Math.min(yEntry, yStop), width, Math.abs(yEntry - yStop));
      // Reward Box
      state.ctx.fillStyle = "#089981";
      state.ctx.fillRect(leftX, Math.min(yEntry, yTP), width, Math.abs(yEntry - yTP));
      state.ctx.globalAlpha = 1.0;
      
      // Labels
      state.ctx.font = "bold 10px sans-serif";
      state.ctx.fillStyle = "#fff";
      const entryPrice = rr.entry_price;
      const riskAbs = Math.abs(entryPrice - rr.stop_price);
      const rewardAbs = Math.abs(rr.take_price - entryPrice);
      const riskPct = entryPrice ? (riskAbs / entryPrice) * 100 : 0;
      const rewardPct = entryPrice ? (rewardAbs / entryPrice) * 100 : 0;
      const rrRatio = riskAbs > 0 ? rewardAbs / riskAbs : 0;
      state.ctx.strokeStyle = "rgba(255,255,255,0.75)";
      state.ctx.lineWidth = 1;
      state.ctx.beginPath();
      state.ctx.moveTo(leftX, yEntry);
      state.ctx.lineTo(leftX + width, yEntry);
      state.ctx.stroke();

      if (isSelected) {
        state.ctx.setLineDash([4, 4]);
        state.ctx.strokeStyle = "rgba(255,255,255,0.25)";
        state.ctx.beginPath();
        state.ctx.moveTo(leftX + width * 0.5, yEntry);
        state.ctx.lineTo(leftX + width * 0.85, yTP);
        state.ctx.stroke();
        state.ctx.setLineDash([]);

        drawPriceTag(state.ctx, {
          x: leftX + width + 8,
          y: yStop - 2,
          text: `Stop: ${riskAbs.toFixed(1)} (${riskPct.toFixed(2)}%)`,
          bg: "#b86ad9",
          align: "left",
        });
        drawPriceTag(state.ctx, {
          x: leftX + width + 8,
          y: yTP + 2,
          text: `Target: ${rewardAbs.toFixed(1)} (${rewardPct.toFixed(2)}%)`,
          bg: "#f39a2d",
          align: "left",
        });
        drawPriceTag(state.ctx, {
          x: leftX + width + 8,
          y: yEntry,
          text: `RR ${rrRatio.toFixed(2)}`,
          bg: "#2a2e39",
          align: "left",
        });

        const handles = getRiskRewardHandlePoints(rr);
        for (const h of handles) {
          state.ctx.fillStyle = "#131722";
          state.ctx.strokeStyle = "#2f73ff";
          state.ctx.lineWidth = 2;
          state.ctx.beginPath();
          state.ctx.rect(h.x - 6, h.y - 6, 12, 12);
          state.ctx.fill();
          state.ctx.stroke();
        }
      }
    }

    if (isSelected && d.type !== "riskreward") {
      pts.forEach(p => {
        state.ctx.beginPath();
        state.ctx.arc(p.x, p.y, 4, 0, Math.PI*2);
        state.ctx.fillStyle = "#fff";
        state.ctx.fill();
        state.ctx.strokeStyle = "#2962ff";
        state.ctx.stroke();
      });
    }
  }

  // Trades
  for (const t of state.session.trades) {
    const hasLinkedRR = tradeHasLinkedRiskReward(t.id);
    const entryTime = t.entry_time;
    const entryPrice = t.manual_entry_price ?? t.entry_price;
    const sl = t.manual_stop_loss ?? t.stop_loss;
    const tp = t.manual_take_profit ?? t.take_profit;
    const direction = t.manual_direction ?? t.direction;
    const x = state.chart.timeScale().timeToCoordinate(entryTime);
    const y = state.series.priceToCoordinate(entryPrice);
    if (x == null || y == null) continue;
    if (hasLinkedRR) continue;
    state.ctx.fillStyle = direction === "long" ? "#089981" : "#f23645";
    state.ctx.beginPath();
    state.ctx.arc(x, y, 6, 0, Math.PI * 2);
    state.ctx.fill();
    state.ctx.strokeStyle = "#fff";
    state.ctx.lineWidth = 1;
    state.ctx.stroke();

    if (t.id === state.activeTradeId) {
      state.ctx.beginPath();
      state.ctx.arc(x, y, 10, 0, Math.PI * 2);
      state.ctx.strokeStyle = "#2962ff";
      state.ctx.lineWidth = 2;
      state.ctx.stroke();
      state.ctx.font = "bold 11px sans-serif";
      state.ctx.fillStyle = "#fff";
      state.ctx.fillText("selected", x + 10, y - 10);
    }

    const endTime = t.manual_exit_time ?? t.exit_time;
    const exitPrice = t.manual_exit_price ?? t.exit_price;
    const x2 = endTime ? state.chart.timeScale().timeToCoordinate(endTime) : null;
    const y2 = exitPrice != null ? state.series.priceToCoordinate(exitPrice) : null;
    if (x2 != null && y2 != null) {
      state.ctx.beginPath();
      state.ctx.moveTo(x, y);
      state.ctx.lineTo(x2, y2);
      state.ctx.strokeStyle = t.manual_hit_reason === "take_profit" ? "#089981" : (t.manual_hit_reason === "stop_loss" ? "#f23645" : "#787b86");
      state.ctx.lineWidth = 1.2;
      state.ctx.stroke();
    }

    // Subtle position visualization for non-selected strategy/manual trades.
    if (t.id !== state.activeTradeId && sl != null && tp != null) {
      const ySl = state.series.priceToCoordinate(sl);
      const yTp = state.series.priceToCoordinate(tp);
      const xEnd = x2 ?? (x + 18);
      if (ySl != null && yTp != null) {
        const left = Math.min(x, xEnd);
        const width = Math.max(4, Math.abs(xEnd - x));
        state.ctx.globalAlpha = RR_FILL_ALPHA_UNSELECTED;
        state.ctx.fillStyle = "#f23645";
        state.ctx.fillRect(left, Math.min(y, ySl), width, Math.abs(y - ySl));
        state.ctx.fillStyle = "#089981";
        state.ctx.fillRect(left, Math.min(y, yTp), width, Math.abs(y - yTp));
        state.ctx.globalAlpha = 1.0;
      }
    }

    // Show full position box for selected trade (TV-like visual context).
    if (t.id === state.activeTradeId && sl != null && tp != null) {
      const ySl = state.series.priceToCoordinate(sl);
      const yTp = state.series.priceToCoordinate(tp);
      const xEnd = x2 ?? (x + 140);
      if (ySl != null && yTp != null) {
        const left = Math.min(x, xEnd);
        const width = Math.max(10, Math.abs(xEnd - x));
        state.ctx.globalAlpha = RR_FILL_ALPHA_SELECTED;
        state.ctx.fillStyle = "#f23645";
        state.ctx.fillRect(left, Math.min(y, ySl), width, Math.abs(y - ySl));
        state.ctx.fillStyle = "#089981";
        state.ctx.fillRect(left, Math.min(y, yTp), width, Math.abs(y - yTp));
        state.ctx.globalAlpha = 1.0;
      }
    }
  }
}

async function loadSymbols() {
  const resp = await api("/api/symbols");
  state.symbols = resp.symbols || [];
  const symbolSelect = document.getElementById("symbolSelect");
  symbolSelect.innerHTML = "";
  let firstValue = "";
  for (const s of state.symbols) {
    const opt = document.createElement("option");
    opt.value = `${s.asset_type}|${s.symbol}`;
    opt.textContent = `${s.symbol}`;
    symbolSelect.appendChild(opt);
    if (!firstValue) firstValue = opt.value;
  }
  if (firstValue) symbolSelect.value = firstValue;
  symbolSelect.addEventListener("change", updateTfOptions);
  updateTfOptions();
}

async function loadBacktests() {
  const resp = await api("/api/backtests");
  state.backtests = resp.backtests || [];
  const sel = document.getElementById("backtestSelect");
  sel.innerHTML = `<option value="">Select Backtest...</option>`;
  for (const bt of state.backtests) {
    const opt = document.createElement("option");
    opt.value = bt.id;
    opt.textContent = `${bt.name}`;
    opt.dataset.symbol = bt.symbol || "";
    opt.dataset.timeframe = bt.timeframe || "";
    opt.dataset.assetType = bt.asset_type || "";
    sel.appendChild(opt);
  }
}

function selectedSymbolObj() {
  const val = document.getElementById("symbolSelect").value;
  if (!val) return null;
  const [assetType, symbol] = val.split("|");
  return state.symbols.find((s) => s.asset_type === assetType && s.symbol === symbol);
}

function queryParam(name) {
  const url = new URL(window.location.href);
  return url.searchParams.get(name);
}

function updateTfOptions() {
  const obj = selectedSymbolObj();
  const tf = document.getElementById("tfSelect");
  tf.innerHTML = "";
  for (const t of obj?.timeframes || ["1", "5", "15", "30"]) {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    tf.appendChild(opt);
  }
}

function pickRandomBacktestInterval(candles) {
  if (!candles?.length) return null;
  const first = candles[0].time;
  const last = candles[candles.length - 1].time;
  if ((last - first) <= TWO_MONTHS_SEC) return { from: first, to: last };
  const latestStart = last - TWO_MONTHS_SEC;
  const candidates = candles.filter((c) => c.time <= latestStart);
  const picked = candidates[Math.floor(Math.random() * candidates.length)] || candles[0];
  return { from: picked.time, to: picked.time + TWO_MONTHS_SEC };
}

function computeIntervalCandles(candles, interval) {
  if (!interval) return candles.slice();
  return candles.filter((c) => c.time >= interval.from && c.time <= interval.to);
}

function lastBarIndexAtTime(candles, time) {
  if (!candles?.length) return -1;
  let idx = 0;
  for (let i = 0; i < candles.length; i += 1) {
    if (candles[i].time <= time) idx = i;
    else break;
  }
  return idx;
}

function updatePlaybackStatus() {
  const el = document.getElementById("playbackStatus");
  if (!el) return;
  if (state.session?.metadata?.playback_mode === "full") {
    el.textContent = "Full Chart";
    return;
  }
  const total = state.intervalCandles.length;
  if (!total) {
    el.textContent = "-";
    return;
  }
  const idx = lastBarIndexAtTime(state.intervalCandles, state.playback.currentTime ?? state.intervalCandles[0].time);
  el.textContent = `${Math.max(1, idx + 1)}/${total}`;
}

function applyPlaybackWindow({ fit = false } = {}) {
  if (!state.intervalCandles.length) {
    state.candles = [];
    state.series.setData([]);
    return;
  }
  if (state.session?.metadata?.playback_mode === "full") {
    state.candles = state.intervalCandles.slice();
    state.series.setData(state.candles);
    if (state.showTech) {
      state.techSeries.ema20.setData(state.tech.ema20);
      state.techSeries.ema50.setData([]);
      state.techSeries.vwap.setData(state.tech.vwap);
    }
    if (fit) state.chart.timeScale().fitContent();
    redrawOverlay();
    updatePlaybackStatus();
    return;
  }
  const cur = state.playback.currentTime ?? state.intervalCandles[Math.min(120, state.intervalCandles.length - 1)].time;
  const idx = lastBarIndexAtTime(state.intervalCandles, cur);
  const reveal = state.intervalCandles.slice(0, Math.max(2, idx + 1));
  state.candles = reveal;
  state.series.setData(reveal);
  if (state.showTech) {
    state.techSeries.ema20.setData(state.tech.ema20.filter((x) => x.time <= reveal[reveal.length - 1].time));
    state.techSeries.ema50.setData([]);
    state.techSeries.vwap.setData(state.tech.vwap.filter((x) => x.time <= reveal[reveal.length - 1].time));
  }
  if (fit) state.chart.timeScale().fitContent();
  redrawOverlay();
  updatePlaybackStatus();
}

function stepPlayback(byBars = 1) {
  if (!state.intervalCandles.length) return;
  const curIdx = lastBarIndexAtTime(state.intervalCandles, state.playback.currentTime ?? state.intervalCandles[0].time);
  const nextIdx = Math.min(state.intervalCandles.length - 1, curIdx + Math.max(1, byBars));
  state.playback.currentTime = state.intervalCandles[nextIdx].time;
  if (state.session) {
    state.session.metadata = state.session.metadata || {};
    state.session.metadata.playback_current_time = state.playback.currentTime;
  }
  applyPlaybackWindow();
  if (nextIdx >= state.intervalCandles.length - 1) {
    togglePlayback(false);
  }
}

function togglePlayback(force = null) {
  if (state.session?.metadata?.playback_mode === "full") return;
  const next = force == null ? !state.playback.isPlaying : !!force;
  state.playback.isPlaying = next;
  const btn = document.getElementById("playToggleBtn");
  if (btn) btn.textContent = next ? "Pause" : "Play";
  if (state.playback.timer) {
    clearInterval(state.playback.timer);
    state.playback.timer = null;
  }
  if (next) {
    state.playback.timer = setInterval(() => stepPlayback(1), 350);
  }
}

function generatedStructureLabelId({ symbol, timeframe, label, time, price }) {
  // Stable per symbol/timeframe + swing identity.
  // Use rounded price to reduce floating inconsistencies.
  const rp = Math.round(Number(price) * 1000000000) / 1000000000;
  return `gen-structure-${symbol}-${timeframe}-${label}-${time}-${rp}`;
}

function syncStructureLabelDrawingsFromIct() {
  if (!state.session) return;
  if (!state.ictOverlay) return;

  const swingLabels = state.ictOverlay.swing_labels || [];
  const symbol = state.session.symbol;
  const timeframe = state.session.timeframe;

  // Remove previously generated label drawings.
  state.session.drawings = (state.session.drawings || []).filter((d) => {
    return !(d?.style?.generated_structure_labels === true);
  });

  const labelColorByLabel = {
    HH: { label_bg: "#1f7a1f", label_fg: "#ffffff" },
    HL: { label_bg: "#2b9348", label_fg: "#ffffff" },
    LL: { label_bg: "#7a1f1f", label_fg: "#ffffff" },
    LH: { label_bg: "#c1121f", label_fg: "#ffffff" },
  };

  for (const item of swingLabels) {
    const time = Number(item.time);
    const price = Number(item.price);
    const label = String(item.label || "");
    if (!Number.isFinite(time) || !Number.isFinite(price) || !label) continue;

    const id = generatedStructureLabelId({ symbol, timeframe, label, time, price });

    const style = {
      generated_structure_labels: true,
      label_bg: labelColorByLabel[label]?.label_bg || "#2a2e39",
      label_fg: labelColorByLabel[label]?.label_fg || "#d1d4dc",
    };

    state.session.drawings.push({
      id,
      type: "text",
      points: [{ time, price }],
      style,
      timeframe_created: timeframe,
      note: label,
      side: null,
      trade_id: null,
      rr: null,
    });
  }
}

async function loadCandles(symbol, timeframe, assetType) {
  const data = await api(`/api/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&asset_type=${encodeURIComponent(assetType)}&limit=140000`);
  state.fullCandles = data.candles || [];
  const md = state.session?.metadata || {};

  let metadataChanged = false;

  let interval = md.backtest_interval || null;
  if (md.playback_mode === "full") {
    interval = state.fullCandles.length
      ? { from: state.fullCandles[0].time, to: state.fullCandles[state.fullCandles.length - 1].time }
      : null;
  } else if (!interval || interval.from == null || interval.to == null) {
    interval = pickRandomBacktestInterval(state.fullCandles);
    if (state.session) {
      state.session.metadata = state.session.metadata || {};
      state.session.metadata.backtest_interval = interval;
      state.session.metadata.interval_randomized = true;
      metadataChanged = true;
    }
  }
  state.playback.interval = interval;
  state.intervalCandles = computeIntervalCandles(state.fullCandles, interval);
  state.tech = computeTechState(state.intervalCandles);
  if (md.playback_mode === "full") {
    state.playback.currentTime = state.intervalCandles[state.intervalCandles.length - 1]?.time ?? null;
  } else if (md.playback_current_time) {
    state.playback.currentTime = Number(md.playback_current_time);
  } else if (state.intervalCandles.length) {
    state.playback.currentTime = state.intervalCandles[Math.min(120, state.intervalCandles.length - 1)].time;
    if (state.session) {
      state.session.metadata = state.session.metadata || {};
      state.session.metadata.playback_current_time = state.playback.currentTime;
      metadataChanged = true;
    }
  } else {
    state.playback.currentTime = null;
  }
  state.techSeries.ema20.setData(state.tech.ema20);
  state.techSeries.ema50.setData([]);
  state.techSeries.vwap.setData(state.tech.vwap);
  state.techSeries.ema20.applyOptions({ visible: !!state.showTech });
  state.techSeries.ema50.applyOptions({ visible: false });
  state.techSeries.vwap.applyOptions({ visible: !!state.showTech });
  if (state.showIct) {
    try {
      state.ictOverlay = await api(`/api/ict-overlay?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&asset_type=${encodeURIComponent(assetType)}&limit=1200`);
    } catch (e) {
      console.warn("ICT overlay load failed", e);
      state.ictOverlay = { fvgs: [], order_blocks: [], liquidity: [], swing_labels: [] };
    }
  } else {
    state.ictOverlay = { fvgs: [], order_blocks: [], liquidity: [], swing_labels: [] };
  }

  if (state.showIct) {
    // Convert HH/HL/LL/LH into persisted editable drawings.
    syncStructureLabelDrawingsFromIct();
  } else if (state.session) {
    // Ensure generated labels are removed when ICT is turned off.
    state.session.drawings = (state.session.drawings || []).filter((d) => {
      return !(d?.style?.generated_structure_labels === true);
    });
  }

  applyPlaybackWindow({ fit: true });

  syncPlaybackUi();
  if (metadataChanged) scheduleSave();
}

function renderTradeList() {
  const el = document.getElementById("tradeList");
  el.innerHTML = "";
  if (!state.session) return;
  document.getElementById("tradeCount").textContent = state.session.trades.length;
  state.session.trades.forEach((t) => {
    const div = document.createElement("div");
    div.className = `trade-item ${state.activeTradeId === t.id ? "active" : ""}`;
    const entry = t.manual_entry_price ?? t.entry_price ?? 0;
    const dir = (t.manual_direction ?? t.direction ?? "").toUpperCase();
    const statusIcon = t.status === "done" ? '<i data-lucide="check-circle-2" style="color:#089981"></i>' : "";
    div.innerHTML = `
      <div class="status-icon">${statusIcon}</div>
      <div class="title"><strong>${dir}</strong> ${t.source}${t.manual_direction ? " (manual)" : ""}</div>
      <div class="meta">E: ${formatPrice(entry)}</div>
      <div class="meta">${new Date(t.entry_time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
    `;
    div.addEventListener("click", () => selectTrade(t.id));
    el.appendChild(div);
  });
  if (window.lucide) lucide.createIcons();
}

function selectTrade(tradeId) {
  state.activeTradeId = tradeId;
  state.selectedId = linkedRiskRewardDrawing(tradeId)?.id || null;
  const t = state.session.trades.find((x) => x.id === tradeId);
  if (!t) return;
  document.getElementById("tradeEditor").classList.remove("hidden");
  document.getElementById("editorTitle").textContent = `Trade ${tradeId.slice(0, 8)}`;
  document.getElementById("editDirection").value = t.manual_direction ?? t.direction;
  document.getElementById("editEntryPrice").value = t.manual_entry_price ?? t.entry_price ?? "";
  document.getElementById("editSL").value = t.manual_stop_loss ?? t.stop_loss ?? "";
  document.getElementById("editTP").value = t.manual_take_profit ?? t.take_profit ?? "";
  document.getElementById("editNotes").value = t.notes ?? "";
  const rr = Array.isArray(t.reason_tags) ? t.reason_tags : [];
  const pick = (prefix) => {
    const item = rr.find((x) => String(x).startsWith(prefix));
    return item ? String(item).slice(prefix.length) : "";
  };
  document.getElementById("editHtfBias").value = pick("htf_bias:");
  document.getElementById("editSessionTag").value = pick("session:");
  document.getElementById("editTriggerTag").value = pick("trigger:");
  document.getElementById("editInvalidatorTag").value = pick("invalidator:");
  document.getElementById("editSetupGrade").value = pick("setup_grade:");
  document.getElementById("editEntryModel").value = pick("entry_model:");
  document.getElementById("editTargetModel").value = pick("target_model:");
  document.getElementById("editWhyValid").value = pick("why_valid:");
  document.getElementById("directionSnapshot").innerHTML = `
    <div class="direction-pill">Strategy: <strong>${(t.direction || "-").toUpperCase()}</strong></div>
    <div class="direction-pill">Manual: <strong>${(t.manual_direction || t.direction || "-").toUpperCase()}</strong></div>
  `;
  // Bring selected trade into view on chart.
  const focusTime = t.entry_time;
  if (focusTime) {
    state.chart.timeScale().setVisibleRange({
      from: focusTime - 60 * 90,
      to: focusTime + 60 * 180,
    });
  }
  renderTradeList();
  redrawOverlay();
}

function updateActiveTrade(markDone = false, outcome = null) {
  const t = state.session.trades.find((x) => x.id === state.activeTradeId);
  if (!t) return;
  t.manual_direction = document.getElementById("editDirection").value;
  t.manual_entry_price = Number(document.getElementById("editEntryPrice").value || t.entry_price || 0);
  t.manual_stop_loss = Number(document.getElementById("editSL").value || 0) || null;
  t.manual_take_profit = Number(document.getElementById("editTP").value || 0) || null;
  t.notes = document.getElementById("editNotes").value;
  const tags = [];
  const htf = document.getElementById("editHtfBias").value;
  const session = document.getElementById("editSessionTag").value;
  const trigger = document.getElementById("editTriggerTag").value;
  const invalid = document.getElementById("editInvalidatorTag").value;
  const setupGrade = document.getElementById("editSetupGrade").value;
  const entryModel = document.getElementById("editEntryModel").value;
  const targetModel = document.getElementById("editTargetModel").value;
  const whyValid = document.getElementById("editWhyValid").value;
  if (htf) tags.push(`htf_bias:${htf}`);
  if (session) tags.push(`session:${session}`);
  if (trigger) tags.push(`trigger:${trigger}`);
  if (invalid) tags.push(`invalidator:${invalid}`);
  if (setupGrade) tags.push(`setup_grade:${setupGrade}`);
  if (entryModel) tags.push(`entry_model:${entryModel}`);
  if (targetModel) tags.push(`target_model:${targetModel}`);
  if (whyValid) tags.push(`why_valid:${whyValid}`);
  t.reason_tags = tags;
  if (outcome) t.outcome = outcome;
  if (markDone) t.status = "done";
  evaluateTradeOutcomeFromPrice(t);
  const snap = document.getElementById("directionSnapshot");
  if (snap) {
    snap.innerHTML = `
      <div class="direction-pill">Strategy: <strong>${(t.direction || "-").toUpperCase()}</strong></div>
      <div class="direction-pill">Manual: <strong>${(t.manual_direction || t.direction || "-").toUpperCase()}</strong></div>
    `;
  }
  
  const entryLog = {
    time: Date.now(),
    action: markDone ? "corrected" : "edited",
    details: { entry: t.manual_entry_price, sl: t.manual_stop_loss, tp: t.manual_take_profit }
  };
  t.audit_trail = t.audit_trail || [];
  t.audit_trail.push(entryLog);

  renderTradeList();
  redrawOverlay();
  scheduleSave();

  if (markDone) {
    const note = prompt("Short correction note for screenshot log:", t.notes || "trade corrected") || "";
    saveArtifact({ note, tradeId: t.id, tag: "trade_corrected" }).catch(console.error);
    document.getElementById("tradeEditor").classList.add("hidden");
    state.activeTradeId = null;
    renderTradeList();
    redrawOverlay();
  }
}

function selectNextTrade() {
  if (!state.session?.trades?.length) return;
  let idx = state.session.trades.findIndex((x) => x.id === state.activeTradeId);
  idx = (idx + 1) % state.session.trades.length;
  selectTrade(state.session.trades[idx].id);
}

async function createSession() {
  const obj = selectedSymbolObj();
  if (!obj) return alert("Select a symbol first");
  let symbol = obj.symbol;
  let assetType = obj.asset_type;
  let timeframe = document.getElementById("tfSelect").value;
  const backtestId = document.getElementById("backtestSelect").value || null;
  const selectedBt = state.backtests.find((b) => b.id === backtestId);
  if (selectedBt && selectedBt.symbol) {
    symbol = selectedBt.symbol;
    timeframe = String(selectedBt.timeframe || timeframe);
    // best-effort infer asset type from current symbol catalog
    const symObj = state.symbols.find((s) => s.symbol === symbol) || null;
    assetType = selectedBt.asset_type || symObj?.asset_type || assetType;
    // Update selects so user sees the actual context.
    const symbolSelect = document.getElementById("symbolSelect");
    const targetVal = `${assetType}|${symbol}`;
    if ([...symbolSelect.options].some((o) => o.value === targetVal)) {
      symbolSelect.value = targetVal;
      updateTfOptions();
      const tfSelect = document.getElementById("tfSelect");
      if ([...tfSelect.options].some((o) => o.value === timeframe)) tfSelect.value = timeframe;
    }
  }
  state.assetType = assetType;
  const payload = await api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({
      symbol,
      asset_type: assetType,
      timeframe,
      name: `${symbol}-${timeframe} Review`,
      backtest_id: backtestId,
    }),
  });
  state.session = payload.session;
  state.sessionId = payload.session_id;
  buildToolbars();
  renderTradeList();
  await loadCandles(state.session.symbol, state.session.timeframe, state.session.asset_type);
}

async function loadExistingSession(sessionId) {
  const sess = await api(`/api/sessions/${sessionId}`);
  state.session = sess;
  state.sessionId = sess.id;
  state.showTech = !!sess.metadata?.show_tech;
  state.showIct = !!sess.metadata?.show_ict;
  const techToggle = document.getElementById("toggleTech");
  const ictToggle = document.getElementById("toggleIct");
  if (techToggle) techToggle.checked = state.showTech;
  if (ictToggle) ictToggle.checked = state.showIct;
  const symbolSelect = document.getElementById("symbolSelect");
  const targetVal = `${sess.asset_type}|${sess.symbol}`;
  if ([...symbolSelect.options].some((o) => o.value === targetVal)) {
    symbolSelect.value = targetVal;
    updateTfOptions();
  }
  const tfSelect = document.getElementById("tfSelect");
  if ([...tfSelect.options].some((o) => o.value === sess.timeframe)) {
    tfSelect.value = sess.timeframe;
  }
  state.assetType = sess.asset_type || "crypto";
  const repaired = repairMissingRiskRewardDrawings();
  buildToolbars();
  renderTradeList();
  await loadCandles(sess.symbol, sess.timeframe, sess.asset_type);
  if (repaired) {
    renderTradeList();
    redrawOverlay();
    scheduleSave();
  }
}

async function saveSession() {
  if (!state.sessionId || !state.session) return;
  const payloadJson = JSON.stringify(state.session);
  if (payloadJson === state.lastSavedJson && !state.saveDirty) return;
  state.saveDirty = false;
  state.saveInFlight = true;
  await api(`/api/sessions/${state.sessionId}`, {
    method: "PUT",
    body: payloadJson,
  });
  state.lastSavedJson = payloadJson;
  state.saveInFlight = false;
  if (state.saveQueued) {
    state.saveQueued = false;
    scheduleSave();
  }
}

function scheduleSave() {
  state.saveDirty = true;
  if (state.saveInFlight) {
    state.saveQueued = true;
    return;
  }
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(() => saveSession().catch((e) => {
    state.saveInFlight = false;
    console.error(e);
  }), 2200);
}

function bindEvents() {
  document.getElementById("newSessionBtn").addEventListener("click", () => createSession().catch(alert));
  document.getElementById("saveBtn").addEventListener("click", () => saveSession().then(() => alert("Saved!")).catch(alert));
  document.getElementById("closeEditor").addEventListener("click", () => {
    document.getElementById("tradeEditor").classList.add("hidden");
    state.activeTradeId = null;
    renderTradeList();
  });
  document.getElementById("tfSelect").addEventListener("change", async () => {
    if (!state.session) return;
    const obj = selectedSymbolObj();
    state.session.timeframe = document.getElementById("tfSelect").value;
    await loadCandles(obj.symbol, state.session.timeframe, obj.asset_type);
    scheduleSave();
  });
  document.getElementById("toggleIct").addEventListener("change", async (e) => {
    state.showIct = e.target.checked;
    if (state.session) {
      await loadCandles(state.session.symbol, state.session.timeframe, state.session.asset_type);
    } else {
      redrawOverlay();
    }
  });

  document.getElementById("toggleTech").addEventListener("change", (e) => {
    state.showTech = e.target.checked;
    if (state.techSeries.ema20 && state.techSeries.vwap) {
      state.techSeries.ema20.applyOptions({ visible: !!state.showTech });
      state.techSeries.ema50.applyOptions({ visible: false });
      state.techSeries.vwap.applyOptions({ visible: !!state.showTech });
    }
  });
  document.getElementById("playToggleBtn").addEventListener("click", () => togglePlayback());
  document.getElementById("step1Btn").addEventListener("click", () => {
    togglePlayback(false);
    stepPlayback(1);
  });
  document.getElementById("step5Btn").addEventListener("click", () => {
    togglePlayback(false);
    stepPlayback(5);
  });
  document.getElementById("markDoneBtn").addEventListener("click", () => updateActiveTrade(true, "corrected"));
  document.getElementById("skipTradeBtn").addEventListener("click", () => updateActiveTrade(true, "skip"));
  document.getElementById("nextTradeBtn").addEventListener("click", () => {
    const currentTradeId = state.activeTradeId;
    updateActiveTrade(false);
    if (currentTradeId) {
      saveArtifact({ note: "progress_snapshot", tradeId: currentTradeId, tag: "trade_progress" }).catch(console.error);
    }
    selectNextTrade();
  });
  document.getElementById("analyticsBtn").addEventListener("click", () => {
    if (state.sessionId) {
      window.location.href = `/analytics?session=${encodeURIComponent(state.sessionId)}`;
    } else {
      window.location.href = "/analytics";
    }
  });
  document.getElementById("signalsBtn").addEventListener("click", () => {
    const selectedBacktest = document.getElementById("backtestSelect").value;
    if (selectedBacktest) {
      window.location.href = `/signals?backtest=${encodeURIComponent(selectedBacktest)}`;
    } else {
      window.location.href = "/signals";
    }
  });
  document.getElementById("finishBtn").addEventListener("click", () => {
    if (!state.session) return;
    state.session.finished = true;
    const note = prompt("Final session note (saved with screenshot):", "Session finished") || "";
    saveArtifact({ note, tradeId: null, tag: "session_finished" })
      .then(() => saveSession())
      .then(() => alert("Analysis complete. Screenshot + note saved."))
      .catch(console.error);
  });

  document.querySelectorAll("[data-note-template]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const ta = document.getElementById("editNotes");
      const txt = btn.getAttribute("data-note-template") || "";
      if (!ta || !txt) return;
      const existing = (ta.value || "").trim();
      ta.value = existing ? `${existing}\n${txt}` : txt;
      if (state.activeTradeId) updateActiveTrade(false);
    });
  });
}

async function main() {
  initChart();
  buildToolbars();
  bindEvents();
  await loadSymbols();
  await loadBacktests();
  const sid = queryParam("session");
  if (sid) {
    await loadExistingSession(sid);
  }
  syncPlaybackUi();
}

main().catch(console.error);
