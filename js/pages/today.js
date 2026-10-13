import { bullet, dayDots, dayRing, draw, esc, interval, RING_CATS, spark } from "../charts.js?v=ad73753ded";
import { clock, day, dur, inSentence, measure, num, pct, signed, t, weekdayShort, wtype } from "../i18n.js?v=ad73753ded";
import { icon, STATE_ICON } from "../icons.js?v=ad73753ded";
import { worseLine } from "./drain.js?v=ad73753ded";

const shiftDay = (iso, n) => { const d = new Date(`${iso}T12:00:00`); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };

function stateChip(m) {
  if (m.partial) return `<span class="chip">${t("state.partial")}</span>`;
  if (!m.state) return `<span class="chip">${t("state.none")}</span>`;
  const cls = m.tone === "good" ? "good" : m.tone === "bad" ? "bad" : "";
  return `<span class="chip ${cls}">${STATE_ICON[m.tone] || ""}${t(`state.${m.state}`)}</span>`;
}

function tile(m, i, extraNote = "") {
  const band = m.band ? t("band", { low: measure(m.band.q1, m.unit), high: measure(m.band.q3, m.unit) }) : "";
  return `<div class="tile">
    <div class="label"><span>${t(`metric.${m.key}`)}</span>${stateChip(m)}</div>
    <div class="value">${esc(measure(m.value, m.unit))}</div>
    <div class="bul" data-i="${i}"></div>
    <div class="spk" data-i="${i}"></div>
    <div class="note">${esc([extraNote, band].filter(Boolean).join(" · "))}</div>
  </div>`;
}

function agendaHtml(a, isToday, workouts) {
  const rows = [];
  a.events.forEach((e) => rows.push({ sort: e.start, html: `<li><span class="when">${clock(e.start)}–${clock(e.end)}</span>
    <span class="what"><b>${esc(e.title)}</b>${e.location ? `<span class="muted">${esc(e.location)}</span>` : ""}</span><span></span></li>` }));
  a.deadlines.forEach((d) => {
    const when = d.days_left <= 1 ? t(`today.days_left.${d.days_left}`) : t("today.days_left.n", { n: d.days_left });
    rows.push({ sort: d.due, html: `<li><span class="when">${d.days_left === 0 ? clock(d.due) : `${weekdayShort(d.due)} ${clock(d.due)}`}</span>
      <span class="what"><b>${esc(d.title)}</b><span class="muted">${esc([d.group, d.weight_pct ? t("today.graded", { pct: num(d.weight_pct) }) : t("today.ungraded")].filter(Boolean).join(" · "))}</span></span>
      <span class="chip ${d.days_left <= 1 ? "watch" : ""}">${t("today.due", { when })}</span></li>` });
  });
  rows.sort((x, y) => (x.sort < y.sort ? -1 : 1));
  const done = (workouts || []).map((w) => esc(t("today.trained", { what: wtype(w.type), d: dur((new Date(w.end) - new Date(w.start)) / 60000), time: clock(w.start) })));
  const plan = a.training ? `<b>${esc(a.training)}</b>` : `<span class="muted">${t("today.rest")}</span>`;
  const training = `<li class="training-row"><span class="when"><span class="workout-icon">${icon("exercise", 15)}</span>${t("today.training")}</span>
    <span class="what">${done.length ? `<b>${done.join("<br>")}</b>${a.training ? `<span class="muted">${esc(t("week.planned", { what: a.training }))}</span>` : ""}` : plan}</span><span></span></li>`;
  let tonight = "";
  if (a.sleep && isToday) {
    const last = a.sleep.last;
    let line = "";
    if (last) {
      const result = last.on_time === true ? t("today.on_time") : last.on_time === false ? t("today.late") : t("today.unknown_morning");
      line = `<p class="xs muted" style="margin:8px 0 0">${t("today.last_morning", { woke: last.woke ? clock(last.woke) : "—", alarm: last.alarm, result })}</p>`;
    }
    tonight = `<h2 class="section-title" style="margin-top:var(--s-5)">${t("today.tonight")}</h2>
      <div class="tonight"><div><span>${t("today.phone_away")}</span><b>${clock(a.sleep.phone_away)}</b></div>
      <div><span>${t("today.asleep_by")}</span><b>${clock(a.sleep.asleep_by)}</b></div>
      <div><span>${t("today.alarm")}</span><b>${clock(a.sleep.alarm)}</b></div></div>${line}`;
  }
  return `<h2 class="section-title">${t("today.agenda")}</h2>
    <ul class="agenda">${rows.length ? rows.map((r) => r.html).join("") : `<li><span></span><span class="muted">${t("today.nothing")}</span><span></span></li>`}${training}</ul>${tonight}`;
}

function heroHtml(p) {
  const r = p.recovery;
  const ringLegend = `<div class="legend">
    <span class="key"><i style="background:var(--c-sleep)"></i>${t("ring.sleep")}</span>
    <span class="key"><i style="background:var(--c-event)"></i>${t("ring.events")}</span>
    ${p.ring.workouts && p.ring.workouts.length ? `<span class="key"><i style="background:var(--c-exercise)"></i>${t("act.exercise")}</span>` : ""}
    ${RING_CATS.map(([key, , color]) => `<span class="key"><i style="background:${color}"></i>${t(`cat.${key}`)}</span>`).join("")}</div>
    <p class="xs muted" style="margin:0;text-align:center">${p.ring.screen_day ? t("ring.screen", { day: day(p.ring.screen_day) }) : ""}</p>`;
  const chips = r.metrics.map((m) => `<span class="chip ${m.tone === "good" ? "good" : m.tone === "bad" ? "bad" : ""}">${t(`metric.${m.key}`)} · ${m.state ? t(`state.${m.state}`) : "—"}</span>`).join("");
  const self = p.self
    ? `<p class="small" style="margin:0"><b>${t("self.title")}</b> ${esc([p.self.energy != null ? t("self.energy", { v: num(p.self.energy) }) : "", p.self.focus != null ? t("self.focus", { v: num(p.self.focus) }) : "", p.self.note ? `“${p.self.note}”` : ""].filter(Boolean).join(" · "))}</p>`
    : `<p class="xs muted" style="margin:0">${t("self.prompt")}</p>`;
  const behind = r.days_behind > 1 ? `<p class="chip watch" style="height:auto;padding:4px 10px;white-space:normal">${t("recovery.behind", { n: r.days_behind, day: day(r.as_of) })}</p>` : "";
  return `<section class="card span-12"><div class="hero">
    <div class="ring-wrap"><div id="ring" style="width:100%;max-width:360px"></div>${ringLegend}</div>
    <div class="stack" style="gap:var(--s-5)">
      <div class="verdict"><span class="eyebrow">${t("recovery.eyebrow")}</span>
        <p class="lede" style="font-size:var(--t-3xl);margin:0">${t(`recovery.${r.verdict}`)}</p>
        <p class="small muted" style="margin:0">${r.as_of ? t("recovery.as_of", { day: day(r.as_of) }) : ""}</p>
        <div class="row" style="gap:6px">${chips}</div>${self}${behind}</div>
      <div>${agendaHtml(p.agenda, !p.looking_back, p.ring.workouts)}</div>
    </div></div></section>`;
}

function recoveryHtml(p) {
  const sleep = p.recovery.metrics.find((m) => m.key === "sleep");
  const tiles = p.recovery.metrics.map((m, i) => tile(m, i, m.key === "sleep" && sleep.start ? t("slept_from", { start: clock(sleep.start), end: clock(sleep.end) }) : "")).join("");
  const act = p.activity.filter((m) => m.key !== "training");
  const training = p.activity.find((m) => m.key === "training");
  const actTiles = act.map((m, i) => tile(m, 10 + i, m.partial ? t("activity.partial") : "")).join("");
  const trainTile = `<div class="tile"><div class="label"><span>${t("metric.training")}</span><span class="chip">${t("training.days", { n: training.value, k: 7 })}</span></div>
    <div class="dots"></div>
    <div class="note">${training.last ? esc(t("training.last", { type: wtype(training.last.type), min: dur(training.last.min) })) : t("training.none")}</div></div>`;
  return `<section class="card"><h2>${t("recovery.title")}<span class="aside">${p.recovery.as_of ? day(p.recovery.as_of) : ""}</span></h2>
    <div class="tiles aligned">${tiles}</div>
    <div class="tiles" style="margin-top:var(--s-3)">${actTiles}${trainTile}</div>
    <details class="how"><summary>${t("ui.how")}</summary><p>${t("recovery.rule")}</p></details></section>`;
}

function attentionHtml(p) {
  const a = p.attention;
  if (!a.day) return `<section class="card"><h2>${t("screens.title", { day: "—" })}</h2><div class="empty">${t("ui.no_data")}</div></section>`;
  const cats = a.by_category || {};
  const total = a.total || 1;
  const bar = RING_CATS.map(([key, keys, color]) => {
    const minutes = keys.reduce((s, k) => s + (cats[k] || 0), 0);
    return minutes ? `<span style="flex:${minutes};background:${color}" data-tip="${esc(`${t(`cat.${key}`)} ${dur(minutes)}`)}"></span>` : "";
  }).join("");
  const tiles = a.metrics.map((m, i) => tile(m, 20 + i)).join("");
  const targets = (a.targets || []).map((g) => {
    const label = t(`target.${g.key}`, { limit: dur(g.limit_min, { short: true }) });
    const cls = g.met === true ? "good" : g.met === false ? "bad" : "";
    return `<div class="row" style="justify-content:space-between"><span class="small">${label}</span>
      <span class="row" style="gap:6px"><span class="chip ${cls}">${g.met === null ? "—" : t(g.met ? "target.met" : "target.missed")}</span>
      <span class="xs muted">${t("target.week", { n: g.week_met, k: g.week_known })}</span></span></div>`;
  }).join("");
  return `<section class="card"><h2>${t("screens.title", { day: day(a.day) })}<span class="aside">${t("screens.total", { total: dur(a.total) })}</span></h2>
    ${a.stale ? `<p class="chip watch" style="height:auto;padding:4px 10px;white-space:normal;margin:0 0 12px">${t("screens.stale", { n: a.days_behind })}</p>` : ""}
    <div class="catbar" role="img" aria-label="${esc(t("screens.total", { total: dur(a.total) }))}">${bar}</div>
    <div class="legend" style="margin:8px 0 14px">${RING_CATS.map(([key, keys, color]) => { const m = keys.reduce((s, k) => s + (cats[k] || 0), 0); return `<span class="key"><i style="background:${color}"></i>${t(`cat.${key}`)} ${dur(m)}</span>`; }).join("")}</div>
    <div class="tiles two aligned">${tiles}</div>
    ${targets ? `<div class="stack" style="margin-top:var(--s-4);gap:8px">${targets}</div>` : ""}
    <p class="small" style="margin:var(--s-3) 0 0"><a href="#time">${t("screens.more")}</a></p>
    <details class="how"><summary>${t("ui.how")}</summary><p>${t("screens.rule")}</p></details></section>`;
}

function effectLabel(r) {
  const p = r.params || {};
  return t(`eff.${r.key}`, { min: num(p.min), hours: num(p.hours), clock: p.clock });
}

function effectsHtml(p) {
  const e = p.effects;
  const seg = e.outcomes.map((o, i) => `<button type="button" data-outcome="${o}" aria-pressed="${i === 0}">${t(`out.${o}`)}</button>`).join("");
  return `<section class="card"><h2>${t("effects.title")}<span class="seg" role="group" aria-label="${esc(t("effects.outcome"))}">${seg}</span></h2>
    <div class="effects" id="effects"></div>
    <details class="how"><summary>${t("ui.how")}</summary><p>${t("effects.rule")}</p></details></section>`;
}

function effectRows(e, outcome) {
  const rows = e.rows[outcome] || [];
  const unit = e.units[outcome];
  const sign = e.better[outcome] === "lower" ? -1 : 1;  // plotted so that right = a better next day
  const domain = Math.max(0.5, ...rows.filter((r) => r.status === "ok").map((r) => Math.max(Math.abs(r.low), Math.abs(r.high))));
  const fmt = (v) => (unit === "%" ? signed(v, 1, "%") : signed(v, 1, unit === "bpm" ? ` ${t("unit.bpm")}` : ` ${t("unit.points")}`));
  const head = `<div class="effect effect-head" aria-hidden="true"><span>${t("effects.col.what")}</span>
    <span class="axis"><span>${t("effects.col.worse")}</span><span>${t("effects.col.better")}</span></span><span>${t("effects.col.diff")}</span></div>`;
  return head + rows.map((r, i) => {
    const ok = r.status === "ok";
    const good = ok && sign * r.diff > 0;
    const verdict = !ok ? `<span class="xs muted">${t("eff.too_few")}</span>`
      : `<span class="chip ${r.detected ? (good ? "good" : "bad") : ""}">${t(r.detected ? "eff.detected" : "eff.not_detected")}</span>`;
    const read = ok ? t(`eff.read.${outcome}.${r.diff >= 0 ? "higher" : "lower"}`, { v: num(Math.abs(r.diff), 1) }) : "";
    const range = ok ? t("eff.range", { low: fmt(r.low), high: fmt(r.high) }) : "";
    return `<div class="effect" ${ok ? `data-tip="${esc(`${read} · ${range}`)}"` : ""}>
      <div class="what">${esc(effectLabel(r))}<span>${t("eff.days", { yes: r.yes_days, no: r.no_days })}</span></div>
      <div class="ivl" data-i="${i}" data-domain="${domain}" data-sign="${sign}"></div>
      <div class="verdict-cell">${verdict}${ok ? `<span class="xs muted read">${esc(read)}</span>` : ""}</div>
      ${ok ? `<span class="sr">${esc(`${read}, ${range}`)}</span>` : ""}</div>`;
  }).join("");
}

function drainHtml(p) {
  const d = p.drain;
  if (!d) return "";
  const worse = worseLine(d.worse, d.compared, d.signals);
  const plan = d.plan_off.length ? t("drain.plan_some", { list: d.plan_off.map((r) => `${inSentence(t(`drain.item.${r.key}`))}${t(`drain.plan.over.${r.key}`, { d: dur(r.over) })}`).join(t("drain.plan_sep")) }) : "";
  // the Drain page for the same 7 days as this card (the latest window when this is today)
  const more = p.looking_back ? `#drain/${d.window.to}` : "#drain";
  return `<section class="card"><h2>${t("today.drain")}<span class="aside">${day(d.window.from, { weekday: false })} – ${day(d.window.to, { weekday: false })}</span></h2>
    <p class="lede" style="font-size:var(--t-lg)">${esc(worse)}</p>
    ${plan ? `<p class="small" style="margin:0 0 8px;color:var(--ink-2)">${esc(plan)}</p>` : ""}
    ${d.strain ? `<p class="chip watch" style="height:auto;padding:4px 10px;white-space:normal">${t("week.strain")}</p>` : ""}
    <p class="small" style="margin:var(--s-3) 0 0"><a href="${more}">${t("today.drain_more")}</a></p></section>`;
}

export default {
  render(p) {
    const prev = shiftDay(p.day, -1), next = shiftDay(p.day, 1);
    const stepper = `<div class="stepper"><a href="#today/${prev}">‹ ${t("ui.prev_day")}</a>
      ${p.looking_back ? `<a href="${next === p.today ? "#today" : `#today/${next}`}">${t("ui.next_day")} ›</a><a href="#today">${t("ui.back_today")}</a>` : `<span aria-disabled="true">${t("ui.next_day")} ›</span>`}</div>`;
    return `<div class="head"><div><h1>${p.looking_back ? t("today.looking_back", { day: day(p.day) }) : t("today.title")}</h1>
      <div class="sub">${day(p.day)} · ${t("ui.computed", { time: clock(p.now) })}</div></div>${stepper}</div>
      <div class="grid">${heroHtml(p)}<div class="col span-7">${recoveryHtml(p)}${effectsHtml(p)}</div><div class="col span-5">${attentionHtml(p)}${drainHtml(p)}</div></div>`;
  },
  mount(root, p) {
    const ringBox = root.querySelector("#ring");
    const now = p.ring.now ? clock(p.ring.now) : clock(p.ring.sleep?.end);
    draw(ringBox, (w) => dayRing(p.ring, { size: Math.max(260, Math.min(360, w)), center: now, centerSub: p.ring.now ? t("ring.now") : day(p.day) }));
    const metrics = { ...Object.fromEntries(p.recovery.metrics.map((m, i) => [i, m])),
      ...Object.fromEntries(p.activity.filter((m) => m.key !== "training").map((m, i) => [10 + i, m])),
      ...Object.fromEntries(p.attention.metrics.map((m, i) => [20 + i, m])) };
    root.querySelectorAll(".spk").forEach((el) => { const m = metrics[el.dataset.i]; draw(el, (w) => spark(m.series, m.band, { width: w, unit: m.unit, tone: m.tone })); });
    root.querySelectorAll(".bul").forEach((el) => { const m = metrics[el.dataset.i]; draw(el, (w) => bullet(m.value, m.band, { width: w, unit: m.unit, tone: m.tone })); });
    const training = p.activity.find((m) => m.key === "training");
    draw(root.querySelector(".dots"), (w) => dayDots(training.series, { width: w }));
    const box = root.querySelector("#effects");
    const show = (outcome) => {
      box.innerHTML = effectRows(p.effects, outcome);
      const rows = p.effects.rows[outcome] || [];
      box.querySelectorAll(".ivl").forEach((el) => draw(el, (w) => interval(rows[el.dataset.i], Number(el.dataset.domain), { width: w, flip: el.dataset.sign === "-1" })));
      root.querySelectorAll("[data-outcome]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.outcome === outcome)));
    };
    root.querySelectorAll("[data-outcome]").forEach((b) => { b.onclick = () => show(b.dataset.outcome); });
    if (p.effects.outcomes.length) show(p.effects.outcomes[0]);
  },
};
