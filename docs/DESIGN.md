# Design notes

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
- Every chart is drawn at its real pixel width (redrawn on resize), so text never scales with the chart.

## The Time page: one rule

The page answers "where did the time go, and what changed?". Every block on it (the sentence and icons at
the top, the per-day tiles, the typical day, the last 30 days) uses the same rule:

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
  biggest activity says nothing. The page names what moved furthest from your normal instead, the same "you
  vs you" rule as every other page. The candidates are entertainment & social, focused work, communication,
  exercise, calendar time and sleep; the screen total is not one (its parts say what moved), nor are other
  screen time and not recorded.
  - *Normal* for an activity on a day = `stats.typical` over that activity's daily minutes in the 28 days
    before it (at least 10 days), counting only days whose record for it exists: a day without Screen Time
    is not a zero-screen day. For the 7 days shown, the value is their daily average and the normal is the
    28 days before the first of them; an average resting on fewer than half of the days is shown but not
    compared.
  - *Score* = how far the value lies outside the band, divided by max(q3 − q1, 15 minutes, 10% of the
    median), so a few minutes outside a very steady habit do not outrank a real change; 0 inside the band.
    The standout is the highest score above 0, ties going to the order above. Its change is value − median.
  - *Tone* (green / red) only gives the direction: less entertainment, more focused work, more exercise and
    more sleep are better; communication and calendar time have none.
  - The top shows the standout's icon in its colour with an up / down badge and one sentence ("Compared with
    your normal, the biggest change these 7 days: entertainment & social, 1h 12m more a day"), with chips for
    the other candidates outside normal; when nothing is outside, a check and "These 7 days look like your
    normal". Each day cell shows that day's standout (or a check for a usual day) with its change, and that
    day's screen total and workout minutes underneath.
  - The tiles (screens with their split, entertainment & social, focused work, exercise, calendar, sleep,
    not recorded) are the 7-day averages, each with a state chip, a bullet against the band and "normal
    x–y", like the Today tiles. There is one baseline for the whole page: nothing is compared with "the 7
    days before".
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

## Colour

- Themes (`dayring/web/css/tokens.css`) change only neutrals and the UI accent: **dusk** (blue-black / violet
  accent), **graphite** (neutral / blue accent), **celadon** (green-grey / jade accent). Each has its own light
  and dark steps.
- Data colours never change between themes:

  | thing | light | dark |
  |---|---|---|
  | focus (work + learning) | `#2a78d6` | `#3987e5` |
  | entertainment & social | `#eb6834` | `#d95926` |
  | communication | `#1baf7a` | `#199e70` |
  | other | `#a3a9b5` | `#5d6474` |
  | sleep (own ring track) | `#4a3aa7` | `#9085e9` |
  | exercise (workouts) | `#bf3fa6` | `#cb4db2` |
  | exercise as text | `#a8318f` | `#de78c8` |

  Focus / entertainment / communication pass the colour-vision checks in both modes for every pair
  (worst CVD ΔE 9.2). Sleep is too close to focus for protanopia, so it is never placed next to it: it has its
  own track on the ring, its own lane on the Time page and its own chart on the Sleep page.
  Exercise was checked against every colour above, sleep included, in both modes: worst CVD ΔE 8.7 in light and
  8.4 in dark (both against sleep), at least 9.3 against the screen colours, and at least 3:1 contrast on every
  theme's surface. So exercise may sit next to sleep: they are neighbouring lanes on the Time page and
  neighbouring tracks on the ring. Exercise minutes written as text use the darker (light mode) or lighter
  (dark mode) text step, at least 5.5:1 on every theme's surface. Calendar blocks are drawn in ink, not a
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
| sleep windows | one bar per night from falling asleep to waking, on an 20:00–14:00 axis; accent tick = that morning's alarm |
| alarm ladder | the alarm as a step line (earlier = higher), dots = actual wake (green on time, red late) |
| lanes | one row per activity (sleep, exercise, calendar, screens; the per-day tiles use the same order), one column per hour or per day; on the 30-day lanes each row has its own scale, written under its label (the hour lanes all run to 60 minutes); screens stack entertainment on the baseline so days compare against the dashed limit, whose label also sits under the row's name; × = no record that day, shaded = the 7 days above |
| activity icons | one stroke icon per lane (screen, exercise, calendar, sleep, a dashed clock for not recorded) and per thing "what changed" can name (entertainment & social = a feed with a play button, focused work = a laptop with a code bracket, communication = a speech bubble), drawn in its colour; a change carries an up / down badge in its tone, a usual day a check |
| week load | one column per week, one block per deadline, height = share of grade, amber = due within 3 days |
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
