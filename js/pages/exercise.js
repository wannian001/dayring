// Exercise: this week against the weekly goal, the last 7 days against your normal, load against recovery,
// twelve weeks by kind, and how the body tends to answer each kind the next day.
import { bullet, draw, esc, spark, stackedColumns } from "../charts.js?v=f86d36d39c";
import { clock, day, dur, measure, num, shortDay, signed, t, weekdayShort, wtype } from "../i18n.js?v=f86d36d39c";
import { STATE_ICON } from "../icons.js?v=f86d36d39c";

// kinds of training share the exercise hue and differ in lightness; minutes outside any logged workout are grey
export const KIND_PARTS = [["strength", "var(--c-exercise)"], ["cardio", "var(--c-exercise-2)"], ["walk", "var(--c-exercise-3)"], ["loose", "var(--c-other)"]];
const parts = (byKind, loose) => ({ strength: byKind.strength || 0, cardio: byKind.cardio || 0, walk: (byKind.walk || 0) + (byKind.other || 0), loose: loose || 0 });
const key = ([k, color]) => `<span class="key"><i style="background:${color}"></i>${t(`ex.kind.${k}`)}</span>`;

function value(r) {
  if (r.unit === "count") return r.value == null ? "—" : num(r.value, 0);
  if (r.unit === "kcal") return r.value == null ? "—" : `${num(r.value)} kcal`;
  return measure(r.value, r.unit);
}

function stateChip(r) {
  if (r.value == null) return `<span class="chip">${t("drain.no_window")}</span>`;
  if (!r.state) return `<span class="chip">${t("state.none")}</span>`;
  const cls = r.tone === "good" ? "good" : r.tone === "bad" ? "bad" : "";
  return `<span class="chip ${cls}">${STATE_ICON[r.tone] || ""}${t(`state.${r.state}`)}</span>`;
}

function tile(r, i) {
  const band = r.band ? t("band", { low: value({ ...r, value: r.band.q1 }), high: value({ ...r, value: r.band.q3 }) }) : "";
  return `<div class="tile"><div class="label"><span>${t(`ex.m.${r.key}`)}</span>${stateChip(r)}</div>
    <div class="value">${esc(value(r))}</div><div class="bul" data-i="${i}"></div><div class="spk" data-i="${i}"></div>
    <div class="note">${esc([t(`ex.how.${r.how}`), band].filter(Boolean).join(" · "))}</div></div>`;
}

function weekLine(w, g) {
  if (!w.is_current) return t("ex.week_past", { d: dur(w.minutes), goal: dur(g.weekly_min) });
  if (w.status === "met") return t("ex.week_met", { d: dur(w.minutes), goal: dur(g.weekly_min) });
  return t("ex.week_left", { d: dur(w.minutes), left: dur(w.remaining_min), n: w.days_left, per: dur(Math.ceil(w.remaining_min / Math.max(1, w.days_left))) });
}

// the seven days of the week: active minutes as a bar split by kind (one scale for the week), the workouts done,
// and the training planned for the days still to come
function weekStrip(p) {
  const w = p.week;
  const top = Math.max(p.goal.weekly_min / 7 * 2, ...w.days.map((d) => d.minutes || 0));
  const cells = w.days.map((d) => {
    const done = d.workouts.map((x) => `${wtype(x.type)} ${dur(x.minutes)}`).join(" · ");
    const loose = Math.max(0, (d.minutes || 0) - Object.values(d.by_kind).reduce((a, b) => a + b, 0));
    const split = parts(d.by_kind, loose);
    const bar = d.future ? "" : `<div class="hbar ex-bar">${KIND_PARTS.map(([k, color]) => (split[k] ? `<span style="width:${(split[k] / top * 100).toFixed(1)}%;background:${color}"></span>` : "")).join("")}</div>`;
    const note = d.future ? (d.planned ? t("week.planned", { what: d.planned }) : t("week.free"))
      : done || (d.planned ? t(d.is_today ? "week.planned" : "week.planned_missed", { what: d.planned }) : "");
    return `<div class="ex-day${d.is_today ? " is-today" : ""}${d.future ? " future" : ""}">
      <span class="xs muted">${weekdayShort(d.date)} ${shortDay(d.date)}</span>
      <b class="num">${d.future ? "—" : esc(dur(d.minutes))}</b>${bar}
      <span class="xs ex-note">${esc(note)}</span></div>`;
  }).join("");
  return `<div class="ex-days">${cells}</div>`;
}

function recentHtml(p) {
  if (!p.recent.length) return `<p class="muted small">${t("ex.no_workouts")}</p>`;
  return `<ul class="agenda">${p.recent.map((x) => {
    const facts = [dur(x.minutes), x.kcal != null ? `${num(x.kcal)} kcal` : null, x.avg_hr != null ? t("ex.avg_hr", { v: num(x.avg_hr) }) : null].filter(Boolean).join(" · ");
    const next = x.hrv_pct == null ? `<span class="xs muted">${t("ex.next_unknown")}</span>` : `<span class="chip">${t("ex.next_hrv", { v: signed(x.hrv_pct, 0, "%") })}</span>`;
    return `<li><span class="when">${weekdayShort(x.start)} ${clock(x.start)}</span><span class="what"><b>${esc(wtype(x.type))}</b><span class="muted">${esc(`${shortDay(x.start)} · ${facts}`)}</span></span>${next}</li>`;
  }).join("")}</ul>`;
}

function responseHtml(p) {
  if (!p.response.length) return `<p class="muted small">${t("ex.response_few", { n: p.rule.min_response })}</p>`;
  const rows = p.response.map((r) => `<tr><th scope="row">${t(`ex.after.${r.kind}`)}</th><td class="num">${num(r.days)}</td>
    <td class="num">${signed(r.hrv_pct, 1, "%")}</td><td class="num">${r.rhr_bpm == null ? "—" : signed(r.rhr_bpm, 1, ` ${t("unit.bpm")}`)}</td></tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr><th></th><th scope="col">${t("ex.col.days")}</th><th scope="col">${t("ex.col.hrv")}</th><th scope="col">${t("ex.col.rhr")}</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

export default {
  render(p) {
    const g = p.goal, w = p.week;
    if (!p.has_data) {
      return `<div class="head"><div><h1>${t("nav.exercise")}</h1></div></div><div class="card"><div class="empty">${t("ex.empty")}</div></div>`;
    }
    const share = Math.min(100, (w.minutes / g.weekly_min) * 100);
    const goalLine = t(g.source === "plan" ? "ex.goal_plan" : "ex.goal_who", { d: dur(g.weekly_min), n: g.strength_days });
    const strength = t("ex.strength_days", { n: w.strength_days, goal: g.strength_days });
    const load = p.load;
    const loadFacts = [
      [t("ex.load.acute"), dur(load.acute_min)],
      [t("ex.load.chronic"), load.chronic_min == null ? "—" : dur(load.chronic_min)],
      [t("ex.load.ratio"), load.ratio == null ? "—" : `${num(load.ratio, 2)}×`],
    ];
    const recovery = `<span class="chip ${p.recovery.verdict === "low" ? "bad" : p.recovery.verdict === "good" ? "good" : ""}">${t(`recovery.${p.recovery.verdict}`)}</span>`;
    return `<div class="head"><div><h1>${t("nav.exercise")}</h1><div class="sub">${esc(goalLine)}</div></div></div>
      <div class="grid">
        <section class="card span-12"><span class="eyebrow">${t("ex.eyebrow", { from: day(w.start, { weekday: false }), to: day(w.end, { weekday: false }) })}</span>
          <p class="lede" style="margin:6px 0 10px">${esc(weekLine(w, g))}</p>
          <div class="progress" role="img" aria-label="${esc(`${dur(w.minutes)} / ${dur(g.weekly_min)}`)}"><span style="width:${share.toFixed(1)}%"></span></div>
          <p class="small" style="margin:8px 0 14px;color:var(--ink-2)">${esc(strength)}${w.strength_left && w.is_current ? ` · ${esc(t("ex.strength_left", { n: w.strength_left, d: w.days_left }))}` : ""}</p>
          ${weekStrip(p)}
          <div class="legend" style="margin-top:10px">${KIND_PARTS.map(key).join("")}</div></section>
        <div class="col span-7">
          <section class="card"><h2>${t("ex.last7")}<span class="aside">${day(p.window.from, { weekday: false })} – ${day(p.window.to, { weekday: false })}</span></h2>
            <div class="tiles two aligned">${p.rows.map(tile).join("")}</div>
            <details class="how"><summary>${t("ui.how")}</summary><p>${t("ex.rule_tiles", { b: p.rule.baseline, k: p.rule.min_total_days })}</p></details></section>
          <section class="card"><h2>${t("ex.weeks", { n: p.rule.weeks })}</h2><div id="exweeks" class="chart"></div>
            <div class="legend" style="margin-top:8px">${KIND_PARTS.map(key).join("")}</div></section>
          <section class="card"><h2>${t("ex.response")}<span class="aside">${t("ex.response_note", { n: p.rule.response_days })}</span></h2>${responseHtml(p)}
            <p class="xs muted" style="margin:10px 0 0">${t("ex.response_rule")}</p></section>
        </div>
        <div class="col span-5">
          <section class="card"><h2>${t("ex.load.title")}</h2>
            <p class="lede" style="font-size:var(--t-lg);margin:0 0 8px">${t(`ex.advice.${p.advice}`)}</p>
            <div class="row" style="gap:6px;margin-bottom:8px"><span class="small muted">${t("ex.recovery_today")}</span>${recovery}
              <span class="chip ${load.state === "high" ? "watch" : ""}">${t(`ex.load.${load.state}`)}</span></div>
            <dl class="facts">${loadFacts.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd class="num">${esc(v)}</dd></div>`).join("")}</dl>
            <details class="how"><summary>${t("ui.how")}</summary><p>${t("ex.load.rule", { hi: num(load.high, 1), lo: num(load.low, 1) })}</p></details></section>
          <section class="card"><h2>${t("ex.recent")}</h2>${recentHtml(p)}</section>
        </div>
      </div>`;
  },
  mount(root, p) {
    if (!p.has_data) return;
    const weeks = p.weeks.map((x) => ({
      label: shortDay(x.week_start),
      values: x.minutes == null ? null : parts(x.by_kind, x.loose),
      tip: `${t("ex.week_of", { day: shortDay(x.week_start) })}${x.partial ? ` (${t("goals.so_far")})` : ""} · ${x.minutes == null ? t("ui.no_data") : dur(x.minutes)} · ${t("ex.strength_days", { n: x.strength_days, goal: p.goal.strength_days })}`,
    }));
    draw(root.querySelector("#exweeks"), (width) => stackedColumns(weeks, KIND_PARTS, { width, height: 210, limit: p.goal.weekly_min,
      limitLabel: t("ex.goal_line", { d: dur(p.goal.weekly_min) }), labelEvery: width < 560 ? 3 : 2 }));
    root.querySelectorAll(".spk").forEach((el) => { const r = p.rows[el.dataset.i]; draw(el, (width) => spark(r.series, r.how === "mean" ? r.band : null, { width, unit: r.unit === "count" ? "" : r.unit, tone: r.tone })); });
    root.querySelectorAll(".bul").forEach((el) => { const r = p.rows[el.dataset.i]; draw(el, (width) => bullet(r.value, r.band, { width, unit: r.unit === "count" ? "" : r.unit, tone: r.tone })); });
  },
};
