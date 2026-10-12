# Design notes

The look itself (tokens, components, charts, icons) is the design kit: [DESIGN_KIT.md](DESIGN_KIT.md), shown on the
gallery page `#kit`. This file is about what dayring's pages say and why.

## Who it is for

One person looking at their own data, usually in the morning and before bed. The page has to answer four
questions in this order: how am I today, what is on, where did yesterday go, what has tended to help.
Everything else is detail behind a "How this is worked out" fold.

## Layout

- **Summary before detail.** Each page opens with one sentence-sized verdict or one number, then the parts that
  produced it. On Today that is the day ring plus "Recovered as usual / below your normal".
- **The day ring** is the one distinctive element: a 24-hour clock with midnight at the top. Outer track = the
  sleep that ended today, middle track = today's calendar, inner bars = screen minutes per hour (stacked from the
  centre: focus, entertainment & social, communication, other; full length = 60 minutes). An accent hand marks now.
  Today's workouts are drawn on the calendar track in the exercise colour, slightly wider than a calendar block.
  Planned training blocks are left off the ring, so it shows the workout you did, not the one you planned.
- **Two columns on desktop, one on phones.** HTML order is the phone priority order; the desktop grid only places
  it. Cards in a column stack so no card stretches over empty space.
- Every chart is drawn at its real pixel width (redrawn on resize), so text never scales with the chart. The charts
  live in the design kit (`dayring/web/js/charts.js`); pages only map their data onto them.

## The Time page: one rule

The page answers "where did the time go, and what changed?". Every block on it (the sentence and icons at
the top, the daily-average tiles, the typical day, the last 30 days) uses the same rule:

- **Each activity from its own record, minute by minute.** Sleep = falling asleep to waking (`sleep_start` to
  `sleep_end`). Exercise = workouts with a start and an end (`workouts.csv`; a paused workout counts its minutes moving); a day known only by its daily
  `workout_min` adds to the totals but cannot be placed in the hours. Calendar = blocks of kind class, work,
  personal and other; planned training is left out because the workout itself counts. Screens = app sessions,
  counted once across devices.
- **Days are calendar days.** Every activity is cut at midnight, sleep included, so a night counts partly in
  each day (the Sleep page files the whole night under the morning you woke up instead). Workouts, screens
  and the calendar are in the configured timezone; Apple Health sleep times are in the zone you slept in, so
  on travel days the sleep lane can sit off the others by the time difference.
- **Lanes may overlap.** A lecture with the laptop open is both calendar and screens, so the activities can add
  up to more than 24 hours. Nothing is subtracted to make them fit.
- **Not recorded.** The minutes of the day that no record covers. It is a tile of its own, not shared out among
  the others.
- **What changed, not what was biggest.** Screens take the most waking time almost every day, so naming the
  biggest activity says nothing. The page names what changed against your normal instead, the same "you
  vs you" rule as every other page. The candidates are entertainment & social, focused work, communication,
  exercise, calendar time and sleep; the screen total is not one (its parts say what moved), nor are other
  screen time and not recorded.
  - *Normal for a day* = `stats.typical` over that activity's daily minutes in the 28 days before it (at
    least 10 days), counting only days whose record for it exists: a day without Screen Time is not a
    zero-screen day.
  - *Normal for the 7 days shown* = the middle half of your 7-day averages (`time.typical_week`): one
    average for the 7 days ending on each of the 28 days before the first shown day, each over the days
    with the record (at least 4 of the 7), and at least 10 such averages. The value is the shown days'
    daily average; an average resting on fewer than half of the shown days is shown but not compared. A
    band of single days would not do here: exercise three times a week or classes on weekdays put many
    single days at 0, so a week with no workout or no class at all would sit inside it, and the change
    would be measured from a daily median of 0.
  - *Score* = how far the value lies outside its band, in band widths: the distance past q1 or q3 divided
    by max(q3 − q1, the floor, 10% of the median), where the floor is 30 minutes for a single day and 15
    minutes a day for the 7-day average; 0 inside the band. Values are compared in whole minutes, as
    printed.
  - *A change* is a score of at least 1 (`STANDOUT_MIN`): at least one band width past the edge of
    normal. Inside the middle half every candidate would land outside about half the time, so with six of
    them nearly every day and every week would name something; one band width keeps the usual ups and
    downs quiet (measured on made-up usual habits: about 1 day in 20 names a change instead of 19 in 20).
    The floor keeps a habit that hardly moves from turning a few minutes into a change.
  - *The standout* is the change furthest from the middle of its normal in minutes (delta = value −
    median), ties going to the order above, so the sentence and the minutes printed with it always agree.
    No change: no standout.
  - *Tone* (green / red) only gives the direction, and only for a change: less entertainment, more focused
    work, more exercise and more sleep are better; communication and calendar time have none. A value
    outside the middle half but not one band width out reads "just above / just below normal", uncoloured.
  - The top shows the standout's icon in its colour with an up / down badge and one sentence ("Compared with
    your normal, the biggest change these 7 days: entertainment & social, 1h 12m more a day"), with chips for
    the other changes; with no change, a check and "These 7 days look like your normal". Each day cell shows
    that day's change (or a check for a usual day, or a dashed clock and "No normal yet" when nothing that
    day could be compared yet) and that day's screen total and workout minutes underneath.
  - The daily-average tiles (screens with their split, entertainment & social, focused work, communication,
    exercise, calendar, sleep, not recorded) are the 7-day averages, each with a state chip, a bullet against
    the band of 7-day averages and "normal x–y" (one value is written once, "usually none" when it is 0),
    like the Today tiles. There is one baseline for the whole page: nothing is compared with "the 7 days
    before".
- **A missing record is not zero.** Each activity is only counted on a day that has the record it needs, and
  is left out of its average otherwise (the tile says "6 of 7 days have a record"; the 30-day lanes draw ×):
  sleep needs the night that ended that morning and the one that started that evening; exercise needs a
  workout, a `workout_min` (0 = rest day), or a day between the first and last logged workout, and never
  counts on the day an Apple Health export was made (`complete = 0`); screens need screen sessions, and when
  Screen Time has stopped arriving its last day counts as cut off; calendar needs an events file. Not
  recorded is only worked out for days with both a night and screen time. When a record stops before the
  last day shown, the page says so. A day left out this way is left out of every later day's normal too.
- **Real minutes.** On the day the clocks go forward the skipped hour is not counted and the day is 23 hours;
  on the day they go back a record that runs through the repeated hour counts it twice and the day is 25.
- **Which days.** Whole days only (today is not over yet), and only days with a record of their own: screen
  time, or a `body_daily` row dated that day (the evening before the first night is not a day). The latest 7
  such days are shown; "Earlier" and "Later" step by 7 such days, and "Later" ends on the newest one, so a
  gap in the data never strands the stepper.

The Today page's screen card links here. Old `#attention` links open this page.

## The Drain page

The page answers "what has been quietly wearing me down this week?" with seven signals named the way physiology
and sleep research name them: resting heart rate (higher is worse), HRV (lower is worse), the time you fall
asleep (later is worse), sleep-timing spread (the standard deviation of each night's midpoint; larger is worse), screens in the
hour before sleep, entertainment & social, and app switches per screen hour. Each row has one line on why it
matters, and says when the evidence is softer (entertainment).

- **Two judgements, never mixed.** Against your normal: the last 7 days' average against the middle half of the
  28 days before (sleep-timing spread against the range of the four 7-night blocks before, because a spread only
  exists over a run of nights). Against your plan, only where `dayring.toml` sets one: falling asleep against
  `plan.sleep.bedtime`, entertainment & social against `plan.screen.entertainment_max_hours`. A habit that was
  already bad reads as "within normal" and still shows up against the plan.
- **No total score.** The signals have different units and different strength of evidence.
- **Missing is missing.** Each signal uses only days its own record covers in full; fewer than 4 of the 7 days and
  the row says so instead of guessing. A screen day counts only when it is whole: not today, and not the last day
  of a Screen Time import that has stopped arriving (the same rule the Time page uses), since that day was most
  likely cut off part-way. Screens in the hour before sleep need a screen record for every day that hour touches.
  When no signal can be set against your normal, the page says so instead of "nothing got worse", and a plan that
  could not be checked is named as such, never counted as within plan.
- **App switches** count each session once, even when the same session was imported under two device names, so
  they agree with screen hours, which count each minute once across devices.
- **Row anatomy.** The design kit's `rangeStrip` and `trendLine`. Grey band = your normal, tick = its median, dot = these 7 days, dashed tick = the plan (the
  legend draws each key the way the row draws it); on the right the value, its normal, the state and the plan
  chips; the last column is eight weekly averages, for slow signals like HRV. All rows share one set of columns,
  so the strips line up down the card. At 900 px and narrower the strip and the weekly line get rows of their
  own and the weekly line carries its own label; on phones the value moves under the name.
- **Stepping.** Earlier / Later move 7 days at a time; Later from a window off the 7-day grid (opened from a past
  day on Today) ends on the latest window. Today's card links to the Drain window it summarises.
- The week stack-up check (at least 3 nights under 7 hours and at least 3 training days) moved here from Today;
  Today keeps a two-line summary that links to this page.

## Menu

Today · Week · Body (Weight, Sleep) · Time · Drain · Review · Data. A menu item that holds more than one page shows
a small switch under the menu, above the page title; the menu item stays highlighted on both, and each page is
titled by its own tab (Weight, Sleep).

## Colour

- The colour rules are the design kit's ([DESIGN_KIT.md](DESIGN_KIT.md#colour-rules)); the values are in
  `dayring/web/css/tokens.css` and on the gallery page (`#kit`).
- Two looks, no theme picker (`dayring/web/css/tokens.css`): **light mode** uses graphite neutrals with a blue
  accent, **dark mode** uses dusk neutrals (blue-black) with a violet accent. The page follows the system setting;
  the moon button overrides it and remembers the choice (a shared `?mode=` link sets the starting look; a click
  wins over it and drops it from the address). The chosen part of a switch (Weight / Sleep, the outcome switch on
  Today) has its own raised step in each look (`--seg-on`), lighter than its track in dark mode.
- Data colours are the same in both modes (each mode has its own step of the same hue):

  | thing | token | light | dark |
  |---|---|---|---|
  | focus (work + learning) | `--c-focus` | `#2a78d6` | `#3987e5` |
  | entertainment & social | `--c-fun` | `#eb6834` | `#d95926` |
  | communication | `--c-comms` | `#1baf7a` | `#199e70` |
  | other | `--c-other` | `#a3a9b5` | `#5d6474` |
  | sleep (own ring track) | `--c-sleep` | `#4a3aa7` | `#9085e9` |
  | exercise (workouts) | `--c-exercise` | `#bf3fa6` | `#cb4db2` |
  | exercise as text | `--c-exercise-ink` | `#a8318f` | `#de78c8` |

  Focus / entertainment / communication pass the colour-vision checks in both modes for every pair
  (worst CVD ΔE 9.2). Sleep is too close to focus for protanopia, so it is never placed next to it: it has its
  own track on the ring, its own lane on the Time page and its own chart on the Sleep page.
  Exercise was checked against every colour above, sleep included, in both modes: worst CVD ΔE 8.7 in light and
  8.4 in dark (both against sleep), at least 9.3 against the screen colours, and at least 3:1 contrast on every
  mode's surface. So exercise may sit next to sleep: they are neighbouring lanes on the Time page and
  neighbouring tracks on the ring. Exercise minutes written as text use the darker (light mode) or lighter
  (dark mode) text step, at least 5.5:1 on every mode's surface. Calendar blocks are drawn in ink, not a
  data colour.
- Status colours (good / watch / off) are reserved for states and always come with a word or icon.
- Charts are otherwise ink and grey. The "normal" band is a faint fill; dashed lines mean a plan or a limit.

## Charts and what they encode

| chart | encodes |
|---|---|
| tile sparkline | 14 days, grey band = your normal on the last day, × = no record, end dot coloured only if out of normal |
| bullet | today's value against the band; tick = median |
| interval | difference after doing vs not doing, 95% interval, against zero |
| weight corridor | dots = weigh-ins, line = 7-day average, shaded corridor = the plan's two weekly rates, dashed = target |
| sleep windows | one bar per night from falling asleep to waking, on an 20:00–14:00 axis; ink tick with a surface halo, drawn over the bar = that morning's alarm |
| alarm ladder | the alarm as a step line (earlier = higher), dots = actual wake (green on time, red late) |
| lanes | one row per activity (sleep, exercise, calendar, screens; the daily-average tiles use the same order), one column per hour or per day; on the 30-day lanes each row has its own scale, written under its label (the hour lanes all run to 60 minutes); screens stack entertainment on the baseline so days compare against the dashed limit, whose label also sits under the row's name; × = no record that day, shaded = the 7 days above |
| activity icons | one stroke icon per lane (screen, exercise, calendar, sleep, a dashed clock for not recorded) and per thing "what changed" can name (entertainment & social = a feed with a play button, focused work = a laptop with a code bracket, communication = a speech bubble), drawn in its colour; a change carries an up / down badge in its tone, a usual day a check, a day with no normal yet a dashed clock |
| week load | `blockColumns`: one column per week, one block per deadline, height = share of grade, amber = due within 3 days (its label in `--on-watch`), faded = done |
| arrivals | one cell per day per stream: has data / partial / nothing |

## Words

- One word, one source. "Exercise / 运动" is logged workouts everywhere (Time, Review, the ring); Apple's
  Exercise-ring minutes on Today are "Exercise ring / 锻炼圆环". Workout types and device names are
  translated; app names and anything you typed stay as written.

- The server returns numbers; the browser writes sentences from `i18n.js`. Add a language by adding a dictionary.
- Labels name what a person recognises ("Entertainment in the hour before sleep"), not how it is stored.
- Page names say what the page measures. The page about the day's hours is **Time** (时间), titled "Where your
  time went" (时间去向), not "Attention": it holds sleep and workouts too, and what it counts is time.
- No scores out of 100, no streaks, no badges. The Review page only lays facts side by side.

## Accessibility

- Every chart has `role="img"` and a label, and every mark with a tooltip is also reachable as text elsewhere on
  the page (the tile values, the table on Review, the sentence under each interval for screen readers).
- Activity icons are hidden from screen readers; the tile names and the sentence at the top of the Time page
  say the same thing in words.
- Focus is visible; motion respects `prefers-reduced-motion`; nothing scrolls sideways at 320 px.
