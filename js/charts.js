// Hand-drawn SVG charts. Each one is drawn at the real pixel width of its box and redrawn on resize,
// so text never scales with the chart. Colours are CSS variables from tokens.css.
import { clock, dur, measure, shortDay, t, toDate, wtype } from "./i18n.js?v=f1813bf9c8";

const has = (v) => v !== null && v !== undefined && !Number.isNaN(v);
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// ---- drawing at real width ---------------------------------------------------------------------
const draws = new WeakMap();
const observer = typeof ResizeObserver === "function"
  ? new ResizeObserver((entries) => entries.forEach(({ target }) => {
      const fn = draws.get(target);
      if (fn && target.clientWidth) target.innerHTML = fn(target.clientWidth);
    }))
  : null;
export function draw(el, fn) {
  if (!el) return;
  draws.set(el, fn);
  el.innerHTML = fn(el.clientWidth || 320);
  if (observer) observer.observe(el);
}

// ---- tooltip (one for the page; marks carry data-tip) ----------------------------------------
let tip = null;
export function installTooltip() {
  if (tip) return;
  tip = document.createElement("div");
  tip.className = "tip";
  tip.setAttribute("role", "status");
  document.body.appendChild(tip);
  const show = (target, x, y) => {
    tip.textContent = target.getAttribute("data-tip");
    tip.classList.add("on");
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = `${Math.min(window.innerWidth - w - 8, Math.max(8, x - w / 2))}px`;
    tip.style.top = `${Math.max(8, y - h - 12)}px`;
  };
  document.addEventListener("pointermove", (e) => {
    const target = e.target.closest && e.target.closest("[data-tip]");
    if (target) show(target, e.clientX, e.clientY); else tip.classList.remove("on");
  });
  document.addEventListener("focusin", (e) => {
    const target = e.target.closest && e.target.closest("[data-tip]");
    if (!target) return;
    const r = target.getBoundingClientRect();
    show(target, r.left + r.width / 2, r.top);
  });
  document.addEventListener("focusout", () => tip.classList.remove("on"));
}

// ---- scales ------------------------------------------------------------------------------------
export function niceStep(span, count = 4) {
  const raw = span / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(raw || 1));
  return [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw;
}
const linear = (d0, d1, r0, r1) => (v) => (d1 === d0 ? (r0 + r1) / 2 : r0 + ((v - d0) / (d1 - d0)) * (r1 - r0));

// ---- sparkline with "your normal" band -------------------------------------------------------
export function spark(series, band, { width, height = 46, unit = "", tone = "neutral" }) {
  const pts = series.map((p, i) => ({ ...p, i }));
  const vals = pts.filter((p) => has(p.value)).map((p) => p.value);
  if (!vals.length) return `<svg viewBox="0 0 ${width} ${height}" height="${height}" aria-hidden="true"></svg>`;
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (band) { lo = Math.min(lo, band.q1); hi = Math.max(hi, band.q3); }
  const pad = (hi - lo) * 0.12 || 1;
  const y = linear(lo - pad, hi + pad, height - 4, 4);
  const x = linear(0, Math.max(1, pts.length - 1), 4, width - 6);
  let path = "", open = false;
  pts.forEach((p) => {
    if (!has(p.value)) { open = false; return; }
    path += `${open ? "L" : "M"}${x(p.i).toFixed(1)},${y(p.value).toFixed(1)}`;
    open = true;
  });
  const last = [...pts].reverse().find((p) => has(p.value));
  const endColor = tone === "good" ? "var(--good)" : tone === "bad" ? "var(--off)" : "var(--c-mark)";
  const hit = pts.map((p) => {
    const w = width / pts.length;
    const label = `${shortDay(p.date)} · ${has(p.value) ? measure(p.value, unit) : t("ui.no_data")}`;
    return `<rect x="${(x(p.i) - w / 2).toFixed(1)}" y="0" width="${w.toFixed(1)}" height="${height}" fill="transparent" data-tip="${esc(label)}"/>`;
  }).join("");
  const gaps = pts.filter((p) => !has(p.value)).map((p) => `<text x="${x(p.i).toFixed(1)}" y="${height - 2}" text-anchor="middle" font-size="9" fill="var(--ink-3)">×</text>`).join("");
  return `<svg viewBox="0 0 ${width} ${height}" height="${height}" role="img" aria-label="${esc(t("band", { low: measure(band?.q1, unit), high: measure(band?.q3, unit) }))}">
    ${band ? `<rect x="0" y="${y(band.q3).toFixed(1)}" width="${width}" height="${Math.max(1, y(band.q1) - y(band.q3)).toFixed(1)}" rx="3" fill="var(--c-band)"/>` : ""}
    <path d="${path}" fill="none" stroke="var(--ink-2)" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>
    ${last ? `<circle cx="${x(last.i).toFixed(1)}" cy="${y(last.value).toFixed(1)}" r="4" fill="${endColor}" stroke="var(--surface-2)" stroke-width="2"/>` : ""}
    ${gaps}${hit}</svg>`;
}

// ---- value vs band on one line -------------------------------------------------------------------
export function bullet(value, band, { width, unit = "", tone = "neutral", height = 18 }) {
  if (!has(value)) return "";
  let lo = value, hi = value;
  if (band) { lo = Math.min(lo, band.q1); hi = Math.max(hi, band.q3); }
  const span = hi - lo || Math.abs(value) || 1;
  const x = linear(lo - span * 0.35, hi + span * 0.35, 6, width - 6);
  const color = tone === "good" ? "var(--good)" : tone === "bad" ? "var(--off)" : "var(--c-mark)";
  return `<svg viewBox="0 0 ${width} ${height}" height="${height}" aria-hidden="true">
    <line x1="2" x2="${width - 2}" y1="${height / 2}" y2="${height / 2}" stroke="var(--line-2)" stroke-width="2" stroke-linecap="round"/>
    ${band ? `<rect x="${x(band.q1).toFixed(1)}" y="${height / 2 - 5}" width="${Math.max(2, x(band.q3) - x(band.q1)).toFixed(1)}" height="10" rx="5" fill="var(--c-band)" stroke="var(--line-2)"/>
      <line x1="${x(band.median).toFixed(1)}" x2="${x(band.median).toFixed(1)}" y1="${height / 2 - 5}" y2="${height / 2 + 5}" stroke="var(--ink-3)" stroke-width="1.5"/>` : ""}
    <circle cx="${x(value).toFixed(1)}" cy="${height / 2}" r="5.5" fill="${color}" stroke="var(--surface-2)" stroke-width="2"/></svg>`;
}

// ---- the day ring --------------------------------------------------------------------------------
const CATS = [["focus", ["work", "learning"], "var(--c-focus)"], ["fun", ["entertainment", "social"], "var(--c-fun)"],
  ["communication", ["communication"], "var(--c-comms)"], ["other", ["other"], "var(--c-other)"]];
export const RING_CATS = CATS;

function polar(cx, cy, r, minute) {
  const a = (minute / 1440) * Math.PI * 2 - Math.PI / 2;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}
function arc(cx, cy, r0, r1, m0, m1) {
  if (m1 - m0 >= 1440) m1 = m0 + 1439.9;
  const large = m1 - m0 > 720 ? 1 : 0;
  const [ax, ay] = polar(cx, cy, r1, m0), [bx, by] = polar(cx, cy, r1, m1);
  const [cx2, cy2] = polar(cx, cy, r0, m1), [dx, dy] = polar(cx, cy, r0, m0);
  return `M${ax.toFixed(2)},${ay.toFixed(2)}A${r1},${r1} 0 ${large} 1 ${bx.toFixed(2)},${by.toFixed(2)}L${cx2.toFixed(2)},${cy2.toFixed(2)}A${r0},${r0} 0 ${large} 0 ${dx.toFixed(2)},${dy.toFixed(2)}Z`;
}
const minuteOf = (iso) => { const d = toDate(iso); return d.getHours() * 60 + d.getMinutes(); };

export function dayRing(ring, { size = 360, center = "", centerSub = "" }) {
  const c = size / 2, s = size / 360;
  const R = { label: 172 * s, sleep: [150 * s, 162 * s], events: [130 * s, 144 * s], screen: [58 * s, 122 * s] };
  const parts = [];
  // tracks
  parts.push(`<circle cx="${c}" cy="${c}" r="${(R.sleep[0] + R.sleep[1]) / 2}" fill="none" stroke="var(--c-band)" stroke-width="${R.sleep[1] - R.sleep[0]}"/>`);
  parts.push(`<circle cx="${c}" cy="${c}" r="${(R.events[0] + R.events[1]) / 2}" fill="none" stroke="var(--c-band)" stroke-width="${R.events[1] - R.events[0]}"/>`);
  parts.push(`<circle cx="${c}" cy="${c}" r="${R.screen[0]}" fill="none" stroke="var(--line-2)" stroke-width="1"/>`);
  // hour ticks + labels
  for (let h = 0; h < 24; h++) {
    const major = h % 6 === 0;
    const [x0, y0] = polar(c, c, R.screen[1] + 2 * s, h * 60), [x1, y1] = polar(c, c, R.screen[1] + (major ? 6 : 3) * s, h * 60);
    parts.push(`<line x1="${x0.toFixed(1)}" y1="${y0.toFixed(1)}" x2="${x1.toFixed(1)}" y2="${y1.toFixed(1)}" stroke="var(--c-axis)" stroke-width="${major ? 1.5 : 1}"/>`);
    if (h % 3 === 0) {
      const [lx, ly] = polar(c, c, R.label, h * 60);
      parts.push(`<text x="${lx.toFixed(1)}" y="${(ly + 4 * s).toFixed(1)}" text-anchor="middle" font-size="${(major ? 12 : 10.5) * s}" font-weight="${major ? 650 : 500}" fill="${major ? "var(--ink-2)" : "var(--ink-3)"}">${String(h).padStart(2, "0")}</text>`);
    }
  }
  // screen: one wedge per hour, stacked from the centre out
  const span = R.screen[1] - R.screen[0];
  (ring.screen_hours || []).forEach((hour, h) => {
    let r = R.screen[0];
    CATS.forEach(([key, cats, color]) => {
      const minutes = cats.reduce((sum, k) => sum + (hour[k] || 0), 0);
      if (!minutes) return;
      const r1 = r + (Math.min(60, minutes) / 60) * span;
      const m0 = h * 60 + 3, m1 = h * 60 + 57;
      parts.push(`<path d="${arc(c, c, r + 0.6, Math.max(r + 1.2, r1 - 0.6), m0, m1)}" fill="${color}" data-tip="${esc(`${String(h).padStart(2, "0")}:00 · ${t(`cat.${key}`)} ${dur(minutes)}`)}"/>`);
      r = r1;
    });
  });
  // events
  (ring.events || []).forEach((e) => {
    const m0 = minuteOf(e.start), m1 = Math.max(m0 + 8, e.end.slice(0, 10) > e.start.slice(0, 10) ? 1440 : minuteOf(e.end));
    const op = e.kind === "class" ? 0.86 : 0.45;
    parts.push(`<path d="${arc(c, c, R.events[0], R.events[1], m0 + 1, m1 - 1)}" fill="var(--c-event)" fill-opacity="${op}" data-tip="${esc(`${clock(e.start)}–${clock(e.end)} · ${e.title}`)}"/>`);
  });
  // workouts share the calendar track, in the exercise colour
  (ring.workouts || []).forEach((wk) => {
    const m0 = minuteOf(wk.start), m1 = Math.max(m0 + 8, minuteOf(wk.end));
    parts.push(`<path d="${arc(c, c, R.events[0] - 1, R.events[1] + 1, m0 + 1, m1 - 1)}" fill="var(--c-exercise)" data-tip="${esc(`${clock(wk.start)}–${clock(wk.end)} · ${wtype(wk.type)}`)}"/>`);
  });
  // sleep (may start the evening before)
  if (ring.sleep && ring.sleep.start && ring.sleep.end) {
    let m0 = minuteOf(ring.sleep.start), m1 = minuteOf(ring.sleep.end);
    if (ring.sleep.start.slice(0, 10) < ring.sleep.end.slice(0, 10)) m0 -= 1440;
    const tipText = `${t("ring.sleep")} ${clock(ring.sleep.start)}–${clock(ring.sleep.end)} · ${dur(m1 - m0)}`;
    if (m0 < 0) {
      parts.push(`<path d="${arc(c, c, R.sleep[0], R.sleep[1], 1440 + m0, 1440)}" fill="var(--c-sleep)" data-tip="${esc(tipText)}"/>`);
      parts.push(`<path d="${arc(c, c, R.sleep[0], R.sleep[1], 0, m1)}" fill="var(--c-sleep)" data-tip="${esc(tipText)}"/>`);
    } else {
      parts.push(`<path d="${arc(c, c, R.sleep[0], R.sleep[1], m0, m1)}" fill="var(--c-sleep)" data-tip="${esc(tipText)}"/>`);
    }
  }
  // now hand
  if (ring.now) {
    const m = minuteOf(ring.now);
    const [x0, y0] = polar(c, c, R.screen[0] - 4 * s, m), [x1, y1] = polar(c, c, R.sleep[1] + 4 * s, m);
    parts.push(`<line x1="${x0.toFixed(1)}" y1="${y0.toFixed(1)}" x2="${x1.toFixed(1)}" y2="${y1.toFixed(1)}" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>`);
    parts.push(`<circle cx="${x1.toFixed(1)}" cy="${y1.toFixed(1)}" r="${4 * s}" fill="var(--accent)" stroke="var(--surface)" stroke-width="2"/>`);
  }
  parts.push(`<text x="${c}" y="${c + 2 * s}" text-anchor="middle" font-size="${30 * s}" font-weight="680" fill="var(--ink)" letter-spacing="-.5">${esc(center)}</text>`);
  parts.push(`<text x="${c}" y="${c + 22 * s}" text-anchor="middle" font-size="${11.5 * s}" font-weight="550" fill="var(--ink-3)">${esc(centerSub)}</text>`);
  return `<svg class="ring" viewBox="0 0 ${size} ${size}" role="img" aria-label="${esc(t("ring.label"))}">${parts.join("")}</svg>`;
}

// ---- difference with interval, against zero ------------------------------------------------------
export function interval(row, domain, { width, height = 26, flip = false }) {
  // right = a better next day: when lower is better (resting heart rate) the values are mirrored
  const x = linear(-domain, domain, 8, width - 8);
  const zero = x(0);
  const base = `<line x1="${zero}" x2="${zero}" y1="2" y2="${height - 2}" stroke="var(--c-axis)" stroke-width="1"/>`;
  if (row.status !== "ok") return `<svg viewBox="0 0 ${width} ${height}" height="${height}" aria-hidden="true">${base}</svg>`;
  const s = flip ? -1 : 1;
  const d = s * row.diff, lo = Math.min(s * row.low, s * row.high), hi = Math.max(s * row.low, s * row.high);
  const color = row.detected ? (d > 0 ? "var(--good)" : "var(--off)") : "var(--ink-3)";
  const clamp = (v) => Math.max(8, Math.min(width - 8, x(v)));
  return `<svg viewBox="0 0 ${width} ${height}" height="${height}" aria-hidden="true">${base}
    <line x1="${clamp(lo).toFixed(1)}" x2="${clamp(hi).toFixed(1)}" y1="${height / 2}" y2="${height / 2}" stroke="${color}" stroke-width="2.5" stroke-linecap="round"/>
    <circle cx="${clamp(d).toFixed(1)}" cy="${height / 2}" r="5" fill="${color}" stroke="var(--surface)" stroke-width="2"/></svg>`;
}

// ---- seven small day columns (training) -------------------------------------------------------------
export function dayDots(series, { width, height = 30 }) {
  const n = series.length, w = width / n;
  return `<svg viewBox="0 0 ${width} ${height}" height="${height}" aria-hidden="true">${series.map((p, i) => {
    const cx = w * i + w / 2;
    const v = p.value;
    const fill = v ? "var(--c-mark)" : "none";
    const stroke = v === null || v === undefined ? "var(--line-2)" : "var(--c-mark)";
    const label = `${shortDay(p.date)} · ${v ? dur(v) : v === 0 ? "0" : t("ui.no_data")}`;
    return `<g data-tip="${esc(label)}"><rect x="${(cx - w / 2).toFixed(1)}" y="0" width="${w.toFixed(1)}" height="${height}" fill="transparent"/>
      <circle cx="${cx.toFixed(1)}" cy="${height / 2 - 4}" r="6" fill="${fill}" stroke="${stroke}" stroke-width="1.6" ${v === null || v === undefined ? 'stroke-dasharray="2 2"' : ""}/>
      <text x="${cx.toFixed(1)}" y="${height}" text-anchor="middle" font-size="9.5" fill="var(--ink-3)">${shortDay(p.date).split(/[ /]/)[shortDay(p.date).includes("/") ? 1 : 0]}</text></g>`;
  }).join("")}</svg>`;
}

// ---- shared axis helpers -----------------------------------------------------------------------------
const dayIndex = (iso, first) => Math.round((toDate(iso) - toDate(first)) / 86400000);
function yTicks(lo, hi, count = 4) {
  const step = niceStep(hi - lo, count);
  const start = Math.ceil(lo / step) * step;
  const out = [];
  for (let v = start; v <= hi + 1e-9; v += step) out.push(Number(v.toFixed(6)));
  return out;
}

// ---- time series: corridor band, points, smoothed line, reference lines ---------------------------------
// layers: { band: [{date, low, high}], points: [{date, value}], line: [{date, value}], refs: [{value, label}] }
export function timeChart(layers, { width, height = 240, first, last, unit = "", fmt = (v) => String(v), yPad = 0.15, maxGap = 7 }) {
  const m = { l: 44, r: 12, t: 12, b: 26 };
  const n = Math.max(1, dayIndex(last, first));
  const vals = [...(layers.points || []), ...(layers.line || [])].map((p) => p.value).filter(has);
  (layers.band || []).forEach((b) => { vals.push(b.low, b.high); });
  (layers.refs || []).forEach((r) => vals.push(r.value));
  if (!vals.length) return "";
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * yPad || 1; lo -= pad; hi += pad;
  const x = linear(0, n, m.l, width - m.r), y = linear(lo, hi, height - m.b, m.t);
  const X = (iso) => x(dayIndex(iso, first));
  const parts = [];
  yTicks(lo, hi).forEach((v) => parts.push(`<line x1="${m.l}" x2="${width - m.r}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}" stroke="var(--c-grid)"/>
    <text x="${m.l - 8}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end" font-size="11" fill="var(--ink-3)" class="num">${esc(fmt(v))}</text>`));
  const tickEvery = n > 90 ? 30 : n > 40 ? 14 : 7;
  for (let k = 0; k <= n; k += tickEvery) {
    const d = new Date(toDate(first)); d.setDate(d.getDate() + k);
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    parts.push(`<text x="${x(k).toFixed(1)}" y="${height - 6}" text-anchor="middle" font-size="11" fill="var(--ink-3)">${esc(shortDay(iso))}</text>`);
  }
  if (layers.band && layers.band.length) {
    const top = layers.band.map((b) => `${X(b.date).toFixed(1)},${y(b.high).toFixed(1)}`);
    const bottom = [...layers.band].reverse().map((b) => `${X(b.date).toFixed(1)},${y(b.low).toFixed(1)}`);
    parts.push(`<polygon points="${[...top, ...bottom].join(" ")}" fill="var(--accent-soft)" stroke="none"/>`);
  }
  (layers.refs || []).forEach((r) => parts.push(`<line x1="${m.l}" x2="${width - m.r}" y1="${y(r.value).toFixed(1)}" y2="${y(r.value).toFixed(1)}" stroke="var(--ink-3)" stroke-dasharray="4 4"/>
    <text x="${width - m.r}" y="${(y(r.value) - 6).toFixed(1)}" text-anchor="end" font-size="11" fill="var(--ink-2)">${esc(r.label)}</text>`));
  (layers.points || []).forEach((p) => parts.push(`<circle cx="${X(p.date).toFixed(1)}" cy="${y(p.value).toFixed(1)}" r="3" fill="var(--ink-3)" fill-opacity=".55"/>`));
  if (layers.line && layers.line.length) {
    let d = "", prev = null;
    layers.line.forEach((p) => {
      const i = dayIndex(p.date, first);
      d += `${prev !== null && i - prev <= maxGap ? "L" : "M"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`;
      prev = i;
    });
    parts.push(`<path d="${d}" fill="none" stroke="var(--c-mark)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`);
    const end = layers.line[layers.line.length - 1];
    parts.push(`<circle cx="${X(end.date).toFixed(1)}" cy="${y(end.value).toFixed(1)}" r="4.5" fill="var(--c-mark)" stroke="var(--surface)" stroke-width="2"/>`);
  }
  // hover columns, one per day
  const byDay = new Map();
  (layers.points || []).forEach((p) => byDay.set(p.date, { ...(byDay.get(p.date) || {}), point: p.value }));
  (layers.line || []).forEach((p) => byDay.set(p.date, { ...(byDay.get(p.date) || {}), line: p.value }));
  const w = (width - m.l - m.r) / (n + 1);
  byDay.forEach((v, iso) => {
    const label = `${shortDay(iso)}${has(v.point) ? ` · ${fmt(v.point)}` : ""}${has(v.line) ? ` · ${t("chart.avg7")} ${fmt(v.line)}` : ""}`;
    parts.push(`<rect x="${(X(iso) - w / 2).toFixed(1)}" y="${m.t}" width="${Math.max(2, w).toFixed(1)}" height="${height - m.t - m.b}" fill="transparent" data-tip="${esc(label)}"/>`);
  });
  return `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${esc(t("chart.series"))}">${parts.join("")}</svg>`;
}

// ---- stacked columns (categories over days or hours) -------------------------------------------------------
// columns: [{label, values: {key: minutes}, shade: bool, tip}] ; groups: [[key, color, name]] bottom first
export function stackedColumns(columns, groups, { width, height = 200, limit = null, limitLabel = "", maxValue = null, labelEvery = 1, unitFmt = dur }) {
  const m = { l: 44, r: 8, t: 14, b: 24 };
  const totals = columns.map((c) => groups.reduce((s, [k]) => s + (c.values?.[k] || 0), 0));
  const top = maxValue || Math.max(limit || 0, ...totals, 1);
  const ticks = yTicks(0, top * 1.05);
  const hi = Math.max(top * 1.05, ticks[ticks.length - 1]);
  const y = linear(0, hi, height - m.b, m.t);
  const slot = (width - m.l - m.r) / columns.length;
  const bw = Math.max(3, Math.min(28, slot - 3));
  const parts = [];
  ticks.forEach((v) => parts.push(`<line x1="${m.l}" x2="${width - m.r}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}" stroke="var(--c-grid)"/>
    <text x="${m.l - 8}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end" font-size="11" fill="var(--ink-3)" class="num">${esc(unitFmt(v))}</text>`));
  columns.forEach((c, i) => {
    const cx = m.l + slot * i + slot / 2;
    if (c.shade) parts.push(`<rect x="${(cx - slot / 2).toFixed(1)}" y="${m.t}" width="${slot.toFixed(1)}" height="${height - m.t - m.b}" fill="var(--c-band)"/>`);
    let base = 0;
    if (!c.values) {
      parts.push(`<text x="${cx.toFixed(1)}" y="${(height - m.b - 4).toFixed(1)}" text-anchor="middle" font-size="10" fill="var(--ink-3)">×</text>`);
    } else {
      groups.forEach(([key, color]) => {
        const v = c.values[key] || 0;
        if (!v) return;
        const y0 = y(base), y1 = y(base + v);
        parts.push(`<rect x="${(cx - bw / 2).toFixed(1)}" y="${(y1 + 1).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0.5, y0 - y1 - 2).toFixed(1)}" rx="2" fill="${color}"/>`);
        base += v;
      });
    }
    const tip = c.tip || `${c.label} · ${unitFmt(totals[i])}`;
    parts.push(`<rect x="${(cx - slot / 2).toFixed(1)}" y="${m.t}" width="${slot.toFixed(1)}" height="${height - m.t - m.b}" fill="transparent" data-tip="${esc(tip)}"/>`);
    if (i % labelEvery === 0) parts.push(`<text x="${cx.toFixed(1)}" y="${height - 6}" text-anchor="middle" font-size="10.5" fill="var(--ink-3)">${esc(c.label)}</text>`);
  });
  parts.push(`<line x1="${m.l}" x2="${width - m.r}" y1="${y(0)}" y2="${y(0)}" stroke="var(--c-axis)"/>`);
  if (limit) parts.push(`<line x1="${m.l}" x2="${width - m.r}" y1="${y(limit).toFixed(1)}" y2="${y(limit).toFixed(1)}" stroke="var(--ink)" stroke-width="1.2" stroke-dasharray="5 4"/>
    <text x="${width - m.r}" y="${(y(limit) - 5).toFixed(1)}" text-anchor="end" font-size="11" fill="var(--ink-2)">${esc(limitLabel)}</text>`);
  return `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${esc(limitLabel)}">${parts.join("")}</svg>`;
}

// ---- nights as bars on an evening-to-afternoon axis ------------------------------------------------------
const fromNoon = (iso) => { const d = toDate(iso); const mm = d.getHours() * 60 + d.getMinutes(); return mm >= 720 ? mm - 720 : mm + 720; };
export function sleepWindows(nights, { width, target = null, rowH = 18 }) {
  const m = { l: 64, r: 12, t: 22, b: 8 };
  const x0 = 8 * 60, x1 = 26 * 60; // 20:00 .. 14:00 next day, in minutes after noon
  const x = linear(x0, x1, m.l, width - m.r);
  const h = m.t + m.b + nights.length * rowH;
  const parts = [];
  const labelStep = width < 520 ? 240 : 120;
  for (let mm = x0; mm <= x1; mm += labelStep) {
    const label = String(((mm / 60) + 12) % 24).padStart(2, "0") + ":00";
    parts.push(`<line x1="${x(mm).toFixed(1)}" x2="${x(mm).toFixed(1)}" y1="${m.t - 4}" y2="${h - m.b}" stroke="var(--c-grid)"/>
      <text x="${x(mm).toFixed(1)}" y="${m.t - 9}" text-anchor="middle" font-size="10.5" fill="var(--ink-3)">${label}</text>`);
  }
  nights.forEach((n, i) => {
    const cy = m.t + i * rowH + rowH / 2;
    parts.push(`<text x="${m.l - 8}" y="${(cy + 4).toFixed(1)}" text-anchor="end" font-size="11" fill="var(--ink-3)">${esc(shortDay(n.date))}</text>`);
    if (target) {
      parts.push(`<rect x="${x(target.start).toFixed(1)}" y="${(cy - rowH / 2 + 2).toFixed(1)}" width="${(x(target.end) - x(target.start)).toFixed(1)}" height="${rowH - 4}" rx="4" fill="none" stroke="var(--line-2)" stroke-dasharray="3 3"/>`);
    }
    if (n.alarm) {
      const [hh, mi] = n.alarm.split(":").map(Number); const am = hh * 60 + mi + 720;
      parts.push(`<line x1="${x(am).toFixed(1)}" x2="${x(am).toFixed(1)}" y1="${(cy - rowH / 2 + 1).toFixed(1)}" y2="${(cy + rowH / 2 - 1).toFixed(1)}" stroke="var(--accent)" stroke-width="2"/>`);
    }
    if (n.start && n.end) {
      const begin = fromNoon(n.start), span = (toDate(n.end) - toDate(n.start)) / 60000; // wake can be after noon
      const a = Math.max(x0, begin), b = Math.min(x1, begin + span);
      parts.push(`<rect x="${x(a).toFixed(1)}" y="${(cy - 5).toFixed(1)}" width="${Math.max(2, x(b) - x(a)).toFixed(1)}" height="10" rx="5" fill="var(--c-sleep)"
        data-tip="${esc(`${shortDay(n.date)} · ${clock(n.start)}–${clock(n.end)} · ${dur(n.sleep_min)}${n.alarm ? ` · ${t("sleep.alarm_at", { alarm: n.alarm })}` : ""}`)}"/>`);
    } else {
      parts.push(`<text x="${x(x0 + 30)}" y="${(cy + 4).toFixed(1)}" font-size="10.5" fill="var(--ink-3)">${esc(t("sleep.no_record"))}</text>`);
    }
  });
  return `<svg viewBox="0 0 ${width} ${h}" width="${width}" height="${h}" role="img" aria-label="${esc(t("sleep.windows"))}">${parts.join("")}</svg>`;
}

// ---- the alarm ladder: steps down after on-time mornings ---------------------------------------------------
export function ladderChart(ladder, { width, height = 200, final }) {
  if (!ladder.length) return "";
  const m = { l: 48, r: 12, t: 14, b: 24 };
  const toMin = (s) => { const [h, mi] = s.split(":").map(Number); return h * 60 + mi; };
  const wakes = ladder.filter((d) => d.woke).map((d) => { const w = toDate(d.woke); return w.getHours() * 60 + w.getMinutes(); });
  const alarmsMin = ladder.map((d) => toMin(d.alarm));
  let lo = Math.min(toMin(final), ...alarmsMin, ...wakes) - 20, hi = Math.max(...alarmsMin, ...wakes) + 20;
  const x = linear(0, Math.max(1, ladder.length), m.l, width - m.r), y = linear(lo, hi, m.t, height - m.b); // earlier = higher
  const parts = [];
  const clockStep = [15, 30, 60, 120].find((st) => (hi - lo) / st <= 5) || 180;  // clock ticks land on round times
  for (let v = Math.ceil(lo / clockStep) * clockStep; v <= hi; v += clockStep) parts.push(`<line x1="${m.l}" x2="${width - m.r}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}" stroke="var(--c-grid)"/>
    <text x="${m.l - 8}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end" font-size="11" fill="var(--ink-3)" class="num">${String(Math.floor(v / 60)).padStart(2, "0")}:${String(Math.round(v % 60)).padStart(2, "0")}</text>`);
  parts.push(`<line x1="${m.l}" x2="${width - m.r}" y1="${y(toMin(final)).toFixed(1)}" y2="${y(toMin(final)).toFixed(1)}" stroke="var(--ink-3)" stroke-dasharray="4 4"/>
    <text x="${width - m.r}" y="${(y(toMin(final)) - 6).toFixed(1)}" text-anchor="end" font-size="11" fill="var(--ink-2)">${esc(t("sleep.final", { alarm: final }))}</text>`);
  let d = "";
  ladder.forEach((day, i) => { const v = y(toMin(day.alarm)); d += `${i ? "L" : "M"}${x(i).toFixed(1)},${v.toFixed(1)}L${x(i + 1).toFixed(1)},${v.toFixed(1)}`; });
  parts.push(`<path d="${d}" fill="none" stroke="var(--accent)" stroke-width="2.2" stroke-linejoin="round"/>`);
  ladder.forEach((day, i) => {
    const cx = (x(i) + x(i + 1)) / 2;
    if (day.woke) {
      const w = toDate(day.woke); const v = w.getHours() * 60 + w.getMinutes();
      const color = day.on_time ? "var(--good)" : "var(--off)";
      parts.push(`<circle cx="${cx.toFixed(1)}" cy="${y(v).toFixed(1)}" r="4.5" fill="${color}" stroke="var(--surface)" stroke-width="2"/>`);
    }
    const tip = `${shortDay(day.date)} · ${t("sleep.alarm_at", { alarm: day.alarm })} · ${day.woke ? t("sleep.woke_at", { woke: clock(day.woke) }) : t("sleep.no_record")}`;
    parts.push(`<rect x="${x(i).toFixed(1)}" y="${m.t}" width="${(x(i + 1) - x(i)).toFixed(1)}" height="${height - m.t - m.b}" fill="transparent" data-tip="${esc(tip)}"/>`);
    if (i % Math.ceil(ladder.length / 7) === 0) parts.push(`<text x="${cx.toFixed(1)}" y="${height - 6}" text-anchor="middle" font-size="10.5" fill="var(--ink-3)">${esc(shortDay(day.date))}</text>`);
  });
  return `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${esc(t("sleep.ladder"))}">${parts.join("")}</svg>`;
}

// ---- arrival calendar: one cell per day ----------------------------------------------------------------------
export function coverage(marks, first, { width, height = 16 }) {
  const n = marks.length, gap = 1.5, w = (width - gap * (n - 1)) / n;
  return `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" aria-hidden="true">${[...marks].map((c, i) => {
    const d = new Date(toDate(first)); d.setDate(d.getDate() + i);
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const fill = c === "1" ? "var(--c-mark)" : c === "p" ? "var(--ink-3)" : "var(--c-band)";
    const op = c === "1" ? 0.8 : c === "p" ? 0.5 : 1;
    return `<rect x="${(i * (w + gap)).toFixed(1)}" y="0" width="${Math.max(1, w).toFixed(1)}" height="${height}" rx="2" fill="${fill}" fill-opacity="${op}" data-tip="${esc(`${shortDay(iso)} · ${t(`data.mark.${c}`)}`)}"/>`;
  }).join("")}</svg>`;
}

// ---- lanes: one row per activity, columns over hours or days, each row on its own scale -------------
// rows: [{key, label, sub, parts: [[partKey, color]], values: [{partKey: minutes} | null], max, limit, limitLabel}]
// cols: [{label, tip, shade}]. showMax: write each row's top value under its name (off when every row has the same scale)
export function lanes(rows, cols, { width, rowH = 46, gap = 10, labelW = 150, labelEvery = 1, unitFmt = dur, showMax = true }) {
  const top = 4, axis = 20;
  const plotW = width - labelW - 8;
  const slot = plotW / cols.length;
  const bw = Math.max(2, Math.min(22, slot - 2));
  const height = top + rows.length * (rowH + gap) + axis;
  const parts = [];
  rows.forEach((row, r) => {
    const y0 = top + r * (rowH + gap), base = y0 + rowH;
    parts.push(`<text x="0" y="${y0 + 16}" font-size="12.5" font-weight="650" fill="var(--ink)">${esc(row.label)}</text>`);
    if (row.sub) parts.push(`<text x="0" y="${y0 + 33}" font-size="11.5" fill="var(--ink-3)">${esc(row.sub)}</text>`);
    parts.push(`<rect x="${labelW}" y="${y0}" width="${plotW}" height="${rowH}" rx="6" fill="var(--c-band)" fill-opacity=".55"/>`);
    const scale = (rowH - 4) / Math.max(1, row.max);
    cols.forEach((c, i) => {
      const cx = labelW + slot * i + slot / 2;
      if (c.shade) parts.push(`<rect x="${(cx - slot / 2).toFixed(1)}" y="${y0}" width="${slot.toFixed(1)}" height="${rowH}" fill="var(--c-band)"/>`);
      const v = row.values[i];
      if (v === null || v === undefined) {
        parts.push(`<text x="${cx.toFixed(1)}" y="${base - 6}" text-anchor="middle" font-size="9" fill="var(--ink-3)">×</text>`);
        return;
      }
      let y = base;
      row.parts.forEach(([key, color]) => {
        const m = v[key] || 0;
        if (m <= 0) return;
        const h = Math.min(rowH - 2, m * scale);
        parts.push(`<rect x="${(cx - bw / 2).toFixed(1)}" y="${(y - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0.8, h - 1).toFixed(1)}" rx="1.5" fill="${color}"/>`);
        y -= h;
      });
      const total = row.parts.reduce((s, [key]) => s + (v[key] || 0), 0);
      const tip = `${row.label} · ${c.tip || c.label} · ${unitFmt(total)}`;
      parts.push(`<rect x="${(cx - slot / 2).toFixed(1)}" y="${y0}" width="${slot.toFixed(1)}" height="${rowH}" fill="transparent" data-tip="${esc(tip)}"/>`);
    });
    // the row's scale and its limit sit under its label, never over the bars
    let ty = y0 + (row.sub ? 48 : 33);
    if (showMax) {
      parts.push(`<text x="0" y="${ty}" font-size="10.5" fill="var(--ink-3)">${esc(t("chart.row_max", { v: unitFmt(row.max) }))}</text>`);
      ty += 15;
    }
    if (row.limit) {
      const ly = base - row.limit * scale;
      parts.push(`<line x1="${labelW}" x2="${labelW + plotW}" y1="${ly.toFixed(1)}" y2="${ly.toFixed(1)}" stroke="var(--ink)" stroke-width="1" stroke-dasharray="4 3"/>
        <line x1="0" x2="12" y1="${ty - 3.5}" y2="${ty - 3.5}" stroke="var(--ink)" stroke-width="1" stroke-dasharray="4 3"/>
        <text x="16" y="${ty}" font-size="10.5" fill="var(--ink-2)">${esc(row.limitLabel || "")}</text>`);
    }
  });
  const yAxis = top + rows.length * (rowH + gap) + 12;
  cols.forEach((c, i) => {
    if (i % labelEvery) return;
    parts.push(`<text x="${(labelW + slot * i + slot / 2).toFixed(1)}" y="${yAxis}" text-anchor="middle" font-size="10.5" fill="var(--ink-3)">${esc(c.label)}</text>`);
  });
  return `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${esc(rows.map((r) => r.label).join(", "))}">${parts.join("")}</svg>`;
}
