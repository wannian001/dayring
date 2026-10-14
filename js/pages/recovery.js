// Recovery (#recovery, under Body signals): how recovered you are (the Today page's verdict), the morning check-in
// (how you feel, 2 / 5 / 8, and where you are sore on the body figure from the author's GEOM90007 Ready to Train
// project; saved into self_report.csv and soreness.csv), the score the morning after each training day (four parts
// side by side, averaged), and how your body has answered training. What training asked of you is on Load.
// The rules are in modules/recovery.py.
import { isStatic, post } from "../api.js?v=8d57b217c2";
import { bullet, draw, esc } from "../charts.js?v=8d57b217c2";
import { day, dur, measure, num, shortDay, t, wtype } from "../i18n.js?v=8d57b217c2";
import { icon, STATE_ICON } from "../icons.js?v=8d57b217c2";

const toneCls = (tone) => (tone === "good" ? "good" : tone === "bad" ? "bad" : "");
const LOAD_TONE = { high: "watch", low: "", steady: "good" };

function stateChip(m) {
  if (m.partial) return `<span class="chip">${t("state.partial")}</span>`;
  if (!m.state) return `<span class="chip">${t("state.none")}</span>`;
  return `<span class="chip ${toneCls(m.tone)}">${STATE_ICON[m.tone] || ""}${t(`state.${m.state}`)}</span>`;
}

function tile(m) {
  const band = m.band ? t("band", { low: measure(m.band.q1, m.unit), high: measure(m.band.q3, m.unit) }) : "";
  return `<div class="tile act-tile">
    <div class="label"><span class="act-name">${icon(m.key === "sleep" ? "sleep" : "heart", 16)}<span>${t(`metric.${m.key}`)}</span></span>${stateChip(m)}</div>
    <div class="act-value"><div class="value">${measure(m.value, m.unit)}</div></div>
    <div class="bul" data-key="${m.key}"></div>
    <div class="note"><span class="piece">${esc(band)}</span></div></div>`;
}

const regionsText = (levels) => Object.entries(levels).sort((a, b) => b[1] - a[1])
  .map(([r, lv]) => t("sore.with_level", { region: t(`sore.region.${r}`), level: t(`sore.level_short.${lv}`) })).join(t("ui.list_sep"));

function heroHtml(p) {
  const r = p.recovery, L = p.load, S = p.soreness;
  const loadChip = L.state === "none" || L.state === "unknown" || L.state === "few_ratings"
    ? `<span class="chip">${t(`rec.load.${L.state}`)}</span>`
    : `<span class="chip ${LOAD_TONE[L.state]}">${t(`rec.load.${L.state}`)}</span>`;
  const sore = S.today ? (Object.keys(S.levels).length ? regionsText(S.levels) : t("sore.none_today")) : t("sore.not_today");
  return `<section class="card span-12"><span class="eyebrow">${t("recovery.eyebrow")}${r.as_of ? ` · ${esc(day(r.as_of))}` : ""}</span>
    <p class="lede" style="margin:6px 0 var(--s-3)">${t(`recovery.${r.verdict}`)}</p>
    <div class="rec-facts"><a class="rec-fact" href="#load">${icon("exercise", 16)}<span>${t("rec.load_title")}</span>${loadChip}</a>
      <span class="rec-fact">${icon("heart", 16)}<span>${t("sore.title")}</span><span class="chip">${esc(sore)}</span></span></div>
    <div class="tiles act-tiles" style="margin-top:var(--s-4)">${r.metrics.map(tile).join("")}</div>
    <p class="xs muted" style="margin:var(--s-3) 0 0">${t("rec.verdict_note")}</p></section>`;
}

// ---- the morning after each training day: four parts side by side, averaged ---------------------------------
const BAND_TONE = { good: "good", ok: "", low: "bad" };
function partText(k, x) {
  if (k === "feel") return t(`feel.${x.value}`);
  if (k === "hrv") return t("after.hrv", { a: num(x.before), b: num(x.after) });
  if (k === "resting_hr") return t("after.rhr", { v: num(x.value), m: num(x.median) });
  return x.efficiency != null ? t("after.sleep_eff", { d: dur(x.value), e: num(x.efficiency) }) : t("after.sleep", { d: dur(x.value) });
}
function afterHtml(p) {
  const A = p.after, L = A.latest;
  if (!A.days.length) return `<section class="card span-12"><h2>${t("after.title")}</h2><p class="muted small">${t("after.none")}</p></section>`;
  const parts = L ? ["feel", "hrv", "resting_hr", "sleep"].map((k) => {
    const x = L.parts[k];
    return `<div class="after-part"><span class="small">${t(`after.part.${k}`)}</span>
      ${x ? `<b class="num">${num(x.score, 1)}</b><span class="after-bar"><span style="width:${(x.score * 10).toFixed(0)}%"></span></span><span class="xs muted">${esc(partText(k, x))}</span>`
        : `<b class="num muted">—</b><span class="after-bar"></span><span class="xs muted">${t(k === "feel" ? "after.no_feel" : "after.no_record")}</span>`}</div>`;
  }).join("") : "";
  const what = (d) => d.sessions.map((s) => `${wtype(s.type)} ${dur(s.minutes)}${s.effort ? ` × ${num(s.effort)}` : ""}`).join(t("ui.list_sep"));
  const rows = A.days.slice(0, 10).map((d) => `<li><span class="num small">${esc(shortDay(d.date))}</span><span class="small">${esc(what(d))}</span>
    <span class="after-bar"><span style="width:${d.score == null ? 0 : (d.score * 10).toFixed(0)}%"></span></span>
    <b class="num small">${d.score == null ? "—" : num(d.score, 1)}</b></li>`).join("");
  return `<section class="card span-12"><h2>${t("after.title")}<span class="aside">${t("after.sub")}</span></h2>
    ${L ? `<div class="after-top"><div><span class="eyebrow">${t("after.eyebrow", { day: day(L.date), m: day(L.morning, { weekday: false }) })}</span>
      <p class="lede" style="margin:4px 0 0"><span class="after-score num">${num(L.score, 1)}</span> <span class="chip ${BAND_TONE[L.band]}">${t(`after.band.${L.band}`)}</span></p>
      <p class="xs muted" style="margin:4px 0 0">${t("after.formula", { n: Object.keys(L.parts).length })}</p></div>
      <div class="after-parts">${parts}</div></div>` : `<p class="muted small">${t("after.no_score")}</p>`}
    <h3 class="section-title" style="margin-top:var(--s-4)">${t("after.recent")}</h3><ul class="after-list">${rows}</ul></section>`;
}

// ---- how the body answered training, the next morning ------------------------------------------------------------
function outcomeText(r, R) {
  const unit = R.units[r.outcome];
  const show = (v) => (unit === "%" ? `${num(Math.abs(v), 1)}%` : unit === "bpm" ? t("stim.bpm", { v: num(Math.abs(v), 1) }) : t("rec.levels", { v: num(Math.abs(v), 1) }));
  const range = (v) => `${v < 0 ? "−" : ""}${unit === "%" ? `${num(Math.abs(v), 1)}%` : num(Math.abs(v), 1)}`;
  return t("stim.out_line", { dir: t(`rec.out.${r.outcome}.${r.diff >= 0 ? "up" : "down"}`, { v: show(r.diff) }), low: range(r.low), high: range(r.high) });
}

function responseHtml(p) {
  const R = p.response;
  const head = R.median_load != null ? t("rec.exp", { v: num(R.median_load) }) : t("rec.exp_none", { n: R.method.min_group_days });
  const items = R.rows.map((r) => {
    let chip, text;
    if (r.status !== "ok") { chip = `<span class="chip">${t("stim.too_few")}</span>`; text = t("stim.too_few_line", { a: r.yes_days, b: r.no_days, n: R.method.min_group_days }); }
    else {
      const worse = (r.diff > 0) === (R.better[r.outcome] === "lower");
      chip = r.detected ? `<span class="chip ${worse ? "bad" : "good"}">${STATE_ICON[worse ? "bad" : "good"]}${t("stim.seen")}</span>` : `<span class="chip">${t("stim.not_seen")}</span>`;
      text = outcomeText(r, R);
    }
    return `<li><span class="stim-out-name">${t(`rec.out.${r.outcome}`)}</span><span class="stim-out-chip">${chip}</span><span class="small muted">${esc(text)}</span></li>`;
  }).join("");
  return `<section class="card span-12"><h2>${t("rec.body_title")}<span class="aside">${t("rec.body_sub", { n: p.rule.response_days })}</span></h2>
    <div class="stim-group"><h3 class="section-title">${esc(head)}</h3><ul class="stim-out">${items}</ul></div>
    <p class="xs muted" style="margin:10px 0 0">${t("rec.body_note")}</p></section>`;
}

// ---- soreness: the body figure (tap a region to set its level), the list, 14 days per region -------------------
const FIGURE = {
  male: { width: 581, height: 794, viewBox: "0 185 581 575", front: 166, back: 411, orientY: 206, sideY: 742, sideX: [138, 194, 383, 439] },
  female: { width: 1024, height: 1536, viewBox: "-163 60 1350 1350", front: 273, back: 750, orientY: 104, sideY: 1400, sideX: [210, 334, 690, 810] },
};
// one hue getting stronger (--c-sore-1..3), the same in both modes: the figure sits on a white plate in both (as in
// Ready to Train); on the strips "not sore" is the band colour
const SORE = ["var(--c-sore-0)", "var(--c-sore-1)", "var(--c-sore-2)", "var(--c-sore-3)"];
const fill = (level) => SORE[level || 0];
const stripFill = (level) => (level ? SORE[level] : "var(--c-band)");

function figureSvg(p, levels) {
  const sex = p.figure === "female" ? "female" : "male", c = FIGURE[sex];
  const masks = p.regions.map((r) => `<mask id="sore-mask-${r}" x="0" y="0" width="${c.width}" height="${c.height}" maskUnits="userSpaceOnUse" style="mask-type:alpha">
    <image href="img/body-mask-${sex}-${r}.png" x="0" y="0" width="${c.width}" height="${c.height}" preserveAspectRatio="none"/></mask>`).join("");
  const regions = p.regions.map((r) => `<g class="sore-region" data-region="${r}" style="fill:${fill(levels[r])}" role="button" tabindex="0"
      aria-label="${esc(t("sore.region_aria", { region: t(`sore.region.${r}`), level: t(`sore.level.${levels[r] || 0}`) }))}"><rect x="0" y="0" width="${c.width}" height="${c.height}" mask="url(#sore-mask-${r})"/></g>`).join("");
  const text = (x, y, s, cls) => `<text x="${x}" y="${y}" text-anchor="middle" class="${cls}">${esc(s)}</text>`;
  return `<svg class="sore-figure" viewBox="${c.viewBox}" role="group" aria-label="${esc(t("sore.figure"))}">
    <defs>${masks}</defs>
    <image href="img/body-${sex}-reference.png" x="0" y="0" width="${c.width}" height="${c.height}" preserveAspectRatio="none" aria-hidden="true"/>
    ${regions}
    ${text(c.front, c.orientY, t("sore.front"), "sore-orient")}${text(c.back, c.orientY, t("sore.back"), "sore-orient")}
    ${text(c.sideX[0], c.sideY, t("sore.r"), "sore-side")}${text(c.sideX[1], c.sideY, t("sore.l"), "sore-side")}
    ${text(c.sideX[2], c.sideY, t("sore.l"), "sore-side")}${text(c.sideX[3], c.sideY, t("sore.r"), "sore-side")}</svg>`;
}

function stripSvg(days, width) {
  const n = days.length, gap = 3, w = (width - gap * (n - 1)) / n, h = 14;
  return `<svg viewBox="0 0 ${width} ${h}" width="${width}" height="${h}" aria-hidden="true">${days.map((d, i) =>
    `<rect x="${(i * (w + gap)).toFixed(1)}" y="0" width="${w.toFixed(1)}" height="${h}" rx="3" fill="${d.level == null ? "none" : stripFill(d.level)}"
      stroke="${d.level == null ? "var(--line-2)" : "none"}" stroke-dasharray="${d.level == null ? "2 2" : ""}" data-tip="${esc(`${shortDay(d.date)} · ${d.level == null ? t("sore.unchecked") : t(`sore.level.${d.level}`)}`)}"/>`).join("")}</svg>`;
}

function sorenessHtml(p) {
  const S = p.soreness;
  const head = S.today ? t("sore.head_today") : S.latest ? t("sore.head_latest", { day: day(S.latest) }) : t("sore.head_none");
  const legend = [0, 1, 2, 3].map((lv) => `<span class="key"><i style="background:${fill(lv)}"></i>${t(`sore.level.${lv}`)}</span>`).join("");
  const rows = S.regions.map((r, i) => `<div class="sore-row"><span>${t(`sore.region.${r.key}`)}</span>
    <span class="xs muted">${t("sore.days", { n: r.sore_days, k: S.checked })}</span><div class="sore-strip" data-i="${i}"></div></div>`).join("");
  return `<section class="card span-12"><h2>${t("sore.title")}<span class="aside">${t("sore.sub")}</span></h2>
    <div class="sore-layout">
      <div class="sore-figure-wrap">${figureSvg(p, S.today ? S.levels : {})}
        <div class="legend sore-legend">${legend}</div></div>
      <div class="sore-side">
        <p class="lede" style="font-size:var(--t-lg);margin:0 0 4px">${esc(head)}</p>
        <p class="small muted" style="margin:0 0 var(--s-3)">${S.latest && !S.today ? esc(t("sore.latest_was", { list: Object.keys(S.levels).length ? regionsText(S.levels) : t("sore.none_short") })) : ""}</p>
        <div class="feel-row" role="group" aria-label="${esc(t("feel.question"))}"><span class="small">${t("feel.question")}</span>
          ${[2, 5, 8].map((v) => `<button type="button" class="goal-btn feel-btn" data-feel="${v}" aria-pressed="${p.feel_today === v}">${t(`feel.${v}`)}</button>`).join("")}</div>
        <p class="small" style="margin:var(--s-3) 0 var(--s-2)">${t("sore.how_to")}</p>
        <div class="goal-act"><button type="button" class="goal-btn primary" id="sore-save"${isStatic ? " disabled" : ""}>${t("sore.save")}</button>
          <button type="button" class="goal-btn" id="sore-clear">${t("sore.clear")}</button></div>
        <p class="xs sore-msg" role="status">${isStatic ? t("sore.static") : ""}</p>
        <h3 class="section-title" style="margin-top:var(--s-4)">${t("sore.last_days", { n: S.days })}</h3>
        <div class="sore-rows">${rows}</div>
      </div></div>
    <p class="xs muted" style="margin:var(--s-3) 0 0">${t("sore.credit")}</p></section>`;
}

export default {
  render(p) {
    return `<div class="head"><div><h1>${t("rec.title")}</h1><div class="sub">${t("rec.sub")}</div></div></div>
      <div class="grid">
        ${heroHtml(p)}
        ${sorenessHtml(p)}
        ${afterHtml(p)}
        ${responseHtml(p)}
        <section class="card span-12"><details class="how"><summary>${t("ui.how")}</summary>
          <p>${t("rec.rule_after", { good: num(p.after.rule.good, 1), low: num(p.after.rule.low, 1), n: p.after.rule.after_days })}</p>
          <p>${t("rec.rule_body", { n: p.rule.response_days, k: p.response.method.min_group_days })}</p>
          <p>${t("sore.rule", { n: p.rule.sore_days })}</p></details></section>
      </div>`;
  },
  mount(root, p) {
    root.querySelectorAll(".bul").forEach((el) => {
      const m = p.recovery.metrics.find((x) => x.key === el.dataset.key);
      draw(el, (w) => bullet(m.value, m.band, { width: w, unit: m.unit, tone: m.tone }));
    });
    const S = p.soreness;
    root.querySelectorAll(".sore-strip").forEach((el) => draw(el, (w) => stripSvg(S.regions[el.dataset.i].days, w)));
    // tap a region: none → a little → clearly → very → none. An SVG mask does not change what a click hits, so the
    // region under the pointer is read from the masks' own pixels (within a few pixels, so a muscle line still counts)
    const levels = { ...(S.today ? S.levels : {}) };
    const paint = (g) => {
      const r = g.dataset.region, lv = levels[r] || 0;
      g.style.fill = fill(lv);
      g.setAttribute("aria-label", t("sore.region_aria", { region: t(`sore.region.${r}`), level: t(`sore.level.${lv}`) }));
    };
    const step = (r) => {
      levels[r] = ((levels[r] || 0) + 1) % 4;
      if (!levels[r]) delete levels[r];
      paint(root.querySelector(`.sore-region[data-region="${r}"]`));
    };
    root.querySelectorAll(".sore-region").forEach((g) => {
      g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); step(g.dataset.region); } });
    });
    const svg = root.querySelector(".sore-figure");
    const sex = p.figure === "female" ? "female" : "male", c = FIGURE[sex];
    const alpha = {};
    p.regions.forEach((r) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = c.width; canvas.height = c.height;
        const g = canvas.getContext("2d", { willReadFrequently: true });
        g.drawImage(img, 0, 0, c.width, c.height);
        alpha[r] = g.getImageData(0, 0, c.width, c.height).data;
      };
      img.src = `img/body-mask-${sex}-${r}.png`;
    });
    const regionAt = (e) => {
      const pt = svg.createSVGPoint();
      pt.x = e.clientX; pt.y = e.clientY;
      const u = pt.matrixTransform(svg.getScreenCTM().inverse());
      const reach = Math.max(3, Math.round(c.width / 110));
      let best = null, most = 0;
      for (const r of p.regions) {
        const a = alpha[r];
        if (!a) continue;
        let n = 0;
        for (let dy = -reach; dy <= reach; dy += 2) {
          for (let dx = -reach; dx <= reach; dx += 2) {
            const x = Math.round(u.x) + dx, y = Math.round(u.y) + dy;
            if (x >= 0 && y >= 0 && x < c.width && y < c.height && a[(y * c.width + x) * 4 + 3] > 40) n += 1;
          }
        }
        if (n > most) { most = n; best = r; }
      }
      return best;
    };
    svg.addEventListener("click", (e) => { const r = regionAt(e); if (r) { step(r); svg.dataset.tip = `${t(`sore.region.${r}`)} · ${t(`sore.level.${levels[r] || 0}`)}`; } });
    svg.addEventListener("mousemove", (e) => {
      const r = regionAt(e);
      svg.style.cursor = r ? "pointer" : "";
      if (r) svg.dataset.tip = `${t(`sore.region.${r}`)} · ${t(`sore.level.${levels[r] || 0}`)}`;
      else delete svg.dataset.tip;
    });
    let feel = p.feel_today ?? null;
    root.querySelectorAll(".feel-btn").forEach((b) => {
      b.onclick = () => {
        feel = feel === Number(b.dataset.feel) ? null : Number(b.dataset.feel);
        root.querySelectorAll(".feel-btn").forEach((x) => x.setAttribute("aria-pressed", String(Number(x.dataset.feel) === feel)));
      };
    });
    root.querySelector("#sore-clear").onclick = () => { Object.keys(levels).forEach((k) => delete levels[k]); root.querySelectorAll(".sore-region").forEach(paint); };
    const msg = root.querySelector(".sore-msg");
    root.querySelector("#sore-save").onclick = async () => {
      if (isStatic) return;
      try {
        await post("checkin", { date: p.today, levels, feel });
        window.dispatchEvent(new HashChangeEvent("hashchange"));
      } catch (error) {
        msg.textContent = t("sore.err", { e: error.message });
      }
    };
  },
};
