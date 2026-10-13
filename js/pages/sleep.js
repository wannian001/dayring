import { draw, esc, ladderChart, sleepWindows } from "../charts.js?v=ad73753ded";
import { clock, day, dur, shortDay, t } from "../i18n.js?v=ad73753ded";

const MARK = { true: ["✓", "good"], false: ["✗", "bad"], null: ["–", ""] };
const CHECKS = ["woke_on_time", "asleep_in_time", "slept_enough", "screen_before_sleep_ok"];

function compare(key, now, before, fmt) {
  return `<div class="tile"><div class="label"><span>${t(`sleep.${key}`)}</span></div>
    <div class="value">${esc(fmt(now))}</div><div class="note">${t("sleep.last_week", { v: fmt(before) })}</div></div>`;
}

export default {
  render(p) {
    const tw = p.this_week, lw = p.last_week;
    const s = p.shift;
    const tonight = p.tonight ? `<div class="tonight" style="margin-top:0"><div><span>${t("today.phone_away")}</span><b>${clock(p.tonight.phone_away)}</b></div>
      <div><span>${t("today.asleep_by")}</span><b>${clock(p.tonight.asleep_by)}</b></div><div><span>${t("today.alarm")}</span><b>${clock(p.tonight.alarm)}</b></div></div>` : `<p class="muted small">${t("sleep.no_plan")}</p>`;
    const progress = s ? (() => {
      const total = Math.max(1, (parseInt(s.first_alarm) * 60 + parseInt(s.first_alarm.split(":")[1])) - (parseInt(s.final_alarm) * 60 + parseInt(s.final_alarm.split(":")[1])));
      const share = Math.min(1, s.moved_min / total);
      return `<div style="margin-top:var(--s-4)"><div class="row" style="justify-content:space-between"><span class="small">${t("sleep.moved", { moved: dur(s.moved_min), total: dur(total) })}</span>
        <span class="xs muted">${s.first_alarm} → ${s.final_alarm}</span></div>
        <div class="progress"><span style="width:${(share * 100).toFixed(1)}%"></span></div>
        <p class="xs muted" style="margin:6px 0 0">${t("sleep.shift_rule", { step: s.step_min, grace: s.grace_min })}</p></div>`;
    })() : "";
    const checkRows = CHECKS.map((c) => `<tr><th scope="row">${t(`sleep.check.${c}`)}</th>${p.checks.map((d) => { const [mark, cls] = MARK[String(d[c])]; return `<td><span class="mark ${cls}" title="${esc(shortDay(d.date))}">${mark}</span></td>`; }).join("")}</tr>`).join("");
    return `<div class="head"><div><h1>${t("nav.sleep")}</h1><div class="sub">${p.plan.target_hours ? t("sleep.sub", { h: p.plan.target_hours }) : ""}</div></div></div>
      <div class="grid">
        <section class="card span-5"><h2>${t("today.tonight")}</h2>${tonight}${progress}</section>
        <section class="card span-7"><h2>${t("sleep.compare")}</h2><div class="tiles two">
          ${compare("asleep", tw.onset, lw.onset, (v) => v || "—")}
          ${compare("woke", tw.wake, lw.wake, (v) => v || "—")}
          ${compare("duration", tw.sleep_min, lw.sleep_min, (v) => dur(v))}
          ${compare("spread", tw.onset_spread_min, lw.onset_spread_min, (v) => (v == null ? "—" : `± ${dur(v)}`))}</div></section>
        <section class="card span-7"><h2>${t("sleep.windows")}<span class="aside legend"><span class="key"><i style="background:var(--c-sleep)"></i>${t("ring.sleep")}</span>${s ? `<span class="key"><i style="background:var(--c-mark);width:3px;height:14px;border-radius:2px"></i>${t("today.alarm")}</span>` : ""}</span></h2><div id="nights" class="chart"></div></section>
        <section class="card span-5"><h2>${t("sleep.checks")}</h2>
          <div class="table-wrap"><table class="checks"><thead><tr><th></th>${p.checks.map((d) => `<th scope="col">${shortDay(d.date)}</th>`).join("")}</tr></thead><tbody>${checkRows}</tbody></table></div>
          <details class="how"><summary>${t("ui.how")}</summary><p>${t("sleep.checks_rule", { min: p.rules.fun_before_sleep_ok_min, slack: p.rules.slack_min })}</p></details></section>
        ${s ? `<section class="card span-12"><h2>${t("sleep.ladder")}<span class="aside legend"><span class="key"><i style="background:var(--accent);height:3px"></i>${t("today.alarm")}</span><span class="key"><i style="background:var(--good);border-radius:50%"></i>${t("sleep.on_time")}</span><span class="key"><i style="background:var(--off);border-radius:50%"></i>${t("sleep.late")}</span></span></h2><div id="ladder" class="chart"></div></section>` : ""}
      </div>`;
  },
  mount(root, p) {
    draw(root.querySelector("#nights"), (w) => sleepWindows([...p.nights].reverse(), { width: w }));
    if (p.shift) draw(root.querySelector("#ladder"), (w) => ladderChart(p.shift.ladder, { width: w, final: p.shift.final_alarm }));
  },
};
