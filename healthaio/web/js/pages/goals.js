// Goals: every plan in one place and on how many days it was kept, grouped by part of life. A plan that is not
// set is listed with the section of healthaio.toml that sets it. Counts, never streaks or scores.
import { draw, esc, keptDots } from "../charts.js";
import { day, dur, inSentence, num, shortDay, t } from "../i18n.js";
import { icon } from "../icons.js";

const DOMAIN_ICON = { sleep: "sleep", exercise: "exercise", food: "food", body: "heart", screens: "screen" };
const SOURCE = { plan: "goals.src.plan", guideline: "goals.src.who", rule: "goals.src.rule" };

function goalName(r) {
  const g = r.target || {};
  switch (r.key) {
    case "asleep_in_time": return g.clock ? t("goals.asleep_clock", { clock: g.clock }) : t("goals.asleep_alarm", { h: num(g.before_alarm_h) });
    case "slept_enough": return t("goals.slept", { h: num(g.hours) });
    case "woke_on_time": return g.shift ? t("goals.woke_shift") : t("goals.woke_clock", { clock: g.clock });
    case "calm_last_hour": return t("goals.calm", { min: num(g.min) });
    case "weekly_min": return t("goals.weekly_min", { d: dur(g.value) });
    case "strength_days": return t("goals.strength", { n: num(g.value) });
    case "kcal_range": return g.low != null && g.high != null ? t("goals.kcal_range", { a: num(g.low), b: num(g.high) }) : g.high != null ? t("goals.kcal_max", { b: num(g.high) }) : t("goals.kcal_min", { a: num(g.low) });
    case "protein": return g.per_kg ? t("goals.protein_kg", { g: num(g.grams), per: num(g.per_kg, 1) }) : t("goals.protein", { g: num(g.grams) });
    case "last_meal": return t("goals.last_meal", { h: num(g.hours) });
    case "weight_pace": return t("goals.weight", { kg: num(g.target_kg, 1), lo: num(Math.min(...g.weekly_loss_pct), 1), hi: num(Math.max(...g.weekly_loss_pct), 1) });
    case "focus_min": return t("goals.focus", { h: num(g.hours) });
    case "fun_max": return t("goals.fun", { h: num(g.hours) });
    default: return r.key;
  }
}

function row(r, i) {
  const src = SOURCE[r.source] ? `<span class="chip">${t(SOURCE[r.source])}</span>` : "";
  if (r.kind === "unset") {
    return `<div class="goal-row goal-unset"><div class="goal-name"><b>${t(`goals.unset.${r.key}`)}</b>
      <span class="xs muted">${t("goals.unset_how")} <code>[${esc(r.section)}]</code></span></div></div>`;
  }
  if (r.kind === "daily") {
    return `<div class="goal-row"><div class="goal-name"><b>${esc(goalName(r))}</b>${src}</div>
      <div class="goal-dots" data-i="${i}"></div>
      <div class="goal-count"><b class="num">${t("goals.kept", { n: r.kept, k: r.known })}</b><span class="xs muted">${t("goals.kept28", { n: r.kept28, k: r.known28 })}</span></div></div>`;
  }
  if (r.kind === "weekly") {
    const weeks = r.weeks.map((w) => {
      const share = w.value == null ? 0 : Math.min(100, (w.value / r.target.value) * 100);
      const text = w.value == null ? "—" : r.key === "weekly_min" ? dur(w.value) : `${num(w.value)}/${num(r.target.value)}`;
      const mark = w.met === true ? `<span class="mark good" aria-label="${esc(t("goal.kept"))}">✓</span>` : w.met === false ? `<span class="mark bad" aria-label="${esc(t("goal.missed"))}">✗</span>` : `<span class="mark" aria-label="${esc(t("ui.no_data"))}">–</span>`;
      return `<div class="goal-week" data-tip="${esc(`${t("ex.week_of", { day: shortDay(w.week_start) })} · ${text}${w.partial ? ` · ${t("goals.so_far")}` : ""}`)}">
        <span class="xs muted">${w.partial ? t("goals.this_week") : shortDay(w.week_start)}</span><div class="progress" style="margin:0"><span style="width:${share.toFixed(0)}%"></span></div>
        <span class="xs num">${esc(text)}</span>${mark}</div>`;
    }).join("");
    return `<div class="goal-row goal-weekly"><div class="goal-name"><b>${esc(goalName(r))}</b>${src}</div><div class="goal-weeks">${weeks}</div>
      <div class="goal-count"><b class="num">${t("goals.weeks_kept", { n: r.kept, k: r.known })}</b></div></div>`;
  }
  // a status: the weight plan against its corridor
  const tone = r.status === "on_track" || r.status === "reached" ? "good" : r.status ? "watch" : "";
  return `<div class="goal-row"><div class="goal-name"><b>${esc(goalName(r))}</b>${src}</div>
    <div class="goal-status">${r.status ? `<span class="chip ${tone}">${t(`body.status.${r.status}`)}</span>` : `<span class="chip">${t("ui.no_data")}</span>`}
      <span class="small muted">${esc([r.value != null ? `${num(r.value, 1)} kg` : "", r.rate_pct != null ? t("goals.rate", { v: num(r.rate_pct, 1) }) : "", r.eta ? t("goals.eta", { day: day(r.eta, { weekday: false }) }) : ""].filter(Boolean).join(" · "))}</span></div></div>`;
}

export default {
  render(p) {
    const name = (x) => inSentence(goalName(p.rows.find((r) => r.key === x.key)));
    const lede = p.best && p.worst
      ? `<span class="ph">${esc(t("goals.lede_best", { best: name(p.best), bn: p.best.kept, bk: p.best.known }))}</span> <span class="ph">${esc(t("goals.lede_worst", { worst: name(p.worst), wn: p.worst.kept, wk: p.worst.known }))}</span>`
      : esc(p.same ? t("goals.lede_same") : t("goals.lede_none"));
    const cards = p.domains.map((d) => {
      const rows = p.rows.map((r, i) => [r, i]).filter(([r]) => r.domain === d);
      if (!rows.length) return "";
      const link = rows.find(([r]) => r.link)?.[0].link;
      return `<section class="card span-6"><h2><span class="row" style="gap:8px">${icon(DOMAIN_ICON[d], 16)}${t(`goals.domain.${d}`)}</span>${link ? `<span class="aside"><a href="${link}">${t("goals.open")} →</a></span>` : ""}</h2>
        <div class="goal-rows">${rows.map(([r, i]) => row(r, i)).join("")}</div></section>`;
    }).join("");
    return `<div class="head"><div><h1>${t("nav.goals")}</h1><div class="sub">${t("goals.sub", { n: p.set, u: p.unset })}</div></div></div>
      <div class="grid">
        <section class="card span-12"><span class="eyebrow">${t("goals.eyebrow", { n: p.rule.recent })}</span><p class="lede" style="margin:6px 0 4px">${lede}</p>
          <div class="legend" style="margin-top:6px"><span class="key"><i style="background:var(--c-mark);border-radius:50%"></i>${t("goal.kept")}</span>
            <span class="key"><i style="background:none;border:1.5px solid var(--c-mark);border-radius:50%"></i>${t("goal.missed")}</span>
            <span class="key"><i style="background:var(--line-2);height:2px"></i>${t("ui.no_data")}</span></div></section>
        ${cards}
        <section class="card span-12"><details class="how" open><summary>${t("ui.how")}</summary><p>${t("goals.rule", { d: p.rule.days, n: p.rule.recent, k: p.rule.min_known, w: p.rule.weeks })}</p></details></section>
      </div>`;
  },
  mount(root, p) {
    root.querySelectorAll(".goal-dots").forEach((el) => { const r = p.rows[el.dataset.i]; draw(el, (w) => keptDots(r.days, { width: w })); });
  },
};
