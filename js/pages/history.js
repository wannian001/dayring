// History (#history): how the author's own personal system, which this project was taken out of, changed over a
// year. Laid out like the design summary page of Ready to Train?: three cards on what it is first, then the year
// drawn to real days, then each generation as "wanted → examples → found / changed", the lessons and what is not
// done yet. Words in ../history-content.js; the server only names the page (modules/docs.py).
import { esc } from "../charts.js?v=150dddf82c";
import { getLang, t } from "../i18n.js?v=150dddf82c";
import { AXIS, HISTORY } from "../history-content.js?v=150dddf82c";

const DAY = 86400000;
const at = (iso) => Date.parse(`${iso}T00:00:00Z`);
const DAYS = (at(AXIS.to) - at(AXIS.from)) / DAY + 1;
const left = (iso) => ((at(iso) - at(AXIS.from)) / DAY / DAYS) * 100;
const width = (a, b) => (((at(b) - at(a)) / DAY + 1) / DAYS) * 100;
const pct = (v) => `${v.toFixed(2)}%`;

function axis(c) {
  const spans = AXIS.spans.map(([a, b, kind]) => `<span class="seg ${kind}" style="left:${pct(left(a))};width:${pct(width(a, b))}"></span>`).join("");
  const ticks = AXIS.ticks.map(([d, label]) => `<span style="left:${pct(left(d))}">${label}</span>`).join("")
    + `<span style="right:0">${AXIS.to.slice(5).replace("-", ".")}</span>`;
  // page links here would change the page (the app routes on the hash), so the labels scroll within the page
  const marks = AXIS.marks.map(([id, d, row], i) =>
    `<button type="button" class="r${row}" data-to="${id}" style="left:${pct(left(d))}">${esc(c.axisLabels[i])}</button>`).join("");
  return `<div class="doc-axis">
      <div class="doc-ticks" aria-hidden="true">${ticks}</div>
      <div class="doc-ribbon" role="img" aria-label="${esc(c.axisAria)}">${spans}</div>
      <div class="doc-marks">${marks}</div>
      <p class="doc-small">${c.axisNote}</p></div>`;
}

const examples = (c, rows) => `<div class="doc-ex"><p class="doc-ex-head">${c.exHead}</p><ul>${rows.map(([tag, text]) =>
  `<li><span class="doc-ver">${esc(tag)}</span><p>${text}</p></li>`).join("")}</ul></div>`;
const pair = (c, [found, changed]) => `<div class="doc-pair">
  <div class="doc-step"><span class="doc-tag find">${c.found}</span><p>${found}</p></div>
  <div class="doc-step"><span class="doc-tag fix">${c.changed}</span><p>${changed}</p></div></div>`;
const part = (c, g) => `<p class="doc-aim">${g.aim}</p>${examples(c, g.examples)}${g.pairs.map((p) => pair(c, p)).join("")}`;

function generation(c, g) {
  const body = g.stages
    ? g.stages.map((s) => `<section class="doc-stage"><h3>${s.title}<span class="doc-when">${s.when}</span></h3>${part(c, s)}</section>`).join("")
    : part(c, g);
  return `<article class="card doc-gen" id="${g.id}">
      <div class="doc-meta"><span class="doc-gen-code">${g.code}</span><span>${g.name}</span><span class="num">${g.dates}</span>${g.extra ? `<span>${g.extra}</span>` : ""}</div>
      <div class="doc-body"><h2 class="doc-h">${g.title}</h2>${body}</div></article>`;
}

export default {
  render() {
    const c = HISTORY[getLang()] || HISTORY.en;
    const go = [["today", "nav.today"], ["sleep", "nav.body"], ["goals", "nav.plan"]].map(([p, key]) => `<a href="#${p}">${t(key)} ›</a>`).join("");
    const cards = c.cards.map((card, i) => `<section class="card doc-card"><h3><span class="doc-n">${"ABC"[i]}</span>${card.h}</h3>
      <ul>${card.items.map((x) => `<li>${x}</li>`).join("")}</ul>${i === 2 ? `<p class="doc-try"><span>${c.tryIt}</span>${go}</p>` : ""}</section>`).join("");
    const sample = c.sample.lines.map((l) => (l ? `<p>${esc(l)}</p>` : `<span class="gap"></span>`)).join("");
    return `<div class="head"><div><h1>${c.title}</h1><div class="sub">${c.sub}</div></div></div>
      <div class="doc">
        <div class="doc-note"><p>${c.note}</p><button type="button" class="doc-link" id="doc-lang">${t("doc.other_lang")}</button></div>
        <h2 class="doc-section">${c.briefTitle}</h2>
        <div class="doc-brief">${cards}</div>
        <div class="doc-glance">
          <figure class="doc-sample"><figcaption>${c.sample.label}</figcaption><div class="doc-bubble">${sample}<span class="time">08:30</span></div></figure>
          ${axis(c)}
        </div>
        <div class="doc-gens">${c.gens.map((g) => generation(c, g)).join("")}</div>
        <h2 class="doc-section">${c.lessonsTitle}</h2>
        <ol class="doc-lessons">${c.lessons.map(([h, p], i) => `<li class="card doc-lesson"><h3><span class="doc-n">${i + 1}</span>${h}</h3><p>${p}</p></li>`).join("")}</ol>
        <p class="doc-small">${c.smallLessons}</p>
        <h2 class="doc-section">${c.notyetTitle}</h2>
        <ul class="doc-notyet">${c.notyet.map(([b, rest]) => `<li><b>${b}</b>${rest ? ` ${rest}` : ""}</li>`).join("")}</ul>
        <p class="doc-small doc-source">${c.source}</p>
      </div>`;
  },
  mount(el) {
    const lang = el.querySelector("#doc-lang");
    if (lang) lang.onclick = () => document.querySelector("#lang")?.click();  // the menu's switch: remembers it and redraws
    const smooth = !matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.querySelectorAll("[data-to]").forEach((b) => {
      b.onclick = () => el.querySelector(`#${b.dataset.to}`)?.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
    });
  },
};
