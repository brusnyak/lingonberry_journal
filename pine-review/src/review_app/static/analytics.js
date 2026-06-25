const st = {
  sessions: [],
  selected: null,
  artifacts: [],
  activeArtifactId: null,
  replay: {
    chart: null,
    series: null,
    ctx: null,
    candles: [],
    candleCache: {},
  },
};

const REPLAY_RR_FILL_ALPHA = 0.14;

async function api(url, opts = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function qp(name) {
  const url = new URL(window.location.href);
  return url.searchParams.get(name);
}

function f(v, n = 2) {
  if (v == null || Number.isNaN(Number(v))) return "-";
  return Number(v).toFixed(n);
}

function computeComparison(session) {
  const rows = [];
  for (const [idx, t] of (session.trades || []).entries()) {
    const se = t.entry_price;
    const ssl = t.stop_loss;
    const stp = t.take_profit;

    const me = t.manual_entry_price ?? se;
    const msl = t.manual_stop_loss ?? ssl;
    const mtp = t.manual_take_profit ?? stp;

    const dEntry = me != null && se != null ? me - se : null;
    const dSL = msl != null && ssl != null ? msl - ssl : null;
    const dTP = mtp != null && stp != null ? mtp - stp : null;

    rows.push({
      idx: idx + 1,
      t,
      strategy: { entry: se, sl: ssl, tp: stp },
      manual: { entry: me, sl: msl, tp: mtp },
      diff: { entry: dEntry, sl: dSL, tp: dTP },
    });
  }
  return rows;
}

function calcSideMetrics(trades, manual = false) {
  let total = 0;
  let wins = 0;
  let pnl = 0;
  for (const t of trades) {
    const entry = manual ? (t.manual_entry_price ?? t.entry_price) : t.entry_price;
    const exit = manual ? (t.manual_exit_price ?? t.exit_price ?? null) : (t.exit_price ?? null);
    if (entry == null || exit == null) continue;
    total += 1;
    const direction = manual ? (t.manual_direction ?? t.direction) : t.direction;
    const tradePnl = direction === "long" ? (exit - entry) : (entry - exit);
    pnl += tradePnl;
    if (tradePnl > 0) wins += 1;
  }
  return {
    count: total,
    win_rate: total ? (wins / total) * 100 : 0,
    pnl,
  };
}

function renderCards(session) {
  const cards = document.getElementById("cards");
  const sys = session._stats?.system || calcSideMetrics(session.trades || [], false);
  const man = session._stats?.manual || calcSideMetrics(session.trades || [], true);
  const done = (session.trades || []).filter((t) => t.status === "done").length;
  const total = (session.trades || []).length;

  cards.innerHTML = `
    <div class="metric-card"><div class="k">Session</div><div class="v">${session.name}</div></div>
    <div class="metric-card"><div class="k">Progress</div><div class="v">${done}/${total}</div></div>
    <div class="metric-card"><div class="k">System WR</div><div class="v">${f(sys.win_rate)}%</div></div>
    <div class="metric-card"><div class="k">Manual WR</div><div class="v">${f(man.win_rate)}%</div></div>
    <div class="metric-card"><div class="k">System PnL</div><div class="v">${f(sys.pnl, 4)}</div></div>
    <div class="metric-card"><div class="k">Manual PnL</div><div class="v">${f(man.pnl, 4)}</div></div>
  `;
}

function renderTable(session) {
  const body = document.getElementById("compareBody");
  const rows = computeComparison(session);
  body.innerHTML = rows
    .map((r) => {
      const t = r.t;
      return `
        <tr data-trade-id="${t.id}">
          <td>${r.idx}</td>
          <td>
            <div>E:${f(r.strategy.entry, 5)} SL:${f(r.strategy.sl, 5)} TP:${f(r.strategy.tp, 5)}</div>
            <div class="muted">${t.direction.toUpperCase()} · ${t.source}</div>
          </td>
          <td>
            <div>E:${f(r.manual.entry, 5)} SL:${f(r.manual.sl, 5)} TP:${f(r.manual.tp, 5)}</div>
            <div class="muted">${(t.notes || "").slice(0, 120)}</div>
          </td>
          <td>
            <div>ΔE ${f(r.diff.entry, 5)}</div>
            <div>ΔSL ${f(r.diff.sl, 5)}</div>
            <div>ΔTP ${f(r.diff.tp, 5)}</div>
          </td>
          <td>${t.status || "pending"}</td>
          <td>${t.outcome || "-"}</td>
        </tr>
      `;
    })
    .join("");

  body.querySelectorAll("tr[data-trade-id]").forEach((row) => {
    row.addEventListener("click", () => {
      const tradeId = row.dataset.tradeId;
      const candidates = (st.artifacts || [])
        .filter((a) => a.trade_id === tradeId)
        .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
      if (candidates.length) {
        setActiveArtifact(candidates[0].id).catch(console.error);
      }
    });
  });
}

function initReplayChart() {
  const container = document.getElementById("replayChartContainer");
  if (!container || st.replay.chart) return;

  st.replay.chart = LightweightCharts.createChart(container, {
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
  st.replay.series = st.replay.chart.addCandlestickSeries({
    upColor: "#089981",
    downColor: "#f23645",
    wickUpColor: "#089981",
    wickDownColor: "#f23645",
    borderVisible: false,
  });

  const canvas = document.getElementById("replayDrawLayer");
  st.replay.ctx = canvas.getContext("2d");

  const resize = () => {
    const rect = container.getBoundingClientRect();
    st.replay.chart.applyOptions({ width: rect.width, height: rect.height });
    canvas.width = rect.width;
    canvas.height = rect.height;
    drawReplayOverlay();
  };

  window.addEventListener("resize", resize);
  st.replay.chart.timeScale().subscribeVisibleTimeRangeChange(() => drawReplayOverlay());
  resize();
}

function replayTimeToX(time, clamp = false) {
  let x = st.replay.chart.timeScale().timeToCoordinate(time);
  if (x != null || !clamp) return x;
  const vr = st.replay.chart.timeScale().getVisibleRange();
  const canvas = document.getElementById("replayDrawLayer");
  if (!vr || !canvas) return null;
  if (time < vr.from) return 0;
  if (time > vr.to) return canvas.width;
  return null;
}

function replayPriceToY(price, clamp = false) {
  let y = st.replay.series.priceToCoordinate(price);
  if (y != null || !clamp) return y;
  const canvas = document.getElementById("replayDrawLayer");
  if (!canvas) return null;
  const topPrice = st.replay.series.coordinateToPrice(0);
  const bottomPrice = st.replay.series.coordinateToPrice(canvas.height);
  if (topPrice == null || bottomPrice == null) return null;
  if (price > topPrice) return 0;
  if (price < bottomPrice) return canvas.height;
  return null;
}

function replayPointXY(pt, clamp = false) {
  const x = replayTimeToX(pt.time, clamp);
  const y = replayPriceToY(pt.price, clamp);
  if (x == null || y == null) return null;
  return { x, y };
}

function drawReplayOverlay() {
  const ctx = st.replay.ctx;
  const canvas = document.getElementById("replayDrawLayer");
  if (!ctx || !canvas) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const artifact = (st.artifacts || []).find((a) => a.id === st.activeArtifactId);
  if (!artifact) return;
  const drawings = artifact.drawing_snapshot || [];

  for (const d of drawings) {
    const pts = (d.points || []).map((p) => replayPointXY(p, true));
    if (pts.some((p) => !p)) continue;

    ctx.lineWidth = 1.5;
    ctx.strokeStyle = "#2962ff";
    ctx.fillStyle = "#2962ff";

    if (d.type === "trendline" && pts.length === 2) {
      ctx.beginPath();
      ctx.moveTo(pts[0].x, pts[0].y);
      ctx.lineTo(pts[1].x, pts[1].y);
      ctx.stroke();
      continue;
    }

    if (d.type === "hline" && pts.length >= 1) {
      ctx.beginPath();
      ctx.moveTo(0, pts[0].y);
      ctx.lineTo(canvas.width, pts[0].y);
      ctx.stroke();
      continue;
    }

    if (d.type === "rect" && pts.length === 2) {
      const x = Math.min(pts[0].x, pts[1].x);
      const y = Math.min(pts[0].y, pts[1].y);
      const w = Math.abs(pts[1].x - pts[0].x);
      const h = Math.abs(pts[1].y - pts[0].y);
      ctx.globalAlpha = 0.14;
      ctx.fillRect(x, y, w, h);
      ctx.globalAlpha = 1;
      ctx.strokeRect(x, y, w, h);
      if (d.note) {
        ctx.fillStyle = "#d1d4dc";
        ctx.font = "11px sans-serif";
        ctx.fillText(d.note, x + 4, y + 14);
      }
      continue;
    }

    if (d.type === "text" && pts.length >= 1) {
      ctx.fillStyle = "#d1d4dc";
      ctx.font = "12px sans-serif";
      ctx.fillText(d.note || "note", pts[0].x + 4, pts[0].y - 4);
      continue;
    }

    if (d.type === "riskreward") {
      const rr = d.rr || null;
      if (!rr) continue;
      const xStart = replayTimeToX(rr.start_time, true);
      const xEnd = replayTimeToX(rr.end_time, true);
      const yEntry = replayPriceToY(rr.entry_price, true);
      const yStop = replayPriceToY(rr.stop_price, true);
      const yTP = replayPriceToY(rr.take_price, true);
      if (xStart == null || xEnd == null || yEntry == null || yStop == null || yTP == null) continue;
      const width = Math.max(8, Math.abs(xEnd - xStart));
      const leftX = Math.min(xStart, xEnd);
      ctx.globalAlpha = REPLAY_RR_FILL_ALPHA;
      ctx.fillStyle = "#f23645";
      ctx.fillRect(leftX, Math.min(yEntry, yStop), width, Math.abs(yEntry - yStop));
      ctx.fillStyle = "#089981";
      ctx.fillRect(leftX, Math.min(yEntry, yTP), width, Math.abs(yEntry - yTP));
      ctx.globalAlpha = 1;
      ctx.fillStyle = "#fff";
      ctx.font = "bold 10px sans-serif";
      ctx.fillText(`E ${f(rr.entry_price, 2)} SL ${f(rr.stop_price, 2)} TP ${f(rr.take_price, 2)}`, leftX + 6, yEntry - 6);
    }
  }
}

async function setActiveArtifact(artifactId) {
  st.activeArtifactId = artifactId;
  renderArtifacts();

  const a = (st.artifacts || []).find((x) => x.id === artifactId);
  if (!a || !st.selected) return;
  const src = `/data/${String(a.file || "").replace(/^data\//, "")}`;
  const snap = document.getElementById("replaySnapshot");
  if (snap) {
    snap.src = src;
    snap.classList.remove("hidden");
  }

  const wrap = document.querySelector(".analytics-replay-wrap");
  const cap = (a.chart_state && a.chart_state.capture_size) ? a.chart_state.capture_size : null;
  if (wrap) {
    if (cap && cap.width && cap.height) {
      wrap.style.aspectRatio = `${Number(cap.width)} / ${Number(cap.height)}`;
      wrap.style.height = "auto";
      wrap.style.maxHeight = "70vh";
    } else {
      wrap.style.aspectRatio = "";
      wrap.style.height = "420px";
      wrap.style.maxHeight = "";
    }
  }

  const cs = a.chart_state || {};
  const symbol = cs.symbol || st.selected.symbol;
  const timeframe = String(cs.timeframe || st.selected.timeframe || "1");
  const assetType = cs.asset_type || st.selected.asset_type || "crypto";
  const cacheKey = `${symbol}|${timeframe}|${assetType}`;
  let data = st.replay.candleCache[cacheKey];
  if (!data) {
    data = await api(`/api/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&asset_type=${encodeURIComponent(assetType)}&limit=20000`);
    st.replay.candleCache[cacheKey] = data;
  }
  st.replay.candles = data.candles || [];
  st.replay.series.setData(st.replay.candles);

  const vr = cs.visible_range || null;
  if (vr && vr.from != null && vr.to != null) {
    const fromTs = Number(vr.from);
    const toTs = Number(vr.to);
    const candles = st.replay.candles;
    if (candles.length) {
      let fromIdx = 0;
      let toIdx = candles.length - 1;
      for (let i = 0; i < candles.length; i += 1) {
        if (candles[i].time >= fromTs) {
          fromIdx = i;
          break;
        }
      }
      for (let i = candles.length - 1; i >= 0; i -= 1) {
        if (candles[i].time <= toTs) {
          toIdx = i;
          break;
        }
      }
      const fromTime = candles[Math.max(0, fromIdx)]?.time ?? fromTs;
      const toTime = candles[Math.max(fromIdx, toIdx)]?.time ?? toTs;
      st.replay.chart.timeScale().setVisibleRange({ from: Number(fromTime), to: Number(toTime) });
    } else {
      st.replay.chart.timeScale().setVisibleRange({ from: fromTs, to: toTs });
    }
  } else {
    st.replay.chart.timeScale().fitContent();
  }

  const trade = a.trade_snapshot || {};
  document.getElementById("replayMeta").textContent = [
    `${symbol} ${timeframe}`,
    a.tag || "artifact",
    trade.id ? `trade ${trade.id}` : "session",
    a.note ? `note: ${a.note}` : "",
  ].filter(Boolean).join(" · ");

  drawReplayOverlay();
  requestAnimationFrame(drawReplayOverlay);
  setTimeout(drawReplayOverlay, 50);
}

async function loadSessions(selectedId = null) {
  const res = await api("/api/sessions");
  st.sessions = res.sessions || [];
  const sel = document.getElementById("sessionSelect");
  sel.innerHTML = st.sessions
    .map((s) => `<option value="${s.id}">${s.name} · ${s.symbol} ${s.timeframe} (${s.done_count}/${s.trade_count})</option>`)
    .join("");
  if (!st.sessions.length) return;
  const id = selectedId || qp("session") || st.sessions[0].id;
  sel.value = id;
  await loadSession(id);
}

async function loadSession(id) {
  const body = document.getElementById("compareBody");
  const root = document.getElementById("artifactGallery");
  try {
    st.selected = await api(`/api/sessions/${id}`);
  } catch (e) {
    console.error("session load failed", e);
    body.innerHTML = `<tr><td colspan="6" class="muted">Failed to load session. It may be corrupted; create a new session or re-open another one.</td></tr>`;
    root.innerHTML = `<div class="muted">Artifacts unavailable for this session.</div>`;
    return;
  }
  try {
    st.selected._stats = await api(`/api/sessions/${id}/stats`);
  } catch (e) {
    console.warn("stats load failed", e);
  }
  renderCards(st.selected);
  renderTable(st.selected);
  await loadArtifacts(id);
}

async function loadArtifacts(sessionId) {
  const payload = await api(`/api/sessions/${sessionId}/artifacts`);
  st.artifacts = (payload.artifacts || []).slice().sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
  renderArtifacts();

  if (st.artifacts.length) {
    const preferred = st.artifacts.find((a) => a.trade_id) || st.artifacts[0];
    await setActiveArtifact(preferred.id);
  } else {
    st.activeArtifactId = null;
    document.getElementById("replayMeta").textContent = "No screenshots saved for this session yet.";
    drawReplayOverlay();
  }
}

function renderArtifacts() {
  const root = document.getElementById("artifactGallery");
  const items = st.artifacts || [];
  if (!items.length) {
    root.innerHTML = `<div class="muted">No screenshots saved for this session yet.</div>`;
    return;
  }

  root.innerHTML = items
    .map((a) => {
      const src = `/data/${String(a.file || "").replace(/^data\//, "")}`;
      const activeCls = a.id === st.activeArtifactId ? "active" : "";
      return `
        <div class="artifact-card ${activeCls}" data-artifact-id="${a.id}">
          <img src="${src}" alt="artifact" />
          <div class="meta">
            <div>${a.tag || "artifact"} · ${a.trade_id || "session"}</div>
            <div>${(a.note || "").slice(0, 80)}</div>
          </div>
        </div>
      `;
    })
    .join("");

  root.querySelectorAll("[data-artifact-id]").forEach((el) => {
    el.addEventListener("click", () => {
      setActiveArtifact(el.dataset.artifactId).catch(console.error);
    });
  });
}

function bind() {
  document.getElementById("sessionSelect").addEventListener("change", (e) => loadSession(e.target.value).catch(console.error));
  document.getElementById("refreshBtn").addEventListener("click", () => loadSessions(document.getElementById("sessionSelect").value).catch(console.error));
  document.getElementById("openReviewBtn").addEventListener("click", () => {
    const id = document.getElementById("sessionSelect").value;
    window.location.href = id ? `/?session=${encodeURIComponent(id)}` : "/";
  });
  document.getElementById("openSessionBtn").addEventListener("click", () => {
    const id = document.getElementById("sessionSelect").value;
    window.location.href = id ? `/?session=${encodeURIComponent(id)}` : "/";
  });
}

async function main() {
  initReplayChart();
  bind();
  await loadSessions();
}

main().catch(console.error);
