const state = {
  data: null,
  tab: "overview",
  routeId: null,
  fares: null,
  fareFilter: "all",
  loadingFares: false,
};

const TABS = ["overview", "realtime", "cpi", "quotes", "method"];

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

function pct(n, digits = 1) {
  if (n == null) return "n/a";
  const sign = n > 0 ? "▲" : n < 0 ? "▼" : "•";
  return `${sign} ${Math.abs(n).toFixed(digits)}%`;
}

function selectedRoute() {
  return (state.data?.market || []).find((row) => row.id === state.routeId) || state.data?.market?.[0];
}

function lastMinutePremium(curve) {
  const d1 = (curve || []).find((c) => c.lead === 1);
  const d21 = (curve || []).find((c) => c.lead === 21);
  if (!d1 || !d21 || !d21.price) return null;
  return (d1.price / d21.price - 1) * 100;
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
  const ticks = 4;
  let grid = "";
  for (let i = 0; i <= ticks; i += 1) {
    const v = min + (span * i) / ticks;
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
  let bands = "";
  (opts.bands || []).forEach((band) => {
    const i0 = points.findIndex((p) => p.key >= band.start);
    const i1 = points.reduce((acc, p, i) => (p.key <= band.end ? i : acc), -1);
    if (i0 < 0 || i1 < 0 || i1 < i0) return;
    const x = xAt(i0);
    const w = Math.max(6, xAt(i1) - xAt(i0));
    bands += `<rect class="band" x="${x}" y="${pad.t}" width="${w}" height="${innerH}"></rect>`;
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
      ${grid}${bands}${baseline}
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

function drawBars(host, rows) {
  host.innerHTML = "";
  if (!rows.length) {
    host.textContent = "No regional index for this day.";
    return;
  }
  const width = 640;
  const rowH = 36;
  const height = 16 + rows.length * rowH;
  const pad = { l: 86, r: 54, t: 8, b: 8 };
  const max = Math.max(100, ...rows.map((r) => r.value));
  const innerW = width - pad.l - pad.r;
  const bars = rows
    .map((row, i) => {
      const y = pad.t + i * rowH;
      const w = (row.value / max) * innerW;
      const alert = row.value >= 130;
      return `
        <text class="axis" x="8" y="${y + 16}">${esc(row.key)}</text>
        <rect x="${pad.l}" y="${y + 4}" width="${w}" height="18" rx="4" fill="${alert ? "#9f1239" : "#1b3a5f"}"></rect>
        <text class="axis" x="${pad.l + w + 8}" y="${y + 17}">${row.value.toFixed(2)}</text>`;
    })
    .join("");
  host.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Regional CPI">${bars}</svg>`;
}

function renderHeader() {
  const data = state.data;
  const idx = data.index;
  document.getElementById("asof").textContent = `as of ${fmtDate(data.as_of)}`;
  document.getElementById("kpi-index").textContent = idx.index_value.toFixed(2);
  const delta = document.getElementById("kpi-delta");
  delta.textContent = `${pct(idx.change_mom)} MoM  ·  YoY ${pct(idx.change_yoy)}  ·  ${idx.confidence} confidence`;
  delta.className = "kpi-delta" + (idx.change_mom > 0 ? " up" : idx.change_mom < 0 ? " down" : "");
  document.getElementById("kpi-read").textContent = idx.reading;
  document.getElementById("kpi-t7").textContent = rupee(data.realtime_median_t7);
  document.getElementById("kpi-cov").textContent =
    `${Math.round(idx.coverage * 100)}% coverage · ${idx.cpi_observations} CPI quotes · ${idx.observations} observed`;
  const method = data.methodology;
  document.getElementById("facts").innerHTML = [
    ["Basket", `${data.market.length} domestic routes`],
    ["Method", `${method.elementary} · v${method.version}`],
    ["CPI lead", `T+${method.domestic_lead} economy`],
    ["HTTP scrape", method.allow_live_http ? "on" : "off"],
  ]
    .map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`)
    .join("");
  document.getElementById("foot-ver").textContent = method.version;
  document.getElementById("foot-basket").textContent = method.basket_id;
}

function renderCallouts() {
  const host = document.getElementById("callouts");
  const items = (state.data.callouts || []).filter((item) => item.tone === "alert" || item.tone === "info");
  host.innerHTML = items
    .map(
      (item) =>
        `<article class="callout ${esc(item.tone)}"><h3>${esc(item.title)}</h3><p>${esc(item.body)}</p></article>`
    )
    .join("");
}

function renderNationalChart() {
  const hist = state.data.history || [];
  const points = hist.map((h) => ({
    key: h.period,
    y: h.value,
    label: h.period.slice(5),
    fullLabel: fmtDate(h.period),
  }));
  const bands = (state.data.events || [])
    .filter((event) => event.on === "collected_on")
    .map((event) => ({ start: event.start, end: event.end, title: event.title }));
  drawLineChart(document.getElementById("national-chart"), points, {
    baseline: 100,
    formatY: (v) => v.toFixed(1),
    bands,
    aria: "Daily national APIx",
  });
  document.getElementById("chart-legend").innerHTML = `
    <span><i style="background:#10243f"></i>Daily APIx</span>
    <span><i style="background:#c4b8a4"></i>100 baseline</span>
    <span><i style="background:#f3d0bf"></i>Fixture shock window</span>`;
}

function renderRoutes() {
  const select = document.getElementById("quote-route");
  if (select) {
    select.innerHTML = state.data.market
      .map(
        (row) =>
          `<option value="${esc(row.id)}" ${row.id === state.routeId ? "selected" : ""}>${esc(row.label)} · ${esc(row.origin_city)}</option>`
      )
      .join("");
  }
  const body = document.querySelector("#route-table tbody");
  body.innerHTML = state.data.market
    .map((row) => {
      const on = row.id === state.routeId ? "is-on" : "";
      const vol = String(row.volatility || "LOW").toLowerCase();
      return `<tr class="${on}" data-route="${esc(row.id)}" tabindex="0" role="button" aria-pressed="${row.id === state.routeId ? "true" : "false"}">
        <td><strong>${esc(row.label)}</strong><span class="cities">${esc(row.origin_city)} → ${esc(row.destination_city)}</span></td>
        <td class="num hide-sm">${Math.round(row.cpi_weight * 100)}%</td>
        <td>${esc(row.region)}</td>
        <td class="num">${row.current ? rupee(row.current.price) : "—"}</td>
        <td class="num hide-sm">${row.cpi_index == null ? "—" : row.cpi_index.toFixed(2)}</td>
        <td><span class="chip ${esc(vol)}">${esc(row.volatility)}</span></td>
      </tr>`;
    })
    .join("");
}

function renderDetail() {
  const row = selectedRoute();
  if (!row) return;
  document.getElementById("detail-title").textContent = `Fare escalation · ${row.label}`;
  document.getElementById("detail-lede").textContent =
    `${row.origin_city} to ${row.destination_city}. Real-time booking windows, not the T+21 CPI sample.`;
  const premium = lastMinutePremium(row.curve);
  document.getElementById("detail-pills").innerHTML = [
    row.cpi_index != null ? `<span class="chip">CPI ${row.cpi_index.toFixed(2)}</span>` : "",
    `<span class="chip ${String(row.volatility).toLowerCase()}">${esc(row.volatility)} vol</span>`,
    premium != null ? `<span class="chip">D+1 vs D+21 ${premium > 0 ? "+" : ""}${premium.toFixed(0)}%</span>` : "",
  ].join("");
  const points = (row.curve || []).map((c) => ({
    key: String(c.lead).padStart(2, "0"),
    y: c.price,
    label: `D+${c.lead}`,
    fullLabel: `D+${c.lead}`,
  }));
  drawLineChart(document.getElementById("curve-chart"), points, {
    height: 180,
    formatY: (v) => rupee(v),
    aria: `Fare curve ${row.id}`,
  });
  document.getElementById("lead-grid").innerHTML = (row.curve || [])
    .map((c) => `<div><span>D+${c.lead}</span><strong>${rupee(c.price)}</strong></div>`)
    .join("");
}

function renderRegions() {
  const regions = [...(state.data.regions || [])].sort((a, b) => b.value - a.value);
  drawBars(document.getElementById("region-chart"), regions);
  const east = regions.find((r) => r.key === "east");
  document.getElementById("region-note").textContent =
    east && east.value >= 130
      ? "East is not a data error. DEL–CCU is carrying a documented fixture shock, and that corridor is 10% of the CPI basket."
      : "Regions move when their member routes move. Passenger traffic is not the weight.";
  document.getElementById("months").innerHTML = (state.data.monthly || [])
    .map(
      (m) =>
        `<div class="month"><span>${esc(m.period)}</span><strong>${m.value.toFixed(2)}</strong></div>`
    )
    .join("");
}

function renderMethod() {
  const m = state.data.methodology;
  document.getElementById("method-facts").innerHTML = [
    ["Elementary index", m.elementary],
    ["Higher-level aggregation", m.aggregation],
    ["Domestic specification", `T+${m.domestic_lead} · ${m.cabin} · ${m.trip}`],
    ["International specification", `T+${m.international_lead} (not collected yet)`],
    ["OTA enters CPI", m.ota_enters_cpi ? "yes" : "no"],
    ["Missing prices", m.never_zero ? "skip, never zero" : m.missing_policy],
    ["Live HTTP", m.allow_live_http ? "allowed" : "forbidden"],
    ["International members", (m.international_members || []).join(", ") || "—"],
  ]
    .map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`)
    .join("");
  document.getElementById("source-grid").innerHTML = state.data.sources
    .map((s) => {
      const cpi = s.can_enter_cpi ? "CPI eligible" : "not CPI";
      const http = s.allow_http ? "HTTP on" : "HTTP off";
      return `<article class="source-card">
        <h3>${esc(s.name)}</h3>
        <div class="meta-row">
          <span class="chip">${esc(s.type)}</span>
          <span class="chip ${s.can_enter_cpi ? "in" : "out"}">${cpi}</span>
          <span class="chip">${esc(s.health)}</span>
          <span class="chip">${esc(s.collection_method)}</span>
          <span class="chip">${http}</span>
        </div>
        <p>${esc(s.note || "No additional note.")}</p>
      </article>`;
    })
    .join("");
  document.getElementById("event-grid").innerHTML = state.data.events
    .map(
      (e) => `<article class="event-card">
        <h3>${esc(e.title)} ${e.active ? '<span class="chip alert">active today</span>' : ""}</h3>
        <p>×${esc(e.factor)} on ${esc((e.routes || [e.hub]).join(", "))} · ${esc(e.on)} ${esc(e.start)} → ${esc(e.end)}</p>
        <p>${esc(e.note)}</p>
      </article>`
    )
    .join("");
}

function renderQuotes() {
  const row = selectedRoute();
  if (!row) return;
  document.getElementById("quotes-title").textContent = `Observed quotes · ${row.label}`;
  document.getElementById("quotes-lede").textContent =
    `Collected ${fmtDate(state.data.as_of)}. Filter to see why a fare is in the CPI sample or only in the market path.`;
  document.getElementById("cpi-rule").textContent =
    state.fares?.rule?.cpi ||
    "CPI sample: airline source, economy, exact T+21, quality not rejected. OTA cannot enter.";
  const body = document.querySelector("#fare-table tbody");
  if (state.loadingFares) {
    body.innerHTML = `<tr><td colspan="8">Loading quotes…</td></tr>`;
    return;
  }
  let rows = state.fares?.fares || [];
  if (state.fareFilter === "cpi") rows = rows.filter((f) => f.can_enter_cpi);
  if (state.fareFilter === "market") rows = rows.filter((f) => !f.can_enter_cpi);
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="8">No quotes in this filter.</td></tr>`;
    return;
  }
  rows.sort((a, b) => a.lead - b.lead || a.total - b.total);
  body.innerHTML = rows
    .map(
      (f) => `<tr>
        <td>${esc(f.source_name)}<span class="cities">${esc(f.source_type)}</span></td>
        <td><span class="chip ${f.can_enter_cpi ? "in" : "out"}">${f.can_enter_cpi ? "in sample" : "excluded"}</span></td>
        <td class="num">D+${f.lead}</td>
        <td class="num">${rupee(f.total)}</td>
        <td>${esc(f.airline_name || f.airline)}</td>
        <td class="hide-sm">${esc(f.flight)}</td>
        <td class="hide-sm">${esc(fmtDate(f.departure))}</td>
        <td class="hide-sm">${esc(f.quality)}</td>
      </tr>`
    )
    .join("");
}

function showTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.classList.toggle("is-on", btn.dataset.tab === tab);
  });
  document.querySelectorAll(".view").forEach((section) => {
    const tags = (section.dataset.view || "").split(/\s+/);
    section.hidden = !tags.includes(tab);
  });
  document.querySelector(".kpis").classList.toggle("compact", tab !== "overview");
  document.querySelector(".callouts").hidden = tab !== "overview";
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
    state.fares = { fares: [], rule: { cpi: String(err) } };
  } finally {
    state.loadingFares = false;
    renderQuotes();
  }
}

function selectRoute(routeId, { fetchQuotes = true } = {}) {
  state.routeId = routeId;
  renderRoutes();
  renderDetail();
  renderQuotes();
  if (fetchQuotes) loadFares(routeId);
}

function bind() {
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      showTab(tab);
      history.replaceState(null, "", tab === "overview" ? location.pathname : `#${tab}`);
    });
  });
  document.querySelector("#route-table tbody").addEventListener("click", (event) => {
    const tr = event.target.closest("tr[data-route]");
    if (!tr) return;
    selectRoute(tr.dataset.route);
  });
  document.querySelector("#route-table tbody").addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const tr = event.target.closest("tr[data-route]");
    if (!tr) return;
    event.preventDefault();
    selectRoute(tr.dataset.route);
  });
  document.getElementById("open-quotes").addEventListener("click", () => {
    showTab("quotes");
    history.replaceState(null, "", "#quotes");
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
    renderHeader();
    renderCallouts();
    renderNationalChart();
    renderRoutes();
    renderDetail();
    renderRegions();
    renderMethod();
    showTab(state.tab);
    await loadFares(state.routeId);
  } catch (err) {
    document.getElementById("boot").hidden = true;
    const crash = document.getElementById("crash");
    crash.hidden = false;
    crash.textContent = "Could not load APIx. Start the API from C:\\SIH\\airfare-index, then refresh. " + err.message;
  }
}

boot();
