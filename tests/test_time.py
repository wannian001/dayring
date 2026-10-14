"""Minutes by activity (the day ring's and the Stimulation page's ground), and the Stimulation page (#time).

Rules under test (healthaio/context.py, healthaio/modules/time.py):
- a record that crosses midnight is split at midnight, minute by minute;
- lanes may overlap (a class with the laptop open counts in both), but a minute is recorded once;
- waking minutes that no record covers are "not recorded", never guessed;
- a day without the record an activity needs shows None for it, never 0 (tests/test_time_coverage.py);
- a workout known only as a daily total (body_daily.workout_min) still counts, without hours;
- planned training on the calendar is not counted; logged workouts are;
- Stimulation: five Screen Time signals, each the shown days' daily average against your usual 7-day averages;
  a day without Screen Time is unknown, never calm; a signal is above or below normal only one band width
  outside it; the page leads with entertainment & social; how the body answered is an association with a
  95% interval and Benjamini-Hochberg, called a difference only when it survives (see Stimulation below).
"""
import json
import re
import shutil
import tempfile
import unittest
from unittest import mock
from datetime import date, datetime, timedelta
from pathlib import Path

from healthaio import config, demo
from healthaio.config import Config
from healthaio import stats
from healthaio.context import ACTIVITIES, SCREEN_PARTS, Context
from healthaio.importers import apple_health
from healthaio.modules import PAGES, static_params
from healthaio.modules import time as time_page
from healthaio.server import payload
from healthaio.store import Store, write_table

ROOT = Path(__file__).resolve().parent.parent
TZ = "Australia/Melbourne"
TODAY = date(2026, 10, 12)
NOW = datetime(2026, 10, 12, 18, 40)
HOUR_KEYS = ("sleep", "calendar") + SCREEN_PARTS  # exercise is checked separately (untimed workouts have no hour)


def dt(month: int, day: int, hour: int, minute: int = 0, year: int = 2026) -> datetime:
    return datetime(year, month, day, hour, minute)


def walk(value, skip=("delta",)):
    """Every leaf value, leaving out keys that may be negative (a change against normal)."""
    if isinstance(value, dict):
        for k, v in value.items():
            if k not in skip:
                yield from walk(v, skip)
    elif isinstance(value, list):
        for v in value:
            yield from walk(v, skip)
    else:
        yield value


class FolderCase(unittest.TestCase):
    """A fresh data folder per test; tables are written with the same writer the importers use."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-time-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def context(self, now: datetime, **tables) -> Context:
        data = self.tmp / "data"
        data.mkdir(exist_ok=True)
        for name, rows in tables.items():
            write_table(data, name, rows)
        cfg = Config(root=self.tmp, data_dir=data, timezone=TZ, devices=["phone", "laptop"])
        return Context(cfg, now=now)


class TimeDaysMinutes(FolderCase):
    def test_records_are_split_at_midnight(self):
        ctx = self.context(
            dt(3, 14, 9),
            body_daily=[{"date": date(2026, 3, 11), "sleep_min": 450,
                         "sleep_start": dt(3, 10, 23, 30), "sleep_end": dt(3, 11, 7, 0)}],
            events=[{"start": dt(3, 11, 21), "end": dt(3, 12, 1), "title": "Night shift", "kind": "work"}],
            screen_sessions=[{"start": dt(3, 11, 23, 50), "end": dt(3, 12, 0, 15), "device": "laptop",
                              "app": "Docs", "category": "work"}],
            workouts=[{"start": dt(3, 12, 23, 40), "end": dt(3, 13, 0, 20), "type": "running", "source": "watch"}],
        )
        days = ctx.time_days()
        d10, d11, d12, d13 = (days[date(2026, 3, d)] for d in (10, 11, 12, 13))

        # the night 23:30 -> 07:00: 30 minutes on the evening it started, 420 on the morning after
        self.assertEqual(d10.total("sleep"), 30)
        self.assertEqual(d10.by_hour[23], {"sleep": 30})
        self.assertEqual(d11.total("sleep"), 420)
        for hour in range(7):
            self.assertEqual(d11.by_hour[hour]["sleep"], 60, hour)
        self.assertNotIn("sleep", d11.by_hour[7])

        # the shift 21:00 -> 01:00 and the screen session 23:50 -> 00:15, each split at midnight
        self.assertEqual(d11.total("calendar"), 180)
        self.assertEqual(d12.total("calendar"), 60)
        self.assertEqual(d11.total("screen"), 10)
        self.assertEqual(d12.total("screen"), 15)
        self.assertEqual(d11.by_hour[23], {"calendar": 60, "focus": 10})
        self.assertEqual(d12.by_hour[0], {"calendar": 60, "focus": 15})

        # the workout 23:40 -> 00:20
        self.assertEqual(d12.total("exercise"), 20)
        self.assertEqual(d13.total("exercise"), 20)
        self.assertEqual(d12.by_hour[23], {"exercise": 20})
        self.assertEqual(d13.by_hour[0], {"exercise": 20})
        self.assertEqual(d12.untimed_exercise, 0)

        # nothing is lost or invented at midnight: the days add back up to the records
        self.assertEqual(sum(td.total("sleep") for td in days.values()), 450)
        self.assertEqual(sum(td.total("calendar") for td in days.values()), 240)
        self.assertEqual(sum(td.total("screen") for td in days.values()), 25)
        self.assertEqual(sum(td.total("exercise") for td in days.values()), 40)

        # every day is 1440 minutes: recorded + not recorded
        self.assertEqual(d10.unrecorded, 1440 - 30)
        self.assertEqual(d11.recorded, 420 + 180)  # the screen minutes sit inside the shift
        self.assertEqual(d11.unrecorded, 1440 - 600)
        self.assertEqual(d12.recorded, 60 + 20)
        self.assertTrue(d11.has_screen and d12.has_screen)
        self.assertFalse(d10.has_screen or d13.has_screen)

        # what the page may say: 3-10 only holds the evening part of the 3-11 night (no row of its own,
        # and no screen record), so it is not a day of its own and nothing on it is known but the calendar
        self.assertFalse(d10.admitted)
        self.assertTrue(d11.admitted and d12.admitted)
        self.assertEqual({k: v for k, v in d10.totals().items() if v is not None}, {"calendar": 0})
        # 3-11 has its morning, but nobody knows whether the evening after it held sleep (no 3-12 row)
        self.assertIsNone(d11.totals()["sleep"])
        self.assertIsNone(d11.totals()["not_recorded"])
        self.assertEqual(d11.totals()["screen"], 10)

    def test_overlap_counts_in_both_lanes_but_once_in_the_day(self):
        ctx = self.context(
            dt(3, 3, 9),
            events=[{"start": dt(3, 2, 10), "end": dt(3, 2, 12), "title": "Lecture", "kind": "class"}],
            screen_sessions=[
                {"start": dt(3, 2, 11), "end": dt(3, 2, 11, 30), "device": "laptop", "app": "Docs", "category": "work"},
                {"start": dt(3, 2, 11, 15), "end": dt(3, 2, 11, 45), "device": "phone", "app": "Reddit", "category": "social"},
                {"start": dt(3, 2, 12), "end": dt(3, 2, 12, 20), "device": "laptop", "app": "Docs", "category": "work"},
            ],
        )
        td = ctx.time_days()[date(2026, 3, 2)]
        totals = td.totals()
        self.assertEqual(totals["calendar"], 120)
        self.assertEqual(totals["screen"], 65)        # two devices at once count once: 11:00-11:45 + 12:00-12:20
        self.assertEqual(totals["focus"], 15 + 20)
        self.assertEqual(totals["fun"], 30)           # the phone wins the shared minutes (device order)
        self.assertEqual(totals["screen"], sum(totals[k] for k in SCREEN_PARTS))
        self.assertEqual(td.recorded, 140)            # 10:00-12:20 once, not 120 + 65
        self.assertEqual(td.unrecorded, 1440 - 140)
        self.assertIsNone(totals["not_recorded"])     # no sleep record that day: the gap would only measure that
        self.assertGreater(sum(td.total(a) for a in ACTIVITIES), td.recorded)  # lanes may add up to more
        self.assertEqual(td.by_hour[11], {"calendar": 60, "focus": 15, "fun": 30})
        self.assertEqual(td.by_hour[12], {"focus": 20})

    def test_untimed_workout_falls_back_to_the_daily_total(self):
        def night(day: date, **extra):
            return {"date": day, "sleep_min": 420, "sleep_start": datetime.combine(day, datetime.min.time()) + timedelta(hours=1),
                    "sleep_end": datetime.combine(day, datetime.min.time()) + timedelta(hours=8), **extra}

        ctx = self.context(
            dt(3, 6, 9),
            body_daily=[night(date(2026, 3, 2), workout_min=45, workout_type="swimming"),  # no clock time anywhere
                        night(date(2026, 3, 3), workout_min=30, workout_type="running"),   # also in workouts.csv
                        night(date(2026, 3, 4), workout_min=0),                           # rest day
                        night(date(2026, 3, 5))],                                         # unknown
            workouts=[{"start": dt(3, 3, 7, 0), "end": dt(3, 3, 7, 30), "type": "running", "source": "watch"}],
        )
        days = ctx.time_days()
        untimed, timed, rest, unknown = (days[date(2026, 3, d)] for d in (2, 3, 4, 5))

        self.assertEqual(untimed.untimed_exercise, 45)
        self.assertEqual(untimed.minutes["exercise"], set())
        self.assertEqual(untimed.total("exercise"), 45)
        self.assertEqual(untimed.recorded, 420 + 45)
        self.assertEqual(untimed.unrecorded, 1440 - 465)
        self.assertTrue(all("exercise" not in h for h in untimed.by_hour))  # no clock time, so no hour

        self.assertEqual(timed.untimed_exercise, 0)  # the timed copy wins; not 30 + 30
        self.assertEqual(timed.total("exercise"), 30)
        self.assertEqual(timed.by_hour[7]["exercise"], 30)
        self.assertEqual(rest.value("exercise"), 0)       # a rest day is a known 0
        self.assertIsNone(unknown.value("exercise"))       # an empty workout_min is unknown, not 0


    def test_planned_training_is_not_counted_but_workouts_are(self):
        ctx = self.context(
            dt(3, 5, 9),
            events=[{"start": dt(3, 3, 9), "end": dt(3, 3, 10), "title": "Lecture", "kind": "class"},
                    {"start": dt(3, 3, 13), "end": dt(3, 3, 13, 30), "title": "Dentist", "kind": "other"},
                    {"start": dt(3, 3, 14), "end": dt(3, 3, 15), "title": "Shift", "kind": "work"},
                    {"start": dt(3, 3, 17), "end": dt(3, 3, 18), "title": "Gym (planned)", "kind": "training"},
                    {"start": dt(3, 3, 19), "end": dt(3, 3, 20), "title": "Dinner", "kind": "personal"},
                    {"start": dt(3, 4, 17), "end": dt(3, 4, 18), "title": "Gym (planned, skipped)", "kind": "training"}],
            workouts=[{"start": dt(3, 3, 17, 5), "end": dt(3, 3, 17, 55), "type": "strength training", "source": "watch"}],
        )
        days = ctx.time_days()
        td = days[date(2026, 3, 3)]
        self.assertEqual(td.total("calendar"), 60 + 30 + 60 + 60)
        self.assertFalse(set(range(17 * 60, 18 * 60)) & td.minutes["calendar"])
        self.assertNotIn("calendar", td.by_hour[17])
        self.assertEqual(td.total("exercise"), 50)  # what was done, from the workout record
        self.assertEqual(td.recorded, 210 + 50)
        skipped = days.get(date(2026, 3, 4))  # a plan with no workout is neither calendar nor exercise
        self.assertTrue(skipped is None or (skipped.total("calendar") == 0 and skipped.total("exercise") == 0))


def history(first: date, last: date, fun=lambda k: 90 + (k % 5) * 10, work=lambda k: 420 + (k % 3) * 20, skip=()):
    """A night every morning (23:00 -> 07:00), work from 09:00 and entertainment from 20:00 every day.
    ``fun`` and ``work`` give the minutes on the k-th day; days in ``skip`` have no screen record."""
    body, sessions, d, k = [], [], first, 0
    while d <= last:
        body.append({"date": d, "sleep_min": 480, "sleep_start": datetime.combine(d - timedelta(days=1), datetime.min.time()) + timedelta(hours=23),
                     "sleep_end": datetime.combine(d, datetime.min.time()) + timedelta(hours=7), "workout_min": 0, "complete": True})
        if d not in skip:
            nine = datetime.combine(d, datetime.min.time()) + timedelta(hours=9)
            eight = datetime.combine(d, datetime.min.time()) + timedelta(hours=20)
            sessions.append({"start": nine, "end": nine + timedelta(minutes=work(k)), "device": "laptop", "app": "Docs", "category": "work"})
            sessions.append({"start": eight, "end": eight + timedelta(minutes=fun(k)), "device": "tablet", "app": "YouTube", "category": "entertainment"})
        d += timedelta(days=1)
        k += 1
    return body, sessions


def weekdays_from(first: date, last: date, weekdays, make):
    """``make(d)`` for every day in [first, last] whose weekday (0 = Monday) is in ``weekdays``."""
    out, d = [], first
    while d <= last:
        if d.weekday() in weekdays:
            out.append(make(d))
        d += timedelta(days=1)
    return out


def at(d: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(d, datetime.min.time()) + timedelta(hours=hour, minutes=minute)


def stressful(first: date, last: date, fun, hrv):
    """history() plus HRV: ``fun(k)`` minutes of entertainment on the k-th day, ``hrv(k)`` the next morning."""
    body, sessions = history(first, last, fun=fun)
    for k, row in enumerate(body):
        if k:
            row["hrv_ms"] = hrv(k - 1)
    return body, sessions


class Stimulation(FolderCase):
    """What goes in against your normal, and how the body answered."""
    WEEK = date(2026, 10, 5)  # the first shown day of the latest page (today = 12 Oct)

    def test_more_entertainment_than_usual_reads_high(self):
        week = self.WEEK
        # four usual weeks (fun 90-130 minutes), then a week with 200 minutes of fun a day
        body, sessions = history(date(2026, 8, 20), date(2026, 10, 11),
                                 fun=lambda k: 200 if date(2026, 8, 20) + timedelta(days=k) >= week else 90 + (k % 5) * 10)
        ctx = self.context(dt(10, 12, 18, 40), body_daily=body, screen_sessions=sessions)
        p = time_page.build(ctx)
        span = p["span"]
        self.assertEqual(span["from"], "2026-10-05")
        fun = span["metrics"]["fun"]
        normal = time_page.typical_week(time_page.stim_series(ctx)["fun"], week)
        self.assertEqual(fun["band"], normal)  # your usual 7-day averages before the first shown day
        self.assertAlmostEqual(fun["value"], 200)
        self.assertEqual((fun["state"], fun["tone"], fun["clear"]), ("high", "bad", True))
        self.assertAlmostEqual(fun["delta"], 200 - normal["median"])
        self.assertEqual(span["level"], "high")
        # the hours add up to the minutes: 20:00-23:20 every day of the week
        self.assertAlmostEqual(sum(p["hours"]["now"]), 200)
        self.assertEqual([round(v) for v in p["hours"]["now"][20:23]], [60, 60, 60])
        self.assertEqual(p["apps"][0]["app"], "YouTube")

    def test_a_usual_week_reads_normal(self):
        body, sessions = history(date(2026, 8, 20), date(2026, 10, 11), fun=lambda k: 110, work=lambda k: 440)
        ctx = self.context(dt(10, 12, 18, 40), body_daily=body, screen_sessions=sessions)
        span = time_page.build(ctx)["span"]
        self.assertEqual(span["level"], "normal")
        self.assertEqual(span["also"], [])
        self.assertTrue(all(m["score"] == 0 and not m["clear"] for m in span["metrics"].values()))
        self.assertEqual(span["metrics"]["ratio"]["state"], "normal")  # one device at a time, as always

    def test_a_varied_usual_week_stays_quiet(self):
        # the same random habits every day: a week lands outside the middle half now and then, but seldom one
        # band width outside it
        import random
        quiet = spans = 0
        for seed in range(6):
            rng = random.Random(seed)
            fun = [rng.randint(100, 200) for _ in range(80)]
            work = [rng.randint(240, 420) for _ in range(80)]
            body, sessions = history(date(2026, 7, 25), date(2026, 10, 11), fun=lambda k: fun[k], work=lambda k: work[k])
            ctx = self.context(dt(10, 12, 18, 40), body_daily=body, screen_sessions=sessions)
            page = time_page.build(ctx)
            for _ in range(5):
                spans += 1
                quiet += page["span"]["level"] == "normal"
                page = time_page.build(ctx, page["prev"])
            shutil.rmtree(self.tmp / "data")
        self.assertGreaterEqual(quiet / spans, 2 / 3, (quiet, spans))

    def test_a_day_without_screen_time_is_unknown_not_calm(self):
        gap = {date(2026, 9, 14) + timedelta(days=k) for k in range(14)}  # Screen Time off for two weeks
        body, sessions = history(date(2026, 8, 1), date(2026, 10, 11), skip=gap)
        ctx = self.context(dt(10, 12, 18, 40), body_daily=body, screen_sessions=sessions)
        series = time_page.stim_series(ctx)
        for key in time_page.STIM_KEYS:
            self.assertFalse(gap & set(series[key]), key)  # the gap is not two weeks of zero
        # the week inside the gap: nothing is known, so nothing is compared
        p = time_page.build(ctx, "2026-09-27")
        self.assertIsNone(p["span"]["level"])
        for key, m in p["span"]["metrics"].items():
            self.assertIsNone(m["value"], key)
            self.assertEqual(m["score"], 0, key)
        # back on screens with the usual habits: the normal skips the gap, so nothing reads as a jump
        span = time_page.build(ctx)["span"]
        self.assertFalse(span["metrics"]["fun"]["clear"])
        self.assertLess(abs(span["metrics"]["fun"]["delta"]), 10)
        self.assertEqual(span["metrics"]["fun"]["band"]["days"], 14)  # 10 averages before the gap, 4 after it

    def test_the_hour_before_sleep_needs_both_days_on_record(self):
        # entertainment until 23:20 every evening, asleep at 23:00: 60 minutes of it in the last hour
        body, sessions = history(date(2026, 9, 1), date(2026, 10, 11), fun=lambda k: 200)
        ctx = self.context(dt(10, 12, 18, 40), body_daily=body, screen_sessions=sessions)
        series = time_page.stim_series(ctx)
        self.assertEqual(series["before_sleep"][date(2026, 10, 1)], 60)
        # the night after the last whole day (11 Oct) ends this morning; its hour is on record
        self.assertIn(date(2026, 10, 10), series["before_sleep"])

    def test_tone_follows_the_better_direction(self):
        band = {"q1": 100.0, "median": 120.0, "q3": 140.0, "days": 20}
        for key in time_page.STIM_KEYS:
            high, low = time_page.compare(key, 400.0, band), time_page.compare(key, 20.0, band)
            want = ("good", "bad") if key == "longest_focus" else ("bad", "good")
            self.assertEqual((high["tone"], low["tone"]), want, key)
            self.assertEqual(time_page.compare(key, 120.0, band)["tone"], "neutral", key)

    def test_score_is_distance_outside_in_band_widths(self):
        band = {"q1": 100.0, "median": 120.0, "q3": 140.0, "days": 20}
        self.assertEqual(time_page.score(120, band, 15), 0)
        self.assertEqual(time_page.score(140, band, 15), 0)                 # the edge is still normal
        self.assertAlmostEqual(time_page.score(180, band, 15), 40 / 40)
        self.assertAlmostEqual(time_page.score(80, band, 15), 20 / 40)
        narrow = {"q1": 10.0, "median": 12.0, "q3": 14.0, "days": 20}
        self.assertAlmostEqual(time_page.score(29, narrow, 15), 15 / 15)    # at least 15 minutes wide
        steady = {"q1": 470.0, "median": 480.0, "q3": 490.0, "days": 20}
        self.assertAlmostEqual(time_page.score(538, steady, 30), 48 / 48)   # or a tenth of the usual value, if larger
        self.assertEqual(time_page.score(None, band, 15), 0)
        self.assertEqual(time_page.score(500, None, 15), 0)

    def test_values_are_compared_as_printed(self):
        band = {"q1": 100.2, "median": 120.0, "q3": 475.5, "days": 20}
        on_edge = time_page.compare("fun", 475.57, band)  # prints as the top of the normal
        self.assertEqual((on_edge["state"], on_edge["score"], on_edge["clear"]), ("normal", 0, False))
        self.assertEqual(time_page.compare("fun", 476.6, band)["state"], "high")
        switches = {"q1": 4.5, "median": 4.6, "q3": 4.71, "days": 20}
        self.assertEqual(time_page.compare("switches", 4.74, switches)["state"], "normal")  # 4.7 / h either way
        self.assertEqual(time_page.compare("switches", 4.76, switches)["state"], "high")

    def test_a_change_must_be_clearly_outside(self):
        band = {"q1": 100.0, "median": 120.0, "q3": 140.0, "days": 20}
        just = time_page.compare("fun", 170.0, band)        # 30 minutes past the edge of a 40-minute band
        self.assertEqual((just["state"], just["clear"]), ("high", False))
        self.assertTrue(time_page.compare("fun", 180.0, band)["clear"])  # one band width past it
        ratio = {"q1": 112.0, "median": 114.0, "q3": 116.0, "days": 20}  # hundredths: 1.12x-1.16x
        self.assertFalse(time_page.compare("ratio", 120.0, ratio)["clear"])  # the band counts as 0.05 wide
        self.assertTrue(time_page.compare("ratio", 121.0, ratio)["clear"])

    def test_the_body_answer_is_called_a_difference_only_when_it_survives(self):
        # 90 days alternating busy (300 minutes of fun) and quiet (60) days; HRV 10% lower after the busy ones
        first, last = date(2026, 7, 1), date(2026, 10, 11)
        busy = lambda k: k % 2 == 0
        body, sessions = stressful(first, last, fun=lambda k: 300 if busy(k) else 60,
                                   hrv=lambda k: (45 if busy(k) else 50) + (k % 3) * 0.5)
        ctx = self.context(dt(10, 12, 18, 40), body_daily=body, screen_sessions=sessions)
        r = time_page.build(ctx)["response"]
        self.assertEqual(r["days"], time_page.RESPONSE_DAYS)
        rows = {(x["exposure"], x["outcome"]): x for x in r["rows"]}
        self.assertEqual(len(rows), 8)
        hrv = rows[("fun_high", "hrv")]
        self.assertTrue(hrv["detected"])
        self.assertLess(hrv["high"], 0)  # lower after busy days, the whole interval below zero
        self.assertFalse(rows[("fun_high", "resting_hr")].get("detected", False))  # no heart rate recorded
        self.assertEqual(rows[("fun_high", "resting_hr")]["status"], "too_few")
        # the same every evening: no calm evenings to compare with
        self.assertEqual(rows[("late_fun", "asleep")]["status"], "too_few")

    def test_too_few_days_say_so(self):
        body, sessions = stressful(date(2026, 10, 1), date(2026, 10, 11), fun=lambda k: 100 + k, hrv=lambda k: 50)
        ctx = self.context(dt(10, 12, 18, 40), body_daily=body, screen_sessions=sessions)
        r = time_page.build(ctx)["response"]
        self.assertIsNone(r["median_fun"])
        self.assertTrue(all(x["status"] == "too_few" for x in r["rows"]))


class DemoTimePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="healthaio-time-demo-"))
        try:
            cls.cfg = config.load(demo.generate(cls.tmp, TODAY, NOW))
        except config.ConfigError:  # Python 3.9/3.10 without tomli
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise unittest.SkipTest("needs Python 3.11+ or tomli to read the demo healthaio.toml")
        cls.latest = payload(cls.cfg, "time", None, NOW)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def page(self, day=None):
        return payload(self.cfg, "time", day, NOW)

    def check_invariants(self, p):
        label = p["day"]
        self.assertFalse(p["empty"], label)
        json.dumps(p)  # JSON-ready without default=str
        for v in walk(p, skip=("delta", "diff", "low", "high", "rows")):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                self.assertGreaterEqual(v, 0, label)
        span = p["span"]
        ctx = Context(self.cfg, now=NOW)
        every = time_page.data_days(ctx)
        shown = [d for d in every if span["from"] <= d.isoformat() <= span["to"]]
        self.assertEqual(span["n"], 7, label)
        self.assertEqual(len(shown), 7, label)
        self.assertTrue(all(d < TODAY for d in shown), label)  # today is not over, so never in the span
        self.assertEqual((shown[-1] - shown[0]).days, 6, label)  # the demo records every day: 7 whole days in a row
        self.assertEqual(p["day"], span["to"])
        series = time_page.stim_series(ctx)
        self.assertEqual(span["screen_days"], sum(1 for d in shown if d in series["fun"]))
        M = span["metrics"]
        self.assertEqual(sorted(M), sorted(time_page.STIM_KEYS))
        for key, m in M.items():
            have = [series[key][d] for d in shown if d in series[key]]
            self.assertEqual(m["known"], len(have), (label, key))
            if key != "ratio" and have:  # each average is over the days that have the record, never padded with zeros
                self.assertAlmostEqual(m["value"], sum(have) / len(have), msg=(label, key))
            if m["state"] in (None, "normal"):
                self.assertEqual(m["score"], 0, (label, key))
            self.assertEqual(m["clear"], m["score"] >= time_page.STANDOUT_MIN, (label, key))
            self.assertEqual(m["tone"], stats.tone(m["state"], time_page.BETTER[key]), (label, key))
        self.assertEqual(span["level"], time_page.level(M))
        self.assertEqual(span["also"], [k for k in time_page.STIM_KEYS[1:] if M[k]["clear"]])
        # the hour chart adds up to the daily average of entertainment & social
        self.assertEqual(len(p["hours"]["now"]), 24)
        self.assertAlmostEqual(sum(p["hours"]["now"]), M["fun"]["value"], msg=label)
        self.assertTrue(all(v <= 60 + 1e-9 for v in p["hours"]["now"]), label)
        # where it came from: entertainment and social apps only, most first
        self.assertTrue(all(a["category"] in ("entertainment", "social") for a in p["apps"]), label)
        minutes = [a["minutes"] for a in p["apps"]]
        self.assertEqual(minutes, sorted(minutes, reverse=True), label)
        self.assertLessEqual(p["plan"]["over"], p["plan"]["known"])
        # how the body answered: eight comparisons; a difference only when it survives the correction
        R = p["response"]
        self.assertEqual(len(R["rows"]), len(time_page.EXPOSURES) * len(time_page.OUTCOMES))
        for row in R["rows"]:
            if row["status"] == "ok":
                self.assertLessEqual(row["low"], row["diff"])
                self.assertLessEqual(row["diff"], row["high"])
                self.assertEqual(row["detected"], row["p_adjusted"] < stats.FDR)
            else:
                self.assertNotIn("detected", row)
        self.assertEqual(span["stale"], [], label)  # every demo record runs up to yesterday

    def test_latest_page_invariants(self):
        p = self.latest
        self.check_invariants(p)
        self.assertEqual(p["day"], (TODAY - timedelta(days=1)).isoformat())
        self.assertEqual(p["newest"], p["day"])
        self.assertIsNone(p["next"])  # nothing later than yesterday
        self.assertEqual(p["page"], "time")

    def test_clock_change_day_is_23_hours(self):
        days = Context(self.cfg, now=NOW).time_days()
        self.assertEqual(days[date(2026, 10, 4)].length, 1380)
        self.assertEqual(days[date(2026, 10, 3)].length, 1440)

    def test_the_demo_body_answers_a_stimulating_day(self):
        # Sam scrolls more on the day before a morning with HRV under his normal, and in the last hour on nights he
        # falls asleep later than usual (demo.Sam.screen), so the card has something to show
        detected = [r for r in self.latest["response"]["rows"] if r.get("detected")]
        self.assertTrue(detected)
        for r in detected:
            if r["outcome"] == "hrv":
                self.assertLess(r["diff"], 0)
            if r["outcome"] == "asleep":
                self.assertGreater(r["diff"], 0)

    def test_earlier_pages_invariants(self):
        for day in ("2026-10-10", "2026-10-04", "2026-09-27", "2026-07-01"):
            with self.subTest(day=day):
                self.check_invariants(self.page(day))

    def test_today_or_future_shows_the_latest_whole_days(self):
        for day in (TODAY.isoformat(), "2026-10-20"):
            with self.subTest(day=day):
                p = self.page(day)
                self.assertEqual(p["span"]["to"], self.latest["span"]["to"])
                self.assertIsNone(p["next"])

    def test_prev_shows_the_seven_days_just_before(self):
        p = self.latest
        self.assertIsNotNone(p["prev"])
        self.assertLess(p["prev"], p["span"]["from"])
        every = time_page.data_days(Context(self.cfg, now=NOW))
        first = every.index(date.fromisoformat(p["span"]["from"]))
        earlier = self.page(p["prev"])
        self.assertEqual(earlier["span"]["to"], every[first - 1].isoformat())
        self.assertEqual(earlier["span"]["from"], every[first - 7].isoformat())

    def test_next_continues_without_skipping_days(self):
        p = self.page("2026-10-04")
        self.assertIsNotNone(p["next"])
        later = self.page(p["next"])
        self.assertGreater(later["span"]["to"], p["span"]["to"])
        first_later = date.fromisoformat(later["span"]["from"])
        self.assertLessEqual(first_later, date.fromisoformat(p["span"]["to"]) + timedelta(days=1))

    def test_next_exists_whenever_a_later_whole_day_exists(self):
        # Every page that does not end on the latest whole day needs a way forward ("Later 7 days" / "Latest").
        latest_day = self.latest["span"]["to"]
        for day in ("2026-10-10", "2026-10-09", "2026-10-04"):
            with self.subTest(day=day):
                p = self.page(day)
                self.assertLess(p["span"]["to"], latest_day)
                self.assertIsNotNone(p["next"], f"span ending {p['span']['to']} has no link to {latest_day}")

    def test_static_site_steppers_land_on_rendered_pages(self):
        # The GitHub Pages demo only has the pre-rendered dates; a "Later" link from one of them should
        # open a page that exists (falling off the oldest end is fine, the app shows a hint there).
        ctx = Context(self.cfg, now=NOW)
        params = static_params("time", ctx)
        rendered = {p for p in params if p}
        for param in params:
            p = self.page(param)
            if p["next"]:
                with self.subTest(param=param):
                    self.assertIn(p["next"], rendered, f"#time/{p['next']} is not pre-rendered")

    def test_trend_card_covers_the_days_up_to_the_shown_day(self):
        # stimulation and focus, averaged: TREND_DAYS consecutive days ending on the page's last day, each
        # 7-day average over the days in it with screen time, and the 28-day levels over the same values
        series = time_page.trend_series(Context(self.cfg, now=NOW))
        for param in (None, "2026-09-27"):
            p = self.page(param)
            tr = p["trend"]
            with self.subTest(param=param):
                self.assertEqual(tr["to"], p["day"])
                self.assertEqual(sorted(tr["series"]), sorted(time_page.TREND_KEYS))
                for key, s in tr["series"].items():
                    values = series[key]
                    dates = [date.fromisoformat(d["date"]) for d in s["days"]]
                    self.assertEqual(len(dates), time_page.TREND_DAYS)
                    self.assertEqual(dates[0].isoformat(), tr["from"])
                    self.assertTrue(all((b - a).days == 1 for a, b in zip(dates, dates[1:])))
                    for d, row in zip(dates, s["days"]):
                        self.assertEqual(row["value"], values.get(d))
                        week = [values[d - timedelta(days=j)] for j in range(7) if d - timedelta(days=j) in values]
                        if len(week) >= time_page.WEEK_MIN_DAYS:
                            self.assertAlmostEqual(row["avg7"], sum(week) / len(week))
                        else:
                            self.assertIsNone(row["avg7"])
                        if row["band"]:
                            self.assertLessEqual(row["band"]["q1"], row["band"]["q3"])
                    end = dates[-1]
                    recent = [values[end - timedelta(days=k)] for k in range(28) if end - timedelta(days=k) in values]
                    self.assertEqual(s["recent"]["n"], len(recent))
                    self.assertAlmostEqual(s["recent"]["avg"], sum(recent) / len(recent))
                    self.assertEqual(s["before"]["to"], (end - timedelta(days=28)).isoformat())
                self.assertTrue(all(v >= 0 for v in walk(tr) if isinstance(v, (int, float))))

    def test_trend_strings_exist_in_both_languages(self):
        i18n = (ROOT / "healthaio" / "web" / "js" / "i18n.js").read_text(encoding="utf-8")
        keys = ["trend.title", "trend.note", "trend.key", "trend.rule", "trend.level", "trend.level_one",
                "trend.level_none", "trend.h", "trend.m"]
        keys += [f"trend.{k}" for k in time_page.TREND_KEYS] + [f"trend.{k}_what" for k in time_page.TREND_KEYS]
        for key in keys:
            self.assertEqual(i18n.count(f'"{key}"'), 2, key)  # English and Chinese
        self.assertNotIn("多巴胺均", i18n)  # dopamine is named as an idea people use, never as a measured value


class TrendAverages(unittest.TestCase):
    """The averages card on made-up values: a day without screen time is missing, never zero."""

    def build(self, values):
        with mock.patch.object(time_page, "trend_series", return_value={"fun": values, "longest_focus": {}}):
            return time_page.trend(None, date(2026, 10, 11))

    def test_a_day_without_screen_time_is_left_out_not_zero(self):
        last = date(2026, 10, 11)
        values = {last - timedelta(days=k): 300.0 for k in range(60) if k not in (1, 2, 3)}  # 8–10 Oct have none
        tr = self.build(values)
        days = {d["date"]: d for d in tr["series"]["fun"]["days"]}
        for k in (1, 2, 3):
            self.assertIsNone(days[(last - timedelta(days=k)).isoformat()]["value"])
        self.assertEqual(days[last.isoformat()]["avg7"], 300.0)  # 4 of the 7 days, not dragged towards 0
        self.assertEqual(tr["series"]["fun"]["recent"], {"from": "2026-09-14", "to": "2026-10-11", "n": 25, "avg": 300.0})
        self.assertIsNone(tr["series"]["longest_focus"]["recent"]["avg"])

    def test_too_few_days_give_no_average(self):
        last = date(2026, 10, 11)
        tr = self.build({last - timedelta(days=k): 100.0 for k in range(0, 28, 2)})  # 14 of the last 28 days
        self.assertEqual(tr["series"]["fun"]["recent"]["avg"], 100.0)
        self.assertIsNone(tr["series"]["fun"]["before"]["avg"])  # nothing before them
        tr = self.build({last - timedelta(days=k): 100.0 for k in range(0, 26, 2)})  # 13 days: too few
        self.assertIsNone(tr["series"]["fun"]["recent"]["avg"])
        days = tr["series"]["fun"]["days"]
        self.assertEqual(days[-1]["avg7"], 100.0)  # the 7 days ending on 11 Oct hold 4 with a value (11, 9, 7, 5 Oct)
        self.assertIsNone(days[-2]["avg7"])  # the 7 ending on 10 Oct hold only 3: too few for an average


class AppleHealthWorkouts(unittest.TestCase):
    """workouts.csv from an export: one row per workout, configured-timezone wall-clock time, copies counted once."""

    EXPORT = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Synthetic. The time strings carry the export's offset (+1100), as real exports do. -->
<HealthData locale="en_AU">
 <ExportDate value="2026-10-12 14:30:00 +1100"/>
 <!-- Watch strength session, and the iPhone Fitness app's copy of it (a little longer): one row, from the watch -->
 <Workout workoutActivityType="HKWorkoutActivityTypeTraditionalStrengthTraining" duration="45" durationUnit="min"
          sourceName="Sam's Apple Watch" startDate="2026-10-10 17:00:00 +1100" endDate="2026-10-10 17:45:00 +1100">
  <MetadataEntry key="HKTimeZone" value="Australia/Melbourne"/>
 </Workout>
 <Workout workoutActivityType="HKWorkoutActivityTypeTraditionalStrengthTraining" duration="49" durationUnit="min"
          sourceName="Sam's iPhone" startDate="2026-10-10 16:58:00 +1100" endDate="2026-10-10 17:47:00 +1100"/>
 <!-- A run in Los Angeles: 02:30 +1100 on 6 Oct is 08:30 on 5 Oct there. workouts.csv keeps the configured
      timezone, like screen time and the calendar, so it is written as 6 Oct 02:30; body_daily counts it on 5 Oct -->
 <Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="30" durationUnit="min"
          sourceName="Sam's Apple Watch" startDate="2026-10-06 02:30:00 +1100" endDate="2026-10-06 03:00:00 +1100">
  <MetadataEntry key="HKTimeZone" value="America/Los_Angeles"/>
 </Workout>
 <!-- Before daylight saving started in Melbourne (4 Oct): 18:00 +1100 is 17:00 local (+1000) -->
 <Workout workoutActivityType="HKWorkoutActivityTypeCycling" duration="0.5" durationUnit="hr"
          sourceName="Sam's Apple Watch" startDate="2026-10-01 18:00:00 +1100" endDate="2026-10-01 18:30:00 +1100">
  <MetadataEntry key="HKTimeZone" value="Australia/Melbourne"/>
 </Workout>
 <!-- No HKTimeZone: the configured timezone -->
 <Workout workoutActivityType="HKWorkoutActivityTypeWalking" duration="40" durationUnit="min"
          sourceName="Sam's Apple Watch" startDate="2026-10-08 12:00:00 +1100" endDate="2026-10-08 12:40:00 +1100"/>
 <!-- Only the phone app recorded this one: kept -->
 <Workout workoutActivityType="HKWorkoutActivityTypeYoga" duration="20" durationUnit="min"
          sourceName="Sam's iPhone" startDate="2026-10-09 07:00:00 +1100" endDate="2026-10-09 07:20:00 +1100"/>
</HealthData>
"""
    EXPECTED = [
        (dt(10, 1, 17, 0), dt(10, 1, 17, 30), "cycling", "Sam's Apple Watch"),
        (dt(10, 6, 2, 30), dt(10, 6, 3, 0), "running", "Sam's Apple Watch"),  # LA's 08:30 in Melbourne time
        (dt(10, 8, 12, 0), dt(10, 8, 12, 40), "walking", "Sam's Apple Watch"),
        (dt(10, 9, 7, 0), dt(10, 9, 7, 20), "yoga", "Sam's iPhone"),
        (dt(10, 10, 17, 0), dt(10, 10, 17, 45), "strength training", "Sam's Apple Watch"),
    ]

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-time-ah-"))
        self.export = self.tmp / "export.xml"
        self.export.write_text(self.EXPORT, encoding="utf-8")
        self.cfg = Config(root=self.tmp, data_dir=self.tmp / "data", timezone=TZ)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def workouts(self):
        loaded = Store(self.cfg.data_dir).load("workouts")
        self.assertTrue(loaded.present)
        self.assertEqual(loaded.problems, [])
        return [(r["start"], r["end"], r["type"], r["source"]) for r in loaded.rows]

    def test_writes_workouts_csv(self):
        summary = apple_health.import_apple_health(self.export, self.cfg)
        self.assertEqual(summary.problems, [])
        self.assertEqual(self.workouts(), self.EXPECTED)
        self.assertTrue(any("5 workouts" in n for n in summary.notes), summary.notes)
        # the daily total agrees: the phone copy is not added to the watch session
        body = Store(self.cfg.data_dir).by_date("body_daily")
        self.assertAlmostEqual(body[date(2026, 10, 10)]["workout_min"], 45)
        self.assertAlmostEqual(body[date(2026, 10, 1)]["workout_min"], 30)  # 0.5 hr

    def test_read_export_returns_validated_sessions(self):
        sessions = []
        apple_health.read_export(self.export, self.cfg.tz, sessions)
        self.assertEqual([(s["start"], s["end"], s["type"], s["source"]) for s in sessions], self.EXPECTED)

    def test_reimport_is_idempotent_and_keeps_older_rows(self):
        self.cfg.data_dir.mkdir()
        write_table(self.cfg.data_dir, "workouts", [
            {"start": dt(9, 1, 7, 0), "end": dt(9, 1, 7, 45), "type": "swimming", "source": "Pool app"}])
        apple_health.import_apple_health(self.export, self.cfg)
        apple_health.import_apple_health(self.export, self.cfg)
        rows = self.workouts()
        self.assertEqual(rows[0], (dt(9, 1, 7, 0), dt(9, 1, 7, 45), "swimming", "Pool app"))  # outside the export's range
        self.assertEqual(rows[1:], self.EXPECTED)

    def test_time_page_reads_the_imported_workouts(self):
        apple_health.import_apple_health(self.export, self.cfg)
        days = Context(self.cfg, now=dt(10, 12, 18, 40)).time_days()
        self.assertEqual(days[date(2026, 10, 10)].total("exercise"), 45)
        self.assertEqual(days[date(2026, 10, 10)].untimed_exercise, 0)
        self.assertEqual(days[date(2026, 10, 6)].by_hour[2]["exercise"], 30)
        self.assertEqual(days[date(2026, 10, 1)].by_hour[17]["exercise"], 30)


class AttentionAlias(unittest.TestCase):
    """The page was called "attention"; old links (#attention, #attention/2026-10-04) must still open it."""

    def test_app_js_maps_attention_to_time(self):
        text = (ROOT / "healthaio" / "web" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertRegex(text, r'const ALIAS\s*=\s*\{[^}]*\battention\s*:\s*"time"')
        self.assertIn("ALIAS[raw]", text)  # route() resolves the alias before picking the page
        nav = re.search(r"const NAV\s*=\s*\[([^\]]*)\]", text)
        self.assertIsNotNone(nav)
        self.assertIn('["time", "nav.time_tab"]', text)  # a page of the Daily life item
        self.assertNotIn('"attention"', nav.group(1))

    def test_no_leftovers_of_where_time_went(self):
        i18n = (ROOT / "healthaio" / "web" / "js" / "i18n.js").read_text(encoding="utf-8")
        for key in ("time.top_line", "time.change_line", "time.usual_line", "time.history_note", "time.workouts", "chg.fun"):
            self.assertNotIn(f'"{key}"', i18n, key)
        page = (ROOT / "healthaio" / "web" / "js" / "pages" / "time.js").read_text(encoding="utf-8")
        for code in ("S.top", "standout", "p.history", "workouts"):
            self.assertNotIn(code, page, code)
        used = set(re.findall(r't\("(stim\.[\w.]+)"', page))
        used |= {f"stim.m.{k}" for k in time_page.STIM_KEYS} | {f"stim.what.{k}" for k in time_page.STIM_KEYS}
        used |= {f"stim.dir.{k}.{s}" for k in time_page.STIM_KEYS[1:] for s in ("high", "low")}
        used |= {f"stim.out.{o}" for o in time_page.OUTCOMES} | {f"stim.out.{o}.{d}" for o in time_page.OUTCOMES for d in ("up", "down")}
        used |= {f"stim.level.{k}" for k in ("high", "low", "normal", "none")} | {f"stim.exp.{e}" for e in time_page.EXPOSURES}
        for key in used:
            self.assertEqual(i18n.count(f'"{key}"'), 2, key)  # English and Chinese
        self.assertIn("can't be measured by a phone or a watch", i18n)  # no number on the page claims to be a hormone

    def test_time_page_is_registered_and_named(self):
        self.assertIn("time", PAGES)
        self.assertNotIn("attention", PAGES)
        i18n = (ROOT / "healthaio" / "web" / "js" / "i18n.js").read_text(encoding="utf-8")
        self.assertEqual(i18n.count('"nav.time_tab"'), 2)  # English and Chinese
        for page in (ROOT / "healthaio" / "web" / "js").rglob("*.js"):
            self.assertNotIn('href="#attention', page.read_text(encoding="utf-8"), page.name)


if __name__ == "__main__":
    unittest.main()
