/**
 * Drawing Engine for Trading Journal
 * Ported and refined from Pine Review App logic.
 * Handles: Canvas Overlay, Magnet Snapping, SMC/ICT Drawings, Risk/Reward Tool.
 */

class DrawingEngine {
  constructor(chart, series, container, canvas) {
    this.chart = chart;
    this.series = series;
    this.container = container;
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");

    this.state = {
      drawings: [],
      tradePanes: [],  // { entryTime, endTime, entry, sl, tp, side }
      currentTool: "cursor",
      selectedId: null,
      selectedIds: [],
      drawingDraft: null,
      dragging: null, // {id, pointIdx, offset}
      lasso: null, // {start:{x,y}, current:{x,y}}
      mouse: null,
      candles: [],
      sessionBreaks: {
        enabled: false,
        times: [],
        color: "rgba(56, 189, 248, 0.35)",
        width: 1,
        dash: [4, 6],
      },
      hoveredHandle: null,
      dragDirty: false,
    };

    this.init();
  }

  init() {
    this.resize();
    window.addEventListener("resize", () => this.resize());

    this.container.addEventListener("mousedown", (e) => this.handleMouseDown(e), true);
    window.addEventListener("mousemove", (e) => this.handleMouseMove(e), true);
    window.addEventListener("mouseup", (e) => this.handleMouseUp(e), true);
    window.addEventListener("keydown", (e) => this.handleKeyDown(e));

    this.chart.timeScale().subscribeVisibleTimeRangeChange(() => this.redraw());
    this.chart.subscribeCrosshairMove((e) => {
      this.state.mouse = e;
      this.redraw();
    });
  }

  resize() {
    const rect = this.container.getBoundingClientRect();

    // Simple 1:1 canvas sizing (no DPR scaling for now to fix visibility)
    this.canvas.width = rect.width;
    this.canvas.height = rect.height;
    this.canvas.style.width = rect.width + 'px';
    this.canvas.style.height = rect.height + 'px';

    console.log('Canvas resized:', rect.width, 'x', rect.height);
    this.redraw();
  }

  setCandles(candles) {
    this.state.candles = candles;
    this.computeSessionBreaks();
  }

  setTool(toolId) {
    this.state.currentTool = toolId;
    this.state.drawingDraft = null;
    this.state.selectedId = null;
    this.state.selectedIds = [];
    this.redraw();
  }

  setSessionBreaks(enabled, opts = {}) {
    this.state.sessionBreaks.enabled = !!enabled;
    if (opts.color) this.state.sessionBreaks.color = opts.color;
    if (opts.width) this.state.sessionBreaks.width = opts.width;
    if (opts.dash)  this.state.sessionBreaks.dash  = opts.dash;
    this.redraw();
  }

  /**
   * Set trade pane overlays (logged trades).
   * These are rendered every frame inside redraw() so coordinates are always fresh.
   */
  setTradePanes(trades, symbolFilter) {
    const toEpoch = (v) => {
      if (!v) return null;
      if (typeof v === 'number') return v;
      const ms = Date.parse(v);
      return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
    };
    this.state.tradePanes = [];
    console.log(`[setTradePanes] Processing ${trades?.length || 0} trades for ${symbolFilter || 'all symbols'}`);
    
    (trades || []).forEach(trade => {
      if (symbolFilter && trade.symbol && trade.symbol !== symbolFilter) return;
      const entryTime = toEpoch(trade.ts_open);
      if (!entryTime) return;
      const endTime = toEpoch(trade.ts_close) || (entryTime + 3600 * 4);
      
      // Use both possible field names
      const entry = parseFloat(trade.entry !== undefined ? trade.entry : trade.entry_price);
      const sl    = parseFloat(trade.sl !== undefined ? trade.sl : trade.sl_price);
      const tp    = parseFloat(trade.tp !== undefined ? trade.tp : trade.tp_price);
      
      if (isNaN(entry) || isNaN(sl) || isNaN(tp)) {
        return;
      }
      
      this.state.tradePanes.push({
        id: trade.id,
        entryTime,
        endTime,
        entry,
        sl,
        tp,
        side: String(trade.direction || '').toUpperCase() === 'LONG' ? 'long' : 'short',
      });
    });
    console.log(`[setTradePanes] Active panes successfully set: ${this.state.tradePanes.length}`);
    this.redraw();
  }

  computeSessionBreaks() {
    const breaks = [];
    let prevKey = null;
    for (const c of this.state.candles || []) {
      const d = new Date(c.time * 1000);
      const key = `${d.getUTCFullYear()}-${d.getUTCMonth()}-${d.getUTCDate()}`;
      if (prevKey && key !== prevKey) breaks.push(c.time);
      prevKey = key;
    }
    this.state.sessionBreaks.times = breaks;
  }

  isSelected(id) {
    return this.state.selectedIds.includes(id);
  }

  setSelection(ids, primaryId = null) {
    this.state.selectedIds = Array.from(new Set(ids));
    this.state.selectedId = primaryId || this.state.selectedIds[0] || null;
  }

  getPointFromMouse(ev, opts = {}) {
    const { disableMagnet = false } = opts;
    const rect = this.container.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const y = ev.clientY - rect.top;

    const mouseTime = this.chart.timeScale().coordinateToTime(x);
    const mousePrice = this.series.coordinateToPrice(y);
    if (mouseTime == null || mousePrice == null) return null;

    let bestPoint = { time: Number(mouseTime), price: Number(mousePrice) };
    if (disableMagnet) return bestPoint;

    let minD2 = 400; // 20px radius
    const visibleRange = this.chart.timeScale().getVisibleRange();

    if (visibleRange && this.state.candles.length) {
      for (const c of this.state.candles) {
        if (c.time < visibleRange.from || c.time > visibleRange.to) continue;
        const cx = this.chart.timeScale().timeToCoordinate(c.time);
        const cp_o = this.series.priceToCoordinate(c.open);
        const cp_h = this.series.priceToCoordinate(c.high);
        const cp_l = this.series.priceToCoordinate(c.low);
        const cp_c = this.series.priceToCoordinate(c.close);

        [
          { y: cp_o, p: c.open }, { y: cp_h, p: c.high },
          { y: cp_l, p: c.low }, { y: cp_c, p: c.close }
        ].forEach(lvl => {
          if (lvl.y == null) return;
          const d2 = (cx - x) ** 2 + (lvl.y - y) ** 2;
          if (d2 < minD2) {
            minD2 = d2;
            bestPoint = { time: c.time, price: lvl.p };
          }
        });
      }
    }
    return bestPoint;
  }

  timeToX(time) {
    const x = this.chart.timeScale().timeToCoordinate(time);
    if (x != null) return x;
    const visibleRange = this.chart.timeScale().getVisibleRange();
    if (!visibleRange) return null;
    if (time < visibleRange.from) return 0;
    if (time > visibleRange.to) return this.canvas.width;
    return null;
  }

  pointToXY(p, opts = {}) {
    const { clampTime = false } = opts;
    const x = clampTime ? this.timeToX(p.time) : this.chart.timeScale().timeToCoordinate(p.time);
    const y = this.series.priceToCoordinate(p.price);
    if (x == null || y == null) return null;
    return { x, y };
  }

  ensureRiskRewardPoints(d) {
    if (d.points.length < 3) {
      const entryP = d.points[0];
      const stopP = d.points[1];
      const diff = entryP.price - stopP.price;
      d.points[2] = { time: entryP.time, price: entryP.price + diff * 2 };
    }
    if (d.points.length < 4) {
      const entryP = d.points[0];
      const hours = 24;
      d.points[3] = { time: entryP.time + 3600 * hours, price: entryP.price };
    }
  }

  getRiskRewardXY(d) {
    this.ensureRiskRewardPoints(d);
    const entryP = d.points[0];
    const stopP = d.points[1];
    const targetP = d.points[2];
    const endP = d.points[3];

    const entryXY = this.pointToXY(entryP, { clampTime: true });
    const stopXY = this.pointToXY(stopP, { clampTime: true });
    const targetXY = this.pointToXY(targetP, { clampTime: true });
    let endXY = this.pointToXY(endP, { clampTime: true });

    if (!entryXY || !stopXY || !targetXY) return null;

    if (!endXY) {
      const fixedWidth = 200;
      const leftX = entryXY.x;
      const maxRight = Math.max(leftX + 20, this.canvas.width - 6);
      const rightX = Math.min(leftX + fixedWidth, maxRight);
      endXY = { x: rightX, y: entryXY.y };
    }

    return { entryXY, stopXY, targetXY, endXY };
  }

  handleMouseDown(ev) {
    const p = this.getPointFromMouse(ev, { disableMagnet: !!ev.shiftKey });
    if (!p) return;

    if (this.state.currentTool !== "cursor") {
      ev.preventDefault();
      ev.stopPropagation();

      if (this.state.currentTool === "hline") {
        this.addDrawing({ type: "hline", points: [p] });
        this.setTool("cursor");
        return;
      }

      if (!this.state.drawingDraft) {
        this.state.drawingDraft = { tool: this.state.currentTool, first: p };
      } else {
        const first = this.state.drawingDraft.first;
        const tool = this.state.drawingDraft.tool;
        this.state.drawingDraft = null;

        if (tool === "trendline") this.addDrawing({ type: "trendline", points: [first, p] });
        if (tool === "rect") this.addDrawing({ type: "rect", points: [first, p] });
        if (tool === "long" || tool === "short") this.addDrawing({ type: "riskreward", points: [first, p], side: tool });

        if (["bos", "choch", "sweep"].includes(tool)) {
          this.addDrawing({
            type: "smc",
            points: [first, p],
            label: tool.toUpperCase(),
            style: {
              stroke: tool === "sweep" ? "#f59e0b" : (tool === "bos" ? "#22c55e" : "#ef4444"),
              dash: tool === "sweep" ? [5, 5] : []
            }
          });
        }

        this.dispatchEvent("drawing-added", { tool, points: [first, p] });
        this.setTool("cursor");
      }
      return;
    }

    const multiKey = ev.metaKey || ev.ctrlKey;

    // Start lasso selection with Cmd/Ctrl + drag
    if (multiKey) {
      const rect = this.container.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;
      this.state.lasso = { start: { x: mx, y: my }, current: { x: mx, y: my } };
      ev.preventDefault();
      ev.stopPropagation();
      this.redraw();
      return;
    }

    // Hit Testing
    const rect = this.container.getBoundingClientRect();
    const mx = ev.clientX - rect.left;
    const my = ev.clientY - rect.top;

    // 1. Check handles of selected drawing first
    if (this.state.selectedId) {
      const selected = this.state.drawings.find(d => d.id === this.state.selectedId);
      if (selected) {
        let pts = [];
        if (selected.type === "riskreward") {
          const rr = this.getRiskRewardXY(selected);
          if (rr) pts = [rr.entryXY, rr.stopXY, rr.targetXY, rr.endXY];
        } else {
          pts = selected.points.map(p => this.pointToXY(p)).filter(x => x);
        }

        for (let i = 0; i < pts.length; i++) {
          const d2 = (pts[i].x - mx) ** 2 + (pts[i].y - my) ** 2;
          if (d2 < 100) { // 10px radius
            ev.preventDefault();
            ev.stopPropagation();
            this.state.dragging = { id: selected.id, pointIdx: i, isHandle: true };
            return;
          }
        }
      }
    }

    // 2. Check for new selection or full drawing drag
    let found = null;
    for (const d of [...this.state.drawings].reverse()) {
      if (this.hitTest(d, mx, my)) {
        found = d.id;
        break;
      }
    }

    if (found) {
      if (multiKey) {
        if (this.isSelected(found)) {
          this.setSelection(this.state.selectedIds.filter(id => id !== found), this.state.selectedId === found ? null : this.state.selectedId);
        } else {
          this.setSelection([...this.state.selectedIds, found], found);
        }
      } else {
        this.setSelection([found], found);
      }
      ev.preventDefault();
      ev.stopPropagation();
      this.state.dragging = { id: found, offset: { time: p.time, price: p.price }, isHandle: false };
      this.state.dragDirty = false;
    } else {
      if (multiKey) {
        const allIds = this.state.drawings.map(d => d.id);
        this.setSelection(allIds, allIds[0] || null);
      } else {
        this.setSelection([], null);
      }
    }
    this.redraw();
  }

  handleMouseMove(ev) {
    const rect = this.container.getBoundingClientRect();
    const mx = ev.clientX - rect.left;
    const my = ev.clientY - rect.top;

    if (this.state.lasso) {
      this.state.lasso.current = { x: mx, y: my };
      this.redraw();
      return;
    }

    if (this.state.dragging) {
      ev.preventDefault();
      const p = this.getPointFromMouse(ev, { disableMagnet: !!ev.shiftKey });
      if (!p) return;

      const d = this.state.drawings.find(x => x.id === this.state.dragging.id);
      if (!d) return;

      if (this.state.dragging.isHandle) {
        if (d.type === "riskreward") {
          const idx = this.state.dragging.pointIdx;
          if (idx === 0) { // Entry moved
            const oldPrice = d.points[0].price;
            d.points[0] = p;
            const diff = p.price - oldPrice;
            // Shift SL and TP with entry to maintain RR
            d.points[1].price += diff;
            d.points[2].price += diff;
            d.points[3].price = p.price; // Keep length handle on entry line
          } else if (idx === 1) { // SL moved
            d.points[1] = p;
            d.points[1].time = d.points[0].time; // Lock to left side
          } else if (idx === 2) { // TP moved
            d.points[2] = p;
            d.points[2].time = d.points[0].time; // Lock to left side
          } else if (idx === 3) { // Length moved
            d.points[3] = p;
            d.points[3].price = d.points[0].price; // Lock to entry line
          }
        } else {
          d.points[this.state.dragging.pointIdx] = p;
        }
      } else {
        // Drag entire drawing (move all selected if applicable)
        const dt = p.time - this.state.dragging.offset.time;
        const dp = p.price - this.state.dragging.offset.price;
        const selected = this.state.selectedIds.length ? this.state.selectedIds : [d.id];
        for (const id of selected) {
          const target = this.state.drawings.find(x => x.id === id);
          if (!target) continue;
          target.points = target.points.map(pt => ({ time: pt.time + dt, price: pt.price + dp }));
        }
        this.state.dragging.offset = p;
      }

      this.state.dragDirty = true;
      this.dispatchEvent("drawing-updated", d);
      this.redraw();
    }
  }

  dispatchEvent(name, detail) {
    const ev = new CustomEvent(name, { detail });
    this.container.dispatchEvent(ev);
  }

  handleMouseUp() {
    if (this.state.lasso) {
      const { start, current } = this.state.lasso;
      const minX = Math.min(start.x, current.x);
      const maxX = Math.max(start.x, current.x);
      const minY = Math.min(start.y, current.y);
      const maxY = Math.max(start.y, current.y);

      const hits = [];
      for (const d of this.state.drawings) {
        const bbox = this.getDrawingBBox(d);
        if (!bbox) continue;
        const intersects = !(bbox.maxX < minX || bbox.minX > maxX || bbox.maxY < minY || bbox.minY > maxY);
        if (intersects) hits.push(d.id);
      }
      this.setSelection(hits, hits[0] || null);
      this.state.lasso = null;
      this.redraw();
      return;
    }

    this.state.dragging = null;
  }

  handleKeyDown(ev) {
    const active = document.activeElement;
    const tag = active?.tagName?.toLowerCase();
    if (tag === "input" || tag === "textarea" || active?.isContentEditable) {
      return;
    }
    const key = ev.key.toLowerCase();
    const multiKey = ev.metaKey || ev.ctrlKey;

    if ((key === "delete" || key === "backspace") && this.state.selectedIds.length) {
      const toDelete = new Set(this.state.selectedIds);
      this.state.drawings = this.state.drawings.filter(x => !toDelete.has(x.id));
      this.setSelection([], null);
      this.redraw();
      return;
    }

    if (multiKey && key === "a") {
      ev.preventDefault();
      const allIds = this.state.drawings.map(d => d.id);
      this.setSelection(allIds, allIds[0] || null);
      this.redraw();
      return;
    }

    if (multiKey && key === "c") {
      ev.preventDefault();
      this.copySelected();
      return;
    }

    if (multiKey && key === "v") {
      ev.preventDefault();
      this.pasteCopied();
      return;
    }
  }

  hitTest(d, mx, my) {
    const pts = d.points.map(p => this.pointToXY(p)).filter(x => x);
    if (pts.length === 0) return false;

    if (d.type === "hline") return Math.abs(pts[0].y - my) < 8;
    if (d.type === "trendline" && pts.length === 2) {
      const dist = this.distToSegment(mx, my, pts[0].x, pts[0].y, pts[1].x, pts[1].y);
      return dist < 8;
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
    if (d.type === "smc" && pts.length === 2) {
      const dist = this.distToSegment(mx, my, pts[0].x, pts[0].y, pts[1].x, pts[1].y);
      return dist < 10;
    }
    if (d.type === "riskreward") {
      const rr = this.getRiskRewardXY(d);
      if (!rr) return false;
      const leftX = rr.entryXY.x;
      const rightX = rr.endXY.x;
      const topY = Math.min(rr.entryXY.y, rr.stopXY.y, rr.targetXY.y);
      const bottomY = Math.max(rr.entryXY.y, rr.stopXY.y, rr.targetXY.y);
      return mx >= leftX && mx <= rightX && my >= topY && my <= bottomY;
    }
    return false;
  }

  distToSegment(px, py, x1, y1, x2, y2) {
    const l2 = (x1 - x2) ** 2 + (y1 - y2) ** 2;
    if (l2 === 0) return Math.sqrt((px - x1) ** 2 + (py - y1) ** 2);
    let t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2;
    t = Math.max(0, Math.min(1, t));
    return Math.sqrt((px - (x1 + t * (x2 - x1))) ** 2 + (py - (y1 + t * (y2 - y1))) ** 2);
  }

  getDrawingBBox(d) {
    if (d.type === "riskreward") {
      const rr = this.getRiskRewardXY(d);
      if (!rr) return null;
      const xs = [rr.entryXY.x, rr.stopXY.x, rr.targetXY.x, rr.endXY.x];
      const ys = [rr.entryXY.y, rr.stopXY.y, rr.targetXY.y, rr.endXY.y];
      return {
        minX: Math.min(...xs),
        maxX: Math.max(...xs),
        minY: Math.min(...ys),
        maxY: Math.max(...ys),
      };
    }

    const pts = d.points.map(p => this.pointToXY(p)).filter(x => x);
    if (!pts.length) return null;
    const xs = pts.map(p => p.x);
    const ys = pts.map(p => p.y);
    return {
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minY: Math.min(...ys),
      maxY: Math.max(...ys),
    };
  }

  addDrawing(partial) {
    const drawing = {
      id: Math.random().toString(36).substr(2, 9),
      type: partial.type,
      points: partial.points.map(p => ({ ...p })),
      style: partial.style || { stroke: "#00a3ff", fill: "rgba(0, 163, 255, 0.1)" },
      side: partial.side || null,
      label: partial.label || null,
      source: partial.source || null,
    };
    this.state.drawings.push(drawing);
    if (partial.select !== false && drawing.type === "riskreward") {
      this.setSelection([drawing.id], drawing.id);
    }
    console.log('✏️ Drawing added:', drawing.type, 'Side:', drawing.side, 'Total drawings:', this.state.drawings.length);
    this.redraw();
    return drawing;
  }

  getClipboardOffsetSeconds() {
    const candles = this.state.candles || [];
    if (candles.length >= 2) {
      const dt = Math.abs(candles[1].time - candles[0].time);
      if (dt > 0) return dt;
    }
    return 3600;
  }

  copySelected() {
    if (!this.state.selectedIds.length) return;
    const selected = this.state.drawings.filter(d => this.state.selectedIds.includes(d.id));
    this.state.clipboard = selected.map(d => ({
      type: d.type,
      points: d.points.map(p => ({ ...p })),
      style: d.style ? { ...d.style } : undefined,
      side: d.side || null,
      label: d.label || null,
      note: d.note,
    }));
  }

  pasteCopied() {
    if (!this.state.clipboard || !this.state.clipboard.length) return;
    const dt = this.getClipboardOffsetSeconds();
    const newIds = [];

    for (const item of this.state.clipboard) {
      const drawing = {
        id: Math.random().toString(36).substr(2, 9),
        type: item.type,
        points: item.points.map(p => ({ time: p.time + dt, price: p.price })),
        style: item.style ? { ...item.style } : { stroke: "#00a3ff", fill: "rgba(0, 163, 255, 0.1)" },
        side: item.side || null,
        label: item.label || null,
        note: item.note,
      };
      this.state.drawings.push(drawing);
      newIds.push(drawing.id);
    }

    if (newIds.length) {
      this.setSelection(newIds, newIds[0]);
      this.redraw();
    }
  }

  redraw() {
    if (!this.ctx) return;

    // Reset draw state to ensure visibility
    this.ctx.globalAlpha = 1.0;
    this.ctx.globalCompositeOperation = 'source-over';

    const rect = this.container.getBoundingClientRect();

    // Clear canvas
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // Session breaks (daily separators)
    if (this.state.sessionBreaks.enabled && this.state.sessionBreaks.times.length) {
      const visibleRange = this.chart.timeScale().getVisibleRange();
      this.ctx.save();
      this.ctx.strokeStyle = this.state.sessionBreaks.color;
      this.ctx.lineWidth = this.state.sessionBreaks.width;
      this.ctx.setLineDash(this.state.sessionBreaks.dash);
      for (const t of this.state.sessionBreaks.times) {
        if (visibleRange && (t < visibleRange.from || t > visibleRange.to)) continue;
        const x = this.chart.timeScale().timeToCoordinate(t);
        if (x == null) continue;
        this.ctx.beginPath();
        this.ctx.moveTo(x, 0);
        this.ctx.lineTo(x, this.canvas.height);
        this.ctx.stroke();
      }
      this.ctx.restore();
    }

    // ── Trade Pane Overlays ──────────────────────────────────────────────────
    if (this.state.tradePanes.length > 0) {
      if (Math.random() < 0.05) console.log(`[redraw] Attempting to render ${this.state.tradePanes.length} trade panes...`);
      const vr = this.chart.timeScale().getVisibleRange();
      this.ctx.save();

      for (const pane of this.state.tradePanes) {
        // Skip if entirely outside visible time range
        if (vr && (pane.endTime < vr.from || pane.entryTime > vr.to)) continue;

        const leftX  = this.timeToX(pane.entryTime);
        const rightX = this.timeToX(pane.endTime);
        
        if (leftX === null || rightX === null) continue;
        if (Math.abs(rightX - leftX) < 0.1) continue;

        const entryY = this.series.priceToCoordinate(pane.entry);
        const slY    = this.series.priceToCoordinate(pane.sl);
        const tpY    = this.series.priceToCoordinate(pane.tp);
        
        const eY = entryY;
        const sY = slY;
        const tY = tpY;

        if (eY === null || sY === null || tY === null) continue;

        const w         = rightX - leftX;
        const isLong    = pane.side === 'long';
        const accentClr = isLong ? '#22c55e' : '#ef4444';

        // ── TP zone (green semi-transparent fill) ────────────────────────
        this.ctx.fillStyle = 'rgba(34, 197, 94, 0.35)'; // Increased opacity
        this.ctx.fillRect(leftX, Math.min(eY, tY), w, Math.abs(tY - eY));

        // ── SL zone (red semi-transparent fill) ──────────────────────────
        this.ctx.fillStyle = 'rgba(239, 68, 68, 0.35)'; // Increased opacity
        this.ctx.fillRect(leftX, Math.min(eY, sY), w, Math.abs(sY - eY));

        // ── Entry line ───────────────────────────────────────────────────
        this.ctx.strokeStyle = accentClr;
        this.ctx.lineWidth = 2;
        this.ctx.setLineDash([]);
        this.ctx.beginPath();
        this.ctx.moveTo(leftX, eY);
        this.ctx.lineTo(rightX, eY);
        this.ctx.stroke();

        // ── TP border line (top edge) ────────────────────────────────────
        this.ctx.strokeStyle = 'rgba(34, 197, 94, 0.8)';
        this.ctx.lineWidth = 1;
        this.ctx.setLineDash([4, 3]);
        this.ctx.beginPath();
        this.ctx.moveTo(leftX, tY);
        this.ctx.lineTo(rightX, tY);
        this.ctx.stroke();

        // ── SL border line (bottom edge) ─────────────────────────────────
        this.ctx.strokeStyle = 'rgba(239, 68, 68, 0.8)';
        this.ctx.beginPath();
        this.ctx.moveTo(leftX, sY);
        this.ctx.lineTo(rightX, sY);
        this.ctx.stroke();

        // ── Left-edge accent bar ─────────────────────────────────────────
        this.ctx.strokeStyle = accentClr;
        this.ctx.lineWidth = 4;
        this.ctx.setLineDash([]);
        this.ctx.beginPath();
        this.ctx.moveTo(leftX, Math.min(sY, tY));
        this.ctx.lineTo(leftX, Math.max(sY, tY));
        this.ctx.stroke();

        // ── Direction label ──────────────────────────────────────────────
        this.ctx.fillStyle = accentClr;
        this.ctx.font = 'bold 10px Inter, sans-serif';
        this.ctx.textAlign = 'left';
        this.ctx.setLineDash([]);
        this.ctx.fillText(isLong ? '▲ LONG' : '▼ SHORT', leftX + 8, eY - 6);
      }

      this.ctx.restore();
    }

    // ── Diagnostic: Draw a bright red dot in the top-left to verify canvas visibility
    this.ctx.fillStyle = "red";
    this.ctx.beginPath();
    this.ctx.arc(10, 10, 5, 0, Math.PI * 2);
    this.ctx.fill();

    // Draw Drawings

    for (const d of this.state.drawings) {
      const pts = d.points.map(p => this.pointToXY(p)).filter(x => x);
    if (pts.length === 0 && d.type !== "riskreward") {
      console.warn('Drawing has no valid points:', d.type);
      continue;
    }

      this.ctx.strokeStyle = d.id === this.state.selectedId ? "#fff" : (d.style.stroke || "#00a3ff");
      this.ctx.lineWidth = 2;

      if (d.type === "hline") {
        this.ctx.beginPath();
        this.ctx.moveTo(0, pts[0].y);
        this.ctx.lineTo(this.canvas.width, pts[0].y);
        this.ctx.stroke();
      } else if (d.type === "trendline" && pts.length === 2) {
        this.ctx.beginPath();
        this.ctx.moveTo(pts[0].x, pts[0].y);
        this.ctx.lineTo(pts[1].x, pts[1].y);
        this.ctx.stroke();
      } else if (d.type === "rect" && pts.length === 2) {
        const w = pts[1].x - pts[0].x;
        const h = pts[1].y - pts[0].y;
        this.ctx.fillStyle = d.style.fill || "rgba(0, 163, 255, 0.1)";
        this.ctx.fillRect(pts[0].x, pts[0].y, w, h);
        this.ctx.strokeRect(pts[0].x, pts[0].y, w, h);
      } else if (d.type === "text") {
        this.ctx.font = "bold 12px Inter, sans-serif";
        this.ctx.fillStyle = d.style.stroke || "#fff";
        this.ctx.textAlign = "center";
        this.ctx.fillText(d.note, pts[0].x, pts[0].y);
      } else if (d.type === "smc" && pts.length === 2) {
        this.ctx.setLineDash(d.style.dash || []);
        this.ctx.beginPath();
        this.ctx.moveTo(pts[0].x, pts[0].y);
        this.ctx.lineTo(pts[1].x, pts[1].y);
        this.ctx.stroke();
        this.ctx.setLineDash([]);

        // Draw Label at the end or middle? User said "according label". 
        // TV usually has it at the end or middle. Let's do middle for now.
        const midX = (pts[0].x + pts[1].x) / 2;
        const midY = (pts[0].y + pts[1].y) / 2;
        this.ctx.font = "bold 10px Inter, sans-serif";
        this.ctx.fillStyle = d.style.stroke;
        this.ctx.textAlign = "center";
        this.ctx.fillText(d.label, midX, midY - 10);
      } else if (d.type === "riskreward" && d.points.length >= 2) {
        // --- Visibility pre-check: skip if trade time range is entirely off-screen ---
        const visibleRange = this.chart.timeScale().getVisibleRange();
        if (visibleRange) {
          this.ensureRiskRewardPoints(d);
          const tradeStart = d.points[0].time;
          const tradeEnd   = d.points[3] ? d.points[3].time : tradeStart + 3600 * 4;
          // If trade is completely to the left or right of the visible area, skip
          if (tradeEnd < visibleRange.from || tradeStart > visibleRange.to) continue;
        }

        const rr = this.getRiskRewardXY(d);
        if (rr) {
          const { entryXY, stopXY, targetXY, endXY } = rr;
          const entryP = d.points[0];
          const stopP  = d.points[1];
          const targetP = d.points[2];

          const leftX  = entryXY.x;
          const rightX = endXY.x;

          // Skip zero-width or reversed boxes (both points clamped to the same edge)
          if (Math.abs(rightX - leftX) < 1) continue;

          const entryY  = entryXY.y;
          const stopY   = stopXY.y;
          const targetY = targetXY.y;

          // Stop Zone (always RED - loss zone)
          this.ctx.fillStyle = "rgba(239, 68, 68, 0.3)";
          const stopBoxY = Math.min(entryY, stopY);
          const stopBoxH = Math.abs(stopY - entryY);
          this.ctx.fillRect(leftX, stopBoxY, rightX - leftX, stopBoxH);

          // Target Zone (always GREEN - profit zone)
          this.ctx.fillStyle = "rgba(34, 197, 94, 0.3)";
          const targetBoxY = Math.min(entryY, targetY);
          const targetBoxH = Math.abs(targetY - entryY);
          this.ctx.fillRect(leftX, targetBoxY, rightX - leftX, targetBoxH);

          this.ctx.strokeStyle = d.side === "long" ? "#22c55e" : "#ef4444";
          this.ctx.lineWidth = 2;
          this.ctx.strokeRect(leftX, Math.min(targetY, stopY), rightX - leftX, Math.abs(stopY - targetY));

          // Entry Line
          this.ctx.strokeStyle = "#94a3b8";
          this.ctx.lineWidth = 2;
          this.ctx.beginPath();
          this.ctx.moveTo(leftX, entryY);
          this.ctx.lineTo(rightX, entryY);
          this.ctx.stroke();

          // Entry direction arrow (triangle at entry line, left edge)
          const arrowSize = 8;
          const isLong = d.side !== "short";
          const arrowColor = isLong ? "#22c55e" : "#ef4444";
          this.ctx.fillStyle = arrowColor;
          this.ctx.beginPath();
          if (isLong) {
            // Upward triangle
            this.ctx.moveTo(leftX + arrowSize, entryY);
            this.ctx.lineTo(leftX, entryY + arrowSize * 1.4);
            this.ctx.lineTo(leftX + arrowSize * 2, entryY + arrowSize * 1.4);
          } else {
            // Downward triangle
            this.ctx.moveTo(leftX + arrowSize, entryY);
            this.ctx.lineTo(leftX, entryY - arrowSize * 1.4);
            this.ctx.lineTo(leftX + arrowSize * 2, entryY - arrowSize * 1.4);
          }
          this.ctx.closePath();
          this.ctx.fill();

          // Labels
          this.ctx.fillStyle = "#fff";
          this.ctx.font = "bold 10px Inter";
          this.ctx.textAlign = "left";
          const rrValue = (Math.abs(targetP.price - entryP.price) / Math.abs(entryP.price - stopP.price)).toFixed(2);
          this.ctx.fillText(`R:R ${rrValue}`, leftX + arrowSize * 2 + 6, entryY - 4);

          // Direction label
          this.ctx.fillStyle = arrowColor;
          this.ctx.font = "bold 9px Inter";
          this.ctx.fillText(isLong ? "LONG" : "SHORT", leftX + arrowSize * 2 + 6, entryY + 10);
        }
      }

      // Draw selection handles
      if (this.isSelected(d.id)) {
        this.ctx.fillStyle = "#fff";
        this.ctx.strokeStyle = "#00a3ff";
        this.ctx.lineWidth = 1;
        let handlePts = pts;
        if (d.type === "riskreward") {
          const rr = this.getRiskRewardXY(d);
          if (rr) handlePts = [rr.entryXY, rr.stopXY, rr.targetXY, rr.endXY];
        }
        for (const pt of handlePts) {
          this.ctx.beginPath();
          this.ctx.arc(pt.x, pt.y, 4, 0, Math.PI * 2);
          this.ctx.fill();
          this.ctx.stroke();
        }
      }
    }

    // Draw Draft
    if (this.state.drawingDraft && this.state.mouse?.point) {
      const firstXY = this.pointToXY(this.state.drawingDraft.first);
      if (firstXY) {
        this.ctx.strokeStyle = "rgba(255, 255, 255, 0.5)";
        this.ctx.setLineDash([5, 5]);
        this.ctx.beginPath();
        this.ctx.moveTo(firstXY.x, firstXY.y);
        this.ctx.lineTo(this.state.mouse.point.x, this.state.mouse.point.y);
        this.ctx.stroke();
        this.ctx.setLineDash([]);
      }
    }

    // Draw Lasso Selection Box
    if (this.state.lasso) {
      const { start, current } = this.state.lasso;
      const x = Math.min(start.x, current.x);
      const y = Math.min(start.y, current.y);
      const w = Math.abs(start.x - current.x);
      const h = Math.abs(start.y - current.y);
      this.ctx.save();
      this.ctx.strokeStyle = "rgba(56, 189, 248, 0.9)";
      this.ctx.fillStyle = "rgba(56, 189, 248, 0.12)";
      this.ctx.lineWidth = 1;
      this.ctx.setLineDash([6, 6]);
      this.ctx.strokeRect(x, y, w, h);
      this.ctx.fillRect(x, y, w, h);
      this.ctx.restore();
    }
  }
}

window.DrawingEngine = DrawingEngine;
