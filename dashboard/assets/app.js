const state = {
  data: null,
  tab: "home",
  routeId: null,
  fares: null,
  fareFilter: "all",
  loadingFares: false,
};

const TABS = ["home", "routes", "about"];

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
  if (!points || points.length < 2) {
    host.textContent = "Not enough points to chart.";
    return;
  }
  const width = 640;
  const height = opts.height || 220;
  const pad = { l: 44, r: 16, t: 16, b: 28 };
  const ys = points.map((p) => p.y);
  const min = opts.min != null ? opts.min : Math.min(...ys);
  const max = opts.max != null ? opts.max : Math.max(...ys);
  const span = max - min || 1;
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const xAt = (i) => pad.l + (i / (points.length - 1)) * innerW;
  const yAt = (v) => pad.t + (1 - (v - min) / span) * innerH;
  const line = points.map((p, i) => `${xAt(i)},${yAt(p.y)}`).join(" ");
  const area = `${pad.l},${pad.t + innerH} ${line} ${pad.l + innerW},${pad.t + innerH}`;
  let grid = "";
  for (let i = 0; i <= 4; i += 1) {
    const v = min + (span * i) / 4;
    const y = yAt(v);
    grid += `<line class="grid" x1="${pad.l}" x2="${width - pad.r}" y1="${y}" y2="${y}"></line>`;
    grid += `<text class="axis" x="4" y="${y + 3}">${opts.formatY ? opts.formatY(v) : v.toFixed(1)}</text>`;
  }
  const labelEvery = Math.max(1, Math.ceil(points.length / 6));
  let xlabels = "";
  points.forEach((p, i) => {
    if (i % labelEvery === 0 || i === points.length - 1) {
      xlabels += `<text class="axis" x="${xAt(i)}" y="${height - 8}" text-anchor="middle">${esc(p.label)}</text>`;
    }
  });
  let baseline = "";
  if (opts.baseline != null) {
    const y = yAt(opts.baseline);
    baseline = `<line class="base" x1="${pad.l}" x2="${width - pad.r}" y1="${y}" y2="${y}"></line>`;
  }
  const wrap = document.createElement("div");
  wrap.style.position = "relative";
  wrap.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(opts.aria || "Chart")}">
      ${grid}${baseline}${xlabels}
      <polygon class="area" points="${area}"></polygon>
      <polyline class="line" points="${line}"></polyline>
      <circle class="dot" r="4" cx="${xAt(points.length - 1)}" cy="${yAt(points[points.length - 1].y)}"></circle>
    </svg>
    <div class="tooltip"></div>`;
  host.appendChild(wrap);
  const svg = wrap.querySelector("svg");
  const tip = wrap.querySelector(".tooltip");
  const dot = wrap.querySelector(".dot");
  svg.addEventListener("mousemove", (event) => {
    const box = svg.getBoundingClientRect();
    const ratio = (event.clientX - box.left) / box.width;
    const i = Math.min(points.length - 1, Math.max(0, Math.round(ratio * (points.length - 1))));
    const p = points[i];
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
  document.getElementById("asof").textContent = fmtDate(data.as_of);
  document.getElementById("kpi-index").textContent = value.toFixed(2);
  const delta = document.getElementById("kpi-delta");
  if (idx.change_mom == null) {
    delta.textContent = "";
    delta.className = "hero-delta";
  } else {
    const dir = idx.change_mom > 0 ? "up" : idx.change_mom < 0 ? "down" : "";
    const word = idx.change_mom > 0 ? "up" : idx.change_mom < 0 ? "down" : "unchanged";
    delta.className = "hero-delta " + dir;
    delta.textContent = `${word} ${Math.abs(idx.change_mom).toFixed(1)}% vs last month`;
  }
  const higher = vsStart >= 0 ? "higher" : "lower";
  document.getElementById("kpi-meaning").textContent =
    `100 is the first month in this demo. ${value.toFixed(1)} means fares in this 8-route basket are about ${Math.abs(vsStart).toFixed(1)}% ${higher} than that start.`;

  const points = (data.history || []).map((h) => ({
    key: h.period,
    y: h.value,
    label: h.period.slice(5),
    fullLabel: fmtDate(h.period),
  }));
  drawLineChart(document.getElementById("national-chart"), points, {
    baseline: 100,
    formatY: (v) => v.toFixed(1),
    aria: "Daily airfare index",
  });

  const east = data.market.find((r) => r.id === "DEL-CCU");
  const note = document.getElementById("table-note");
  if (east && east.cpi_index != null && east.cpi_index >= 130) {
    note.textContent = "Delhi → Kolkata is high in this demo (a built-in shock). That is why the East looks expensive — not a site error.";
  } else {
    note.textContent = "";
  }
}

function renderRoutesTable() {
  const select = document.getElementById("quote-route");
  select.innerHTML = state.data.market
    .map(
      (row) =>
        `<option value="${esc(row.id)}" ${row.id === state.routeId ? "selected" : ""}>${esc(row.origin_city)} → ${esc(row.destination_city)}</option>`
    )
    .join("");
  document.querySelector("#route-table tbody").innerHTML = state.data.market
    .map((row) => {
      const on = row.id === state.routeId ? "is-on" : "";
      return `<tr class="${on}" data-route="${esc(row.id)}" tabindex="0">
        <td><strong>${esc(row.label)}</strong><span class="cities">${esc(row.origin_city)} → ${esc(row.destination_city)}</span></td>
        <td class="num">${row.current ? rupee(row.current.price) : "—"}</td>
        <td class="num">${row.cpi_index == null ? "—" : row.cpi_index.toFixed(1)}</td>
      </tr>`;
    })
    .join("");
}

function renderDetail() {
  const row = selectedRoute();
  if (!row) return;
  document.getElementById("detail-title").textContent =
    `${row.origin_city} → ${row.destination_city}`;
  const points = (row.curve || []).map((c) => ({
    key: String(c.lead).padStart(2, "0"),
    y: c.price,
    label: `${c.lead}d`,
    fullLabel: `Book ${c.lead} day${c.lead === 1 ? "" : "s"} ahead`,
  }));
  drawLineChart(document.getElementById("curve-chart"), points, {
    height: 180,
    formatY: (v) => rupee(v),
    aria: `Fares by booking window ${row.id}`,
  });
  document.getElementById("lead-grid").innerHTML = (row.curve || [])
    .map((c) => `<div><span>${c.lead === 1 ? "Tomorrow" : `${c.lead} days ahead`}</span><strong>${rupee(c.price)}</strong></div>`)
    .join("");
}

function renderQuotes() {
  const row = selectedRoute();
  if (!row) return;
  document.getElementById("quotes-title").textContent =
    `Fares collected · ${row.origin_city} → ${row.destination_city}`;
  const body = document.querySelector("#fare-table tbody");
  if (state.loadingFares) {
    body.innerHTML = `<tr><td colspan="5">Loading…</td></tr>`;
    return;
  }
  let rows = state.fares?.fares || [];
  if (state.fareFilter === "cpi") rows = rows.filter((f) => f.can_enter_cpi);
  if (state.fareFilter === "market") rows = rows.filter((f) => !f.can_enter_cpi);
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="5">Nothing in this filter.</td></tr>`;
    return;
  }
  rows.sort((a, b) => a.lead - b.lead || a.total - b.total);
  body.innerHTML = rows
    .map(
      (f) => `<tr>
        <td>${esc(f.source_name)}</td>
        <td><span class="chip ${f.can_enter_cpi ? "in" : "out"}">${f.can_enter_cpi ? "yes" : "no"}</span></td>
        <td class="num">${f.lead} days</td>
        <td class="num">${rupee(f.total)}</td>
        <td>${esc(f.airline_name || f.airline)}</td>
      </tr>`
    )
    .join("");
}

function renderAbout() {
  document.getElementById("source-list").innerHTML = state.data.sources
    .map((s) => {
      const role = s.can_enter_cpi ? "used in the index" : s.enabled ? "market only" : "off";
      return `<div class="source-row"><strong>${esc(s.name)}</strong><span>${esc(role)}</span></div>`;
    })
    .join("");
}

function showTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.classList.toggle("is-on", btn.dataset.tab === tab);
  });
  document.querySelectorAll(".view").forEach((section) => {
    section.hidden = section.dataset.view !== tab;
  });
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

function selectRoute(routeId, { openRoutes = false } = {}) {
  state.routeId = routeId;
  renderRoutesTable();
  renderDetail();
  renderQuotes();
  loadFares(routeId);
  if (openRoutes) {
    showTab("routes");
    history.replaceState(null, "", "#routes");
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
  document.querySelector("#route-table tbody").addEventListener("click", (event) => {
    const tr = event.target.closest("tr[data-route]");
    if (!tr) return;
    selectRoute(tr.dataset.route, { openRoutes: true });
  });
  document.getElementById("quote-route").addEventListener("change", (event) => {
    selectRoute(event.target.value);
  });
  document.getElementById("fare-filters").addEventListener("click", (event) => {
    const btn = event.target.closest("[data-filter]");
    if (!btn) return;
    state.fareFilter = btn.dataset.filter;
    document.querySelectorAll("#fare-filters .chip-btn").forEach((node) => {
      node.classList.toggle("is-on", node === btn);
    });
    renderQuotes();
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
    renderRoutesTable();
    renderDetail();
    renderAbout();
    showTab(state.tab);
    await loadFares(state.routeId);
  } catch (err) {
    document.getElementById("boot").hidden = true;
    const crash = document.getElementById("crash");
    crash.hidden = false;
    crash.textContent = "Could not load the index. " + err.message;
  }
}

boot();
