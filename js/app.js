// Shell: header, language and light/dark, hash routing (#today, #today/2026-10-11).
import { get, isStatic } from "./api.js";
import { installTooltip, esc } from "./charts.js";
import { getLang, setLang, t, clock } from "./i18n.js";
import body from "./pages/body.js";
import data from "./pages/data.js";
import drain from "./pages/drain.js";
import review from "./pages/review.js";
import sleep from "./pages/sleep.js";
import time from "./pages/time.js";
import today from "./pages/today.js";
import week from "./pages/week.js";

const PAGES = { today, week, body, sleep, time, drain, review, data };
const NAV = ["today", "week", "body", "time", "drain", "review", "data"];
// a menu item that holds several pages shows a small switch under the page title
const GROUPS = { body: [["body", "nav.weight"], ["sleep", "nav.sleep_tab"]] };
const groupOf = (page) => Object.keys(GROUPS).find((g) => GROUPS[g].some(([p]) => p === page)) || page;
const ALIAS = { attention: "time" };  // old links keep working
const store = {
  get(key) { try { return localStorage.getItem(`dayring.${key}`); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(`dayring.${key}`, value); } catch { /* private mode */ } },
};
let settings = { title: "dayring", locale: "en", demo: false };

const ICON = {
  logo: `<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="12.5" fill="none" stroke="var(--c-band)" stroke-width="5"/><path d="M16 3.5a12.5 12.5 0 0 1 11.8 8.3" fill="none" stroke="var(--c-sleep)" stroke-width="5" stroke-linecap="round"/><path d="M28.3 18.5a12.5 12.5 0 0 1-6.6 9.1" fill="none" stroke="var(--c-focus)" stroke-width="5" stroke-linecap="round"/><path d="M17.5 28.4a12.5 12.5 0 0 1-9.7-3.7" fill="none" stroke="var(--c-fun)" stroke-width="5" stroke-linecap="round"/></svg>`,
  moon: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15.5 12.6A6.5 6.5 0 0 1 7.4 4.5a6.5 6.5 0 1 0 8.1 8.1z"/></svg>`,
  swatch: `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="10" cy="10" r="6.5"/><path d="M10 3.5v13" /><path d="M10 3.5a6.5 6.5 0 0 1 0 13z" fill="currentColor"/></svg>`,
};

const query = new URLSearchParams(location.search);  // ?mode=light&lang=zh for shared links
function applyLook() {
  const root = document.documentElement;
  const mode = query.get("mode") || store.get("mode");
  if (mode === "light" || mode === "dark") root.dataset.mode = mode; else delete root.dataset.mode;
}

function header(active) {
  const top = document.querySelector(".top-in");
  top.innerHTML = `
    <a class="brand" href="#today">${ICON.logo}<span>${esc(settings.title)}</span></a>
    <nav class="nav" aria-label="Pages">${NAV.filter((p) => PAGES[p]).map((p) => `<a href="#${p}" ${p === groupOf(active) ? 'aria-current="page"' : ""}>${t(`nav.${p}`)}</a>`).join("")}</nav>
    <div class="tools">
      ${settings.demo ? `<span class="demo-badge" title="${esc(t("ui.demo"))}">${t("ui.demo")}</span>` : ""}
      <button class="tool" id="lang" type="button" aria-label="Language">${t("ui.lang")}</button>
      <button class="tool" id="mode" type="button" aria-label="${esc(t("ui.mode"))}" title="${esc(t("ui.mode"))}">${ICON.moon}</button>
    </div>`;
  // on a narrow phone the nav scrolls sideways (its scrollbar is hidden): keep the current page's tab in view
  const nav = top.querySelector(".nav"), current = nav.querySelector("[aria-current]");
  if (current && nav.scrollWidth > nav.clientWidth) {
    const n = nav.getBoundingClientRect(), c = current.getBoundingClientRect();
    if (c.right > n.right) nav.scrollLeft += c.right - n.right + 12;
    else if (c.left < n.left) nav.scrollLeft -= n.left - c.left + 12;
  }
  top.querySelector("#lang").onclick = () => { const next = getLang() === "zh" ? "en" : "zh"; store.set("lang", next); setLang(next); route(); };
  top.querySelector("#mode").onclick = () => {
    const dark = document.documentElement.dataset.mode ? document.documentElement.dataset.mode === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    store.set("mode", dark ? "light" : "dark"); applyLook();
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
    document.title = `${t(`nav.${page}`)} · ${settings.title}`;
    const group = GROUPS[groupOf(page)];
    const sub = group ? `<nav class="subnav seg" aria-label="${esc(t(`nav.${groupOf(page)}`))}">${group.map(([p, key]) => `<a href="#${p}" ${p === page ? 'aria-current="page"' : ""}>${t(key)}</a>`).join("")}</nav>` : "";
    main.innerHTML = sub + PAGES[page].render(data);
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
  try { settings = { ...settings, ...(await get("settings")) }; } catch { /* defaults */ }
  setLang(query.get("lang") || store.get("lang") || settings.locale);
  applyLook();
  installTooltip();
  window.addEventListener("hashchange", route);
  route();
}

start();
export { clock };
