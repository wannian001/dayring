// AI work: how much AI agents worked for you, on how many instructions, next to your own focused work, each
// against your normal (modules/ai.py). Usage is input, not output, so the AI numbers are never coloured better or
// worse; only your focused work keeps the Time page's direction. AI work is drawn in focus blue stripes (work, done
// for you), scheduled tasks and scripts in grey stripes, your instructions in ink. A day before the AI record shows
// × (never 0); a day in between without AI use is a real zero.
import { bullet, draw, esc, lanes } from "../charts.js?v=150dddf82c";
import { day, dur, getLang, num, shortDay, t } from "../i18n.js?v=150dddf82c";
import { COLOR, icon, STATE_ICON } from "../icons.js?v=150dddf82c";

const TILES = [  // key, icon, icon colour
  ["ai", "ai", COLOR.ai], ["prompts", "communication", "var(--ink-2)"], ["per_prompt", "ai", "var(--ink-2)"],
  ["focus", "focus", COLOR.focus], ["leverage", "ratio", "var(--ink-2)"]];
const SCREEN_PARTS = [["fun", "var(--c-fun)"], ["focus", "var(--c-focus)"], ["communication", "var(--c-comms)"], ["other", "var(--c-other)"]];
const AI_PARTS = [["you", "var(--c-focus)", { hatch: true }], ["other", "var(--c-other)", { hatch: true }]];
const keep = (text) => text.replace(/ /g, " ");
const count = (v) => (v == null ? "—" : t("ai.count_v", { n: num(v, v > 0 && v < 1 ? 1 : 0) }));  // instructions
const things = (v) => (v == null ? "—" : t("ai.done_v", { n: num(v) }));  // things done
const ratio = (v) => (v == null ? "—" : t("time.ratio_v", { v: num(v / 100, 1) }));
const fmt = (key, v) => (key === "prompts" ? count(v) : key === "leverage" ? ratio(v) : dur(v));
const toneCls = (tone) => (tone === "good" ? "good" : tone === "bad" ? "bad" : "");
const dirWord = (m) => t(`chg.${m.key === "per_prompt" || m.key === "leverage" ? (m.state === "high" ? "higher" : "lower") : (m.state === "high" ? "more" : "less")}`);
const phrases = (text) => (getLang() === "zh"
  ? text.split(/(?<=[，：；。])|\|/).filter(Boolean).map((x) => `<span class="ph">${esc(x)}</span>`).join("")
  : esc(text.replace(/\|/g, "")));

function bandLabel(key, b) {
  const low = keep(fmt(key, b.q1)), high = keep(fmt(key, b.q3));
  return low === high ? t("band_one", { low }) : t("band", { low, high });
}

function stateChip(m) {
  if (m.value == null) return "";
  if (!m.state) return `<span class="chip">${t(m.few ? "time.few" : "state.none")}</span>`;
  if (m.state !== "normal" && !m.clear) return `<span class="chip">${t(`time.slight_${m.state}`)}</span>`;
  const tone = m.clear ? m.tone : "neutral";
  return `<span class="chip ${toneCls(tone)}">${STATE_ICON[tone] || ""}${t(`state.${m.state}`)}</span>`;
}

function tile([key, glyph, color], S) {
  const m = S.metrics[key];
  const known = S.known[key] < S.n ? (S.known[key] ? t("time.known", { n: S.known[key], k: S.n }) : t("time.no_record")) : "";
  const pieces = [m.band ? bandLabel(key, m.band) : "", known, t(`ai.note.${key}`)].filter(Boolean);
  const note = pieces.map((x, i) => `<span class="piece">${esc(x)}${i < pieces.length - 1 ? " ·" : ""}</span>`).join(" ");
  return `<div class="tile act-tile ai-tile">
    <div class="label"><span class="act-name" style="color:${color}">${icon(glyph, 16)}<span>${t(`ai.m.${key}`)}</span></span>${stateChip(m)}</div>
    <div class="act-value"><div class="value">${fmt(key, m.value)}</div></div>
    <div class="bul" data-key="${key}"></div>
    <div class="note">${note}</div></div>`;
}

function heroHtml(p) {
  const S = p.span, A = S.avg;
  const lede = A.ai ? t("ai.line", { ai: keep(dur(A.ai)), n: count(A.prompts) }) : t("ai.line_none");
  const subs = [A.per_prompt != null ? t("ai.sub_per", { per: keep(dur(A.per_prompt)) }) : "",
    A.leverage != null && A.focus ? t("ai.sub_focus", { focus: keep(dur(A.focus)), lev: ratio(A.leverage) }) : "",
    A.other >= 1 ? t("ai.other", { v: keep(dur(A.other)) }) : ""].filter(Boolean).join(" ");
  const compared = Object.values(S.metrics).filter((m) => m.state);
  const chips = S.changes.length
    ? `<div class="chg-also"><span class="xs muted">${t("ai.changes")}</span>${S.changes.map((m) => `<span class="chip ${toneCls(m.tone)}">${icon(m.state === "high" ? "up" : "down", 12)}${esc(t("time.chip", { what: t(`ai.m.${m.key}`), d: fmt(m.key, Math.abs(m.delta)), dir: dirWord(m) }))}</span>`).join("")}</div>`
    : `<p class="xs muted" style="margin:8px 0 0">${t(compared.length ? "ai.usual" : "ai.no_normal")}</p>`;
  // the AI record stops before yesterday: say how old it is (an import that stopped, or days without AI)
  const behind = p.newest ? Math.round((new Date(`${p.today}T12:00`) - new Date(`${p.newest}T12:00`)) / 864e5) : 0;
  const stale = behind > 1 && p.newest === S.to ? `<p class="chip watch stale">${esc(t("time.stale", { what: t("ai.title"), day: day(p.newest) }))}</p>` : "";
  return `<section class="card span-12"><div class="time-hero">
    <div class="time-top"><span class="chg-icon" style="color:${COLOR.ai}">${icon("ai", 56)}</span></div>
    <div class="time-lede"><span class="eyebrow">${t("ai.eyebrow", { n: S.n })}</span><p class="lede" style="margin:4px 0">${phrases(lede)}</p>
      <p class="small muted" style="margin:0">${esc(subs)}</p>${chips}${stale}</div></div></section>`;
}

export default {
  render(p) {
    const head = `<div class="head"><div><h1>${t("ai.title")}</h1>`;
    if (p.empty) {
      const back = p.next ? `<p class="small"><a href="${p.next === p.newest ? "#ai" : `#ai/${p.next}`}">${t("time.next")} ›</a></p>` : "";
      return `${head}</div></div><div class="card"><div class="empty">${t("ai.empty")}</div><pre class="code">python3 -m healthaio import ai-logs</pre>${back}</div>`;
    }
    const S = p.span;
    const nextHref = p.next === p.newest ? "#ai" : `#ai/${p.next}`;
    const stepper = `<div class="stepper">${p.prev ? `<a href="#ai/${p.prev}">‹ ${t("time.prev")}</a>` : `<span aria-disabled="true">‹ ${t("time.prev")}</span>`}
      ${p.next ? `<a href="${nextHref}">${t("time.next")} ›</a>${p.next !== p.newest ? `<a href="#ai">${t("time.latest")}</a>` : ""}` : ""}</div>`;
    const aiKeys = `<span class="key"><i class="hatch" style="color:var(--c-focus)"></i>${t("ai.key.you")}</span><span class="key"><i class="hatch" style="color:var(--c-other)"></i>${t("ai.key.other")}</span>`;
    return `${head}<div class="sub">${t("ai.span", { from: day(S.from, { weekday: false }), to: day(S.to, { weekday: false }), n: S.n })}</div></div>${stepper}</div>
      <div class="grid">
        ${heroHtml(p)}
        <section class="card span-12"><h2>${t("time.per_day")}<span class="aside">${t("time.vs_normal", { n: p.baseline_days })}</span></h2><div class="tiles act-tiles ai-tiles">${TILES.map((x) => tile(x, S)).join("")}</div></section>
        <section class="card span-12"><h2><span>${phrases(t("ai.day"))}</span><span class="aside legend">${SCREEN_PARTS.map(([k, c]) => `<span class="key"><i style="background:${c}"></i>${t(`cat.${k}`)}</span>`).join("")}${aiKeys}</span></h2>
          <div id="ai-hours" class="chart"></div><p class="xs muted" style="margin:8px 0 0">${t("ai.day_note")}</p></section>
        <section class="card span-12"><h2>${t("time.history")}<span class="aside">${phrases(t("time.history_note"))}</span></h2><div id="ai-history" class="chart"></div></section>
        <section class="card span-12"><h2>${t("ai.weeks")}<span class="aside">${phrases(t("ai.weeks_note"))}</span></h2><div id="ai-weeks" class="chart"></div></section>
        <section class="card span-12"><details class="how"><summary>${t("ui.how")}</summary><p>${esc(t("ai.rule", { n: p.baseline_days, min: p.baseline_min }))}</p></details></section>
      </div>`;
  },
  mount(root, p) {
    if (p.empty) return;
    const S = p.span;
    root.querySelectorAll(".ai-tile .bul").forEach((el) => {
      const m = S.metrics[el.dataset.key];
      draw(el, (w) => bullet(m.value, m.band, { width: w, unit: "min", tone: m.clear ? m.tone : "neutral" }));
    });
    const every = (w, labelW, n, px) => Math.max(1, Math.ceil(px / Math.max(1, (w - labelW - 8) / n)));
    const labelW = (w) => (w < 560 ? 92 : 150);
    const H = S.by_hour;
    const peak = (values, floor) => Math.max(floor, ...values.map((v) => (v ? Object.values(v).reduce((a, b) => a + b, 0) : 0)));
    const aiHour = H.map((h) => (h.you == null ? null : { you: h.you, other: h.other || 0 }));
    const promptHour = H.map((h) => (h.prompts == null ? null : { prompts: h.prompts }));
    const hourRows = [
      { key: "sleep", label: t("act.sleep"), parts: [["sleep", "var(--c-sleep)"]], values: H.map((h) => (h.sleep == null ? null : { sleep: h.sleep })), max: 60 },
      { key: "screen", label: t("act.screen"), parts: SCREEN_PARTS, values: H.map((h) => (h.fun == null ? null : h)), max: 60 },
      { key: "ai", label: t("ai.row.ai"), parts: AI_PARTS, values: aiHour, max: peak(aiHour, 60) },
      { key: "prompts", label: t("ai.row.prompts"), parts: [["prompts", "var(--c-mark)"]], values: promptHour, max: peak(promptHour, 3), fmt: count },
    ];
    const hourCols = H.map((_, i) => ({ label: String(i).padStart(2, "0"), tip: `${String(i).padStart(2, "0")}:00` }));
    draw(root.querySelector("#ai-hours"), (w) => lanes(hourRows, hourCols, { width: w, labelW: labelW(w), labelEvery: Math.max(every(w, labelW(w), 24, 26), w < 560 ? 6 : 3) }));

    const D = p.history;
    const val = (fn) => D.map(fn);
    const aiDay = val((d) => (d.ai == null ? null : { you: d.ai, other: d.other || 0 }));
    const promptDay = val((d) => (d.prompts == null ? null : { prompts: d.prompts }));
    const focusDay = val((d) => (d.focus == null ? null : { focus: d.focus }));
    const dayRows = [
      { key: "ai", label: t("ai.row.ai"), parts: AI_PARTS, values: aiDay, max: peak(aiDay, 60) },
      { key: "prompts", label: t("ai.row.prompts"), parts: [["prompts", "var(--c-mark)"]], values: promptDay, max: peak(promptDay, 5), fmt: count },
      { key: "focus", label: t("ai.row.focus"), parts: [["focus", "var(--c-focus)"]], values: focusDay, max: peak(focusDay, 60) },
    ];
    const dayCols = D.map((d) => ({ label: shortDay(d.date), tip: day(d.date), shade: d.in_span }));
    draw(root.querySelector("#ai-history"), (w) => lanes(dayRows, dayCols, { width: w, rowH: 58, labelW: labelW(w), labelEvery: Math.max(every(w, labelW(w), D.length, 44), w < 560 ? 7 : 3) }));

    // seven days at a time: what came out (deadlines marked submitted or done) and what each took
    const W = p.weeks;
    const few = (w, known) => (known * 2 < 7 ? null : w);
    const weekRows = [
      { key: "done", label: t("ai.row.done"), parts: [["done", "var(--c-mark)"]], values: W.map((w) => ({ done: w.done })), max: Math.max(3, ...W.map((w) => w.done)), fmt: things },
      { key: "focus_per", label: t("ai.row.focus_per"), parts: [["v", "var(--c-focus)"]], values: W.map((w) => (w.focus_per_done == null ? (w.done ? null : {}) : { v: w.focus_per_done })), max: Math.max(60, ...W.map((w) => w.focus_per_done || 0)) },
      { key: "ai_per", label: t("ai.row.ai_per"), parts: [["v", "var(--c-focus)", { hatch: true }]], values: W.map((w) => (w.ai_per_done == null ? (w.done ? null : {}) : { v: w.ai_per_done })), max: Math.max(60, ...W.map((w) => w.ai_per_done || 0)) },
      { key: "ai_day", label: t("ai.row.ai_day"), parts: [["v", "var(--c-focus)", { hatch: true }]], values: W.map((w) => (few(w, w.ai_known) && w.ai != null ? { v: w.ai } : null)), max: Math.max(60, ...W.map((w) => w.ai || 0)) },
    ];
    const weekCols = W.map((w, i) => ({ label: shortDay(w.to), tip: `${day(w.from, { weekday: false })} – ${day(w.to, { weekday: false })}`, shade: i === W.length - 1 }));
    draw(root.querySelector("#ai-weeks"), (w) => lanes(weekRows, weekCols, { width: w, rowH: 52, labelW: labelW(w) }));
  },
};
