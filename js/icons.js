// dayring design kit: stroke icons, coloured by currentColor. Part of the kit (see docs/DESIGN_KIT.md).
// One per lane of the Time page and one per thing "what changed" can name, plus a check (a usual day), the
// up / down arrows of the change badge and the menu's glyphs (sun, calendar, heart, clock, battery, list,
// database, and sidebar for the fold button). Same grid (24), stroke (1.8) and round joins throughout.
// Convention: the comment line right above each export is its one-line doc (`dayring kit json` reads it).
const svg = (body, size) => `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
const PATHS = {
  screen: '<rect x="2.5" y="4" width="15" height="10.5" rx="1.6"/><path d="M7 18.5h6M10 14.5v4"/><rect x="16.5" y="8.5" width="5" height="10" rx="1.2" fill="var(--halo)"/><path d="M18.4 16.6h1.2"/>',
  exercise: '<path d="M6.5 7.5v9M17.5 7.5v9M3.5 10v4M20.5 10v4M6.5 12h11"/>',
  calendar: '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/><path d="M7.5 13h3M13.5 13h3M7.5 16.5h3"/>',
  sleep: '<path d="M19.5 14.6A8 8 0 0 1 9.4 4.5a8 8 0 1 0 10.1 10.1z"/>',
  not_recorded: '<circle cx="12" cy="12" r="8.5" stroke-dasharray="2.4 2.6"/><path d="M12 8v4.5l2.6 1.6"/>',
  // entertainment & social: a feed with a play button
  fun: '<rect x="3" y="4.5" width="18" height="15" rx="3"/><path d="M10 9.2v5.6l4.6-2.8z"/>',
  // focused work: a laptop with a code bracket
  focus: '<rect x="4.5" y="5" width="15" height="10" rx="1.5"/><path d="M2.5 18.5h19"/><path d="m10.3 8-2 2 2 2M13.7 8l2 2-2 2"/>',
  // screens at once (the stacking ratio): two screens, one in front of the other
  ratio: '<rect x="2.5" y="4" width="13" height="9.5" rx="1.6"/><rect x="8.5" y="9.5" width="13" height="9.5" rx="1.6" fill="var(--halo)"/>',
  // AI agents working for you: a sparkle
  ai: '<path d="M11 3.5 12.8 9l5.5 1.8-5.5 1.8L11 18l-1.8-5.4L3.7 10.8 9.2 9z"/><path d="M18.5 14.5l.8 2.1 2.2.8-2.2.8-.8 2.1-.8-2.1-2.1-.8 2.1-.8z"/>',
  // the longest stretch on one thing: a stopwatch
  single: '<circle cx="12" cy="13.5" r="7"/><path d="M12 13.5V10M10 3.5h4M12 3.5v3M18.2 7.3l1.3-1.3"/>',
  // communication: a speech bubble
  communication: '<path d="M6.5 4.5h11A2.5 2.5 0 0 1 20 7v6.5a2.5 2.5 0 0 1-2.5 2.5H11l-4.5 3.5V16A2.5 2.5 0 0 1 4 13.5V7a2.5 2.5 0 0 1 2.5-2.5z"/><path d="M8 8.8h8M8 11.8h5"/>',
  check: '<circle cx="12" cy="12" r="8.5"/><path d="m8.3 12.2 2.5 2.5 4.9-5.2"/>',
  up: '<path d="M12 19V5.5M6.5 11 12 5.5l5.5 5.5"/>',
  down: '<path d="M12 5v13.5M6.5 13 12 18.5l5.5-5.5"/>',
  // the menu
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4"/>',
  heart: '<path d="M12 19.5s-7.5-4.6-7.5-10A4.2 4.2 0 0 1 12 7a4.2 4.2 0 0 1 7.5 2.5c0 5.4-7.5 10-7.5 10z"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  battery: '<rect x="2.5" y="7" width="17" height="10" rx="2.2"/><path d="M21.5 10.5v3M6 10.5v3"/>',
  list: '<path d="M9 6.5h11M9 12h11M9 17.5h11"/><circle cx="4.75" cy="6.5" r=".9"/><circle cx="4.75" cy="12" r=".9"/><circle cx="4.75" cy="17.5" r=".9"/>',
  database: '<ellipse cx="12" cy="6" rx="7.5" ry="2.8"/><path d="M4.5 6v12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8V6M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8"/>',
  sidebar: '<rect x="3" y="4.5" width="18" height="15" rx="2.6"/><path d="M9 4.5v15"/>',
};
// The names icon() knows, in drawing order.
export const ICON_KEYS = Object.freeze(Object.keys(PATHS));
// The icon for key at size px (an unknown key draws the dashed clock of "not recorded").
export function icon(key, size = 20) { return svg(PATHS[key] || PATHS.not_recorded, size); }
// The colour each icon is drawn in: its data colour (ai: focus blue, work done for you), ink-3 for not recorded, ink-2 for the check and the two devices-at-once measures; the menu glyphs take the text colour.
export const COLOR = { sleep: "var(--c-sleep)", exercise: "var(--c-exercise)", calendar: "var(--c-event)", screen: "var(--c-focus)",
  focus: "var(--c-focus)", fun: "var(--c-fun)", communication: "var(--c-comms)", other: "var(--c-other)", not_recorded: "var(--ink-3)",
  ratio: "var(--ink-2)", single: "var(--ink-2)", ai: "var(--c-focus)", check: "var(--ink-2)" };
// The 12px glyphs inside a state chip: good = a tick, bad = an exclamation mark.
export const STATE_ICON = Object.freeze({
  good: `<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m2.5 6.3 2.3 2.3 4.7-5.1"/></svg>`,
  bad: `<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 2.6v4.2"/><circle cx="6" cy="9.3" r=".4" fill="currentColor"/></svg>`,
});
