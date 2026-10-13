// Time: where the day went, and what changed. One rule for every block: each activity is measured from
// its own record, minute by minute, and compared with one baseline, your normal (a day with the middle
// half of the 28 days before it, the 7-day average with your usual 7-day averages). The page never names
// the biggest activity (screens would win every day); it names the biggest change that lies clearly
// outside normal (`clear`, worked out in modules/time.py), and colours only those. Lanes may overlap;
// unrecorded waking time is shown as such. A day without an activity's record shows "—" for it (never 0)
// and is left out of its average and normal. Devices at once (each device counting its own minutes) has its
// own card; its two measures, screens at once (a ratio, kept in hundredths) and the longest stretch on one thing,
// are candidates of "what changed" like the rest.
import { bullet, draw, esc, lanes } from "../charts.js?v=a1a20d3f3d";
import { day, device, dur, getLang, num, shortDay, t, weekdayShort, wtype } from "../i18n.js?v=a1a20d3f3d";
import { COLOR, icon, STATE_ICON } from "../icons.js?v=a1a20d3f3d";

const ORDER = ["sleep", "exercise", "calendar", "screen"];  // the lanes, in the same order in both lane charts
const TILES = ["screen", "fun", "focus", "communication", "exercise", "calendar", "sleep", "not_recorded"];  // every candidate has a tile
const SCREEN_PARTS = [["fun", "var(--c-fun)"], ["focus", "var(--c-focus)"], ["communication", "var(--c-comms)"], ["other", "var(--c-other)"]];
// compact, for the small day cells; a narrow cell may break before the unit, never inside it ("10.6 / 小时")
const hours = (m) => t("time.hours", { h: num(m / 60, 1) });
const CAT_COLOR = { work: "var(--c-focus)", learning: "var(--c-focus)", entertainment: "var(--c-fun)", social: "var(--c-fun)", communication: "var(--c-comms)", other: "var(--c-other)" };
const keep = (text) => text.replace(/ /g, "\u00a0");  // one duration never breaks across lines ("4 小时 23 分")
const toneCls = (tone) => (tone === "good" ? "good" : tone === "bad" ? "bad" : "");
const shownTone = (c) => (c.clear ? c.tone : "neutral");  // green and red only for a clear change
// a value in its own unit: the stacking ratio is kept in hundredths (142 = 1.42×), everything else in minutes
const ratio = (v) => (v == null ? "—" : t("time.ratio_v", { v: num(v / 100, 2) }));
const fmt = (key, v) => (key === "ratio" ? ratio(v) : dur(v));
const dirWord = (c, kind) => (c.key === "ratio" ? t(`chg.${c.state === "high" ? "higher" : "lower"}`)
  : t(`chg.${c.state === "high" ? (kind === "short" ? "up" : "more") : (kind === "short" ? "down" : "less")}`));
const listOf = (keys) => keys.map((k) => t(`chg.${k}`)).join(t("ui.list_sep"));
// "normal 0m–0m" reads as a glitch: a normal that is one value is written once ("usually none" when 0)
function bandLabel(b, { range = "band", one = "band_one", none = "time.band_none" } = {}, vars = {}, key = "") {
  const low = keep(fmt(key, b.q1)), high = keep(fmt(key, b.q3));
  if (low !== high) return t(range, { ...vars, low, high });
  return Math.round(b.q3) === 0 ? t(none, vars) : t(one, { ...vars, low });
}
// Chinese has no spaces between words, so a balanced line may break inside one ("最 / 大"): keep each
// phrase together, breaking inside it only when it is longer than the line. Phrases end at punctuation
// or at a "|" in the string (a break hint, never shown)
const phrases = (text) => (getLang() === "zh"
  ? text.split(/(?<=[，：；。])|\|/).filter(Boolean).map((x) => `<span class="ph">${esc(x)}</span>`).join("")
  : esc(text.replace(/\|/g, "")));

// how many of the shown days have this record, when not all of them do
function knownNote(S, key) {
  const k = S.known[key];
  if (k === S.n) return "";
  if (key === "not_recorded") return t("time.nr_known", { n: k, k: S.n });  // it needs both a night and screen time
  return k ? t("time.known", { n: k, k: S.n }) : t("time.no_record");
}

// within normal; just past its edge (grey, "just above normal"); or clearly outside (coloured, "above normal")
function stateChip(m) {
  if (m.value == null) return "";
  if (!m.state) return `<span class="chip">${t(m.few ? "time.few" : "state.none")}</span>`;
  if (m.state !== "normal" && !m.clear) return `<span class="chip">${t(`time.slight_${m.state}`)}</span>`;
  const tone = shownTone(m);
  return `<span class="chip ${toneCls(tone)}">${STATE_ICON[tone] || ""}${t(`state.${m.state}`)}</span>`;
}

function tile(key, S, extra = [], body = "", cls = "") {
  const m = S.metrics[key];
  const band = m.band ? bandLabel(m.band, {}, {}, key) : "";
  // each piece of the note wraps as a whole ("娱乐上限 3 小时" never leaves "时" alone on a line)
  const pieces = [band, knownNote(S, key), ...extra].filter(Boolean);
  const note = pieces.map((x, i) => `<span class="piece">${esc(x)}${i < pieces.length - 1 ? " ·" : ""}</span>`).join(" ");
  // four rows shared with the tiles beside it (CSS subgrid), so values and bullets line up across a row
  return `<div class="tile act-tile${key === "screen" ? " act-wide" : ""}${cls}">
    <div class="label"><span class="act-name" style="color:${COLOR[key === "stacked" ? "screen" : key]}">${icon(key === "stacked" ? "screen" : key, 16)}<span>${t(`act.${key}`)}</span></span>${stateChip(m)}</div>
    <div class="act-value"><div class="value">${fmt(key, m.value)}</div>${body}</div>
    <div class="bul" data-key="${key}"></div>
    <div class="note">${note}</div></div>`;
}

// the coloured icon of a change, with an up / down badge in its tone
function changeIcon(key, state, tone, size) {
  const badge = state ? `<span class="chg-badge ${toneCls(tone)}">${icon(state === "high" ? "up" : "down", Math.max(14, Math.round(size * 0.42)))}</span>` : "";
  return `<span class="chg-icon" style="color:${COLOR[key]}">${icon(key, size)}${badge}</span>`;
}

function dayCell(d) {
  const s = d.standout;
  const tot = d.totals;
  const ex = tot.exercise;
  const foot = [t("time.foot_screen", { v: tot.screen == null ? "—" : hours(tot.screen) }),
    ex == null ? t("time.foot_ex", { v: "—" }) : ex ? t("time.foot_ex", { v: dur(ex) }) : t("time.foot_rest")];
  let mark, label, delta = "";
  if (s) {
    mark = changeIcon(s.key, s.state, s.tone, 30);  // a day's standout is always a clear change
    label = t("time.day_label", { what: t(`chg.short.${s.key}`), dir: dirWord(s, "short") });
    delta = `<b class="daycell-delta num ${toneCls(s.tone)}">${fmt(s.key, Math.abs(s.delta))}</b>`;
  } else if (d.compared) {
    mark = `<span class="chg-icon" style="color:var(--ink-3)">${icon("check", 30)}</span>`;
    label = t("time.day_usual");
  } else {
    mark = `<span class="chg-icon" style="color:var(--ink-3)">${icon("not_recorded", 30)}</span>`;
    label = t("time.day_no_normal");
  }
  return `<div class="daycell${s ? "" : " usual"}">
    <span class="daycell-date xs muted"><span>${weekdayShort(d.date)}</span><span>${shortDay(d.date)}</span></span>
    <span class="daycell-mark">${mark}</span>
    <span class="daycell-what"><span class="daycell-label">${esc(label)}</span>${delta}</span>
    <span class="daycell-foot xs muted">${foot.map((f) => `<span>${esc(f)}</span>`).join('<span class="sep" aria-hidden="true"> · </span>')}</span></div>`;
}

function staleNote(S) {
  return (S.stale || []).map((s) => `<p class="chip watch stale">${esc(s.last
    ? t("time.stale", { what: t(`act.${s.activity}`), day: day(s.last) })
    : t("time.stale_none", { what: t(`act.${s.activity}`) }))}</p>`).join("");
}

// devices at once: device time, screens at once and the longest stretch on one thing, then device time by hour
function stackHtml(p) {
  const S = p.span, K = S.stack, A = S.avg;
  if (!K) return "";
  const byDevice = Object.entries(K.devices).sort((a, b) => b[1] - a[1]).map(([d, m]) => `${device(d)} ${dur(m)}`).join(" · ");
  const best = K.best_single;
  const tiles = [
    tile("stacked", S, [t("time.stack_clock", { v: dur(A.screen) }), byDevice], "", " stack-tile"),
    tile("ratio", S, A.stacked != null ? [t("time.ratio_note", { s: dur(A.stacked), c: dur(A.screen) })] : [], "", " stack-tile"),
    tile("single", S, best ? [t("time.single_best", { d: dur(best.minutes), app: best.app, device: device(best.device), day: day(best.date), at: best.start })] : [], "", " stack-tile"),
  ].join("");
  const agent = Object.values(K.agent_by_hour).reduce((a, b) => a + b, 0);
  return `<section class="card span-12"><h2>${t("time.stack")}<span class="aside">${phrases(t("time.stack_note"))}</span></h2>
    <div class="tiles act-tiles stack-tiles">${tiles}</div>
    <div class="section-title stack-hours-title"><span>${phrases(t("time.stack_hours"))}</span><span class="aside legend">${SCREEN_PARTS.map(([k, c]) => `<span class="key"><i style="background:${c}"></i>${t(`cat.${k}`)}</span>`).join("")}
      <span class="key"><i style="background:var(--c-axis)"></i>${t("time.key_clock")}</span><span class="key"><i class="hatch"></i>${t("time.key_extra")}</span></span></div>
    <div id="stack-hours" class="chart"></div>
    ${agent >= 1 ? `<p class="xs muted" style="margin:8px 0 0">${esc(t("time.agent_note", { v: dur(agent) }))}</p>` : ""}</section>`;
}

function heroHtml(p) {
  const S = p.span;
  const top = S.standout;
  const compared = S.changes.filter((c) => c.state).map((c) => c.key);
  const skipped = S.changes.filter((c) => !c.state).map((c) => c.key);
  let mark, lede, sub, chips = "";
  if (top) {
    mark = changeIcon(top.key, top.state, top.tone, 56);
    lede = t(top.key === "ratio" ? "time.change_line_ratio" : "time.change_line", { n: S.n, what: t(`chg.${top.key}`), dir: dirWord(top), d: keep(fmt(top.key, Math.abs(top.delta))) });
    sub = bandLabel(top.band, { range: "time.change_sub", one: "time.change_sub_one", none: "time.change_sub_none" }, { v: keep(fmt(top.key, top.value)) }, top.key);
    const others = S.changes.filter((c) => c.key !== top.key && c.clear);  // the same rule as the standout
    if (others.length) {
      chips = `<div class="chg-also"><span class="xs muted">${t("time.also")}</span>${others.map((c) => `<span class="chip ${toneCls(c.tone)}">${icon(c.state === "high" ? "up" : "down", 12)}${esc(t("time.chip", { what: t(`act.${c.key}`), d: fmt(c.key, Math.abs(c.delta)), dir: dirWord(c) }))}</span>`).join("")}</div>`;
    }
  } else if (compared.length) {
    mark = `<span class="chg-icon" style="color:${COLOR.check}">${icon("check", 56)}</span>`;
    lede = t("time.usual_line", { n: S.n });
    const slight = S.changes.filter((c) => c.state === "high" || c.state === "low").map((c) => c.key);
    sub = slight.length ? t("time.usual_sub_slight", { list: listOf(slight) }) : t("time.usual_sub", { list: listOf(compared) });
  } else {
    mark = `<span class="chg-icon" style="color:var(--ink-3)">${icon("not_recorded", 56)}</span>`;
    lede = t("time.no_normal_line");
    sub = t("time.no_normal_sub", { n: p.baseline_days, min: p.baseline_min });
  }
  const notCompared = compared.length && skipped.length ? `<p class="xs muted" style="margin:6px 0 0">${esc(t("time.not_compared", { list: listOf(skipped) }))}</p>` : "";
  return `<section class="card span-12"><div class="time-hero">
    <div class="time-top">${mark}</div>
    <div class="time-lede"><span class="eyebrow">${t("time.eyebrow")}</span><p class="lede" style="margin:4px 0">${phrases(lede)}</p>
      <p class="small muted" style="margin:0">${esc(sub)}</p>${chips}${notCompared}${staleNote(S)}</div>
    <div class="days-strip">${S.days.map(dayCell).join("")}</div></div></section>`;
}

export default {
  render(p) {
    if (p.empty) {
      const back = p.next ? `<p class="small"><a href="${p.next === p.newest ? "#time" : `#time/${p.next}`}">${t("time.next")} ›</a></p>` : "";
      return `<div class="head"><div><h1>${t("time.title")}</h1></div></div><div class="card"><div class="empty">${t("time.empty")}</div>${back}</div>`;
    }
    const S = p.span;
    // a server started before this page changed still sends the old numbers (no normal, or no `clear`)
    if (!S.metrics || !S.changes.every((c) => "clear" in c)) return `<div class="head"><div><h1>${t("time.title")}</h1></div></div><div class="card"><div class="empty">${t("time.restart")}</div></div>`;
    const A = S.avg;
    // "Later" ends on the newest day when it gets there; that page is the latest one (#time, also on the static site)
    const nextHref = p.next === p.newest ? "#time" : `#time/${p.next}`;
    const stepper = `<div class="stepper">${p.prev ? `<a href="#time/${p.prev}">‹ ${t("time.prev")}</a>` : `<span aria-disabled="true">‹ ${t("time.prev")}</span>`}
      ${p.next ? `<a href="${nextHref}">${t("time.next")} ›</a>${p.next !== p.newest ? `<a href="#time">${t("time.latest")}</a>` : ""}` : ""}</div>`;
    const screenSplit = SCREEN_PARTS.map(([k, c]) => (A[k] ? `<span style="flex:${A[k]};background:${c}" data-tip="${esc(`${t(`cat.${k}`)} ${dur(A[k])}`)}"></span>` : "")).join("");
    const exKnown = S.exercise_known;
    const exDays = exKnown ? t("time.exercise_days", { n: S.exercise_days, k: exKnown }) : "";
    const L = p.limits;
    const tiles = TILES.map((key) => {
      if (key === "screen") return tile(key, S, [], A.screen != null ? `<div class="catbar" style="height:8px" role="img" aria-label="${esc(SCREEN_PARTS.map(([k]) => `${t(`cat.${k}`)} ${dur(A[k])}`).join(", "))}">${screenSplit}</div>` : "");
      if (key === "fun") return tile(key, S, L.fun_max_min ? [t("time.fun_limit", { v: dur(L.fun_max_min, { short: true }) })] : []);
      if (key === "focus") return tile(key, S, L.focus_min_min ? [t("time.focus_goal", { v: dur(L.focus_min_min, { short: true }) })] : []);
      if (key === "exercise") return tile(key, S, [exDays]);
      if (key === "sleep") return tile(key, S, [t("time.sleep_note")]);
      return tile(key, S);
    }).join("");
    const maxApp = Math.max(1, ...S.apps.map((a) => a.minutes));
    const apps = S.apps.map((a) => `<li><span class="app"><span class="app-name" title="${esc(a.app)}">${esc(a.app)}</span><span class="chip">${esc(device(a.device))}</span></span>
      <span class="hbar"><span style="width:${(a.minutes / maxApp * 100).toFixed(1)}%;background:${CAT_COLOR[a.category]}"></span></span>
      <span class="num small">${dur(a.minutes)}</span></li>`).join("");
    const workouts = S.workouts.length
      ? `<ul class="agenda">${S.workouts.map((w) => `<li><span class="when">${weekdayShort(w.start)} ${w.start.slice(11, 16)}</span>
          <span class="what"><b>${esc(wtype(w.type))}</b><span class="muted">${esc(w.source || "")}</span></span><span class="chip" style="color:var(--c-exercise-ink)">${dur(w.minutes)}</span></li>`).join("")}</ul>`
      : `<p class="muted small">${t(S.untimed_exercise ? "time.untimed" : "time.no_workouts")}</p>`;
    const devices = Object.entries(S.devices).sort((a, b) => b[1] - a[1]).map(([d, m]) => `${esc(device(d))} ${dur(m)}`).join(" · ");
    return `<div class="head"><div><h1>${t("time.title")}</h1><div class="sub">${t("time.span", { from: day(S.from, { weekday: false }), to: day(S.to, { weekday: false }), n: S.n })}</div></div>${stepper}</div>
      <div class="grid">
        ${heroHtml(p)}
        <section class="card span-12"><h2>${t("time.per_day")}<span class="aside">${t("time.vs_normal", { n: p.baseline_days })}</span></h2><div class="tiles act-tiles">${tiles}</div></section>
        <section class="card span-12"><h2><span>${phrases(t("time.typical"))}</span><span class="aside legend">${SCREEN_PARTS.map(([k, c]) => `<span class="key"><i style="background:${c}"></i>${t(`cat.${k}`)}</span>`).join("")}</span></h2><div id="hours" class="chart"></div></section>
        ${stackHtml(p)}
        <section class="card span-12"><h2>${t("time.history")}<span class="aside">${phrases(t("time.history_note"))}</span></h2><div id="history" class="chart"></div></section>
        <section class="card span-7"><h2>${t("time.apps")}<span class="aside">${t("time.apps_note")}</span></h2>${apps ? `<ul class="apps">${apps}</ul>
          <p class="xs muted" style="margin:10px 0 0">${t("time.devices")}: ${devices}</p>` : `<p class="muted small">${t("time.no_screens")}</p>`}</section>
        <section class="card span-5"><h2>${t("time.workouts")}<span class="aside">${t("time.workouts_note")}</span></h2>${workouts}</section>
        <section class="card span-12"><details class="how" open><summary>${t("ui.how")}</summary><p>${esc(t("time.rule", { n: p.baseline_days, min: p.baseline_min }))}</p><p>${esc(t("time.rule_stack"))}</p></details></section>
      </div>`;
  },
  mount(root, p) {
    if (p.empty || !p.span.metrics || !p.span.changes.every((c) => "clear" in c)) return;
    const S = p.span;
    root.querySelectorAll(".bul").forEach((el) => {
      const m = S.metrics[el.dataset.key];
      draw(el, (w) => bullet(m.value, m.band, { width: w, unit: "min", tone: shownTone(m) }));
    });
    const ROW = {
      sleep: { parts: [["sleep", "var(--c-sleep)"]] },
      exercise: { parts: [["exercise", "var(--c-exercise)"]] },
      calendar: { parts: [["calendar", "var(--c-event)"]] },
      screen: { parts: SCREEN_PARTS },
    };
    // a column with no record for that activity is null (drawn as ×), never an empty bar
    const hourVal = (key) => S.by_hour.map((h) => (key === "screen" ? (h.fun == null ? null : h) : h[key] == null ? null : { [key]: h[key] }));
    const hourRows = ORDER.map((key) => ({ key, label: t(`act.${key}`), sub: dur(S.avg[key]), parts: ROW[key].parts, values: hourVal(key), max: 60 }));
    const hourCols = S.by_hour.map((_, i) => ({ label: String(i).padStart(2, "0"), tip: `${String(i).padStart(2, "0")}:00` }));
    const every = (w, labelW, n, px) => Math.max(1, Math.ceil(px / Math.max(1, (w - labelW - 8) / n)));  // labels never touch
    const labelW = (w) => (w < 560 ? 92 : 150);
    draw(root.querySelector("#hours"), (w) => lanes(hourRows, hourCols, { width: w, labelW: labelW(w), labelEvery: Math.max(every(w, labelW(w), 24, 26), w < 560 ? 6 : 3), showMax: false }));
    const K = S.stack;
    if (K) {
      // one row per device in the priority order (others after), then all devices: the clock time and what devices at once add on top
      const order = [...(p.devices_order || []).filter((d) => d in K.devices), ...Object.keys(K.devices).filter((d) => !(p.devices_order || []).includes(d)).sort()];
      const devRows = order.map((d) => ({ key: d, label: device(d), sub: dur(K.devices[d]), parts: SCREEN_PARTS, max: 60,
        values: K.by_hour.map((h) => h[d] || {}) }));
      const totals = K.by_hour.map((h) => Object.values(h).reduce((s, parts) => s + Object.values(parts).reduce((a, b) => a + b, 0), 0));
      const allMax = Math.max(60, ...totals);
      const allRow = { key: "all", label: t("time.all_devices"), sub: t("chart.row_max", { v: dur(allMax) }), max: allMax,
        parts: [["clock", "var(--c-axis)"], ["extra", "var(--ink)", { hatch: true }]],
        values: totals.map((m, h) => ({ clock: K.clock_by_hour[h], extra: Math.max(0, m - K.clock_by_hour[h]) })) };
      draw(root.querySelector("#stack-hours"), (w) => lanes([...devRows, allRow], hourCols, { width: w, labelW: labelW(w), labelEvery: Math.max(every(w, labelW(w), 24, 26), w < 560 ? 6 : 3), showMax: false }));
    }
    const H = p.history;
    const val = (key) => H.map((d) => { const v = d.totals?.[key]; return v == null ? null : key === "screen" ? d.totals : { [key]: v }; });
    const peak = (key) => Math.max(30, ...H.map((d) => d.totals?.[key] ?? 0));
    const limit = p.limits.fun_max_min;
    // devices at once: the minutes several devices add beyond the clock, striped like the extra on the card above
    const extra = H.map((d) => (d.totals?.stacked == null || d.totals?.screen == null ? null : { extra: Math.max(0, d.totals.stacked - d.totals.screen) }));
    const extraRow = { key: "extra", label: t("time.extra_row"), sub: t("time.extra_sub"), parts: [["extra", "var(--ink)", { hatch: true }]], values: extra,
      max: Math.max(30, ...extra.map((v) => v?.extra ?? 0)) };
    const dayRows = (w) => [...ORDER.map((key) => ({ key, label: t(`act.${key}`), parts: ROW[key].parts, values: val(key), max: peak(key),
      ...(key === "screen" && limit ? { limit, limitLabel: t(w < 560 ? "time.limit_short" : "time.fun_limit", { v: dur(limit, { short: true }) }) } : {}) })),
      ...(extra.some((v) => v) ? [extraRow] : [])];
    const dayCols = H.map((d) => ({ label: shortDay(d.date), tip: day(d.date), shade: d.in_span }));
    draw(root.querySelector("#history"), (w) => lanes(dayRows(w), dayCols, { width: w, rowH: 58, labelW: labelW(w), labelEvery: Math.max(every(w, labelW(w), H.length, 44), w < 560 ? 7 : 3) }));
  },
};
