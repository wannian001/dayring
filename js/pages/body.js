import { draw, esc, timeChart } from "../charts.js?v=8d57b217c2";
import { day, num, signed, t } from "../i18n.js?v=8d57b217c2";

const kg = (v) => (v == null ? "—" : `${num(v, 1)} kg`);
const STATUS = { on_track: "good", faster: "watch", slower: "watch", reached: "good" };

export default {
  render(p) {
    if (!p.points.length) {
      return `<div class="head"><div><h1>${t("nav.weight")}</h1></div></div><div class="card"><div class="empty">${t("body.empty")}</div></div>`;
    }
    const L = p.latest;
    const plan = p.plan;
    const facts = [
      [t("body.rate"), L.rate_per_week == null ? "—" : `${signed(L.rate_per_week, 2, " kg")} · ${signed(L.rate_pct, 1, "%")}`],
      plan ? [t("body.since_start", { day: day(plan.start_date, { weekday: false }) }), signed(L.since_start, 1, " kg")] : null,
      plan ? [t("body.to_go", { target: kg(plan.target_kg) }), kg(L.to_go)] : null,
      plan && L.eta ? [t("body.eta"), day(L.eta, { weekday: false })] : null,
      [t("body.weighed"), t("body.weighed_n", { n: p.weighed_days_14 })],
    ].filter(Boolean);
    return `<div class="head"><div><h1>${t("nav.weight")}</h1><div class="sub">${t("body.sub")}</div></div></div>
      <div class="grid">
        <section class="card span-4"><h2>${t("body.weight")}</h2>
          <p class="hero-num">${kg(L.avg7)}</p>
          <p class="small muted" style="margin:0 0 10px">${t("body.avg7_on", { day: day(L.date) })}</p>
          ${L.status ? `<span class="chip ${STATUS[L.status]}">${t(`body.status.${L.status}`)}</span>` : `<span class="chip">${t("body.no_plan")}</span>`}
          <dl class="facts">${facts.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd class="num">${esc(v)}</dd></div>`).join("")}</dl>
        </section>
        <section class="card span-8"><h2>${t("body.chart")}<span class="aside legend">
            <span class="key"><i style="background:var(--ink-3);border-radius:50%"></i>${t("body.daily")}</span>
            <span class="key"><i style="background:var(--c-mark);height:3px"></i>${t("chart.avg7")}</span>
            ${plan ? `<span class="key"><i style="background:var(--accent-soft);border:1px solid var(--accent)"></i>${t("body.corridor", { lo: num(Math.min(...plan.weekly_loss_pct), 1), hi: num(Math.max(...plan.weekly_loss_pct), 1) })}</span>` : ""}</span></h2>
          <div id="wchart" class="chart"></div>
          <details class="how"><summary>${t("ui.how")}</summary><p>${t("body.rule")}</p></details></section>
        <section class="card span-8"><h2>${t("body.long")}<span class="aside">${t("body.long_note")}</span></h2><div id="mchart" class="chart"></div></section>
        <section class="card span-4"><h2>${t("body.waist")}</h2>${p.waist.length ? `<ul class="agenda">${p.waist.slice(-6).reverse().map((w) => `<li style="grid-template-columns:1fr auto"><span>${day(w.date)}</span><b class="num">${num(w.value, 1)} cm</b></li>`).join("")}</ul>` : `<p class="muted small">${t("body.no_waist")}</p>`}</section>
      </div>`;
  },
  mount(root, p) {
    if (!p.points.length) return;
    const first = p.points[0].date, last = p.corridor.length ? p.corridor[p.corridor.length - 1].date : p.day;
    const band = p.corridor.filter((c) => c.date >= first);
    draw(root.querySelector("#wchart"), (w) => timeChart({
      band, points: p.points.map((x) => ({ date: x.date, value: x.kg })), line: p.avg7.map((x) => ({ date: x.date, value: x.kg })),
      refs: p.plan ? [{ value: p.plan.target_kg, label: t("body.target", { kg: num(p.plan.target_kg, 1) }) }] : [],
    }, { width: w, height: 280, first, last, fmt: (v) => num(v, 1) }));
    const months = p.monthly.map((m) => ({ date: `${m.month}-15`, value: m.kg }));
    if (months.length > 1) {
      draw(root.querySelector("#mchart"), (w) => timeChart({ line: months, points: months }, { width: w, height: 200, first: months[0].date, last: months[months.length - 1].date, fmt: (v) => num(v, 1), maxGap: 45 }));
    }
  },
};
