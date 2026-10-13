"""What the Time and Review pages do when a record is missing, late or odd.

Rules under test:
- a day without the record an activity needs shows None for that activity (never 0), is left out of
  that activity's average, and the page says which record stopped;
- only days with a record of their own are shown (not the evening before the first night);
- "Earlier" and "Later" step by days with records and never loop or dead-end;
- the days the clocks change are 23 and 25 hours long, minute by minute;
- Review's workout minutes use the same rule.
"""
import shutil
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path

from healthaio.config import Config
from healthaio.context import Context
from healthaio.modules import review, static_params
from healthaio.modules import time as time_page
from healthaio.store import write_table

TZ = "Australia/Melbourne"


def at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm))


def nights(first: date, last: date, **extra):
    """A body row per day with a 23:00 -> 07:00 night (480 minutes) ending that morning."""
    out, d = [], first
    while d <= last:
        out.append({"date": d, "sleep_min": 480, "sleep_start": at(d - timedelta(days=1), 23), "sleep_end": at(d, 7),
                    "workout_min": 0, "complete": True, **extra})
        d += timedelta(days=1)
    return out


def screens(first: date, last: date, minutes: int = 480, category: str = "work"):
    out, d = [], first
    while d <= last:
        out.append({"start": at(d, 9), "end": at(d, 9) + timedelta(minutes=minutes), "device": "laptop",
                    "app": "Docs", "category": category})
        d += timedelta(days=1)
    return out


class Folder(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-cov-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def context(self, now: datetime, **tables) -> Context:
        data = self.tmp / "data"
        data.mkdir(exist_ok=True)
        for name, rows in tables.items():
            write_table(data, name, rows)
        return Context(Config(root=self.tmp, data_dir=data, timezone=TZ, devices=["phone", "laptop"]), now=now)


class MissingRecords(Folder):
    def test_screen_import_behind_the_watch(self):
        # sleep and workouts run to 12 Oct, Screen Time stops on 5 Oct
        workouts = [{"start": at(date(2026, 10, d), 17), "end": at(date(2026, 10, d), 17, 45), "type": "running",
                     "source": "Apple Watch"} for d in range(1, 12)]
        ctx = self.context(at(date(2026, 10, 12), 18, 40),
                           body_daily=nights(date(2026, 9, 20), date(2026, 10, 12)),
                           screen_sessions=screens(date(2026, 9, 20), date(2026, 10, 5)), workouts=workouts)
        p = time_page.build(ctx)
        span = p["span"]
        self.assertEqual((span["from"], span["to"]), ("2026-10-05", "2026-10-11"))
        # the stream's last day (5 Oct) was probably cut off by the import, so no day here has whole screen time
        self.assertEqual(span["known"]["screen"], 0)
        self.assertIsNone(span["avg"]["screen"])  # not 480/7 = 69 minutes, which would read as a big drop
        self.assertAlmostEqual(time_page.build(ctx, p["prev"])["span"]["avg"]["screen"], 480)  # the week before had it
        # the note names the last whole day (4 Oct), the same day the numbers stop counting
        self.assertEqual(span["stale"], [{"activity": "screen", "last": "2026-10-04"}])
        for d in span["days"]:
            self.assertIsNone(d["totals"]["screen"], d["date"])
            self.assertIsNone(d["totals"]["not_recorded"], d["date"])
            if d["standout"]:  # unknown screens are never "less fun" or "less focus"
                self.assertNotIn(d["standout"]["key"], ("fun", "focus", "communication"), d["date"])
        for c in span["changes"]:
            if c["key"] in ("fun", "focus", "communication"):
                self.assertIsNone(c["state"], c["key"])
        self.assertIsNone(span["metrics"]["screen"]["state"])
        hist = {h["date"]: h["totals"] for h in p["history"]}
        self.assertEqual(hist["2026-10-04"]["screen"], 480)
        self.assertIsNone(hist["2026-10-08"]["screen"])  # × in the 30-day lanes, not an empty bar
        self.assertEqual(hist["2026-10-08"]["exercise"], 45)
        # once the import catches up, 5 Oct is a whole day again
        write_table(self.tmp / "data", "screen_sessions", screens(date(2026, 9, 20), date(2026, 10, 11)))
        ctx = Context(ctx.cfg, now=ctx.now)
        self.assertEqual(time_page.build(ctx)["span"]["known"]["screen"], 7)

    def test_mid_day_export_is_not_a_whole_day(self):
        # Apple Health exported at noon on 11 Oct: that row is partial and there is no 12 Oct row
        body = nights(date(2026, 10, 1), date(2026, 10, 11))
        body[-1].update(complete=False, workout_min=None)
        ctx = self.context(at(date(2026, 10, 12), 18, 40), body_daily=body,
                           screen_sessions=screens(date(2026, 10, 1), date(2026, 10, 11)))
        day = ctx.time_days()[date(2026, 10, 11)]
        self.assertIsNone(day.value("exercise"))  # the evening workout may not be exported yet
        self.assertIsNone(day.value("sleep"))     # the night that starts that evening is not in yet
        self.assertIsNone(day.totals()["not_recorded"])
        span = time_page.build(ctx)["span"]
        self.assertEqual(span["known"]["exercise"], 6)
        self.assertEqual(span["exercise_known"], 6)
        self.assertEqual(span["known"]["sleep"], 6)
        self.assertAlmostEqual(span["avg"]["sleep"], 480)

    def test_unknown_workouts_are_not_zero(self):
        # workout_min empty (before the first logged workout), and no workouts.csv at all
        ctx = self.context(at(date(2026, 10, 12), 9),
                           body_daily=nights(date(2026, 10, 1), date(2026, 10, 12), workout_min=None),
                           screen_sessions=screens(date(2026, 10, 1), date(2026, 10, 11)))
        span = time_page.build(ctx)["span"]
        self.assertIsNone(span["avg"]["exercise"])
        self.assertEqual(span["exercise_known"], 0)
        self.assertTrue(all(d["totals"]["exercise"] is None for d in span["days"]))
        self.assertIn({"activity": "exercise", "last": None}, span["stale"])

    def test_evening_before_the_first_night_is_not_a_day(self):
        ctx = self.context(at(date(2026, 11, 12), 18, 40),
                           body_daily=nights(date(2026, 11, 1), date(2026, 11, 12)),
                           screen_sessions=screens(date(2026, 11, 1), date(2026, 11, 12)))
        self.assertIn(date(2026, 10, 31), ctx.time_days())  # it holds the first night's first hour
        self.assertFalse(ctx.time_days()[date(2026, 10, 31)].admitted)
        p = time_page.build(ctx, "2026-11-06")
        self.assertEqual(p["span"]["from"], "2026-11-01")
        self.assertIsNone(p["prev"])  # nothing before the first night
        for key in ("sleep", "screen", "not_recorded"):
            self.assertAlmostEqual(p["span"]["avg"][key], 480, msg=key)


class Stepping(Folder):
    def ctx_with_gap(self, now: datetime, last: date, gap=()):
        days = [d for d in (date(2026, 8, 1) + timedelta(days=k) for k in range((last - date(2026, 8, 1)).days + 1))
                if d not in gap]
        body = [r for r in nights(date(2026, 8, 1), last) if r["date"] in days]
        sessions = [r for r in screens(date(2026, 8, 1), last) if r["start"].date() in days]
        return self.context(now, body_daily=body, screen_sessions=sessions)

    def walk(self, ctx):
        """Follow Earlier three times, then Later back up; every page reached must exist and move."""
        latest = time_page.build(ctx)
        pages = [latest]
        for _ in range(3):
            pages.append(time_page.build(ctx, pages[-1]["prev"]))
        page = pages[-1]
        for _ in range(3):
            self.assertIsNotNone(page["next"], page["span"]["to"])
            later = time_page.build(ctx, page["next"])
            self.assertGreater(later["span"]["to"], page["span"]["to"])
            page = later
        self.assertEqual(page["span"], latest["span"])
        self.assertIsNone(page["next"])

    def test_stale_data_does_not_loop(self):
        ctx = self.ctx_with_gap(at(date(2026, 10, 12), 9), date(2026, 10, 1))
        p = time_page.build(ctx)
        self.assertEqual(p["span"]["to"], "2026-10-01")
        self.assertEqual(p["newest"], "2026-10-01")
        self.assertIsNone(p["next"])  # nothing later exists, so no "Later" that reopens the same page
        self.walk(ctx)

    def test_a_day_without_records_does_not_strand_the_stepper(self):
        ctx = self.ctx_with_gap(at(date(2026, 10, 12), 9), date(2026, 10, 11), gap=(date(2026, 10, 7),))
        for day in ("2026-10-10", "2026-10-03", "2026-10-04"):
            p = time_page.build(ctx, day)
            self.assertLess(p["span"]["to"], "2026-10-11")
            self.assertIsNotNone(p["next"], day)
        self.walk(ctx)

    def test_static_site_has_every_page_its_steppers_open(self):
        ctx = self.ctx_with_gap(at(date(2026, 10, 12), 9), date(2026, 10, 11), gap=(date(2026, 10, 7),))
        params = static_params("time", ctx)
        rendered = {p for p in params if p}
        for param in params:
            p = time_page.build(ctx, param)
            if p["next"]:
                self.assertIn(p["next"], rendered, param)
            if p["prev"] and param != params[-1]:
                self.assertIn(p["prev"], rendered, param)


class ClockChanges(Folder):
    def test_spring_forward(self):
        # Melbourne, 4 Oct 2026: 02:00 jumps to 03:00
        ctx = self.context(
            at(date(2026, 10, 6), 9),
            body_daily=[{"date": date(2026, 10, 4), "sleep_min": 420, "sleep_start": at(date(2026, 10, 3), 23),
                         "sleep_end": at(date(2026, 10, 4), 7)},
                        {"date": date(2026, 10, 5), "sleep_min": 480, "sleep_start": at(date(2026, 10, 4), 23),
                         "sleep_end": at(date(2026, 10, 5), 7)}],
            screen_sessions=[{"start": at(date(2026, 10, 4), 1, 50), "end": at(date(2026, 10, 4), 3, 10),
                              "device": "phone", "app": "Reddit", "category": "social"}])
        days = ctx.time_days()
        d3, d4 = days[date(2026, 10, 3)], days[date(2026, 10, 4)]
        self.assertEqual(d4.length, 1380)
        self.assertEqual(d3.total("sleep"), 60)
        # 00:00-07:00 less the hour that never happened: the night is 420 real minutes, not 480
        self.assertEqual(sum(d4.by_hour[h].get("sleep", 0) for h in range(7)), 360)
        self.assertEqual(d4.total("sleep"), 360 + 60)  # plus 23:00-24:00 of the next night
        self.assertNotIn(2, [h for h in range(24) if d4.by_hour[h].get("sleep")])  # 02:xx never happened
        self.assertEqual(d4.total("screen"), 20)  # 01:50-02:00 and 03:00-03:10
        self.assertEqual(d4.unrecorded, 1380 - d4.recorded)

    def test_fall_back(self):
        # Melbourne, 5 Apr 2026: 03:00 goes back to 02:00, so the night 23:00 -> 07:00 is 9 hours
        ctx = self.context(
            at(date(2026, 4, 7), 9),
            body_daily=[{"date": date(2026, 4, 5), "sleep_min": 540, "sleep_start": at(date(2026, 4, 4), 23),
                         "sleep_end": at(date(2026, 4, 5), 7)}])
        days = ctx.time_days()
        self.assertEqual(days[date(2026, 4, 5)].length, 1500)
        self.assertEqual(days[date(2026, 4, 4)].total("sleep") + days[date(2026, 4, 5)].total("sleep"), 540)
        self.assertEqual(days[date(2026, 4, 5)].by_hour[2]["sleep"], 120)  # the repeated hour, twice


class ReviewWorkouts(Folder):
    def metric(self, page, key):
        return next(m for s in page["sections"] for m in s["metrics"] if m["key"] == key)

    def test_unknown_days_and_today_are_not_zero(self):
        # screen time every day since 7 Sep, health data (with workouts) only from 5 Oct, exported on the 8th
        body = nights(date(2026, 10, 5), date(2026, 10, 8))
        body[-1]["complete"] = False
        workouts = [{"start": at(date(2026, 10, 6), 18), "end": at(date(2026, 10, 6), 18, 40), "type": "running",
                     "source": "Apple Watch"}]
        ctx = self.context(at(date(2026, 10, 12), 9), body_daily=body, workouts=workouts,
                           screen_sessions=screens(date(2026, 9, 7), date(2026, 10, 12)))
        page = review.build(ctx, "2026-10-05")
        m = self.metric(page, "workout_min")
        values = {p["date"]: p["value"] for p in m["points"]}
        self.assertEqual(values["2026-10-05"], 0)
        self.assertEqual(values["2026-10-06"], 40)
        self.assertEqual(values["2026-10-07"], 0)
        for d in ("2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11"):
            self.assertIsNone(values[d], d)  # exported mid-day on the 8th, nothing after
        self.assertEqual(m["days"], 3)
        self.assertAlmostEqual(m["value"], 40 / 3)
        self.assertIsNone(m["before"])  # weeks with screen time only: workouts unknown, not 0
        self.assertEqual(m["before_days"], 0)
        days = self.metric(page, "workout_days")
        self.assertEqual(days["value"], 1)
        self.assertIsNone(days["before"])

        current = review.build(ctx, "2026-10-12")  # today is not over
        self.assertIsNone(self.metric(current, "workout_min")["value"])


class Words(unittest.TestCase):
    """The page's words, read from i18n.js."""

    @classmethod
    def setUpClass(cls):
        import re
        root = Path(__file__).resolve().parent.parent / "healthaio" / "web" / "js"
        cls.text = (root / "i18n.js").read_text(encoding="utf-8")
        cls.pages = {f.name: f.read_text(encoding="utf-8") for f in (root / "pages").glob("*.js")}
        cls.strings = {}
        for key, value in re.findall(r'"([a-z_]+\.[\w. ]+)":\s*"((?:[^"\\]|\\.)*)"', cls.text):
            cls.strings.setdefault(key, []).append(value)

    def test_one_word_one_source(self):
        # Today's ring minutes and the workout-based exercise of Time/Review must not share a name
        for ring, workouts in zip(self.strings["metric.exercise"], self.strings["act.exercise"]):
            self.assertNotEqual(ring, workouts)
        self.assertIn("review.m.workout_min", self.strings)
        self.assertNotIn("review.m.exercise_min", self.strings)

    def test_no_leftovers_of_the_attention_page(self):
        self.assertFalse([k for k in self.strings if k.startswith("attention.") or k == "nav.attention"])
        for name, text in self.pages.items():
            self.assertNotIn('t("attention.', text, name)

    def test_workout_types_have_chinese_names(self):
        for kind in ("strength training", "walking", "running", "cycling", "workout"):
            self.assertIn(f"wtype.{kind}", self.strings, kind)
        # the pages that name a workout: Exercise lists them (the Time page's list moved there), Today names today's
        self.assertIn("wtype(", self.pages["exercise.js"])
        self.assertIn("wtype(", self.pages["today.js"])


if __name__ == "__main__":
    unittest.main()
