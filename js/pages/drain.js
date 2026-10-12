// Drain: seven quiet signals over the last 7 days, each against your normal and, where set, your plan.
// No total score: the signals have different units and different strength of evidence.
import { draw, esc } from "../charts.js?v=60b432d5aa";
import { day, dur, inSentence, num, shortDay, t } from "../i18n.js?v=60b432d5aa";

const STATUS = { bad: "bad", good: "good", neutral: "" };
const clockOf = (noon) => { const m = ((Math.round(noon + 720) % 1440) + 1440) % 1440; return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`; };

function fmt(unit, v) {
  if (v === null || v === undefined) return "—";
  if (unit === "bpm") return `${num(v)} ${t("unit.bpm")}`;
  if (unit === "ms") return `${num(v)} ms`;
  if (unit === "clock") return clockOf(v);
  if (unit === "per_hour") return t("drain.per_hour", { v: num(v, 1) });
  return dur(v);
}

// one row's own scale: grey band = normal, tick = its median, dot = these 7 days, dashed tick = plan.
// Nothing is drawn for a row without a value: a plan tick on an empty line says nothing.
function strip(row, width) {
  if (row.value === null || row.value === undefined) return "";
  const h = 30, pad = 10;
  const vals = [row.value, row.band?.q1, row.band?.q3, row.plan?.limit].filter((v) => v !== null && v !== undefined);
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
  const color = row.tone === "bad" ? "var(--off)" : row.tone === "good" ? "var(--good)" : "var(--c-mark)";
  parts.push(`<circle cx="${x(row.value).toFixed(1)}" cy="${h / 2}" r="6" fill="${color}" stroke="var(--surface)" stroke-width="2"/>`);
  return `<svg viewBox="0 0 ${width} ${h}" width="${width}" height="${h}" aria-hidden="true">${parts.join("")}</svg>`;
}

// the legend keys, each drawn the way its mark is drawn in the rows
const KEY = {
  normal: `<svg width="20" height="12" aria-hidden="true"><rect x=".5" y=".5" width="19" height="11" rx="5.5" fill="var(--c-band)" stroke="var(--line-2)"/></svg>`,
  median: `<svg width="20" height="12" aria-hidden="true"><rect x=".5" y=".5" width="19" height="11" rx="5.5" fill="var(--c-band)" stroke="var(--line-2)"/><line x1="10" x2="10" y1=".5" y2="11.5" stroke="var(--ink-3)" stroke-width="1.5"/></svg>`,
  now: `<svg width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="5" fill="var(--c-mark)"/></svg>`,
  plan: `<svg width="6" height="18" aria-hidden="true"><line x1="3" x2="3" y1="1" y2="17" stroke="var(--ink)" stroke-width="1.5" stroke-dasharray="3 2"/></svg>`,
  weeks: `<svg width="22" height="12" aria-hidden="true"><path d="M1 9 7 5l6 2.5L19 2" fill="none" stroke="var(--ink-2)" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/><circle cx="19" cy="2.6" r="2" fill="var(--c-mark)"/></svg>`,
};

// eight weekly averages, to see the direction (HRV in particular moves slowly)
function weeks(row, width) {
  const h = 34, pts = row.weeks.map((w, i) => ({ ...w, i })).filter((w) => w.value !== null && w.value !== undefined);
  if (pts.length < 2) return "";
  const vals = pts.map((p) => p.value);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.2 || 1; lo -= pad; hi += pad;
  const x = (i) => 4 + (i / (row.weeks.length - 1)) * (width - 8), y = (v) => h - 4 - ((v - lo) / (hi - lo)) * (h - 8);
  const d = pts.map((p, k) => `${k ? "L" : "M"}${x(p.i).toFixed(1)},${y(p.value).toFixed(1)}`).join("");
  const last = pts[pts.length - 1];
  const tips = row.weeks.map((w, i) => `<rect x="${(x(i) - width / 16).toFixed(1)}" y="0" width="${(width / 8).toFixed(1)}" height="${h}" fill="transparent" data-tip="${esc(`${t("drain.week_to", { day: shortDay(w.to) })} · ${fmt(row.unit, w.value)}`)}"/>`).join("");
  return `<svg viewBox="0 0 ${width} ${h}" width="${width}" height="${h}" aria-hidden="true">
    <path d="${d}" fill="none" stroke="var(--ink-2)" stroke-width="1.6" stroke-linejoin="round"/>
    <circle cx="${x(last.i).toFixed(1)}" cy="${y(last.value).toFixed(1)}" r="3.5" fill="var(--c-mark)"/>${tips}</svg>`;
}

function stateChip(row) {
  if (row.value === null || row.value === undefined) return `<span class="chip">${t("drain.no_window")}</span>`;
  if (!row.band) return `<span class="chip">${t("drain.no_baseline")}</span>`;
  return `<span class="chip ${STATUS[row.tone]}">${t(`drain.state.${row.tone}`)}</span>`;
}

function planChip(row) {
  if (!row.plan || row.plan_over === undefined) return "";
  if (row.plan_tone === "good") return `<span class="chip good">${t("drain.plan.ok")}</span>`;
  return `<span class="chip bad">${t(`drain.plan.over.${row.key}`, { d: dur(row.plan_over) })}</span>`;
}

function usual(r) {
  if (!r.band) return "";
  if (r.unit === "per_hour") return t("drain.usual_per_hour", { a: num(r.band.q1, 1), b: num(r.band.q3, 1) });
  return t("drain.usual", { a: fmt(r.unit, r.band.q1), b: fmt(r.unit, r.band.q3) });
}

function planText(r) {
  if (!r.plan) return "";
  return r.plan.kind === "bedtime" ? t("drain.plan.bedtime", { clock: r.plan.clock }) : t("drain.plan.limit", { v: fmt(r.unit, r.plan.limit) });
}

const label = (k) => t(`drain.item.${k}`);
const listOf = (keys) => keys.map((k) => inSentence(label(k))).join(t("drain.sep"));
const hasValue = (r) => r.value !== null && r.value !== undefined;

// the top line: only signals that have both these 7 days and a normal can be set against your normal
export function worseLine(worse, compared, total) {
  if (worse.length) return t("drain.worse_some", { n: worse.length, list: listOf(worse) });
  if (compared === 0) return t("drain.worse_unknown");
  return compared < total ? t("drain.worse_none_some", { n: compared }) : t("drain.worse_none");
}

// the plan line names what is off the plan, and what could not be checked for want of records
export function planLine(rows) {
  const planned = rows.filter((r) => r.plan);
  if (!planned.length) return t("drain.plan_unset");
  const off = planned.filter((r) => r.plan_tone === "bad");
  const within = planned.filter((r) => r.plan_tone === "good");
  const unchecked = planned.filter((r) => r.plan_over === null || r.plan_over === undefined);
  const parts = [];
  if (off.length) parts.push(t("drain.plan_some", { list: off.map((r) => `${inSentence(label(r.key))}${t(`drain.plan.over.${r.key}`, { d: dur(r.plan_over) })}`).join(t("drain.plan_sep")) }));
  else if (within.length && !unchecked.length) parts.push(t("drain.plan_none"));
  else if (within.length) parts.push(t("drain.plan_within", { list: listOf(within.map((r) => r.key)) }));
  if (unchecked.length) parts.push(t("drain.plan_unchecked", { list: listOf(unchecked.map((r) => r.key)) }));
  return parts.join(t("drain.sentence_sep"));
}

export default {
  render(p) {
    const compared = p.rows.filter((r) => hasValue(r) && r.band).length;
    const worse = worseLine(p.worse, compared, p.rows.length);
    const plan = planLine(p.rows);
    const later = p.next === p.latest ? "#drain" : `#drain/${p.next}`;
    const stepper = `<div class="stepper"><a href="#drain/${p.prev}">‹ ${t("drain.prev")}</a>${p.next ? `<a href="${later}">${t("drain.next")} ›</a><a href="#drain">${t("drain.latest")}</a>` : ""}</div>`;
    const rows = p.rows.map((r, i) => `<div class="drain-row">
      <div class="what"><b>${esc(label(r.key))}</b><span>${esc(t(`drain.why.${r.key}`))}</span></div>
      <div class="drain-strip" data-i="${i}"></div>
      <div class="drain-value"><b class="num">${esc(fmt(r.unit, r.value))}</b>
        <span class="xs muted">${esc([usual(r), planText(r)].filter(Boolean).join(" · "))}</span>
        <span class="drain-chips">${stateChip(r)}${planChip(r)}</span></div>
      <div class="drain-weeks-cell"><span class="drain-weeks-label xs muted" aria-hidden="true">${t("drain.weeks")}</span><div class="drain-weeks" data-i="${i}"></div></div></div>`).join("");
    const s = p.strain;
    const strainFacts = s.nights ? [t("week.nights", { short: s.short_nights, n: s.nights, h: s.rule.short_hours }), t("week.train", { n: s.train_days })] : [];
    if (s.hrv_change !== null && s.hrv_change !== undefined) strainFacts.push(t("week.hrv", { dir: t(s.hrv_change >= 0 ? "week.up" : "week.down"), pct: `${num(Math.abs(s.hrv_change) * 100)}%` }));
    const load = s.strain ? "drain.load_strain" : s.nights < p.rule.min_window ? "drain.load_unknown" : "drain.load_ok";
    const key = (k, text) => `<span class="key">${KEY[k]}${text}</span>`;
    return `<div class="head"><div><h1>${t("drain.title")}</h1><div class="sub">${t("drain.sub", { from: day(p.window.from, { weekday: false }), to: day(p.window.to, { weekday: false }) })}</div></div>${stepper}</div>
      <div class="grid">
        <section class="card span-12"><span class="eyebrow">${t("drain.eyebrow")}</span>
          <p class="lede" style="margin:6px 0 4px">${esc(worse)}</p><p class="small" style="margin:0;color:var(--ink-2)">${esc(plan)}</p></section>
        <section class="card span-12"><h2>${t("drain.items")}<span class="aside legend">
            ${key("normal", t("drain.key.normal"))}${key("median", t("drain.key.median"))}${key("now", t("drain.key.now"))}${key("plan", t("drain.key.plan"))}<span class="drain-weeks-key">${key("weeks", t("drain.key.weeks"))}</span></span></h2>
          <div class="drain-rows"><div class="drain-head" aria-hidden="true"><span></span><span></span><span></span><span>${t("drain.weeks")}</span></div>${rows}</div></section>
        <section class="card span-12"><h2>${t("drain.load_title")}</h2>
          <p class="lede" style="font-size:var(--t-lg)">${t(load)}</p>
          ${strainFacts.length ? `<ul class="agenda">${strainFacts.map((f) => `<li style="grid-template-columns:minmax(0,1fr)"><span>${esc(f)}</span></li>`).join("")}</ul>` : ""}
          <details class="how"><summary>${t("ui.how")}</summary><p>${t("week.rule")}</p></details></section>
        <section class="card span-12"><details class="how" open><summary>${t("ui.how")}</summary><p>${t("drain.rule", { w: p.rule.window, b: p.rule.baseline })}</p></details></section>
      </div>`;
  },
  mount(root, p) {
    root.querySelectorAll(".drain-strip").forEach((el) => draw(el, (w) => strip(p.rows[el.dataset.i], w)));
    root.querySelectorAll(".drain-weeks").forEach((el) => draw(el, (w) => weeks(p.rows[el.dataset.i], w)));
  },
};
