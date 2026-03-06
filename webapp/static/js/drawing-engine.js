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
      currentTool: "cursor",
      selectedId: null,
      drawingDraft: null,
      dragging: null, // {id, pointIdx, offset}
      mouse: null,
      candles: [],
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
    this.canvas.width = rect.width;
    this.canvas.height = rect.height;
    this.redraw();
  }

  setCandles(candles) {
    this.state.candles = candles;
  }

  setTool(toolId) {
    this.state.currentTool = toolId;
    this.state.drawingDraft = null;
    this.state.selectedId = null;
    this.redraw();
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

  pointToXY(p) {
    const x = this.chart.timeScale().timeToCoordinate(p.time);
    const y = this.series.priceToCoordinate(p.price);
    if (x == null || y == null) return null;
    return { x, y };
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
          // PointToXY doesn't work directly because RR has virtual points sometimes or depends on entry
          const entryXY = this.pointToXY(selected.points[0]);
          const stopXY = this.pointToXY(selected.points[1]);
          const targetXY = this.pointToXY(selected.points[2]);
          const endXY = this.pointToXY(selected.points[3]);
          if (entryXY && stopXY && targetXY && endXY) {
            pts = [entryXY, stopXY, targetXY, { x: endXY.x, y: entryXY.y }];
          }
        } else {
          pts = selected.points.map(p => this.pointToXY(p)).filter(x => x);
        }

        for (let i = 0; i < pts.length; i++) {
          const d2 = (pts[i].x - mx)**2 + (pts[i].y - my)**2;
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
    
    this.state.selectedId = found;
    if (found) {
      ev.preventDefault();
      ev.stopPropagation();
      this.state.dragging = { id: found, offset: { time: p.time, price: p.price }, isHandle: false };
      this.state.dragDirty = false;
    }
    this.redraw();
  }

  handleMouseMove(ev) {
    const rect = this.container.getBoundingClientRect();
    const mx = ev.clientX - rect.left;
    const my = ev.clientY - rect.top;

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
        // Drag entire drawing
        const dt = p.time - this.state.dragging.offset.time;
        const dp = p.price - this.state.dragging.offset.price;
        d.points = d.points.map(pt => ({ time: pt.time + dt, price: pt.price + dp }));
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
    this.state.dragging = null;
  }

  handleKeyDown(ev) {
    if ((ev.key === "Delete" || ev.key === "Backspace") && this.state.selectedId) {
      this.state.drawings = this.state.drawings.filter(x => x.id !== this.state.selectedId);
      this.state.selectedId = null;
      this.redraw();
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
    if (d.type === "riskreward" && pts.length >= 2) {
      const leftX = pts[0].x;
      const rightX = pts[3]?.x || pts[1].x;
      const topY = Math.min(pts[0].y, pts[1].y, pts[2]?.y || pts[1].y);
      const bottomY = Math.max(pts[0].y, pts[1].y, pts[2]?.y || pts[1].y);
      return mx >= leftX && mx <= rightX && my >= topY && my <= bottomY;
    }
    return false;
  }

  distToSegment(px, py, x1, y1, x2, y2) {
    const l2 = (x1 - x2)**2 + (y1 - y2)**2;
    if (l2 === 0) return Math.sqrt((px - x1)**2 + (py - y1)**2);
    let t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2;
    t = Math.max(0, Math.min(1, t));
    return Math.sqrt((px - (x1 + t * (x2 - x1)))**2 + (py - (y1 + t * (y2 - y1)))**2);
  }

  addDrawing(partial) {
    const drawing = {
      id: Math.random().toString(36).substr(2, 9),
      type: partial.type,
      points: partial.points.map(p => ({...p})),
      style: partial.style || { stroke: "#00a3ff", fill: "rgba(0, 163, 255, 0.1)" },
      side: partial.side || null,
      label: partial.label || null,
    };
    this.state.drawings.push(drawing);
    this.redraw();
  }

  redraw() {
    if (!this.ctx) return;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // Draw Drawings
    for (const d of this.state.drawings) {
      const pts = d.points.map(p => this.pointToXY(p)).filter(x => x);
      if (pts.length === 0) continue;

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
        const entryP = d.points[0];
        const stopP = d.points[1];
        
        // Ensure we have target and end points
        if (d.points.length < 3) {
          const diff = entryP.price - stopP.price;
          d.points[2] = { time: entryP.time, price: entryP.price + diff * 2 }; // Target 2R
        }
        if (d.points.length < 4) {
          const hours = 24; // Default length
          d.points[3] = { time: entryP.time + 3600 * hours, price: entryP.price }; 
        }

        const targetP = d.points[2];
        const endP = d.points[3];

        const entryXY = this.pointToXY(entryP);
        const stopXY = this.pointToXY(stopP);
        const targetXY = this.pointToXY(targetP);
        const endXY = this.pointToXY(endP);

        if (entryXY && stopXY && targetXY && endXY) {
          const leftX = entryXY.x;
          const rightX = endXY.x;
          const entryY = entryXY.y;
          const stopY = stopXY.y;
          const targetY = targetXY.y;

          // Stop Zone
          this.ctx.fillStyle = d.side === "long" ? "rgba(239, 68, 68, 0.2)" : "rgba(34, 197, 94, 0.2)";
          const stopBoxY = Math.min(entryY, stopY);
          const stopBoxH = Math.abs(stopY - entryY);
          this.ctx.fillRect(leftX, stopBoxY, rightX - leftX, stopBoxH);

          // Target Zone
          this.ctx.fillStyle = d.side === "long" ? "rgba(34, 197, 94, 0.2)" : "rgba(239, 68, 68, 0.2)";
          const targetBoxY = Math.min(entryY, targetY);
          const targetBoxH = Math.abs(targetY - entryY);
          this.ctx.fillRect(leftX, targetBoxY, rightX - leftX, targetBoxH);
          
          this.ctx.strokeStyle = d.side === "long" ? "#22c55e" : "#ef4444";
          this.ctx.lineWidth = 1;
          this.ctx.strokeRect(leftX, Math.min(targetY, stopY), rightX - leftX, Math.abs(stopY - targetY));
          
          // Entry Line
          this.ctx.strokeStyle = "#94a3b8";
          this.ctx.beginPath();
          this.ctx.moveTo(leftX, entryY);
          this.ctx.lineTo(rightX, entryY);
          this.ctx.stroke();

          // Labels
          this.ctx.fillStyle = "#fff";
          this.ctx.font = "10px Inter";
          this.ctx.textAlign = "left";
          const rr = (Math.abs(targetP.price - entryP.price) / Math.abs(entryP.price - stopP.price)).toFixed(2);
          this.ctx.fillText(`R:R ${rr}`, leftX + 5, entryY - 5);
        }
      }

      // Draw selection handles
      if (d.id === this.state.selectedId) {
        this.ctx.fillStyle = "#fff";
        this.ctx.strokeStyle = "#00a3ff";
        this.ctx.lineWidth = 1;
        for (const pt of pts) {
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
  }
}

window.DrawingEngine = DrawingEngine;
