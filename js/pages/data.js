import { coverage, draw, esc } from "../charts.js?v=f1813bf9c8";
import { clock, day, num, t } from "../i18n.js?v=f1813bf9c8";

const STATUS = { ok: "good", stale: "watch", missing: "bad" };

export default {
  render(p) {
    const streams = p.streams.map((s, i) => `<div class="stream">
      <div class="stream-head"><b>${t(`data.s.${s.key}`)}</b><span class="chip ${STATUS[s.status]}">${t(`data.status.${s.status}`)}</span>
        <span class="xs muted">${s.last ? (s.days_behind === 0 ? t("data.last_today") : t("data.last", { day: day(s.last), n: s.days_behind })) : t("data.never")}</span>
        <span class="spacer"></span><span class="xs muted">${t("data.days", { n: s.days_with_data, k: p.days })}</span></div>
      <div class="cov" data-i="${i}"></div></div>`).join("");
    const tables = p.tables.map((tb) => `<tr><th scope="row"><code>${esc(tb.file)}</code><span class="xs muted" style="display:block;font-weight:400">${esc(tb.doc)}</span></th>
      <td class="num">${tb.present ? num(tb.rows) : `<span class="muted">${t("data.absent")}</span>`}</td>
      <td class="xs muted">${tb.modified ? `${day(tb.modified, { weekday: false })} ${clock(tb.modified)}` : "—"}</td>
      <td>${tb.problem_count ? `<span class="chip bad">${t("data.problems", { n: tb.problem_count })}</span>` : tb.present ? `<span class="chip good">${t("data.clean")}</span>` : ""}</td></tr>
      ${tb.problems.map((pr) => `<tr class="problem"><td colspan="4" class="xs">${t("data.problem_line", { line: pr.line, column: pr.column })}: ${esc(pr.message)}</td></tr>`).join("")}`).join("");
    return `<div class="head"><div><h1>${t("nav.data")}</h1><div class="sub">${t("data.sub", { n: p.days })}</div></div>
      <span class="chip ${p.ok ? "good" : "watch"}">${t(p.ok ? "data.ok" : "data.attention")}</span></div>
      <div class="grid">
        <section class="card span-12"><h2>${t("data.arrivals")}<span class="aside legend">
          <span class="key"><i style="background:var(--c-mark);opacity:.8"></i>${t("data.mark.1")}</span>
          <span class="key"><i style="background:var(--ink-3);opacity:.5"></i>${t("data.mark.p")}</span>
          <span class="key"><i style="background:var(--c-band)"></i>${t("data.mark.0")}</span></span></h2>
          <div class="streams">${streams}</div>
          <p class="xs muted" style="margin:12px 0 0">${t("data.honest")}</p></section>
        <section class="card span-7"><h2>${t("data.files")}</h2><div class="table-wrap"><table class="review data-table">
          <thead><tr><th scope="col">${t("data.file")}</th><th scope="col">${t("data.rows")}</th><th scope="col">${t("data.modified")}</th><th scope="col"></th></tr></thead>
          <tbody>${tables}</tbody></table></div></section>
        <section class="card span-5"><h2>${t("data.import")}</h2><p class="small" style="margin-top:0">${t("data.import_lede")}</p>
          <pre class="code">python -m dayring import apple-health export.zip
python -m dayring import ics timetable.ics --kind class
python -m dayring import macos-screentime
python -m dayring import csv deadlines my.csv \\
  --map "Due=due,Task=title,Course=group"
python -m dayring check</pre>
          <p class="xs muted">${t("data.import_note")}</p></section>
      </div>`;
  },
  mount(root, p) {
    root.querySelectorAll(".cov").forEach((el) => draw(el, (w) => coverage(p.streams[el.dataset.i].marks, p.first, { width: w })));
  },
};
