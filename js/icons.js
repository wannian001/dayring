// dayring design kit: stroke icons, coloured by currentColor. Part of the kit (see docs/DESIGN_KIT.md).
// One per lane of the Time page and one per thing "what changed" can name, plus a check (a usual day) and
// the up / down arrows of the change badge. Same grid (24), stroke (1.8) and round joins throughout.
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
  // communication: a speech bubble
  communication: '<path d="M6.5 4.5h11A2.5 2.5 0 0 1 20 7v6.5a2.5 2.5 0 0 1-2.5 2.5H11l-4.5 3.5V16A2.5 2.5 0 0 1 4 13.5V7a2.5 2.5 0 0 1 2.5-2.5z"/><path d="M8 8.8h8M8 11.8h5"/>',
  check: '<circle cx="12" cy="12" r="8.5"/><path d="m8.3 12.2 2.5 2.5 4.9-5.2"/>',
  up: '<path d="M12 19V5.5M6.5 11 12 5.5l5.5 5.5"/>',
  down: '<path d="M12 5v13.5M6.5 13 12 18.5l5.5-5.5"/>',
};
// The names icon() knows, in drawing order.
export const ICON_KEYS = Object.freeze(Object.keys(PATHS));
// The icon for key at size px (an unknown key draws the dashed clock of "not recorded").
export function icon(key, size = 20) { return svg(PATHS[key] || PATHS.not_recorded, size); }
// The colour each icon is drawn in: its data colour, ink-3 for not recorded, ink-2 for the check.
export const COLOR = { sleep: "var(--c-sleep)", exercise: "var(--c-exercise)", calendar: "var(--c-event)", screen: "var(--c-focus)",
  focus: "var(--c-focus)", fun: "var(--c-fun)", communication: "var(--c-comms)", other: "var(--c-other)", not_recorded: "var(--ink-3)",
  check: "var(--ink-2)" };
// The 12px glyphs inside a state chip: good = a tick, bad = an exclamation mark.
export const STATE_ICON = Object.freeze({
  good: `<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m2.5 6.3 2.3 2.3 4.7-5.1"/></svg>`,
  bad: `<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 2.6v4.2"/><circle cx="6" cy="9.3" r=".4" fill="currentColor"/></svg>`,
});
