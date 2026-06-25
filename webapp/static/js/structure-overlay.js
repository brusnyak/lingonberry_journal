/**
 * StructureOverlay — Canvas-based rendering of ICT/SMC structure components
 * on a Lightweight Charts chart.
 *
 * Inspired by the pine review drawing engine (Canvas overlay + time/price coordinate mapping).
 *
 * Usage:
 *   const overlay = new StructureOverlay(chart, candleSeries, data);
 *   overlay.renderAll();
 *   overlay.remove();     // clean up
 *
 * Data format (from /api/analysis/structure/visualize):
 *   candles: [{time, open, high, low, close, volume}, ...]
 *   swing_highs: [{time, price}]
 *   swing_lows: [{time, price}]
 *   structure_breaks: [{time, price, type: "BOS"|"CHoCH", direction: "bullish"|"bearish"}]
 *   fvgs: [{type: "bullish"|"bearish", top, bottom, start_time, end_time, mitigated}]
 *   order_blocks: [{type: "bullish"|"bearish", top, bottom, time, mitigated}]
 *   liquidity_levels: [{type: "high"|"low", price, swept}]
 *   liquidity_sweeps: [{time, price, type, reclaim, wick_only}]
 */
class StructureOverlay {
  constructor(chart, candleSeries, data, container) {
    this.chart = chart;
    this.candleSeries = candleSeries;
    this.data = data;
    this._container = container || chart._chartElement?.parentElement || chart._container;
    this._priceLines = [];
    this._series = [];
    this._canvas = null;
    this._ctx = null;
    this._enabled = true;
    this._hovered = null; // { type, index }
  }

  /** Remove all overlays and destroy canvas */
  remove() {
    for (const pl of this._priceLines) pl();
    this._priceLines = [];
    for (const s of this._series) {
      try { this.chart.removeSeries(s); } catch (_) {}
    }
    this._series = [];
    this.candleSeries.setMarkers([]);
    this._destroyCanvas();
  }

  /** Render all structure components */
  renderAll() {
    this.remove();
    this._ensureCanvas();

    const allMarkers = [];
    this._swingMarkers(allMarkers);
    this._renderLines();
    this._renderRectangles();
    this._liquiditySweeps(allMarkers);

    if (allMarkers.length > 0) {
      this.candleSeries.setMarkers(allMarkers);
    }

    this._scheduleRedraw();
  }

  /** Return array of Lightweight Charts series objects (for cleanup tracking) */
  getSeries() { return this._series; }

  // ------------------------------------------------------------------
  // Canvas setup
  // ------------------------------------------------------------------

  _ensureCanvas() {
    if (this._canvas) return;
    // Use provided container or try to find chart's container element
    const container = this._container || this.chart._chartElement?.parentElement || document.getElementById('chart');
    if (!container) {
      // Fallback: try to find the chart container from the DOM
      return;
    }
    this._canvas = document.createElement('canvas');
    this._canvas.style.position = 'absolute';
    this._canvas.style.top = '0';
    this._canvas.style.left = '0';
    this._canvas.style.pointerEvents = 'none';
    this._canvas.style.zIndex = '10';
    container.appendChild(this._canvas);
    this._ctx = this._canvas.getContext('2d');

    const resize = () => {
      const rect = container.getBoundingClientRect();
      if (this._canvas) {
        this._canvas.width = rect.width;
        this._canvas.height = rect.height;
        this._redrawNow();
      }
    };
    this._resizeHandler = resize;
    window.addEventListener('resize', resize);

    // Redraw on chart scroll/zoom
    this._chartMoveHandler = () => this._scheduleRedraw();
    this.chart.timeScale().subscribeVisibleTimeRangeChange(this._chartMoveHandler);
    this.chart.subscribeCrosshairMove(() => this._scheduleRedraw());

    resize();
  }

  _destroyCanvas() {
    if (this._resizeHandler) window.removeEventListener('resize', this._resizeHandler);
    if (this._chartMoveHandler) {
      try {
        this.chart.timeScale().unsubscribeVisibleTimeRangeChange(this._chartMoveHandler);
        this.chart.unsubscribeCrosshairMove(this._chartMoveHandler);
      } catch (_) {}
    }
    if (this._canvas && this._canvas.parentNode) {
      this._canvas.parentNode.removeChild(this._canvas);
    }
    this._canvas = null;
    this._ctx = null;
    this._redrawTimer = null;
  }

  _scheduleRedraw() {
    if (this._redrawTimer) return;
    this._redrawTimer = requestAnimationFrame(() => {
      this._redrawTimer = null;
      this._redrawNow();
    });
  }

  // ------------------------------------------------------------------
  // Coordinate mapping helpers
  // ------------------------------------------------------------------

  _timeToX(time) {
    return this.chart.timeScale().timeToCoordinate(time);
  }

  _priceToY(price) {
    return this.candleSeries.priceToCoordinate(price);
  }

  _pointToXY(point) {
    const x = this._timeToX(point.time);
    const y = this._priceToY(point.price);
    if (x == null || y == null) return null;
    return { x, y };
  }

  // ------------------------------------------------------------------
  // Canvas redraw
  // ------------------------------------------------------------------

  _redrawNow() {
    const ctx = this._ctx;
    const canvas = this._canvas;
    if (!ctx || !canvas) return;
    const rect = canvas.parentNode?.getBoundingClientRect();
    if (!rect) return;
    canvas.width = rect.width;
    canvas.height = rect.height;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // FVGs
    this._drawFvgs(ctx);
    // Order blocks
    this._drawOrderBlocks(ctx);
    // Structure breaks (BOS/CHOCH trendlines)
    this._drawStructureBreaks(ctx);
    // Liquidity levels
    this._drawLiquidityLevels(ctx);

    // Labels on top
    this._drawLabels(ctx);
  }

  // ------------------------------------------------------------------
  // FVGs — semi-transparent filled rectangles
  // ------------------------------------------------------------------

  _drawFvgs(ctx) {
    const fvgs = this.data.fvgs || [];
    for (const fvg of fvgs) {
      const start = fvg.start_time || fvg.end_time;
      const end = fvg.end_time || fvg.start_time;
      if (!start || !end) continue;

      // For FVGs with only end_time (single candle), expand a bit
      const timeStart = Math.min(start, end);
      const timeEnd = Math.max(start, end);

      const x1 = this._timeToX(timeStart);
      const x2 = this._timeToX(timeEnd);
      const yTop = this._priceToY(fvg.top);
      const yBottom = this._priceToY(fvg.bottom);
      if (x1 == null || x2 == null || yTop == null || yBottom == null) continue;

      const w = Math.max(x2 - x1, 4); // minimum 4px width
      const h = yBottom - yTop;
      const x = x1;

      const baseColor = fvg.type === 'bullish' ? '#10b981' : '#ef4444';
      const alpha = fvg.mitigated ? '18' : '30';
      const borderAlpha = '50';

      ctx.fillStyle = baseColor + alpha;
      ctx.strokeStyle = baseColor + borderAlpha;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.rect(x, yTop, w, h);
      ctx.fill();
      ctx.stroke();

      // Label
      const label = fvg.mitigated ? 'FVG (mit)' : 'FVG';
      ctx.fillStyle = baseColor;
      ctx.font = '11px monospace';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'bottom';
      ctx.fillText(label, x + 2, yTop - 2);
    }
  }

  // ------------------------------------------------------------------
  // Order blocks — rectangles
  // ------------------------------------------------------------------

  _drawOrderBlocks(ctx) {
    const obs = this.data.order_blocks || [];
    for (const ob of obs) {
      if (!ob.time) continue;
      const x = this._timeToX(ob.time);
      const yTop = this._priceToY(ob.top);
      const yBottom = this._priceToY(ob.bottom);
      if (x == null || yTop == null || yBottom == null) continue;

      const w = this._timeToX(ob.time + 1) - x || 6;
      const h = yBottom - yTop;

      const baseColor = ob.type === 'bullish' ? '#10b981' : '#ef4444';
      const alpha = ob.mitigated ? '15' : '25';

      ctx.fillStyle = baseColor + alpha;
      ctx.strokeStyle = baseColor + '60';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.rect(x, yTop, Math.max(w, 4), h);
      ctx.fill();
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  // ------------------------------------------------------------------
  // Structure breaks — arrow-tipped trendlines
  // ------------------------------------------------------------------

  _drawStructureBreaks(ctx) {
    const breaks = this.data.structure_breaks || [];
    // Collect breaks by time for labeling
    for (const brk of breaks) {
      if (!brk.time) continue;
      const y = this._priceToY(brk.price);
      const x = this._timeToX(brk.time);
      if (x == null || y == null) continue;

      // Find nearby swing points to draw arrow from
      const isBullish = brk.direction === 'bullish';
      const swings = isBullish ? (this.data.swing_lows || []) : (this.data.swing_highs || []);
      let fromX = x - 60; // default: draw from left
      let fromY = y;

      // Find the most recent swing in the right direction
      let bestSwing = null;
      for (const sw of swings) {
        if (sw.time < brk.time) {
          if (!bestSwing || sw.time > bestSwing.time) {
            bestSwing = sw;
          }
        }
      }
      if (bestSwing) {
        const xy = this._pointToXY(bestSwing);
        if (xy) {
          fromX = xy.x;
          fromY = xy.y;
        }
      }

      // Horizontal line at break level
      const color = brk.type === 'BOS' ? '#a78bfa' : '#f43f5e';
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(x - 40, y);
      ctx.lineTo(x + 40, y);
      ctx.stroke();
      ctx.setLineDash([]);

      // Arrow
      const arrowLen = 10;
      const arrowAngle = Math.PI / 6;
      const dir = isBullish ? 1 : -1;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x - arrowLen, y - dir * arrowLen);
      ctx.moveTo(x, y);
      ctx.lineTo(x + arrowLen, y - dir * arrowLen);
      ctx.stroke();

      // Label
      const label = brk.type + ' ' + brk.direction;
      ctx.fillStyle = color;
      ctx.font = 'bold 11px monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = isBullish ? 'top' : 'bottom';
      ctx.fillText(label, x, isBullish ? y + 6 : y - 6);
    }
  }

  // ------------------------------------------------------------------
  // Liquidity levels — horizontal lines with labels
  // ------------------------------------------------------------------

  _drawLiquidityLevels(ctx) {
    const levels = this.data.liquidity_levels || [];
    for (const liq of levels) {
      if (!liq.price) continue;
      const y = this._priceToY(liq.price);
      if (y == null) continue;

      // Pick a representative time for x positioning
      const time = liq.time || (this.data.candles?.length ? this.data.candles[0].time : null);
      if (!time) continue;
      const x = this._timeToX(time);
      if (x == null) continue;

      const color = liq.type === 'high' ? '#fbbf24' : '#60a5fa';
      ctx.strokeStyle = color;
      ctx.lineWidth = liq.swept ? 1 : 1.5;
      ctx.setLineDash(liq.swept ? [] : [4, 4]);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(ctx.canvas.width, y);
      ctx.stroke();
      ctx.setLineDash([]);

      // Label
      const label = liq.swept ? 'Liq ' + (liq.type === 'high' ? 'H ✓' : 'L ✓') : 'Liq ' + (liq.type === 'high' ? 'H' : 'L');
      ctx.fillStyle = color;
      ctx.font = 'bold 10px monospace';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'bottom';
      ctx.fillText(label, ctx.canvas.width - 4, y - 2);

      // Price
      ctx.fillStyle = color + 'aa';
      ctx.font = '10px monospace';
      ctx.textBaseline = 'top';
      ctx.fillText(liq.price.toFixed(5), ctx.canvas.width - 4, y + 2);
    }
  }

  // ------------------------------------------------------------------
  // Labels — structure labels, sweep labels
  // ------------------------------------------------------------------

  _drawLabels(ctx) {
    const labels = this.data.structure_labels || [];
    for (const l of labels) {
      const xy = this._pointToXY(l);
      if (!xy) continue;

      const color = l.type === 'high' ? '#f59e0b' : '#06b6d4';
      ctx.fillStyle = color;
      ctx.font = 'bold 12px monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = l.type === 'high' ? 'bottom' : 'top';
      ctx.fillText(l.label, xy.x, l.type === 'high' ? xy.y - 4 : xy.y + 4);
    }
  }

  // --------------------------------------------------------------
  // Swing markers (via Lightweight Charts marker API)
  // --------------------------------------------------------------

  _swingMarkers(markers) {
    for (const sh of this.data.swing_highs || []) {
      markers.push({
        time: sh.time,
        position: 'aboveBar',
        shape: 'arrowDown',
        color: '#f59e0b',
        size: 1,
        text: formatPrice(sh.price),
      });
    }
    for (const sl of this.data.swing_lows || []) {
      markers.push({
        time: sl.time,
        position: 'belowBar',
        shape: 'arrowUp',
        color: '#06b6d4',
        size: 1,
        text: formatPrice(sl.price),
      });
    }
  }

  // --------------------------------------------------------------
  // Structure breaks (horizontal price lines as fallback + canvas rendering)
  // --------------------------------------------------------------

  _renderLines() {
    for (const brk of this.data.structure_breaks || []) {
      const color = brk.type === 'BOS' ? '#a78bfa' : '#f43f5e';
      const label = brk.type + ' ' + (brk.direction || '');
      // Lightweight price line as backup
      try {
        const pl = this.candleSeries.createPriceLine({
          price: brk.price,
          color: color + '44',
          title: '',
          lineWidth: 1,
          lineStyle: LightweightCharts.LineStyle.Dashed,
          axisLabelVisible: false,
        });
        this._priceLines.push(() => this.candleSeries.removePriceLine(pl));
      } catch (_) {}
    }
  }

  // --------------------------------------------------------------
  // Rectangle series fallback for FVGs/OBs (for axis labels)
  // --------------------------------------------------------------

  _renderRectangles() {
    for (const fvg of this.data.fvgs || []) {
      if (!fvg.start_time) continue;
      const time = fvg.start_time || fvg.end_time;
      if (!time) continue;
      const baseColor = fvg.type === 'bullish' ? '#10b981' : '#ef4444';
      try {
        const rect = this.chart.addRectangleSeries({
          color: baseColor + '00',
          borderColor: baseColor + '00',
          borderWidth: 0,
        });
        rect.setData([{ time, high: fvg.top, low: fvg.bottom }]);
        this._addSeries(rect);
      } catch (_) {}
    }
  }

  _addSeries(series) {
    this._series.push(series);
    return series;
  }

  _liquiditySweeps(markers) {
    for (const swp of this.data.liquidity_sweeps || []) {
      markers.push({
        time: swp.time,
        position: swp.type === 'buy' ? 'belowBar' : 'aboveBar',
        shape: 'circle',
        color: swp.reclaim ? '#10b981' : '#f43f5e',
        size: 2,
      });
    }
  }
}

function formatPrice(val) {
  if (val == null || isNaN(val)) return '';
  const abs = Math.abs(val);
  if (abs < 0.01) return val.toFixed(5);
  if (abs < 1) return val.toFixed(4);
  return val.toFixed(2);
}