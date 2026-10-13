// Shell: the menu (a left sidebar that folds to icons, a bottom tab bar on phones), language and light/dark,
// hash routing (#today, #today/2026-10-11).
import { get, isStatic } from "./api.js?v=ad73753ded";
import { installTooltip, esc, setFormat } from "./charts.js?v=ad73753ded";
import { getLang, setLang, t, clock, dur, measure, shortDay, toDate, wtype } from "./i18n.js?v=ad73753ded";
import { icon } from "./icons.js?v=ad73753ded";
import ai from "./pages/ai.js?v=ad73753ded";
import body from "./pages/body.js?v=ad73753ded";
import data from "./pages/data.js?v=ad73753ded";
import drain from "./pages/drain.js?v=ad73753ded";
import kit from "./pages/kit.js?v=ad73753ded";
import review from "./pages/review.js?v=ad73753ded";
import sleep from "./pages/sleep.js?v=ad73753ded";
import time from "./pages/time.js?v=ad73753ded";
import today from "./pages/today.js?v=ad73753ded";
import week from "./pages/week.js?v=ad73753ded";

// the design kit gallery (#kit) is a page but not a menu item: the footer of every page and the Data page link to it
const PAGES = { today, week, body, sleep, time, ai, drain, review, data, kit };
const NAV = ["today", "week", "body", "time", "drain", "review", "data"];
// a menu item that holds several pages shows a small switch above the page title
const GROUPS = { body: [["body", "nav.weight"], ["sleep", "nav.sleep_tab"]], time: [["time", "nav.time_tab"], ["ai", "nav.ai"]] };
const groupOf = (page) => Object.keys(GROUPS).find((g) => GROUPS[g].some(([p]) => p === page)) || page;
// a page inside a group is titled by its own tab (Weight, Sleep), not by the group
const titleKey = (page) => (GROUPS[groupOf(page)] || []).find(([p]) => p === page)?.[1] || `nav.${page}`;
const ALIAS = { attention: "time" };  // old links keep working
// each menu item's glyph (icons.js)
const NAV_ICON = { today: "sun", week: "calendar", body: "heart", time: "clock", drain: "battery", review: "list", data: "database" };
const store = {
  get(key) { try { return localStorage.getItem(`dayring.${key}`); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(`dayring.${key}`, value); } catch { /* private mode */ } },
};
let settings = { title: "dayring", locale: "en", demo: false };
// the kit's charts write their words and numbers with this app's i18n (charts.js imports nothing)
setFormat({ t, dur, clock, shortDay, measure, toDate, wtype });
const footer = () => `<footer class="foot"><a href="#kit">${t("kit.link")}</a></footer>`;

const ICON = {
  logo: `<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="12.5" fill="none" stroke="var(--c-band)" stroke-width="5"/><path d="M16 3.5a12.5 12.5 0 0 1 11.8 8.3" fill="none" stroke="var(--c-sleep)" stroke-width="5" stroke-linecap="round"/><path d="M28.3 18.5a12.5 12.5 0 0 1-6.6 9.1" fill="none" stroke="var(--c-focus)" stroke-width="5" stroke-linecap="round"/><path d="M17.5 28.4a12.5 12.5 0 0 1-9.7-3.7" fill="none" stroke="var(--c-fun)" stroke-width="5" stroke-linecap="round"/></svg>`,
  moon: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15.5 12.6A6.5 6.5 0 0 1 7.4 4.5a6.5 6.5 0 1 0 8.1 8.1z"/></svg>`,
};

const query = new URLSearchParams(location.search);  // ?mode=light&lang=zh for shared links
let picked = null;  // the moon button's choice in this tab: wins over a ?mode= link, works without storage
function applyLook() {
  const root = document.documentElement;
  const mode = picked || query.get("mode") || store.get("mode");
  if (mode === "light" || mode === "dark") root.dataset.mode = mode; else delete root.dataset.mode;
}

// the sidebar folds to an icon rail on desktop (remembered in this browser; index.html applies it before first paint)
const folded = () => document.documentElement.classList.contains("side-folded");
const wide = () => matchMedia("(min-width: 900px)").matches;

function header(active) {
  const top = document.querySelector(".side");
  const group = groupOf(active);
  // a menu item that holds several pages lists them under it while one of them is open
  const items = NAV.filter((p) => PAGES[p]).map((p) => {
    const here = p === group;
    const subs = here && GROUPS[p] ? GROUPS[p].map(([page, key]) => `<a class="side-sub" href="#${page}" ${page === active ? 'aria-current="page"' : ""}><span>${t(key)}</span></a>`).join("") : "";
    return `<a href="#${p}" title="${esc(t(`nav.${p}`))}" ${here ? 'aria-current="page"' : ""}>${icon(NAV_ICON[p], 18)}<span>${t(`nav.${p}`)}</span></a>${subs}`;
  }).join("");
  top.innerHTML = `
    <div class="side-head">
      <a class="brand" href="#today">${ICON.logo}<span>${esc(settings.title)}</span></a>
      <button class="side-fold" id="fold" type="button" aria-label="${esc(t("ui.fold"))}" title="${esc(t("ui.fold"))}">${icon("sidebar", 18)}</button>
    </div>
    <nav class="side-nav" aria-label="Pages">${items}</nav>
    <div class="side-tools">
      ${settings.demo ? `<span class="demo-badge" title="${esc(t("ui.demo"))}">${t("ui.demo")}</span>` : ""}
      <button class="tool" id="lang" type="button" aria-label="Language">${t("ui.lang")}</button>
      <button class="tool" id="mode" type="button" aria-label="${esc(t("ui.mode"))}" title="${esc(t("ui.mode"))}">${ICON.moon}</button>
    </div>`;
  // folded, the logo unfolds the sidebar instead of opening Today
  const brand = top.querySelector(".brand");
  const label = () => {
    if (folded() && wide()) { brand.title = t("ui.unfold"); brand.setAttribute("aria-label", t("ui.unfold")); }
    else { brand.removeAttribute("title"); brand.removeAttribute("aria-label"); }
  };
  const setFold = (on) => { document.documentElement.classList.toggle("side-folded", on); store.set("side", on ? "folded" : "open"); label(); };
  label();
  top.querySelector("#fold").onclick = () => { setFold(true); brand.focus(); };
  brand.onclick = (e) => { if (folded() && wide()) { e.preventDefault(); setFold(false); top.querySelector("#fold").focus(); } };
  top.querySelector("#lang").onclick = () => { const next = getLang() === "zh" ? "en" : "zh"; store.set("lang", next); setLang(next); route(); };
  top.querySelector("#mode").onclick = () => {
    const dark = document.documentElement.dataset.mode ? document.documentElement.dataset.mode === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    picked = dark ? "light" : "dark";
    store.set("mode", picked);
    if (query.has("mode")) {  // so a reload keeps the choice instead of the link's
      query.delete("mode");
      const rest = query.toString();
      history.replaceState(null, "", `${location.pathname}${rest ? `?${rest}` : ""}${location.hash}`);
    }
    applyLook();
  };
}

async function route() {
  const [raw, param] = (location.hash.replace(/^#/, "") || "today").split("/");
  const name = ALIAS[raw] || raw;
  const page = PAGES[name] ? name : "today";
  header(page);
  const main = document.querySelector("main");
  main.setAttribute("aria-busy", "true");
  try {
    const data = await get(page, param);
    document.title = `${t(titleKey(page))} · ${settings.title}`;
    const group = GROUPS[groupOf(page)];
    const sub = group ? `<nav class="subnav seg" aria-label="${esc(t(`nav.${groupOf(page)}`))}">${group.map(([p, key]) => `<a href="#${p}" ${p === page ? 'aria-current="page"' : ""}>${t(key)}</a>`).join("")}</nav>` : "";
    main.innerHTML = sub + PAGES[page].render(data) + footer();
    PAGES[page].mount?.(main, data);
  } catch (error) {
    const staticGap = isStatic && /^404/.test(error.message);  // the demo site only has a few pre-rendered dates
    main.innerHTML = `<div class="card"><p class="lede">${t(staticGap ? "ui.static_gap" : "ui.error")}</p><p class="muted small">${t(staticGap ? "ui.static_gap_hint" : "ui.error_hint")}</p>
      ${staticGap ? `<p><a href="#${page}">${t("ui.back_latest")}</a></p>` : `<p class="xs muted">${esc(error.message)}</p>`}</div>`;
  } finally {
    main.removeAttribute("aria-busy");
  }
}

async function start() {
  window.dayringStarted = true;  // index.html shows a reload message if this never runs
  try { settings = { ...settings, ...(await get("settings")) }; } catch { /* defaults */ }
  setLang(query.get("lang") || store.get("lang") || settings.locale);
  applyLook();
  installTooltip();
  window.addEventListener("hashchange", route);
  route();
}

start();
export { clock };
