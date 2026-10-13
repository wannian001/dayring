// dayring design kit: hand-drawn SVG charts. Part of the kit (see docs/DESIGN_KIT.md).
// Each chart is drawn at the real pixel width of its box and redrawn on resize (draw()), so text never
// scales with the chart. Colours are CSS variables from tokens.css. This file imports nothing: words and
// number formats come from the app through setFormat() (dayring hands over its i18n.js in app.js).
// Convention: the comment line right above each export is its one-line doc (`dayring kit json` reads it).

const has = (v) => v !== null && v !== undefined && !Number.isNaN(v);
// Escapes text for HTML and SVG attributes and content.
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// ---- words and formats -------------------------------------------------------------------------
const MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
// The words the charts write, with their English defaults; an app's own t() gets the same keys.
export const CHART_WORDS = Object.freeze({
  "ui.no_data": "No data yet", band: "normal {low}–{high}",
  "ring.label": "Day ring: last night's sleep, the day's calendar and workouts, and screen time by hour", "ring.sleep": "Sleep",
  "cat.focus": "Focus", "cat.fun": "Entertainment & social", "cat.communication": "Communication", "cat.other": "Other",
  "chart.avg7": "7-day average", "chart.series": "Chart", "chart.row_max": "top {v}",
  "sleep.alarm_at": "alarm {alarm}", "sleep.no_record": "no record", "sleep.windows": "Last 21 nights", "sleep.final": "goal {alarm}",
  "sleep.woke_at": "woke {woke}", "sleep.ladder": "The alarm ladder",
  "data.mark.1": "has data", "data.mark.p": "partial", "data.mark.0": "nothing",
});
const parseIso = (iso) => {
  const [d, time = "00:00"] = String(iso).split("T");
  const [y, m, dd] = d.split("-").map(Number);
  const [hh, mm] = time.split(":").map(Number);
  return new Date(y, m - 1, dd, hh || 0, mm || 0);
};
const fill = (text, vars = {}) => String(text).replace(/\{(\w+)\}/g, (_, name) => (vars[name] ?? `{${name}}`));
const FMT = {
  t: (key, vars = {}) => fill(CHART_WORDS[key] ?? key, vars),
  toDate: parseIso,
  dur: (minutes) => {
    if (!has(minutes)) return "—";
    const total = Math.round(Math.abs(minutes)), h = Math.floor(total / 60), m = total % 60;
    return h === 0 ? `${m}m` : m ? `${h}h ${m}m` : `${h}h`;
  },
  clock: (iso) => { if (!iso) return "—"; const d = parseIso(iso); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; },
  shortDay: (iso) => { const d = parseIso(iso); return `${d.getDate()} ${MONTH[d.getMonth()]}`; },
  measure: (value, unit) => (!has(value) ? "—" : unit === "min" ? FMT.dur(value) : `${Math.round(value)}${unit && unit !== "steps" ? ` ${unit}` : ""}`),
  wtype: (name) => (name ? String(name).charAt(0).toUpperCase() + String(name).slice(1) : "—"),
};
// Hands the kit an app's words and formats: any of t, dur, clock, shortDay, measure, toDate, wtype; a word t() lacks falls back to CHART_WORDS.
export function setFormat(fns) {
  const next = { ...fns };
  if (typeof fns.t === "function") {
    // an app's t() usually answers a key it does not know with the key itself: the chart then writes CHART_WORDS' English
    const appT = fns.t;
    next.t = (key, vars = {}) => {
      const said = appT(key, vars);
      return (said === key || said === undefined || said === null) && key in CHART_WORDS ? fill(CHART_WORDS[key], vars) : said;
    };
  }
  Object.assign(FMT, next);
}
const t = (...a) => FMT.t(...a), dur = (...a) => FMT.dur(...a), clock = (...a) => FMT.clock(...a);
const shortDay = (...a) => FMT.shortDay(...a), measure = (...a) => FMT.measure(...a), toDate = (...a) => FMT.toDate(...a);
const wtype = (...a) => FMT.wtype(...a);
// Minutes written as a duration by the dur() handed to setFormat() ("7h 54m" by default); stackedColumns and lanes write their values with it.
export const formatDuration = (minutes) => FMT.dur(minutes);

// ---- tone ----------------------------------------------------------------------------------------
// The colour of a mark for a tone: "good" = --good, "bad" = --off, anything else = the neutral --c-mark.
export const toneColor = (tone) => (tone === "good" ? "var(--good)" : tone === "bad" ? "var(--off)" : "var(--c-mark)");

// ---- drawing at real width ---------------------------------------------------------------------
const draws = new WeakMap();
const observer = typeof ResizeObserver === "function"
  ? new ResizeObserver((entries) => entries.forEach(({ target }) => {
      const fn = draws.get(target);
      if (fn && target.clientWidth) target.innerHTML = fn(target.clientWidth);
    }))
  : null;
// Draws fn(width) into el at its real pixel width and again whenever the box is resized.
export function draw(el, fn) {
  if (!el) return;
  draws.set(el, fn);
  el.innerHTML = fn(el.clientWidth || 320);
  if (observer) observer.observe(el);
}

// ---- tooltip (one for the page; marks carry data-tip) ----------------------------------------
let tip = null;
// Adds the page's one tooltip (.tip): any element with data-tip shows it on hover and on keyboard focus.
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
// A round axis step (1, 2, 2.5 or 5 times a power of ten) that splits span into about count parts.
export function niceStep(span, count = 4) {
  const raw = span / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(raw || 1));
  return [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw;
}
// about how wide a label is at font size `size`: CJK characters are square, Latin ones about 0.56 em
const textWidth = (text, size = 11) => [...String(text)].reduce((w, ch) => w + (/[\u2e80-\u9fff\uff00-\uffef]/.test(ch) ? size : size * 0.56), 0);
const linear = (d0, d1, r0, r1) => (v) => (d1 === d0 ? (r0 + r1) / 2 : r0 + ((v - d0) / (d1 - d0)) * (r1 - r0));

// ---- sparkline with "your normal" band -------------------------------------------------------
// 14 days as a line over the "your normal" band; × marks a day without a record, the end dot takes the tone.
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
  const endColor = toneColor(tone);
  const hit = pts.map((p) => {
    const w = width / pts.length;
    const label = `${shortDay(p.date)} · ${has(p.value) ? measure(p.value, unit) : t("ui.no_data")}`;
    return `<rect x="${(x(p.i) - w / 2).toFixed(1)}" y="0" width="${w.toFixed(1)}" height="${height}" fill="transparent" data-tip="${esc(label)}"/>`;
  }).join("");
  const gaps = pts.filter((p) => !has(p.value)).map((p) => `<text x="${x(p.i).toFixed(1)}" y="${height - 2}" text-anchor="middle" font-size="9" fill="var(--ink-3)">×</text>`).join("");
  return `<svg viewBox="0 0 ${width} ${height}" height="${height}" role="img" aria-label="${esc(t("band", { low: measure(band?.q1, unit), high: measure(band?.q3, unit) }))}">
    ${band ? `<rect x="0" y="${y(band.q3).toFixed(1)}" width="${width}" height="${Math.max(1, y(band.q1) - y(band.q3)).toFixed(1)}" rx="3" fill="var(--c-band)"/>` : ""}
    <path d="${path}" fill="none" stroke="var(--ink-2)" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>
    ${last ? `<circle cx="${x(last.i).toFixed(1)}" cy="${y(last.value).toFixed(1)}" r="4" fill="${endColor}" stroke="var(--halo)" stroke-width="2"/>` : ""}
    ${gaps}${hit}</svg>`;
}

// ---- value vs band on one line -------------------------------------------------------------------
// One value against its band on a line: band = normal, tick = its median, dot = the value in its tone.
export function bullet(value, band, { width, unit = "", tone = "neutral", height = 18 }) {
  if (!has(value)) return "";
  let lo = value, hi = value;
  if (band) { lo = Math.min(lo, band.q1); hi = Math.max(hi, band.q3); }
  const span = hi - lo || Math.abs(value) || 1;
  const x = linear(lo - span * 0.35, hi + span * 0.35, 6, width - 6);
  const color = toneColor(tone);
  return `<svg viewBox="0 0 ${width} ${height}" height="${height}" aria-hidden="true">
    <line x1="2" x2="${width - 2}" y1="${height / 2}" y2="${height / 2}" stroke="var(--line-2)" stroke-width="2" stroke-linecap="round"/>
    ${band ? `<rect x="${x(band.q1).toFixed(1)}" y="${height / 2 - 5}" width="${Math.max(2, x(band.q3) - x(band.q1)).toFixed(1)}" height="10" rx="5" fill="var(--c-band)" stroke="var(--line-2)"/>
      <line x1="${x(band.median).toFixed(1)}" x2="${x(band.median).toFixed(1)}" y1="${height / 2 - 5}" y2="${height / 2 + 5}" stroke="var(--ink-3)" stroke-width="1.5"/>` : ""}
    <circle cx="${x(value).toFixed(1)}" cy="${height / 2}" r="5.5" fill="${color}" stroke="var(--halo)" stroke-width="2"/></svg>`;
}

// ---- one value on its own scale, with a plan --------------------------------------------------------
// One value on its own scale: band = normal (q1–q3), tick = median, dot = the value, dashed tick = a plan or limit.
export function rangeStrip(row, { width, height = 30, pad = 10 }) {
  // nothing is drawn for a row without a value: a plan tick on an empty line says nothing
  if (!has(row.value)) return "";
  const h = height;
  const vals = [row.value, row.band?.q1, row.band?.q3, row.plan?.limit].filter(has);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const span = hi - lo || Math.abs(hi) * 0.2 || 1;
  lo -= span * 0.25; hi += span * 0.25;
  const x = (v) => pad + ((v - lo) / (hi - lo)) * (width - 2 * pad);
  const parts = [`<line x1="${pad}" x2="${width - pad}" y1="${h / 2}" y2="${h / 2}" stroke="var(--line-2)" stroke-width="2" stroke-linecap="round"/>`];
  if (row.band) {
    parts.push(`<rect x="${x(row.band.q1).toFixed(1)}" y="${h / 2 - 6}" width="${Math.max(3, x(row.band.q3) - x(row.band.q1)).toFixed(1)}" height="12" rx="6" fill="var(--c-band)" stroke="var(--line-2)"/>`);
    parts.push(`<line x1="${x(row.band.median).toFixed(1)}" x2="${x(row.band.median).toFixed(1)}" y1="${h / 2 - 6}" y2="${h / 2 + 6}" stroke="var(--ink-3)" stroke-width="1.5"/>`);
  }
  if (row.plan) parts.push(`<line x1="${x(row.plan.limit).toFixed(1)}" x2="${x(row.plan.limit).toFixed(1)}" y1="2" y2="${h - 2}" stroke="var(--ink)" stroke-width="1.5" stroke-dasharray="3 2"/>`);
  parts.push(`<circle cx="${x(row.value).toFixed(1)}" cy="${h / 2}" r="6" fill="${toneColor(row.tone)}" stroke="var(--halo)" stroke-width="2"/>`);
  return `<svg viewBox="0 0 ${width} ${h}" width="${width}" height="${h}" aria-hidden="true">${parts.join("")}</svg>`;
}

// ---- a few averages as a line --------------------------------------------------------------------
// A short line through a few averages (eight weeks, say) with an end dot; missing points are bridged; needs two.
export function trendLine(points, { width, height = 34, tip = () => "" }) {
  const h = height, n = points.length;
  const pts = points.map((p, i) => ({ ...p, i })).filter((p) => has(p.value));
  if (pts.length < 2) return "";
  const vals = pts.map((p) => p.value);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.2 || 1; lo -= pad; hi += pad;
  const x = (i) => 4 + (i / (n - 1)) * (width - 8), y = (v) => h - 4 - ((v - lo) / (hi - lo)) * (h - 8);
  const d = pts.map((p, k) => `${k ? "L" : "M"}${x(p.i).toFixed(1)},${y(p.value).toFixed(1)}`).join("");
  const last = pts[pts.length - 1];
  const slot = width / n;
  const tips = points.map((p, i) => `<rect x="${(x(i) - slot / 2).toFixed(1)}" y="0" width="${slot.toFixed(1)}" height="${h}" fill="transparent" data-tip="${esc(tip(p, i))}"/>`).join("");
  return `<svg viewBox="0 0 ${width} ${h}" width="${width}" height="${h}" aria-hidden="true">
    <path d="${d}" fill="none" stroke="var(--ink-2)" stroke-width="1.6" stroke-linejoin="round"/>
    <circle cx="${x(last.i).toFixed(1)}" cy="${y(last.value).toFixed(1)}" r="3.5" fill="var(--c-mark)"/>${tips}</svg>`;
}

// ---- legend keys ---------------------------------------------------------------------------------
const KEY = {
  normal: `<svg width="20" height="12" aria-hidden="true"><rect x=".5" y=".5" width="19" height="11" rx="5.5" fill="var(--c-band)" stroke="var(--line-2)"/></svg>`,
  median: `<svg width="20" height="12" aria-hidden="true"><rect x=".5" y=".5" width="19" height="11" rx="5.5" fill="var(--c-band)" stroke="var(--line-2)"/><line x1="10" x2="10" y1=".5" y2="11.5" stroke="var(--ink-3)" stroke-width="1.5"/></svg>`,
  now: `<svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="5" fill="var(--c-mark)"/></svg>`,
  plan: `<svg width="6" height="18" aria-hidden="true"><line x1="3" x2="3" y1="1" y2="17" stroke="var(--ink)" stroke-width="1.5" stroke-dasharray="3 2"/></svg>`,
  weeks: `<svg width="22" height="12" aria-hidden="true"><path d="M1 9 7 5l6 2.5L19 2" fill="none" stroke="var(--ink-2)" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/><circle cx="19" cy="2.6" r="2" fill="var(--c-mark)"/></svg>`,
};
// A legend key drawn the way its mark is drawn: "normal" (band), "median", "now" (dot), "plan" (dashed tick), "weeks" (trend).
export function legendKey(kind) { return KEY[kind] || ""; }

// ---- the day ring --------------------------------------------------------------------------------
// The screen groups of the ring, inside out: [key, the categories it adds up, colour].
export const RING_CATS = [["focus", ["work", "learning"], "var(--c-focus)"], ["fun", ["entertainment", "social"], "var(--c-fun)"],
  ["communication", ["communication"], "var(--c-comms)"], ["other", ["other"], "var(--c-other)"]];

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

// A 24-hour clock, midnight at the top: sleep outside, calendar and workouts in the middle, screen minutes per hour inside.
export function dayRing(ring, { size = 360, center = "", centerSub = "", cats = RING_CATS }) {
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
    cats.forEach(([key, keys, color]) => {
      const minutes = keys.reduce((sum, k) => sum + (hour[k] || 0), 0);
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
    parts.push(`<circle cx="${x1.toFixed(1)}" cy="${y1.toFixed(1)}" r="${4 * s}" fill="var(--accent)" stroke="var(--halo)" stroke-width="2"/>`);
  }
  parts.push(`<text x="${c}" y="${c + 2 * s}" text-anchor="middle" font-size="${30 * s}" font-weight="680" fill="var(--ink)" letter-spacing="-.5">${esc(center)}</text>`);
  parts.push(`<text x="${c}" y="${c + 22 * s}" text-anchor="middle" font-size="${11.5 * s}" font-weight="550" fill="var(--ink-3)">${esc(centerSub)}</text>`);
  return `<svg class="ring" viewBox="0 0 ${size} ${size}" role="img" aria-label="${esc(t("ring.label"))}">${parts.join("")}</svg>`;
}

// ---- difference with interval, against zero ------------------------------------------------------
// A difference with its 95% interval against a zero line; right = a better next day (flip mirrors it).
export function interval(row, domain, { width, height = 26, flip = false }) {
  // right = a better next day: when lower is better (resting heart rate) the values are mirrored
  const x = linear(-domain, domain, 8, width - 8);
  const zero = x(0);
  const base = `<line x1="${zero}" x2="${zero}" y1="2" y2="${height - 2}" stroke="var(--c-axis)" stroke-width="1"/>`;
  if (row.status !== "ok") return `<svg viewBox="0 0 ${width} ${height}" height="${height}" aria-hidden="true">${base}</svg>`;
  const s = flip ? -1 : 1;
  const d = s * row.diff, lo = Math.min(s * row.low, s * row.high), hi = Math.max(s * row.low, s * row.high);
  const color = row.detected ? toneColor(d > 0 ? "good" : "bad") : "var(--ink-3)";
  const clamp = (v) => Math.max(8, Math.min(width - 8, x(v)));
  return `<svg viewBox="0 0 ${width} ${height}" height="${height}" aria-hidden="true">${base}
    <line x1="${clamp(lo).toFixed(1)}" x2="${clamp(hi).toFixed(1)}" y1="${height / 2}" y2="${height / 2}" stroke="${color}" stroke-width="2.5" stroke-linecap="round"/>
    <circle cx="${clamp(d).toFixed(1)}" cy="${height / 2}" r="5" fill="${color}" stroke="var(--halo)" stroke-width="2"/></svg>`;
}

// ---- seven small day columns (training) -------------------------------------------------------------
// One circle per day: filled = done, hollow = 0, dashed = no record; the day of the month under each.
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
// text drawn over marks gets a ring in the colour behind it (the kit's halo rule)
const HALO = 'paint-order="stroke" stroke="var(--halo)" stroke-width="3" stroke-linejoin="round"';
const dayIndex = (iso, first) => Math.round((toDate(iso) - toDate(first)) / 86400000);
// a step for an axis in minutes: a round number of minutes or hours, so ticks read 0 / 2h / 4h, never 3h 20m
const minuteStep = (span, count = 4) => [5, 10, 15, 30, 60, 120, 180, 240, 360, 480, 720, 1440].find((s) => span / s <= count) || niceStep(span, count);
// the smallest k at which every k-th label, centred in slots `slot` wide, keeps `gap` px from the next one kept
function keepEvery(widths, slot, gap) {
  for (let k = 1; k < widths.length; k++) {
    let fits = true;
    for (let i = 0; i + k < widths.length && fits; i += k) fits = (widths[i] + widths[i + k]) / 2 + gap <= k * slot;
    if (fits) return k;
  }
  return Math.max(1, widths.length);
}
// a label centred on x, kept inside 0..width (the first and last labels of a narrow chart would be cut at the edge)
function inside(x, text, size, width) {
  const half = textWidth(text, size) / 2;
  return x - half < 1 ? 'x="1" text-anchor="start"' : x + half > width - 1 ? `x="${width - 1}" text-anchor="end"` : `x="${x.toFixed(1)}" text-anchor="middle"`;
}
function yTicks(lo, hi, count = 4, stepOf = niceStep) {
  const step = stepOf(hi - lo, count);
  const start = Math.ceil(lo / step) * step;
  const out = [];
  for (let v = start; v <= hi + 1e-9; v += step) out.push(Number(v.toFixed(6)));
  return out;
}

// ---- time series: corridor band, points, smoothed line, reference lines ---------------------------------
// layers: { band: [{date, low, high}], points: [{date, value}], line: [{date, value}], refs: [{value, label}] }
// A date axis with a shaded corridor, faint daily points, a line that breaks after maxGap days and dashed reference lines.
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
  // date labels at least 44 px apart (a label is up to ~38 px), so a long span on a phone does not pile up
  const base = n > 90 ? 30 : n > 40 ? 14 : 7;
  const room = Math.max(2, Math.floor((width - m.l - m.r) / 44));
  const tickEvery = Math.max(base, Math.ceil(n / (room - 1) / base) * base);
  for (let k = 0; k <= n; k += tickEvery) {
    const d = new Date(toDate(first)); d.setDate(d.getDate() + k);
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const anchor = x(k) + 20 > width ? "end" : "middle";  // the last label stays inside the chart
    parts.push(`<text x="${(anchor === "end" ? width - 1 : x(k)).toFixed(1)}" y="${height - 6}" text-anchor="${anchor}" font-size="11" fill="var(--ink-3)">${esc(shortDay(iso))}</text>`);
  }
  if (layers.band && layers.band.length) {
    const top = layers.band.map((b) => `${X(b.date).toFixed(1)},${y(b.high).toFixed(1)}`);
    const bottom = [...layers.band].reverse().map((b) => `${X(b.date).toFixed(1)},${y(b.low).toFixed(1)}`);
    parts.push(`<polygon points="${[...top, ...bottom].join(" ")}" fill="var(--accent-soft)" stroke="none"/>`);
  }
  (layers.refs || []).forEach((r) => parts.push(`<line x1="${m.l}" x2="${width - m.r}" y1="${y(r.value).toFixed(1)}" y2="${y(r.value).toFixed(1)}" stroke="var(--ink-3)" stroke-dasharray="4 4"/>`));
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
    parts.push(`<circle cx="${X(end.date).toFixed(1)}" cy="${y(end.value).toFixed(1)}" r="4.5" fill="var(--c-mark)" stroke="var(--halo)" stroke-width="2"/>`);
  }
  // a reference line's label goes over the points and the line, with a halo so it reads on top of them
  (layers.refs || []).forEach((r) => parts.push(`<text x="${width - m.r}" y="${(y(r.value) - 6).toFixed(1)}" text-anchor="end" font-size="11" fill="var(--ink-2)" ${HALO}>${esc(r.label)}</text>`));
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
// Columns of stacked categories on one scale (minutes tick on round hours), with an optional dashed limit named in a key under the axis; × = no record.
export function stackedColumns(columns, groups, { width, height = 200, limit = null, limitLabel = "", maxValue = null, labelEvery = 1, unitFmt = formatDuration, minutes = true }) {
  const totals = columns.map((c) => groups.reduce((s, [k]) => s + (c.values?.[k] || 0), 0));
  const top = maxValue || Math.max(limit || 0, ...totals, 1);
  // values in minutes step on round minutes or hours (0 / 2h / 4h); anything else on 1, 2, 2.5 or 5 times a power of ten
  const ticks = yTicks(0, top * 1.05, 4, minutes ? minuteStep : niceStep);
  // the limit's label sits in a key row under the axis, never over the columns (as lanes() keeps it under the row's name)
  const keyRow = limit && limitLabel ? 20 : 0;
  // the left margin fits the longest tick label ("6h", "6 小时")
  const m = { l: Math.max(44, Math.ceil(12 + Math.max(...ticks.map((v) => textWidth(unitFmt(v)))))), r: 8, t: 14, b: 24 + keyRow };
  const hi = Math.max(top * 1.05, ticks[ticks.length - 1]);
  const y = linear(0, hi, height - m.b, m.t);
  const slot = (width - m.l - m.r) / columns.length;
  const bw = Math.max(3, Math.min(28, slot - 3));
  // labelEvery, or more when neighbouring labels would still run into each other
  const every = Math.max(labelEvery, keepEvery(columns.map((c) => textWidth(c.label || "", 10.5)), slot, 6));
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
    if (i % every === 0) parts.push(`<text ${inside(cx, c.label || "", 10.5, width)} y="${height - keyRow - 6}" font-size="10.5" fill="var(--ink-3)">${esc(c.label)}</text>`);
  });
  parts.push(`<line x1="${m.l}" x2="${width - m.r}" y1="${y(0)}" y2="${y(0)}" stroke="var(--c-axis)"/>`);
  if (limit) parts.push(`<line x1="${m.l}" x2="${width - m.r}" y1="${y(limit).toFixed(1)}" y2="${y(limit).toFixed(1)}" stroke="var(--ink)" stroke-width="1.2" stroke-dasharray="5 4"/>`);
  if (keyRow) parts.push(`<line x1="${m.l}" x2="${m.l + 14}" y1="${height - 7.5}" y2="${height - 7.5}" stroke="var(--ink)" stroke-width="1.2" stroke-dasharray="5 4"/>
    <text x="${m.l + 20}" y="${height - 4}" font-size="11" fill="var(--ink-2)">${esc(limitLabel)}</text>`);
  return `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${esc(limitLabel)}">${parts.join("")}</svg>`;
}

// ---- blocks stacked in columns ------------------------------------------------------------------------------
// columns: [{label, sub, total, blocks: [{value, tone: "mark" | "watch" | "none", faded, text, tip}]}], bottom block first
// Columns of stacked blocks, one per item (block height = its value), a total above each column and two label lines under it.
export function blockColumns(columns, { width, height = 210, minTop = 60, label = "", maxChars = 12 }) {
  const m = { l: 8, r: 8, t: 18, b: 34 };
  const slot = (width - m.l - m.r) / columns.length;
  const bw = Math.min(120, slot - 14);
  const max = Math.max(minTop, ...columns.map((c) => c.blocks.reduce((s, b) => s + b.value, 0)));
  const scale = (height - m.t - m.b) / max;
  // in a narrow box a label that would run into its neighbour's is left out, every k-th one kept (k the same along the row)
  const labelEvery = keepEvery(columns.map((c) => textWidth(c.label || "", 11)), slot, 5);
  const subEvery = keepEvery(columns.map((c) => textWidth(c.sub || "", 10.5)), slot, 4);
  const parts = [];
  columns.forEach((col, i) => {
    const cx = m.l + slot * i + slot / 2;
    let y = height - m.b;
    col.blocks.forEach((b) => {
      const h = Math.max(4, b.value * scale);
      const fill = b.tone === "none" ? "var(--c-band)" : b.tone === "watch" ? "var(--watch)" : "var(--c-mark)";
      const op = b.tone === "none" ? 1 : b.tone === "watch" ? 0.9 : b.faded ? 0.25 : 0.72;
      // text on the block: inverted on the ink block, dark on amber, plain ink on a faded or empty one
      const ink = b.tone === "watch" ? "var(--on-watch)" : b.tone === "none" ? "var(--ink-2)" : b.faded ? "var(--ink)" : "var(--surface)";
      parts.push(`<rect x="${(cx - bw / 2).toFixed(1)}" y="${(y - h + 1).toFixed(1)}" width="${bw.toFixed(1)}" height="${(h - 2).toFixed(1)}" rx="4" fill="${fill}" fill-opacity="${op}"
        data-tip="${esc(b.tip || "")}"/>`);
      if (b.text && h > 18 && bw > 50) parts.push(`<text x="${cx.toFixed(1)}" y="${(y - h / 2 + 4).toFixed(1)}" text-anchor="middle" font-size="10.5" font-weight="600" fill="${ink}" pointer-events="none">${esc(String(b.text).slice(0, maxChars))}</text>`);
      y -= h;
    });
    parts.push(`<text x="${cx.toFixed(1)}" y="${(y - 6).toFixed(1)}" text-anchor="middle" font-size="11" fill="var(--ink-2)" font-weight="600">${esc(col.total || "")}</text>`);
    if (i % labelEvery === 0) parts.push(`<text ${inside(cx, col.label || "", 11, width)} y="${height - 18}" font-size="11" fill="var(--ink-2)" font-weight="600">${esc(col.label || "")}</text>`);
    if (i % subEvery === 0) parts.push(`<text ${inside(cx, col.sub || "", 10.5, width)} y="${height - 4}" font-size="10.5" fill="var(--ink-3)">${esc(col.sub || "")}</text>`);
  });
  parts.push(`<line x1="${m.l}" x2="${width - m.r}" y1="${height - m.b}" y2="${height - m.b}" stroke="var(--c-axis)"/>`);
  return `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${esc(label)}">${parts.join("")}</svg>`;
}

// ---- nights as bars on an evening-to-afternoon axis ------------------------------------------------------
const fromNoon = (iso) => { const d = toDate(iso); const mm = d.getHours() * 60 + d.getMinutes(); return mm >= 720 ? mm - 720 : mm + 720; };
// One bar per night on a 20:00–14:00 axis, the alarm as an ink tick over it, an optional dashed target window.
export function sleepWindows(nights, { width, target = null, rowH = 18 }) {
  const m = { l: 64, r: 18, t: 22, b: 8 };  // r: half of the last hour label ("14:00") must fit
  const x0 = 8 * 60, x1 = 26 * 60; // 20:00 .. 14:00 next day, in minutes after noon
  const x = linear(x0, x1, m.l, width - m.r);
  const h = m.t + m.b + nights.length * rowH;
  const parts = [];
  const room = (step) => (width - m.l - m.r) / ((x1 - x0) / step);  // px between two hour labels
  const labelStep = [120, 240, 360].find((step) => room(step) >= textWidth("00:00", 10.5) + 12) || 540;
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
    if (n.start && n.end) {
      const begin = fromNoon(n.start), span = (toDate(n.end) - toDate(n.start)) / 60000; // wake can be after noon
      const a = Math.max(x0, begin), b = Math.min(x1, begin + span);
      parts.push(`<rect x="${x(a).toFixed(1)}" y="${(cy - 5).toFixed(1)}" width="${Math.max(2, x(b) - x(a)).toFixed(1)}" height="10" rx="5" fill="var(--c-sleep)"
        data-tip="${esc(`${shortDay(n.date)} · ${clock(n.start)}–${clock(n.end)} · ${dur(n.sleep_min)}${n.alarm ? ` · ${t("sleep.alarm_at", { alarm: n.alarm })}` : ""}`)}"/>`);
    } else {
      parts.push(`<text x="${x(x0 + 30)}" y="${(cy + 4).toFixed(1)}" font-size="10.5" fill="var(--ink-3)">${esc(t("sleep.no_record"))}</text>`);
    }
    // the alarm goes on top of the bar, in ink with a halo, so it shows on a night that ran past it
    if (n.alarm) {
      const [hh, mi] = n.alarm.split(":").map(Number); const ax = x(hh * 60 + mi + 720).toFixed(1);
      const y1 = (cy - rowH / 2 + 1).toFixed(1), y2 = (cy + rowH / 2 - 1).toFixed(1);
      parts.push(`<line x1="${ax}" x2="${ax}" y1="${y1}" y2="${y2}" stroke="var(--halo)" stroke-width="5" stroke-linecap="round" pointer-events="none"/>
        <line x1="${ax}" x2="${ax}" y1="${y1}" y2="${y2}" stroke="var(--c-mark)" stroke-width="2" stroke-linecap="round" pointer-events="none"/>`);
    }
  });
  return `<svg viewBox="0 0 ${width} ${h}" width="${width}" height="${h}" role="img" aria-label="${esc(t("sleep.windows"))}">${parts.join("")}</svg>`;
}

// ---- the alarm ladder: steps down after on-time mornings ---------------------------------------------------
// The alarm as a step line (earlier = higher) with wake dots, green on time and red late, and the goal dashed.
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
  parts.push(`<line x1="${m.l}" x2="${width - m.r}" y1="${y(toMin(final)).toFixed(1)}" y2="${y(toMin(final)).toFixed(1)}" stroke="var(--ink-3)" stroke-dasharray="4 4"/>`);
  // at most seven day labels, and never closer than the longest one needs
  const dayEvery = Math.max(Math.ceil(ladder.length / 7), keepEvery(ladder.map((day) => textWidth(shortDay(day.date), 10.5)), (width - m.l - m.r) / ladder.length, 8));
  let d = "";
  ladder.forEach((day, i) => { const v = y(toMin(day.alarm)); d += `${i ? "L" : "M"}${x(i).toFixed(1)},${v.toFixed(1)}L${x(i + 1).toFixed(1)},${v.toFixed(1)}`; });
  parts.push(`<path d="${d}" fill="none" stroke="var(--accent)" stroke-width="2.2" stroke-linejoin="round"/>`);
  ladder.forEach((day, i) => {
    const cx = (x(i) + x(i + 1)) / 2;
    if (day.woke) {
      const w = toDate(day.woke); const v = w.getHours() * 60 + w.getMinutes();
      parts.push(`<circle cx="${cx.toFixed(1)}" cy="${y(v).toFixed(1)}" r="4.5" fill="${toneColor(day.on_time ? "good" : "bad")}" stroke="var(--halo)" stroke-width="2"/>`);
    }
    const tip = `${shortDay(day.date)} · ${t("sleep.alarm_at", { alarm: day.alarm })} · ${day.woke ? t("sleep.woke_at", { woke: clock(day.woke) }) : t("sleep.no_record")}`;
    parts.push(`<rect x="${x(i).toFixed(1)}" y="${m.t}" width="${(x(i + 1) - x(i)).toFixed(1)}" height="${height - m.t - m.b}" fill="transparent" data-tip="${esc(tip)}"/>`);
    if (i % dayEvery === 0) parts.push(`<text ${inside(cx, shortDay(day.date), 10.5, width)} y="${height - 6}" font-size="10.5" fill="var(--ink-3)">${esc(shortDay(day.date))}</text>`);
  });
  // the goal's label goes over the step line and the wake dots, with a halo
  parts.push(`<text x="${width - m.r}" y="${(y(toMin(final)) - 6).toFixed(1)}" text-anchor="end" font-size="11" fill="var(--ink-2)" ${HALO} pointer-events="none">${esc(t("sleep.final", { alarm: final }))}</text>`);
  return `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${esc(t("sleep.ladder"))}">${parts.join("")}</svg>`;
}

// ---- arrival calendar: one cell per day ----------------------------------------------------------------------
// One cell per day from first: "1" = has data, "p" = partial, anything else = nothing.
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
// rows: [{key, label, sub, parts: [[partKey, color, {hatch}]], values: [{partKey: minutes} | null], max, limit, limitLabel, fmt}]
// (a row's fmt writes its values in its own unit, such as a count; the others use unitFmt)
// cols: [{label, tip, shade}]. showMax: write each row's top value under its name (off when every row has the same scale)
// A part with {hatch: true} is drawn in diagonal stripes of its colour: something on top of the rest, such as the
// minutes several devices add beyond the clock. .legend .key i.hatch is its key.
let hatchIds = 0;
// One row per activity with columns over hours or days, each row on its own scale; × = no record, dashed = a limit, stripes = a hatch part.
export function lanes(rows, cols, { width, rowH = 46, gap = 10, labelW = 150, labelEvery = 1, unitFmt = formatDuration, showMax = true }) {
  const top = 4, axis = 20;
  const plotW = width - labelW - 8;
  const slot = plotW / cols.length;
  const bw = Math.max(2, Math.min(22, slot - 2));
  const height = top + rows.length * (rowH + gap) + axis;
  const parts = [];
  const hatches = new Map();  // colour -> pattern id, unique on the page (several charts share one document)
  const fillOf = (color, opts) => {
    if (!opts?.hatch) return color;
    if (!hatches.has(color)) hatches.set(color, `lanes-hatch-${++hatchIds}`);
    return `url(#${hatches.get(color)})`;
  };
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
      row.parts.forEach(([key, color, opts]) => {
        const m = v[key] || 0;
        if (m <= 0) return;
        const h = Math.min(y - y0 - 2, m * scale);
        if (h <= 0) return;
        parts.push(`<rect x="${(cx - bw / 2).toFixed(1)}" y="${(y - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0.8, h - 1).toFixed(1)}" rx="1.5" fill="${fillOf(color, opts)}"${opts?.hatch ? ` stroke="${color}" stroke-width=".8"` : ""}/>`);
        y -= h;
      });
      const total = row.parts.reduce((s, [key]) => s + (v[key] || 0), 0);
      const tip = `${row.label} · ${c.tip || c.label} · ${(row.fmt || unitFmt)(total)}`;
      parts.push(`<rect x="${(cx - slot / 2).toFixed(1)}" y="${y0}" width="${slot.toFixed(1)}" height="${rowH}" fill="transparent" data-tip="${esc(tip)}"/>`);
    });
    // the row's scale and its limit sit under its label, never over the bars
    let ty = y0 + (row.sub ? 48 : 33);
    if (showMax) {
      parts.push(`<text x="0" y="${ty}" font-size="10.5" fill="var(--ink-3)">${esc(t("chart.row_max", { v: (row.fmt || unitFmt)(row.max) }))}</text>`);
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
  const defs = [...hatches].map(([color, id]) => `<pattern id="${id}" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="1.6" height="4" fill="${color}"/></pattern>`).join("");
  return `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${esc(rows.map((r) => r.label).join(", "))}">${defs ? `<defs>${defs}</defs>` : ""}${parts.join("")}</svg>`;
}
