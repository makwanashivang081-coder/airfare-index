const state = {
  data: null,
  tab: "home",
  routeId: null,
  proofRouteId: "DEL-CCU",
  proof: null,
  fares: null,
  fareFilter: "all",
  liveFilter: "live",
  loadingFares: false,
  loadingProof: false,
  liveRaw: null,
};

const TABS = ["home", "routes", "live", "proof"];

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[ch]);
}

function rupee(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return "₹" + Math.round(Number(n)).toLocaleString("en-IN");
}

function fmtDate(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

function selectedRoute() {
  return (state.data?.market || []).find((row) => row.id === state.routeId) || state.data?.market?.[0];
}

function drawLineChart(host, points, opts = {}) {
  host.innerHTML = "";
  if (!points || !points.length) {
    host.innerHTML = `<p class="chart-empty">No chart data for this day yet.</p>`;
    return;
  }
  const series =
    points.length === 1
      ? [points[0], { ...points[0], label: points[0].label, fullLabel: points[0].fullLabel }]
      : points;
  const width = 640;
  const height = opts.height || 220;
  const pad = { l: opts.padL || 56, r: 16, t: 16, b: 28 };
  const ys = series.map((p) => p.y).filter((v) => Number.isFinite(v));
  if (ys.length < 1) {
    host.innerHTML = `<p class="chart-empty">No chart data for this day yet.</p>`;
    return;
  }
  const min = opts.min != null ? opts.min : Math.min(...ys);
  const max = opts.max != null ? opts.max : Math.max(...ys);
  const span = max - min || 1;
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const xAt = (i) => pad.l + (i / Math.max(1, series.length - 1)) * innerW;
  const yAt = (v) => pad.t + (1 - (v - min) / span) * innerH;
  const line = series.map((p, i) => `${xAt(i)},${yAt(p.y)}`).join(" ");
  const area = `${pad.l},${pad.t + innerH} ${line} ${pad.l + innerW},${pad.t + innerH}`;
  let grid = "";
  for (let i = 0; i <= 4; i += 1) {
    const v = min + (span * i) / 4;
    const y = yAt(v);
    grid += `<line class="grid" x1="${pad.l}" x2="${width - pad.r}" y1="${y}" y2="${y}"></line>`;
    grid += `<text class="axis" x="4" y="${y + 3}">${opts.formatY ? opts.formatY(v) : v.toFixed(1)}</text>`;
  }
  const labelEvery = Math.max(1, Math.ceil(series.length / 6));
  let xlabels = "";
  series.forEach((p, i) => {
    if (i % labelEvery === 0 || i === series.length - 1) {
      xlabels += `<text class="axis" x="${xAt(i)}" y="${height - 8}" text-anchor="middle">${esc(p.label)}</text>`;
    }
  });
  let baseline = "";
  if (opts.baseline != null) {
    const y = yAt(opts.baseline);
    baseline = `<line class="base" x1="${pad.l}" x2="${width - pad.r}" y1="${y}" y2="${y}"></line>`;
  }
  const wrap = document.createElement("div");
  wrap.className = "chart-wrap";
  wrap.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(opts.aria || "Chart")}">
      ${grid}${baseline}${xlabels}
      <polygon class="area" points="${area}"></polygon>
      <polyline class="line" points="${line}"></polyline>
      <circle class="dot" r="4" cx="${xAt(series.length - 1)}" cy="${yAt(series[series.length - 1].y)}"></circle>
    </svg>
    <div class="tooltip"></div>`;
  host.appendChild(wrap);
  const svg = wrap.querySelector("svg");
  const tip = wrap.querySelector(".tooltip");
  const dot = wrap.querySelector(".dot");
  svg.addEventListener("mousemove", (event) => {
    const box = svg.getBoundingClientRect();
    const ratio = (event.clientX - box.left) / box.width;
    const i = Math.min(series.length - 1, Math.max(0, Math.round(ratio * (series.length - 1))));
    const p = series[i];
    dot.setAttribute("cx", String(xAt(i)));
    dot.setAttribute("cy", String(yAt(p.y)));
    tip.style.display = "block";
    tip.style.left = `${((xAt(i) / width) * 100).toFixed(2)}%`;
    tip.style.top = `${(yAt(p.y) / height) * 100}%`;
    tip.textContent = `${p.fullLabel || p.label}  ·  ${opts.formatY ? opts.formatY(p.y) : p.y}`;
  });
  svg.addEventListener("mouseleave", () => {
    tip.style.display = "none";
  });
}

function renderHome() {
  const data = state.data;
  const idx = data.index;
  const value = idx.index_value;
  const vsStart = value - 100;
  const demo = data.demo || {};
  document.getElementById("asof").textContent = fmtDate(data.as_of);
  document.getElementById("foot-mode").textContent = "";
  const ticketInr = data.typical_ticket_inr;
  document.getElementById("kpi-index").textContent =
    ticketInr != null ? rupee(ticketInr) : value.toFixed(2);
  const delta = document.getElementById("kpi-delta");
  if (idx.change_mom == null) {
    delta.textContent = "";
    delta.className = "score-delta";
  } else {
    const dir = idx.change_mom > 0 ? "up" : idx.change_mom < 0 ? "down" : "";
    const word = idx.change_mom > 0 ? "up" : idx.change_mom < 0 ? "down" : "flat";
    delta.className = "score-delta " + dir;
    let moneyBit = "";
    if (ticketInr != null && Number.isFinite(idx.change_mom)) {
      const lastMonth = Math.round(ticketInr / (1 + idx.change_mom / 100));
      moneyBit = ` · was about ${rupee(lastMonth)} last month`;
    }
    delta.textContent = `${word} ${Math.abs(idx.change_mom).toFixed(1)}% vs last month${moneyBit}`;
  }
  const higher = vsStart >= 0 ? "higher" : "lower";
  document.getElementById("kpi-meaning").textContent =
    ticketInr != null
      ? `Households pay about ${rupee(ticketInr)} for a typical ticket on this basket today. Air travel is ${Math.abs(vsStart).toFixed(1)}% ${higher} than the start of the series.`
      : `Air travel on this basket is ${Math.abs(vsStart).toFixed(1)}% ${higher} than the starting point of 100.`;

  const monthPts = (data.cost_monthly || []).map((h) => ({
    key: h.period,
    y: h.inr,
    label: h.period.slice(2),
    fullLabel: h.period,
  }));
  drawLineChart(document.getElementById("monthly-cost-chart"), monthPts, {
    height: 220,
    formatY: (v) => "₹" + Math.round(v).toLocaleString("en-IN"),
    aria: "Monthly typical ticket cost in rupees",
  });

  const dayPts = (data.cost_daily || []).map((h) => ({
    key: h.period,
    y: h.inr,
    label: h.period.slice(5),
    fullLabel: fmtDate(h.period),
  }));
  drawLineChart(document.getElementById("daily-cost-chart"), dayPts, {
    height: 180,
    formatY: (v) => "₹" + Math.round(v).toLocaleString("en-IN"),
    aria: "Daily typical ticket cost in rupees",
  });

  drawLineChart(
    document.getElementById("national-chart"),
    (data.history || []).map((h) => ({
      key: h.period,
      y: h.value,
      label: h.period.slice(5),
      fullLabel: fmtDate(h.period),
    })),
    { height: 160, baseline: 100, formatY: (v) => v.toFixed(1), aria: "Daily airfare index" }
  );
  renderModeBanner();
}

function renderModeBanner() {
  const banner = document.getElementById("mode-banner");
  if (!banner) return;
  banner.hidden = true;
  banner.textContent = "";
}

function renderRouteStrip() {
  const host = document.getElementById("route-strip");
  if (!host) return;
  host.innerHTML = (state.data.market || [])
    .map((row) => {
      const on = row.id === state.routeId ? "is-on" : "";
      const price = row.current ? rupee(row.current.price) : "—";
      const idx = row.cpi_index == null ? "—" : row.cpi_index.toFixed(1);
      return `<button type="button" class="route-card ${on}" data-route="${esc(row.id)}" role="option" aria-selected="${row.id === state.routeId}">
        <span class="rc-city">${esc(row.origin_city)} → ${esc(row.destination_city)}</span>
        <span class="rc-code">${esc(row.label)}</span>
        <span class="rc-price">${price}</span>
        <span class="rc-meta">index ${idx}</span>
      </button>`;
    })
    .join("");
}

function renderDetail() {
  const row = selectedRoute();
  if (!row) return;
  document.getElementById("detail-title").textContent =
    `${row.origin_city} → ${row.destination_city}`;
  const pill = document.getElementById("detail-pill");
  const hist = row.index_history || [];
  const latest = hist.length ? hist[hist.length - 1].value : row.cpi_index;
  const first = hist.length ? hist[0].value : 100;
  if (pill) {
    if (latest == null) {
      pill.textContent = "No route index yet";
    } else {
      const delta = latest - first;
      const word = delta >= 0 ? "up" : "down";
      pill.textContent = `Index ${latest.toFixed(1)} · ${word} ${Math.abs(delta).toFixed(1)} pts`;
    }
  }
  const sub = document.getElementById("detail-sub");
  if (sub) {
    sub.textContent = "Route inflation index over time (100 = start). Pick another corridor to compare.";
  }
  drawLineChart(
    document.getElementById("curve-chart"),
    hist.map((h) => ({
      key: h.period,
      y: h.value,
      label: h.period.slice(5),
      fullLabel: fmtDate(h.period),
    })),
    {
      height: 200,
      baseline: 100,
      formatY: (v) => v.toFixed(1),
      aria: `Route inflation index ${row.id}`,
    }
  );
  // Compact stats instead of flat booking-window chips
  const start = hist[0];
  const end = hist[hist.length - 1];
  document.getElementById("lead-grid").innerHTML = [
    start ? `<div class="lead-chip"><span>Start</span><strong>${start.value.toFixed(1)}</strong></div>` : "",
    end ? `<div class="lead-chip"><span>Today</span><strong>${end.value.toFixed(1)}</strong></div>` : "",
    row.current
      ? `<div class="lead-chip"><span>Typical fare today</span><strong>${rupee(row.current.price)}</strong></div>`
      : "",
  ].join("");
}

function renderQuotes() {
  const row = selectedRoute();
  if (!row) return;
  document.getElementById("quotes-title").textContent =
    `Fares · ${row.origin_city} → ${row.destination_city}`;
  const host = document.getElementById("fare-list");
  if (state.loadingFares) {
    host.innerHTML = `<p class="chart-empty">Loading fares…</p>`;
    return;
  }
  let rows = state.fares?.fares || [];
  if (state.fareFilter === "cpi") rows = rows.filter((f) => f.can_enter_cpi);
  if (state.fareFilter === "market") rows = rows.filter((f) => !f.can_enter_cpi);
  if (!rows.length) {
    host.innerHTML = `<p class="chart-empty">Nothing in this filter.</p>`;
    return;
  }
  rows = [...rows].sort((a, b) => a.lead - b.lead || a.total - b.total);
  host.innerHTML = rows
    .map(
      (f) => `<article class="fare-card">
        <div class="fc-top">
          <strong>${esc(f.source_name)}</strong>
          <span class="badge ${f.can_enter_cpi ? "in" : "out"}">${f.can_enter_cpi ? "in inflation index" : "market check"}</span>
          ${f.is_live ? `<span class="badge live">live</span>` : `<span class="badge">sample</span>`}
        </div>
        <div class="fc-row">
          <span>${esc(f.airline_name || f.airline)} · ${esc(f.flight || "—")}</span>
          <span class="num">${f.lead}d ahead</span>
          <span class="num price">${rupee(f.total)}</span>
        </div>
      </article>`
    )
    .join("");
}

function renderLive() {
  const live = state.data?.live || {
    live_count: 0,
    sample_count: 0,
    total_count: 0,
    quotes: [],
    sources: [],
    schedule: {},
  };
  const noteEl = document.getElementById("live-note");
  if (noteEl) noteEl.textContent = "Collected this morning for the fixed basket.";
  const sched = live.schedule || {};
  const run = live.run_summary;
  document.getElementById("live-schedule").innerHTML = run
    ? `<strong>${esc(fmtDate(run.collected_on))}</strong> · ${run.live_ok ?? 0} live · ${run.fixture_fallback ?? 0} sample`
    : `<strong>${esc(sched.label || "Daily collect")}</strong>`;

  document.getElementById("live-kpis").innerHTML = `
    <div class="lk"><span>Total</span><strong>${live.total_count ?? live.quotes?.length ?? 0}</strong></div>
    <div class="lk"><span>Live</span><strong>${live.live_count ?? 0}</strong></div>
    <div class="lk"><span>Sample</span><strong>${live.sample_count ?? 0}</strong></div>
    <div class="lk"><span>Lead</span><strong>T+${live.lead ?? 21}</strong></div>`;

  const sources = live.sources || [];
  const withLive = sources.filter((s) => (s.live || 0) > 0);
  const blocked = sources.filter((s) => (s.live || 0) === 0 && (s.sample || 0) > 0);
  const max = Math.max(1, ...withLive.map((s) => s.live));
  document.getElementById("live-sources").innerHTML = withLive.length
    ? withLive
        .map((s) => {
          const livePct = (s.live / max) * 100;
          return `<div class="sb">
        <div class="sb-label"><strong>${esc(s.source_name)}</strong><span>${s.live} live</span></div>
        <div class="sb-track">
          <i class="sb-live" style="width:${livePct}%"></i>
        </div>
      </div>`;
        })
        .join("")
    : `<p class="chart-empty">No live page reads today.</p>`;

  const blockedEl = document.getElementById("live-blocked");
  if (blockedEl) {
    if (blocked.length) {
      const names = blocked.map((s) => s.source_name).join(", ");
      blockedEl.hidden = false;
      blockedEl.innerHTML = `Also collected as sample: ${esc(names)}`;
    } else {
      blockedEl.hidden = true;
      blockedEl.textContent = "";
    }
  }

  // Quote grid defaults to live pages (see state.liveFilter).

  const grid = document.getElementById("live-grid");
  const rawBox = document.getElementById("live-raw");
  let rows = live.quotes || [];
  if (state.liveFilter === "live") rows = rows.filter((q) => q.is_live);
  if (state.liveFilter === "sample") rows = rows.filter((q) => !q.is_live);
  if (state.liveFilter === "cpi") rows = rows.filter((q) => q.can_enter_cpi);

  if (!rows.length) {
    grid.innerHTML = `<p class="chart-empty">Nothing in this filter for today.</p>`;
    rawBox.hidden = true;
    return;
  }
  grid.innerHTML = rows
    .map((q, i) => {
      const idx = (live.quotes || []).indexOf(q);
      return `<button type="button" class="live-card ${q.is_live ? "is-live" : "is-sample"}" data-live="${idx}">
        <span class="lc-route">${esc(q.route)}</span>
        <span class="lc-src">${esc(q.source_name)}${q.site ? " · " + esc(q.site) : ""}</span>
        <span class="lc-price">${rupee(q.total)}</span>
        <span class="lc-meta">
          <span class="badge ${q.is_live ? "live" : ""}">${q.is_live ? "live" : "sample"}</span>
          <span class="badge ${q.can_enter_cpi ? "in" : "out"}">${q.can_enter_cpi ? "in index" : "market"}</span>
          ${esc(q.airline_name || q.airline || "")} · ${q.lead}d
        </span>
      </button>`;
    })
    .join("");

  grid.querySelectorAll("[data-live]").forEach((btn) => {
    btn.addEventListener("click", () => {
      grid.querySelectorAll(".live-card").forEach((n) => n.classList.remove("is-on"));
      btn.classList.add("is-on");
      const item = live.quotes[Number(btn.dataset.live)];
      rawBox.hidden = false;
      rawBox.textContent = JSON.stringify(
        {
          observation_id: item.id,
          raw_id: item.raw_id,
          route: item.route,
          source: item.source_name,
          collection: item.collection,
          site: item.site,
          raw: item.raw,
        },
        null,
        2
      );
    });
  });
}

function renderImprovements() {
  const host = document.getElementById("improve-list");
  const rows = state.data.improvements || [];
  host.innerHTML = rows
    .map(
      (row) => `<article class="improve-card">
        <h3>${esc(row.title || row.id)}</h3>
        <p class="improve-why">${esc(row.why_government_cares || row.we_add)}</p>
      </article>`
    )
    .join("");
}

function renderProof() {
  const select = document.getElementById("proof-route");
  select.innerHTML = (state.data.market || [])
    .map(
      (row) =>
        `<option value="${esc(row.id)}" ${row.id === state.proofRouteId ? "selected" : ""}>${esc(row.origin_city)} → ${esc(row.destination_city)}</option>`
    )
    .join("");

  const proof = state.proof || state.data.proof;
  const host = document.getElementById("proof-chain");
  const rawBox = document.getElementById("proof-raw");
  const receipt = document.getElementById("proof-receipt");
  const rawToggle = document.getElementById("proof-raw-toggle");
  const storyEl = document.getElementById("proof-story");
  const msgEl = document.getElementById("proof-receipt-msg");
  rawBox.hidden = true;
  rawBox.textContent = "";
  receipt.hidden = true;
  receipt.innerHTML = "";
  rawToggle.hidden = true;

  if (state.loadingProof) {
    host.innerHTML = `<div class="step"><p>Loading…</p></div>`;
    return;
  }
  if (!proof) {
    host.innerHTML = `<div class="step"><p>No proof loaded.</p></div>`;
    return;
  }

  if (proof.story) {
    storyEl.textContent = proof.story.headline;
  } else if (proof.spec?.one_liner) {
    storyEl.textContent = proof.spec.one_liner;
  }

  const national = proof.national;
  const route = proof.route_index;
  document.getElementById("proof-summary").textContent = "Click a quote to open its receipt.";
  msgEl.textContent = "";

  const steps = [
    `<div class="step step-num"><strong>1 · National</strong><p>${
      national ? `<span class="big-num">${national.value}</span>` : "—"
    }</p></div>`,
    `<div class="step step-num"><strong>2 · ${esc(proof.route_id)}</strong><p>${
      route ? `<span class="big-num">${route.value}</span>` : "—"
    }</p></div>`,
    `<div class="step step-num"><strong>3 · Quotes in the index</strong><p>Select one below.</p></div>`,
  ];

  const obs = (proof.cpi_observations || [])
    .map(
      (o, i) => `<button type="button" class="obs ${o.is_live ? "is-live" : "is-sample"}" data-obs="${i}">
        <span>${esc(o.source_name)} · ${esc(o.flight)}</span>
        <span class="badge ${o.is_live ? "live" : ""}">${o.is_live ? "live" : "sample"}</span>
        <span>${o.lead}d</span>
        <span class="num">${rupee(o.total)}</span>
        <span class="badge in">open</span>
      </button>`
    )
    .join("");

  host.innerHTML =
    steps.join("") +
    (obs || `<div class="step"><p>No quotes for this route today.</p></div>`);

  let selected = null;
  host.querySelectorAll("[data-obs]").forEach((btn) => {
    btn.addEventListener("click", () => {
      host.querySelectorAll(".obs").forEach((node) => node.classList.remove("is-on"));
      btn.classList.add("is-on");
      selected = proof.cpi_observations[Number(btn.dataset.obs)];
      receipt.hidden = false;
      receipt.innerHTML = `
        <div class="receipt-top">
          <div>
            <p class="eyebrow">Receipt</p>
            <h3>${esc(selected.source_name)} · ${esc(selected.flight)}</h3>
          </div>
          <p class="receipt-price">${rupee(selected.total)}</p>
        </div>
        <dl class="receipt-grid">
          <div><dt>Route</dt><dd>${esc(proof.route_id)}</dd></div>
          <div><dt>Lead</dt><dd>T+${selected.lead}</dd></div>
          <div><dt>Type</dt><dd>${esc(selected.collection || (selected.is_live ? "LIVE" : "SAMPLE"))}</dd></div>
          <div><dt>Source</dt><dd>${esc(selected.site || selected.source_name)}</dd></div>
        </dl>`;
      rawToggle.hidden = false;
      rawBox.hidden = true;
      rawBox.textContent = JSON.stringify(
        {
          observation_id: selected.observation_id,
          raw_id: selected.raw_id,
          source: selected.source_name,
          collection: selected.collection,
          site: selected.site,
          raw: selected.raw,
        },
        null,
        2
      );
    });
  });

  rawToggle.onclick = () => {
    if (!selected) return;
    rawBox.hidden = !rawBox.hidden;
    rawToggle.textContent = rawBox.hidden ? "Show raw JSON" : "Hide raw JSON";
  };
}

async function loadFares(routeId) {
  const row = (state.data.market || []).find((item) => item.id === routeId);
  if (!row) return;
  state.loadingFares = true;
  renderQuotes();
  try {
    const res = await fetch(
      `/api/v1/fares?origin=${encodeURIComponent(row.origin)}&destination=${encodeURIComponent(row.destination)}&date=${encodeURIComponent(state.data.as_of)}`
    );
    if (!res.ok) throw new Error("fares " + res.status);
    state.fares = await res.json();
  } catch (err) {
    state.fares = { fares: [] };
  } finally {
    state.loadingFares = false;
    renderQuotes();
  }
}

async function loadProof(routeId) {
  state.proofRouteId = routeId;
  state.loadingProof = true;
  renderProof();
  try {
    const res = await fetch(
      `/api/v1/proof/routes/${encodeURIComponent(routeId)}?date=${encodeURIComponent(state.data.as_of)}`
    );
    if (!res.ok) throw new Error("proof " + res.status);
    state.proof = await res.json();
  } catch (err) {
    state.proof = state.data.proof;
  } finally {
    state.loadingProof = false;
    renderProof();
  }
}

function selectRoute(routeId, { openRoutes = false } = {}) {
  state.routeId = routeId;
  renderRouteStrip();
  renderDetail();
  renderQuotes();
  loadFares(routeId);
  if (openRoutes) {
    showTab("routes");
    history.replaceState(null, "", "#routes");
  }
}

function showTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.classList.toggle("is-on", btn.dataset.tab === tab);
  });
  document.querySelectorAll(".view").forEach((section) => {
    section.hidden = section.dataset.view !== tab;
  });
  if (tab === "live") renderLive();
  if (tab === "routes") {
    renderRouteStrip();
    renderDetail();
  }
}

function bind() {
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      showTab(tab);
      history.replaceState(null, "", tab === "home" ? location.pathname : `#${tab}`);
    });
  });
  document.getElementById("route-strip").addEventListener("click", (event) => {
    const btn = event.target.closest("[data-route]");
    if (!btn) return;
    selectRoute(btn.dataset.route);
  });
  document.getElementById("fare-filters").addEventListener("click", (event) => {
    const btn = event.target.closest("[data-filter]");
    if (!btn) return;
    state.fareFilter = btn.dataset.filter;
    document.querySelectorAll("#fare-filters .chip").forEach((node) => {
      node.classList.toggle("is-on", node === btn);
    });
    renderQuotes();
  });
  document.getElementById("live-filters").addEventListener("click", (event) => {
    const btn = event.target.closest("[data-live-filter]");
    if (!btn) return;
    state.liveFilter = btn.dataset.liveFilter;
    document.querySelectorAll("#live-filters .chip").forEach((node) => {
      node.classList.toggle("is-on", node === btn);
    });
    renderLive();
  });
  document.getElementById("proof-route").addEventListener("change", (event) => {
    loadProof(event.target.value);
  });
  document.querySelectorAll("[data-go]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.getAttribute("data-go");
      if (!TABS.includes(tab)) return;
      showTab(tab);
      history.replaceState(null, "", tab === "home" ? location.pathname : `#${tab}`);
    });
  });
}

async function boot() {
  const hash = location.hash.replace("#", "");
  if (TABS.includes(hash)) state.tab = hash;
  try {
    const res = await fetch("/api/v1/analytics/overview");
    if (!res.ok) throw new Error("API " + res.status);
    state.data = await res.json();
    state.routeId = state.data.market?.[0]?.id;
    document.getElementById("boot").hidden = true;
    document.getElementById("main").hidden = false;
    bind();
    renderHome();
    renderRouteStrip();
    renderDetail();
    renderLive();
    renderImprovements();
    showTab(state.tab);
    await loadFares(state.routeId);
    await loadProof(state.proofRouteId);
  } catch (err) {
    document.getElementById("boot").hidden = true;
    const crash = document.getElementById("crash");
    crash.hidden = false;
    crash.textContent = "Could not load the index. " + err.message;
  }
}

boot();
