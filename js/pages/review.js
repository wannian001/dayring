import { esc } from "../charts.js?v=f1813bf9c8";
import { clock, day, dur, measure, num, signed, t } from "../i18n.js?v=f1813bf9c8";

function fmt(m, v) {
  if (v == null) return "—";
  if (m.unit === "clock" || m.unit === "clock_day") { const total = Math.round(v + (m.unit === "clock" ? 720 : 0)) % 1440; return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`; }
  if (m.unit === "days") return num(v, Number.isInteger(v) ? 0 : 1);
  if (m.unit === "points") return num(v, 1);
  return measure(v, m.unit);
}

function changeCell(m) {
  if (m.change == null) return `<td class="muted">—</td>`;
  const isClock = m.unit === "clock" || m.unit === "clock_day";
  const tiny = m.unit === "min" || isClock ? Math.abs(m.change) < 10 : Math.abs(m.change) < (m.unit === "steps" ? 300 : m.unit === "points" || m.unit === "days" ? 0.3 : 1);
  // a change too small to matter, or one that rounds to nothing, reads "about the same" (no "−0m")
  const digits = m.unit === "points" || m.unit === "days" ? 1 : 0;
  const rounded = m.unit === "min" || isClock ? Math.round(m.change) : Number(m.change.toFixed(digits));
  if (tiny || rounded === 0) return `<td><span class="chip">${t("review.same")}</span></td>`;
  let cls = "";
  if (m.better !== "none") cls = (m.better === "higher") === (m.change > 0) ? "good" : "bad";
  let text;
  if (m.unit === "min" || isClock) text = `${m.change >= 0 ? (isClock ? t("review.later") : "+") : (isClock ? t("review.earlier") : "−")}${isClock ? " " : ""}${dur(Math.abs(m.change))}`;
  else text = signed(m.change, digits);
  return `<td><span class="chip ${cls}">${esc(text)}</span></td>`;
}

export default {
  render(p) {
    const stepper = `<div class="stepper"><a href="#review/${p.prev}">‹ ${t("review.prev")}</a>${p.next ? `<a href="#review/${p.next}">${t("review.next")} ›</a>` : `<span aria-disabled="true">${t("review.next")} ›</span>`}</div>`;
    const rows = p.sections.map((s) => `<tr class="sec"><th colspan="4" scope="rowgroup">${t(`review.sec.${s.key}`)}</th></tr>${s.metrics.map((m) => `<tr>
      <th scope="row">${t(`review.m.${m.key}`)}${m.key === "workout_days" && p.planned_workouts ? `<span class="xs muted"> · ${t("review.planned", { n: p.planned_workouts })}</span>` : ""}</th>
      <td class="num"><b>${esc(fmt(m, m.value))}</b>${m.days != null && m.key !== "workout_days" ? `<span class="xs muted"> · ${t("review.days", { n: m.days })}</span>` : ""}</td>
      <td class="num muted">${esc(fmt(m, m.before))}</td>${changeCell(m)}</tr>`).join("")}`).join("");
    const w = p.weight;
    const due = (items) => (items.length ? `<ul class="agenda">${items.map((x) => `<li><span class="when">${day(x.due)}</span><span class="what"><b>${esc(x.title)}</b><span class="muted">${esc([x.group, x.weight_pct ? `${num(x.weight_pct)}%` : ""].filter(Boolean).join(" · "))}</span></span><span class="chip ${x.status === "todo" ? "" : "good"}">${t(`status.${x.status}`)}</span></li>`).join("")}</ul>` : `<p class="muted small">${t("review.none")}</p>`);
    return `<div class="head"><div><h1>${t("review.title", { from: day(p.week_start, { weekday: false }), to: day(p.week_end, { weekday: false }) })}</h1>
      <div class="sub">${p.partial ? t("review.partial") : t("review.sub")}</div></div>${stepper}</div>
      <div class="grid">
        <section class="card span-7"><h2>${t("review.facts")}</h2><div class="table-wrap"><table class="review">
          <thead><tr><th></th><th scope="col">${t("review.this")}</th><th scope="col">${t("review.before")}</th><th scope="col">${t("review.change")}</th></tr></thead>
          <tbody>${rows}</tbody></table></div>
          ${p.gaps.length ? `<p class="xs muted" style="margin-top:12px">${t("review.gaps", { days: p.gaps.map((d) => day(d, { weekday: false })).join("、") })}</p>` : ""}
          <details class="how"><summary>${t("ui.how")}</summary><p>${t("review.rule")}</p></details></section>
        <div class="col span-5">
          <section class="card"><h2>${t("review.weight")}</h2><p class="hero-num" style="font-size:var(--t-2xl)">${w.avg == null ? "—" : `${num(w.avg, 1)} kg`}</p>
            <p class="small muted" style="margin:0">${w.prev_avg != null && w.avg != null ? t("review.weight_change", { v: signed(w.avg - w.prev_avg, 1, " kg") }) : t("review.weight_days", { n: w.days })}</p></section>
          <section class="card"><h2>${t("review.due_this")}</h2>${due(p.due_this)}</section>
          <section class="card"><h2>${t("review.due_next")}</h2>${due(p.due_next)}</section>
        </div>
      </div>`;
  },
};
