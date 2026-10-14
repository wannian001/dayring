# Importers

Importers turn exports from other apps into the CSV tables described in
[DATA_FORMAT.md](DATA_FORMAT.md). They only read the file you give them and only write
into your data directory (the `data_dir` in `healthaio.toml`). Nothing is uploaded.

| command | source | writes |
|---|---|---|
| `healthaio import apple-health PATH` | Apple Health `export.zip`, `export.xml` or the unzipped folder | `body_daily.csv`, `workouts.csv`, `meals.csv` |
| `healthaio import ics PATH [--kind K]` | any iCalendar `.ics` file | `events.csv` |
| `healthaio import macos-screentime [--days N]` | macOS Screen Time data on this Mac (experimental) | `screen_sessions.csv` |
| `healthaio import csv TABLE PATH --map ...` | any CSV with your own column names | any table |

Each command prints how many rows it imported, their date range, the file it wrote and any
problems (with line numbers where there is a line to point at). Importing again is safe:
every importer merges with what is already there, as described below.

Run `healthaio check` afterwards to see the tables the pages will read.

---

## Apple Health

### Export from your iPhone

1. Open the **Health** app and tap your picture or initials (top right).
2. Scroll down and tap **Export All Health Data**, then **Export**. This can take several
   minutes and the file can be large (hundreds of MB to several GB zipped).
3. In the share sheet, AirDrop it to your Mac or choose **Save to Files**.
4. Run:

   ```sh
   python -m healthaio import apple-health ~/Downloads/export.zip
   ```

The zip is read in place; there is no need to unzip it. The file is streamed, so even a
multi-gigabyte export needs little memory.

### Or let the iPhone app send it

The iPhone app ([ios/README.md](../ios/README.md)) reads the same records on the phone and sends the
last 3 days to `healthaio serve --lan` each time you open it. The server turns each package back into
export XML and reads it with this importer, so the rows and every rule below are the same; only the
days in the package's window are written. The protocol is [CAPTURE.md](CAPTURE.md). An export is still
the way to bring in years of history at once.

### What it fills in

`sleep_min`, `in_bed_min`, `sleep_start`, `sleep_end`, `hrv_ms` (SDNN), `resting_hr`, `vo2max` (the day's
VO2 max estimates averaged; the watch makes one only on some outdoor walks, runs and hikes), `steps`,
`exercise_min`, `workout_min`, `workout_type`, `active_kcal`, `basal_kcal`, `weight_kg` and `complete` in
`body_daily.csv`; one row per workout in `workouts.csv` with `start`, `end`, `type`, `source`, `kcal`,
`avg_hr`, `effort` and `effort_source`; and one row per meal in `meals.csv`, from what food-logging apps write into Health.

How the numbers are made:

- **Time zones.** Every time in the export is written with the UTC offset the phone had *when
  you exported*, not when the record was made. Records that carry the `HKTimeZone` metadata are
  converted to that zone, so a night abroad is filed under the day you woke up *there*; other
  records use the `timezone` in `healthaio.toml`. `sleep_start` and `sleep_end` are written in the
  zone you slept in; workout times in `workouts.csv` are written in the configured timezone, like
  screen time and the calendar (see below).
- **Sleep** is filed under the day you woke up. Sleep records closer than 60 minutes apart form
  one session; the longest session of a wake-up day is its main sleep (naps are not added).
  When the watch and the phone (or a sleep app) both recorded the same night, only the watch
  is used for asleep minutes, so the night is not counted twice. `sleep_start` and `sleep_end`
  are the first and last asleep moments of the main sleep.
- **Steps, exercise minutes and energy burned.** The watch and the phone both count the same walk. The watch
  is taken first; another source only counts for the part of its time span the watch did not
  record (pro rata). Priority: Apple Watch, then other apps and wearables, then iPhone. The same rule makes
  `active_kcal` (the Move ring's active energy) and `basal_kcal` (resting energy), kJ converted to kcal. The Food
  page adds the two to set what you burned against what you logged.
- **HRV** and **resting heart rate** are daily means; **weight** is the last reading of the day
  (pounds and stones are converted to kg).
- **Workouts.** Durations are summed per day, but a workout that overlaps one already counted by
  more than half (the same run saved by the watch and by a running app) counts once.
  `workout_type` is the longest workout's type in plain words (`strength training`, `running`).
  A day after your first logged workout that has data but no workout gets `workout_min = 0`
  (rest day); days before that stay empty (unknown).
- **Workouts with their times** (`workouts.csv`). Apple Fitness and Workout app sessions, and
  those of any app that saves workouts to Health. `type` is the plain-words type (`workout` when
  the export names none), and `source` is the name of the app or device that recorded it, as the
  export gives it (usually your watch's name).
  - *Pauses.* A workout you paused (or that the watch auto-paused) is written as one row per
    stretch of moving, split at its pause and resume events, so the rows add up to the workout's
    duration as Apple Fitness shows it and as `workout_min` counts it. When the export has no
    pause events but the duration is clearly shorter than start to end, the row runs from the
    start for the duration. The Time page lists the stretches of one workout as one.
  - *Times.* `start` and `end` are rounded to the minute and written in the configured timezone,
    so a workout lines up with your screen time and calendar on the Time page even when you
    travel. (`body_daily` still files the workout under the day it started where you were.) The
    end is always after the start: a stretch under 30 seconds is left out, and one that runs
    through the hour the clocks go back keeps its real length.
  - *Copies.* The same workout saved by two apps is written once, by the same rule as above,
    compared on the real (UTC) times: a workout that overlaps a kept one by more than half of
    the shorter of the two is a copy. The copy from the more trusted source is kept (Apple Watch,
    then other apps, then iPhone); between equally trusted copies, the longer one.
  - *Odd dates.* Workouts dated before 2000 (exports carry epoch-0 junk) or after the export are
    left out; the summary says how many.
  - `effort` is how hard the workout was on Apple's 1–10 scale (iOS 18 and later): your own rating in the Fitness
    or Workout app (`HKQuantityTypeIdentifierWorkoutEffortScore`) when there is one, otherwise the watch's
    estimate (`HKQuantityTypeIdentifierEstimatedWorkoutEffortScore`); `effort_source` says `rated` or
    `estimated`. Apple keeps an effort as a sample spanning the workout, so it is matched to the workout that
    starts within two minutes of it or that it covers for at least half. The Recovery page multiplies it by
    the minutes for the training load.
  - `kcal` is the workout's active energy (`ActiveEnergyBurned`, kJ converted), on the first
    stretch. `avg_hr` is the workout's average heart rate when its statistics hold one (newer exports),
    on every stretch. The day ring places exercise in the day from these rows; `workout_min` stays the
    daily total.
- **Meals** (`meals.csv`). Food-logging apps (MyFitnessPal, Lose It!, Cronometer and others, once you allow them to
  write to Health) save what you ate as dietary records: energy, protein, carbohydrate, fat and fibre, each stamped
  with the time of the meal.
  - *One meal.* Records that start in the same minute are one meal. When two apps wrote the same minute, the one with
    more energy is kept, so one meal is never counted twice.
  - *Which meal.* From a `meal` (or `HKFoodMeal`) metadata entry when the app wrote one, otherwise from the clock:
    before 10:30 breakfast, before 15:00 lunch, 17:00 to 21:30 dinner, anything else a snack. The Food page counts a
    day once two main meals are logged.
  - *Units and names.* kJ become kcal, mg become g. `title` joins up to three `HKFoodType` names; `source` is the
    app's name. Times are written in the configured timezone, like workouts.
- **`complete`** is `0` for the day you exported (it was not over yet), `1` for all other days.

### Re-importing

In `body_daily.csv`, dates that are not in the new export are kept. For a date in the export,
every column the export has a value for is overwritten; a cell the export has nothing for keeps
its old value. So `waist_cm`, or a weight you typed on a day without a scale reading, survives a
re-import.
Lines of the old file whose date does not parse are kept at the end untouched (the Data page
shows them so you can fix them). Columns that are not in the schema are not kept.

`workouts.csv` works differently, because an export holds each source's whole workout history:
existing rows from a source that appears in the export (its `sourceName`, e.g. your watch) and
that start between the export's first and last workout are replaced by the export's workouts.
Rows from any other source (typed by hand, mapped from Garmin or Strava with `healthaio import
csv`) are kept, unless a row overlaps an imported workout by more than half of the shorter of the
two: then it is the same workout and the copy is removed. Rows of the export's sources outside
its range are kept too. The summary says how many rows were replaced, removed as copies and kept.
An export without workouts leaves the file as it is.

`meals.csv` follows the same idea: rows from a food app that is in the export and that fall between the export's
first and last meal are replaced; a meal you typed by hand, or mapped from another app's CSV, is kept.

### Limitations

- Only the columns above. Heart rate through the day, VO2 max, stand hours, water, caffeine and sleep stages are
  not imported (a workout's own active energy and average heart rate are, as `kcal` and `avg_hr`).
- Meals are only as complete as your food log. A day you did not log is left out, never read as zero.
- HRV is Apple's SDNN. If you also keep RMSSD from another app, keep it in a separate file:
  `hrv_ms` must hold one kind.
- A source is recognised as a watch or a phone by its name or device (`Watch`, `iPhone`). A
  watch you renamed to something without "Watch" in it may be treated as an "other" source.
- Steps, HRV and the other daily values use the configured timezone unless the record has
  `HKTimeZone` (most of them do not), so on travel days they follow your home calendar day.
- Exports with broken XML (rare, usually a truncated file) stop with a parse error; export again.

---

## Calendars (.ics)

```sh
python -m healthaio import ics ~/Downloads/timetable.ics
python -m healthaio import ics ~/Downloads/gym.ics --kind training
```

### Getting an .ics file

Health AIO reads files, not URLs: download the file first.

- **Google Calendar** (web): *Settings* > *Import & export* > *Export* downloads a zip with one
  `.ics` per calendar. For a single calendar: *Settings* > the calendar under *Settings for my
  calendars* > *Integrate calendar* > *Secret address in iCal format*, then open that address
  in a browser to download it. Treat the secret address like a password.
- **Outlook / Microsoft 365** (web): *Settings* > *Calendar* > *Shared calendars* > *Publish a
  calendar*, choose the calendar and *Can view all details*, then download the ICS link.
  Classic Outlook for Windows: *File* > *Save Calendar*.
- **Apple Calendar** (Mac): select the calendar in the sidebar, then *File* > *Export* > *Export...*.
- **A university timetable**: most timetable systems have an *Export*, *Subscribe* or *Add to
  calendar* button that gives an `.ics` file or link. Download the file from that link. If the
  only option is "subscribe", add it to Google or Apple Calendar first and export from there.

### What it handles

- `DTSTART`/`DTEND` in UTC (`...Z`), with `TZID=` (IANA names such as `Australia/Melbourne`, the
  Windows names Outlook writes such as `AUS Eastern Standard Time`, or a `VTIMEZONE` that names
  its location), or floating times (read in your configured timezone). All times are written in
  your configured timezone.
- `DURATION` instead of `DTEND`.
- Repeating events: `RRULE` with `FREQ=DAILY` or `FREQ=WEEKLY`, `INTERVAL`, `COUNT`, `UNTIL`,
  `BYDAY` and `WKST`, plus `RDATE` and `EXDATE`. Repeats keep their wall-clock time across a
  daylight-saving change.
- Moved or cancelled single instances (`RECURRENCE-ID`), and cancelled events (`STATUS:CANCELLED`).
- Only events overlapping the window are written: 180 days back to 180 days ahead by default
  (`--days-back N`, `--days-ahead N`).
- **All-day events are skipped** because they are not time blocks. `--all-day` keeps them as
  00:00-23:59 rows (a multi-day event runs from its first day 00:00 to its last day 23:59).

### Kinds

`kind` is chosen from the title, matching whole words (an optional plural "s" is allowed):

| kind | words |
|---|---|
| `class` | lecture, lec, tutorial, tut, workshop, practical, prac, seminar, class, lab, laboratory |
| `training` | gym, run, running, workout, training |
| `other` | anything else |

`--kind K` sets one kind (`class`, `work`, `training`, `personal`, `other`) for every event in the
file, which is the easiest way to import, say, a work roster or a gym booking calendar.

### Re-importing

Re-importing a calendar replaces its events inside the window: an existing row in the window
whose title also appears in the file is removed before the file's events are written. Rows
outside the window and rows with titles the file does not have (another calendar, rows typed by
hand) are kept. An event you deleted from a calendar with a one-off title stays until you
delete the row.

### Limitations

- `FREQ=MONTHLY` and `FREQ=YEARLY` are not expanded: the first instance is kept and a problem
  is reported. `BYMONTH`, `BYMONTHDAY`, `BYSETPOS` and `RANGE=THISANDFUTURE` are ignored.
- The rules inside a `VTIMEZONE` are not computed. A `TZID` that is neither an IANA name, a
  known Windows name nor a VTIMEZONE with `X-LIC-LOCATION` is read with the fixed offset in its
  label (for example `(UTC+10:00) Canberra, Melbourne, Sydney`, daylight saving ignored) or as
  your configured timezone; the summary says which.
- Times are kept to the minute; attendees, descriptions and alarms are not imported.

---

## macOS Screen Time (experimental)

```sh
python -m healthaio import macos-screentime            # last 28 days
python -m healthaio import macos-screentime --days 7 --device laptop
```

This reads the foreground-app record that Screen Time itself is built on (Apple's "Biome"
`App.InFocus` stream in `~/Library/Biome/streams/restricted/`). The format is undocumented
and may change with a macOS update; the importer was checked on macOS 27.

### Permission

The folder is protected. The app you run the command in (Terminal, iTerm, VS Code, ...) needs
**Full Disk Access**: *System Settings* > *Privacy & Security* > *Full Disk Access*, turn it on
for that app, quit and reopen it, then run the import again. Without it the importer stops with
a message saying exactly this; it never writes an empty table.

Better: give Full Disk Access to the **Health AIO Mac app** ([mac/README.md](../mac/README.md))
instead of your terminal. It runs `healthaio collect` every 2 hours, and the import inherits the
app's permission, so neither your terminal nor Python needs it. Since Biome keeps only about four
weeks, that also means no gap is ever lost.

### iPhone and iPad

If *Screen Time* > *Share across devices* is on, your iPhone and iPad send their records to
this Mac, and they are imported too. Devices are named `laptop` / `desktop` (this Mac; override
with `--device`), `phone`, `tablet` and `mac` (another Mac), from Biome's own device list. A
second device of the same kind becomes `phone-2`, and so on. Put the names in the order you
want in `[devices] priority` in `healthaio.toml`. If you renamed a computer, list it in
`[devices] computers` too, so the Time page's devices-at-once card can tell an AI agent left
working on it (an app in `[devices] agent_apps`) from you.

### How sessions are built

- A session runs from an app coming to the front until it leaves or another app comes to the
  front. The lock screen, login window and system overlays are not counted.
- A session is capped at 3 hours. On a Mac it is capped at 45 minutes unless the app is
  entertainment, because a Mac left with a window open looks the same as one in use.
- The last session has no end yet and is left for the next import.
- Times are rounded to the nearest minute; sessions shorter than about 30 seconds disappear,
  and touching sessions of the same app are joined.

### Categories

`work`, `learning`, `communication`, `entertainment`, `social` or `other`, from
`healthaio/importers/screen_categories.json`, which lists common apps (by bundle id), app names and
websites. To change or add entries, put a `screen_categories.json` with the same shape in your
data directory; your entries win:

```json
{
  "apps": {
    "com.apple.Safari": "learning",
    "com.example.MyEditor": {"name": "My Editor", "category": "work"}
  },
  "names": {"My Game": "entertainment"},
  "domains": {"intranet.example.edu": "learning"},
  "ignore": ["com.example.MenuBarHelper"]
}
```

### Re-importing

For each device in the import, existing rows from that device's first imported session onward
are replaced. Older rows (which Biome may no longer have) and rows of other devices are kept.

### Limitations

- macOS only; Biome keeps about four weeks, so import at least every few weeks.
- There is no idle signal: time with an app in front counts as use (within the caps above).
- A browser counts as the browser (`other`), not per website.
- Device kinds are inferred from Biome's device list; an old or unknown device is `other`.
- Older Macs that store the stream in the previous file format (SEGB v1) are reported, not read.
- Times use your configured timezone, also for days you spent elsewhere.

## Any CSV (column mapping)

```sh
python -m healthaio import csv body_daily weights.csv --map 'Date=date,Weight (kg)=weight_kg'
python -m healthaio import csv body_daily scale.csv --map 'Day=date,Kilos=weight_kg' --date-format '%d/%m/%Y'
python -m healthaio import csv screen_sessions activitywatch.csv --map 'timestamp=start'
python -m healthaio import csv workouts my-runs.csv --map 'Began=start,Finished=end,Sport=type'
python -m healthaio import csv meals food-log.csv --map 'Date=time,Meal=meal,Calories=kcal,Protein (g)=protein_g'
```

A food app's CSV export usually has one row per meal (or per food) with a date but no clock time. Map the date to
`time`: a time of exactly 00:00 is read as "a date without a time", so the meal counts for its own day and stays out
of the last-meal timing. `meal` must be one of `breakfast`, `lunch`, `dinner`, `snack`, `drink` (any case).

- `--map 'Source=column,...'` renames your columns to the schema's (see `healthaio schema`).
  Repeat `--map` as often as you like. Columns already named like the schema (any case) need
  no mapping; other columns are ignored and listed in the summary.
- Every cell is checked against the schema (type, allowed values, plausible range). A row with a
  bad cell is skipped and reported as `line N: 'Source' -> column: 'value': reason`; the other
  rows are imported.
- `--date-format` / `--datetime-format` read dates in another layout (Python `strptime` codes);
  ISO dates are accepted either way. The delimiter (comma, semicolon, tab, pipe) is detected, or
  set it with `--delimiter`.
- For `screen_sessions` without a category column, the category comes from
  `screen_categories.json` by app name or website.
- Rows replace existing rows with the same key (for example the same `date` in `body_daily`);
  other rows are kept. `--replace` rewrites the table with only this file's rows.

### Limitations

- Numbers must use a dot as the decimal separator (`74.8`, not `74,8`) and carry no units.
- No unit conversion: map a column only if it is already in the schema's unit.
