"use strict";

async function loadJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return r.json();
}

function fmtValue(v, unit) {
  if (v === null || v === undefined) return "—";
  if (unit === "percent") return `${(+v).toFixed(3).replace(/\.?0+$/, "")} %`;
  if (unit === "ms") return `${(+v).toFixed(1)} ms`;
  if (unit === "seconds") return `${(+v).toFixed(3)} s`;
  if (unit === "count") return Math.round(v).toLocaleString("en");
  return String(v);
}

function fillSelect(el, values) {
  el.innerHTML = values.map((v) => `<option value="${v}">${v}</option>`).join("");
}

// Inline SVG line chart. points: [[isoDate, value, label?]]
function svgLineChart(el, points, opts = {}) {
  const height = opts.height || 280;
  const W = Math.max(el.clientWidth || 720, 320);
  const H = height;
  const m = { t: 16, r: 16, b: 28, l: 56 };
  const xs = points.map((p) => Date.parse(p[0]));
  const ys = points.map((p) => p[1]);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  let y0 = Math.min(...ys);
  let y1 = Math.max(...ys);
  if (y0 === y1) { y0 -= 1; y1 += 1; }
  const pad = (y1 - y0) * 0.08;
  y0 -= pad; y1 += pad;
  const X = (t) => m.l + (x1 === x0 ? 0.5 : (t - x0) / (x1 - x0)) * (W - m.l - m.r);
  const Y = (v) => m.t + (1 - (v - y0) / (y1 - y0)) * (H - m.t - m.b);
  const path = points
    .map((p, i) => `${i ? "L" : "M"}${X(Date.parse(p[0])).toFixed(1)},${Y(p[1]).toFixed(1)}`)
    .join("");
  const grid = [];
  for (let i = 0; i <= 4; i++) {
    const v = y0 + (i / 4) * (y1 - y0);
    const yy = Y(v).toFixed(1);
    grid.push(`<line class="grid" x1="${m.l}" x2="${W - m.r}" y1="${yy}" y2="${yy}"/>`);
    grid.push(`<text class="tick y" x="${m.l - 6}" y="${(+yy + 3).toFixed(1)}">${v.toFixed(Math.abs(v) < 10 ? 1 : 0)}</text>`);
  }
  const n = Math.min(6, points.length);
  const seen = new Set();
  for (let i = 0; i < n; i++) {
    const idx = Math.round((i * (points.length - 1)) / Math.max(n - 1, 1));
    const d = new Date(xs[idx]);
    const lab = points.length > 40
      ? `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`
      : points[idx][0];
    if (seen.has(lab)) continue;
    seen.add(lab);
    grid.push(`<text class="tick x" text-anchor="middle" x="${X(xs[idx]).toFixed(1)}" y="${H - 8}">${lab}</text>`);
  }
  el.innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" role="img">${grid.join("")}` +
    `<path class="line" fill="none" d="${path}"/></svg>`;
}

// Pick the most representative series: prefer dedicated_api, service ALL,
// then the longest series available.
function pickSeries(list) {
  if (!list.length) return null;
  const score = (s) =>
    (s.interface === "dedicated_api" ? 4 : 0) +
    (s.service === "ALL" ? 2 : 0) +
    Math.min(s.points.length / 1000, 1);
  return [...list].sort((a, b) => score(b) - score(a))[0];
}

function seriesInfo(s) {
  const inf = s.inferred ? ` · ${s.inferred} values interpreted` : "";
  return `${s.interface} · ${s.service} · ${s.points.length} points · group ` +
    `${s.comparability_group}${inf}`;
}

async function initCompare() {
  const [meta, rows] = await Promise.all([
    loadJSON("data/meta.json"),
    loadJSON("data/compare.json"),
  ]);
  const sel = (id) => document.getElementById(id);
  fillSelect(sel("sel-period"), [...meta.quarters].reverse().concat([...meta.months].reverse()));
  fillSelect(sel("sel-metric"), meta.metrics);
  fillSelect(sel("sel-service"), meta.services);
  fillSelect(sel("sel-iface"), meta.interfaces);

  function table(group, rs) {
    const body = rs
      .map(
        (r) =>
          `<tr><td><a href="entity-${r.entity_id}.html">${r.entity_id}</a></td>` +
          `<td class="num">${fmtValue(r.value, r.unit)}</td>` +
          `<td>${r.aggregation || ""}</td>` +
          `<td class="num">${r.n_days ?? "—"}</td></tr>`
      )
      .join("");
    return `<h3 class="group">${group}</h3>` +
      `<table><thead><tr><th>Entity</th><th class="num">Value</th><th>Basis</th><th class="num">Days</th></tr></thead><tbody>${body}</tbody></table>`;
  }

  function render() {
    const p = sel("sel-period").value;
    const mt = sel("sel-metric").value;
    const sv = sel("sel-service").value;
    const itf = sel("sel-iface").value;
    const sub = rows.filter(
      (r) => r.period === p && r.metric === mt && r.service === sv && r.interface === itf
    );
    const out = document.getElementById("compare-out");
    if (!sub.length) {
      out.innerHTML = '<p class="muted">No reported values for this combination.</p>';
      return;
    }
    const groups = {};
    for (const r of sub) (groups[r.comparability_group] ??= []).push(r);
    const names = Object.keys(groups).sort((a, b) => groups[b].length - groups[a].length);
    const showAll = sel("chk-all").checked;
    const shown = showAll ? names : names.slice(0, 1);
    let html = shown.map((g) => table(g, groups[g])).join("");
    if (names.length > 1 && !showAll) {
      html += `<p class="muted">${names.length - 1} other comparability group(s) hidden — methodologies differ.</p>`;
    }
    out.innerHTML = html;
  }

  for (const id of ["sel-period", "sel-metric", "sel-service", "sel-iface", "chk-all"]) {
    sel(id).addEventListener("change", render);
  }
  render();
}

async function initHistory() {
  const meta = await loadJSON("data/meta.json");
  const sel = (id) => document.getElementById(id);
  fillSelect(sel("sel-entity"), meta.entities.map((e) => e.id));
  let data = null;

  async function loadEntity() {
    data = await loadJSON(`data/history-${sel("sel-entity").value}.json`);
    fillSelect(sel("sel-metric"), Object.keys(data.metrics));
    render();
  }

  function render() {
    const series = data.metrics[sel("sel-metric").value] || [];
    const gran = sel("sel-gran").value;
    const cand = series.filter((s) => s.period_type === gran);
    const s = pickSeries(cand);
    const chart = document.getElementById("chart");
    const info = document.getElementById("history-info");
    if (!s) {
      chart.innerHTML = '<p class="muted">No series for this combination.</p>';
      info.textContent = "";
      return;
    }
    svgLineChart(chart, s.points, { unit: s.unit });
    info.textContent =
      seriesInfo(s) + (cand.length > 1 ? ` · ${cand.length - 1} more series available` : "");
  }

  sel("sel-entity").addEventListener("change", loadEntity);
  sel("sel-metric").addEventListener("change", render);
  sel("sel-gran").addEventListener("change", render);
  const gran = sel("sel-gran");
  if (gran.options.length === 0) {
    fillSelect(gran, ["day", "month", "quarter"]);
  }
  await loadEntity();
}

async function initEntityChart() {
  const el = document.getElementById("entity-chart");
  const data = await loadJSON(`data/history-${el.dataset.entity}.json`);
  const daily = (data.metrics.availability || []).filter((s) => s.period_type === "day");
  const s = pickSeries(daily) || pickSeries(data.metrics.availability || []);
  const info = document.getElementById("entity-chart-info");
  if (!s) {
    el.innerHTML = '<p class="muted">No availability series.</p>';
    return;
  }
  svgLineChart(el, s.points, { unit: s.unit });
  info.textContent = seriesInfo(s);
}

const page = document.body.dataset.page;
if (page === "compare") initCompare();
if (page === "history") initHistory();
if (page === "entity") initEntityChart();
