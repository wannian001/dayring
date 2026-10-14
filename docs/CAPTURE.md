# Capture protocol (iPhone app ⇄ your computer)

The iPhone app reads Apple Health on the phone and sends it to `healthaio serve` on your own computer, over your home
network or Tailscale. Nothing goes through a cloud service. This file is the contract both sides are tested against;
`tests/fixtures/capture/*.json` hold example packages that the Python tests and the iPhone app's tests both read.

```
iPhone app ──HTTP on your network──▶ healthaio serve --lan ──▶ the same rules as `import apple-health` ──▶ CSV files
   │  HealthKit, read only                │ .healthaio/capture/landed/…   (every package, kept as sent)
   └─ panel tab: the dashboard ◀──────────┘ .healthaio/capture/receipts/… (what happened to it)
```

## Network and who may talk to the server

- `healthaio serve` listens on `127.0.0.1` only, as before. `healthaio serve --lan` listens on every interface but
  answers only private addresses (10/8, 172.16/12, 192.168/16, 169.254/16, fc00::/7, fe80::/10) and Tailscale
  (100.64/10). Any other source gets 403. Do not forward the port on your router.
- The `Host` header must be an IP address, `localhost`, a `.local` name or a `.ts.net` name (a DNS name pointed at
  your computer cannot read it from a web page).
- A request from this computer itself (loopback) needs no token, as before.
- A request from another device needs a token from pairing:
  - the **capture token** (`Authorization: Bearer …`) for every `/capture/v1/*` route except `hello` and `pair`;
  - the **read token** for the dashboard (`/`, its files and `/api/*`), as the cookie `healthaio_read=…` or as
    `Authorization: Bearer …`. The iPhone app puts it in its web view's cookie store; the page never sees the
    capture token.
- The server keeps only the SHA-256 of each token (`.healthaio/devices.json`). `healthaio devices revoke ID` (or
  `--all`) cuts a device off at once.
- Request bodies are JSON (`Content-Type: application/json`) and at most 8 MB. No CORS headers are ever sent, and a
  write that carries an `Origin` header is refused, so a web page cannot post to the server.

## Pairing

On the computer, `healthaio pair` (or **Pair iPhone…** in the Mac app) opens an 8-digit code for 10 minutes and
prints the addresses the phone can use and a link:

```
healthaio://pair?url=http%3A%2F%2F192.168.1.20%3A8790&code=48213907
```

The Mac app shows this link as a QR code; the iPhone camera opens it in the app. The code can also be typed by hand.
Five wrong codes close it. The server stores a salt and the code's SHA-256, never the code.

## Routes

All bodies are UTF-8 JSON. Errors are `{"error": "…"}` with a readable sentence.

| route | token | answer |
|---|---|---|
| `GET /capture/v1/hello` | none | `{"app":"healthaio","protocol":1,"version":"0.3.0","timezone":"Australia/Melbourne","kinds":["health"],"max_bytes":8388608}` |
| `POST /capture/v1/pair` | none | body `{"code":"48213907","device_name":"iPhone","device_id":"<uuid the app made>"}` → `{"device_id":"…","capture_token":"…","read_token":"…","server":{"version":"0.3.0","timezone":"…"}}`. 403 wrong code, 410 no code open. Tokens are returned only here, once. |
| `POST /capture/v1/packages` | capture | a package (below) → its receipt |
| `GET /capture/v1/packages/<id>` | capture | the receipt, or `{"package_id":"…","status":"not_found"}`. Asking never creates anything. |
| `GET /capture/v1/status` | capture | `{"version", "timezone", "device":{"id","name","paired_at"}, "latest":{"body_daily":"2026-10-13","workouts":…,"meals":…,"screen_sessions":…}, "last_package":{…receipt…}, "update":{…as /api/version…}, "iphone":{…as GET renew…}}` |
| `POST /capture/v1/renew` | capture | asks the computer to re-sign and reinstall the iPhone app (below): 202 `{"started":true}`, 409 already running, 503 `{"error":"…","reason":"no_xcode"|"no_project"|"no_team"|"not_macos"}` |
| `GET /capture/v1/renew` | capture | `{"can_renew":true,"reason":null,"running":false,"last":{"at","ok","expires_at","version","message"}}` |
| `GET /api/version` | read | `{"current":"0.3.0","latest":"0.3.1","update_available":true,"url":"…/releases/tag/v0.3.1","notes":"…","checked_at":"…","install":"git"|"pip"|"unknown","can_update":true}`; `latest` is `null` when the check is off or failed |
| `POST /api/update` | this computer's own page only | 202 `{"started":true}`: installs the latest version, then the server restarts itself |

## Packages

One package is one read of Apple Health over a window of days. Attribute names and values are the ones Apple's
`export.xml` uses, so the server feeds a package through exactly the code that reads an export: an export imported
by hand and the same days sent by the app give the same rows.

```json
{
  "schema": "healthaio-capture-v1",
  "package_id": "ios-2F1C0B9E-7A41-4C55-9D7B-2B0C3F6E5A10",
  "kind": "health",
  "created_at": "2026-10-13T21:05:11+11:00",
  "timezone": "Australia/Melbourne",
  "device": {"id": "<the app's random install id>", "name": "iPhone", "app_version": "0.3.0 (3)"},
  "window": {
    "start_date": "2026-10-11", "end_date": "2026-10-13",
    "query_start": "2026-10-10 18:00:00 +1100", "query_end": "2026-10-13 21:05:10 +1100",
    "read_completed_at": "2026-10-13 21:05:10 +1100"
  },
  "records": [
    {"type": "HKQuantityTypeIdentifierStepCount", "sourceName": "iPhone", "device": "iPhone", "unit": "count",
     "startDate": "2026-10-13 08:01:00 +1100", "endDate": "2026-10-13 08:09:00 +1100", "value": "812"},
    {"type": "HKCategoryTypeIdentifierSleepAnalysis", "sourceName": "Apple Watch", "device": "Watch",
     "startDate": "2026-10-12 23:40:00 +1100", "endDate": "2026-10-13 01:10:00 +1100",
     "value": "HKCategoryValueSleepAnalysisAsleepCore", "metadata": {"HKTimeZone": "Australia/Melbourne"}}
  ],
  "workouts": [
    {"workoutActivityType": "HKWorkoutActivityTypeRunning", "duration": "31.5", "durationUnit": "min",
     "sourceName": "Apple Watch", "device": "Watch",
     "startDate": "2026-10-12 07:00:00 +1100", "endDate": "2026-10-12 07:34:00 +1100",
     "events": [{"type": "HKWorkoutEventTypePause", "date": "2026-10-12 07:10:00 +1100"},
                {"type": "HKWorkoutEventTypeResume", "date": "2026-10-12 07:12:30 +1100"}],
     "statistics": [{"type": "HKQuantityTypeIdentifierActiveEnergyBurned", "sum": "286", "unit": "kcal"},
                    {"type": "HKQuantityTypeIdentifierHeartRate", "average": "148", "unit": "count/min"}]}
  ]
}
```

- `package_id` matches `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`. One package holds one `kind`; `health` is the only one so
  far.
- Times are `yyyy-MM-dd HH:mm:ss Z`, as in the export. Values may be strings or numbers.
- Record fields the server reads: `type`, `sourceName`, `device`, `unit`, `startDate`, `endDate`, `value`, and from
  `metadata` only `HKTimeZone`, `HKFoodType`, `HKFoodMeal` and `meal`. Anything else is dropped before the package is
  stored.
- Types the app reads: sleep analysis, steps, exercise minutes, resting heart rate, HRV (SDNN), VO2 max
  (`HKQuantityTypeIdentifierVO2Max`, the watch's cardio fitness estimate), body mass, active and resting energy,
  dietary energy, protein, carbohydrate, fat and fibre, and workouts; on iOS 18 and later also the workout effort
  scores, `HKQuantityTypeIdentifierWorkoutEffortScore` (the 1–10 rating you give a workout) and
  `HKQuantityTypeIdentifierEstimatedWorkoutEffortScore` (the watch's own estimate), each sample spanning its
  workout's start and end. Units: `count`, `min`, `count/min`, `ms`, `mL/min·kg` for VO2 max (the dot is U+00B7,
  as in the export), `kg`, `kcal`, `g`, and `appleEffortScore` (values 1–10) for the effort scores. Sleep values are
  the `HKCategoryValueSleepAnalysis…` names (InBed, AsleepUnspecified, Awake, AsleepCore, AsleepDeep, AsleepREM).
  The app also asks to read heart rate, because iOS hides a workout's average heart rate without it; heart-rate
  samples themselves are never read or sent.
- **No personal names.** Apple's own sources carry the name you gave your devices ("Sam's Apple Watch"). The app
  sends the product instead: `sourceName` "Apple Watch" or "iPhone", `device` "Watch" or "iPhone". Third-party app
  names (a food logger) are kept, since the merge rules need them.

### The window

- `start_date`…`end_date` are whole local days on the phone. Every type is read from `start_date` 00:00, except sleep,
  which is read from 18:00 the evening before (a night belongs to the day you wake up). `query_end` is the moment of
  the read.
- The server keeps only the `body_daily` rows dated inside the window, and only workouts and meals that start inside
  it. The day of the read is written with `complete = 0`.
- A window is at most 4 days. The app's normal read is the last 3 days; its "catch up 14 days" sends four or five
  packages of up to 4 days each.

### What the server does with a package

1. Checks the whole package (schema, id, kind, sizes, every record's fields). A package that fails is refused with
   400 and leaves nothing on disk.
2. Stores it once, exactly as it will be read: temporary file → `fsync` → `.healthaio/capture/landed/<date>/<id>.json`
   (create only). The same id with the same content returns the first receipt; the same id with other content
   gets 409.
3. Projects it into `body_daily.csv`, `workouts.csv` and `meals.csv` with the merge rules of `import apple-health`,
   holding `.healthaio/write.lock`, and writes the receipt last.

A receipt:

```json
{"ok": true, "package_id": "ios-…", "status": "projected", "landed_at": "2026-10-13T21:05:12+11:00",
 "projected_at": "2026-10-13T21:05:12+11:00", "rows": {"body_daily": 3, "workouts": 1, "meals": 0},
 "window": {"start_date": "2026-10-11", "end_date": "2026-10-13"}}
```

`status` is `landed` (stored, not yet in the tables), `projected` (in the tables) or `failed` (stored, but the rows
could not be written; `error` says why, and the next server start tries again).

### What the app does (so the two sides agree)

- On coming to the front (about one second later) it reads the last 3 days. It keeps only a fingerprint (SHA-256 of
  the canonical records) of the last read and does not send a read that is the same or empty.
- A package is frozen (id and exact bytes) in the app's outbox before it is posted. The app clears it only when the
  answer is 200, `ok` is true, the ids match and the status is `projected`. A timeout, 5xx or an unreadable answer is
  "unknown": the app asks `GET /capture/v1/packages/<id>` and re-sends the same bytes only when the server says
  `not_found`. It never makes a new package of a kind that still has one waiting.
- No background delivery: the app reads and sends while it is open.

## Signing and updates of the iPhone app

An app you build yourself with a free Apple ID runs for 7 days; then iOS will not open it until it is signed again.
(A paid developer account makes that one year.) The app and the computer share the job of keeping it alive:

- **On the phone**, the first time the app opens each day it checks three things: when its own signature runs out
  (read from the app's `embedded.mobileprovision`), whether GitHub has a newer release than the app, and the
  computer's `GET /capture/v1/status`. When the signature has two days or less left, or a newer version exists, it
  shows a banner and posts a local notification. It also schedules a notification for the day before the signature
  runs out, so the reminder comes even if the app is not opened.
- **On the computer**, `healthaio iphone renew` builds the app from this repository with Xcode
  (`ios/Local.xcconfig` holds your bundle id and team) and installs it on the paired iPhone with `devicectl` (cable
  or the same Wi-Fi). The banner's **Renew now** button asks the computer to do this (`POST /capture/v1/renew`), and
  the Mac app has the same item in its menu. Building needs the Mac to be logged in at the desktop: from an SSH
  session the keychain is locked and signing fails.
- Updating the computer first (`healthaio update`) and then renewing installs the new version of the app as well.
