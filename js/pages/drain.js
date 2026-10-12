// Drain: seven quiet signals over the last 7 days, each against your normal and, where set, your plan.
// No total score: the signals have different units and different strength of evidence.
import { draw, esc } from "../charts.js";
import { day, dur, num, shortDay, t } from "../i18n.js";

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

// one row's own scale: grey band = normal, tick = median, dot = last 7 days, dashed tick = plan
function strip(row, width) {
  const h = 30, pad = 10;
  const vals = [row.value, row.band?.q1, row.band?.q3, row.plan?.limit].filter((v) => v !== null && v !== undefined);
  if (!vals.length) return "";
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
  if (row.value !== null && row.value !== undefined) {
    const color = row.tone === "bad" ? "var(--off)" : row.tone === "good" ? "var(--good)" : "var(--c-mark)";
    parts.push(`<circle cx="${x(row.value).toFixed(1)}" cy="${h / 2}" r="6" fill="${color}" stroke="var(--surface)" stroke-width="2"/>`);
  }
  return `<svg viewBox="0 0 ${width} ${h}" width="${width}" height="${h}" aria-hidden="true">${parts.join("")}</svg>`;
}

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

export default {
  render(p) {
    const name = (k) => t(`drain.item.${k}`);
    const worse = p.worse.length ? t("drain.worse_some", { n: p.worse.length, list: p.worse.map(name).join(t("drain.sep")) }) : t("drain.worse_none");
    const offRows = p.rows.filter((r) => r.plan_tone === "bad");
    const planned = p.rows.filter((r) => r.plan);
    const plan = offRows.length
      ? t("drain.plan_some", { list: offRows.map((r) => `${name(r.key)}${t(`drain.plan.over.${r.key}`, { d: dur(r.plan_over) })}`).join(t("drain.sep")) })
      : planned.length ? t("drain.plan_none") : t("drain.plan_unset");
    const stepper = `<div class="stepper"><a href="#drain/${p.prev}">‹ ${t("drain.prev")}</a>${p.next ? `<a href="#drain/${p.next}">${t("drain.next")} ›</a><a href="#drain">${t("drain.latest")}</a>` : ""}</div>`;
    const rows = p.rows.map((r, i) => `<div class="drain-row">
      <div class="what"><b>${esc(name(r.key))}</b><span>${esc(t(`drain.why.${r.key}`))}</span></div>
      <div class="drain-strip" data-i="${i}"></div>
      <div class="drain-value"><b class="num">${esc(fmt(r.unit, r.value))}</b>
        <span class="xs muted">${r.band ? esc(t("drain.usual", { a: fmt(r.unit, r.band.q1), b: fmt(r.unit, r.band.q3) })) : ""}${r.plan ? ` · ${esc(r.plan.kind === "bedtime" ? t("drain.plan.bedtime", { clock: r.plan.clock }) : t("drain.plan.limit", { v: fmt(r.unit, r.plan.limit) }))}` : ""}</span>
        <span class="row" style="gap:6px;justify-content:flex-end">${stateChip(r)}${planChip(r)}</span></div>
      <div class="drain-weeks" data-i="${i}"></div></div>`).join("");
    const s = p.strain;
    const strainFacts = [t("week.nights", { short: s.short_nights, n: s.nights, h: s.rule.short_hours }), t("week.train", { n: s.train_days })];
    if (s.hrv_change !== null && s.hrv_change !== undefined) strainFacts.push(t("week.hrv", { dir: t(s.hrv_change >= 0 ? "week.up" : "week.down"), pct: `${num(Math.abs(s.hrv_change) * 100)}%` }));
    return `<div class="head"><div><h1>${t("drain.title")}</h1><div class="sub">${t("drain.sub", { from: day(p.window.from, { weekday: false }), to: day(p.window.to, { weekday: false }) })}</div></div>${stepper}</div>
      <div class="grid">
        <section class="card span-12"><span class="eyebrow">${t("drain.eyebrow")}</span>
          <p class="lede" style="margin:6px 0 4px">${esc(worse)}</p><p class="small" style="margin:0;color:var(--ink-2)">${esc(plan)}</p></section>
        <section class="card span-12"><h2>${t("drain.items")}<span class="aside legend">
            <span class="key"><i style="background:var(--c-band);border:1px solid var(--line-2)"></i>${t("drain.key.normal")}</span>
            <span class="key"><i style="background:var(--c-mark);border-radius:50%"></i>${t("drain.key.now")}</span>
            <span class="key"><i style="background:none;border-left:2px dashed var(--ink);border-radius:0;width:2px"></i>${t("drain.key.plan")}</span></span></h2>
          <div class="drain-head" aria-hidden="true"><span></span><span></span><span></span><span>${t("drain.weeks")}</span></div>
          <div class="drain-rows">${rows}</div></section>
        <section class="card span-12"><h2>${t("week.title")}</h2>
          <p class="lede" style="font-size:var(--t-lg)">${t(s.strain ? "week.strain" : "week.ok")}</p>
          <ul class="agenda">${strainFacts.map((f) => `<li style="grid-template-columns:minmax(0,1fr)"><span>${esc(f)}</span></li>`).join("")}</ul>
          <details class="how"><summary>${t("ui.how")}</summary><p>${t("week.rule")}</p></details></section>
        <section class="card span-12"><details class="how" open><summary>${t("ui.how")}</summary><p>${t("drain.rule", { w: p.rule.window, b: p.rule.baseline })}</p></details></section>
      </div>`;
  },
  mount(root, p) {
    root.querySelectorAll(".drain-strip").forEach((el) => draw(el, (w) => strip(p.rows[el.dataset.i], w)));
    root.querySelectorAll(".drain-weeks").forEach((el) => draw(el, (w) => weeks(p.rows[el.dataset.i], w)));
  },
};
