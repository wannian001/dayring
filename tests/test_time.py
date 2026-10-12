"""The Time page: each activity measured from its own record, minute by minute.

Rules under test (dayring/context.py, dayring/modules/time.py):
- a record that crosses midnight is split at midnight, minute by minute;
- lanes may overlap (a class with the laptop open counts in both), but a minute is recorded once;
- waking minutes that no record covers are "not recorded", never guessed;
- a day without the record an activity needs shows None for it, never 0 (tests/test_time_coverage.py);
- a workout known only as a daily total (body_daily.workout_min) still counts, without hours;
- planned training on the calendar is not counted; logged workouts are;
- the page names what changed compared with your normal, never the biggest activity: the screen
  total is not a candidate, a day without a record is left out of the normal, a change counts only
  when it is at least one band width outside normal, and the biggest of those in minutes is named; a
  day is compared with the 28 days before it, the 7-day average with your usual 7-day averages (see
  WhatChanged below).
"""
import json
import re
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from dayring import config, demo
from dayring.config import Config
from dayring import stats
from dayring.context import ACTIVITIES, SCREEN_PARTS, Context
from dayring.importers import apple_health
from dayring.modules import PAGES, static_params
from dayring.modules import time as time_page
from dayring.server import payload
from dayring.store import Store, write_table

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
                yield from walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk(v)
    else:
        yield value


class FolderCase(unittest.TestCase):
    """A fresh data folder per test; tables are written with the same writer the importers use."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dayring-time-"))

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

        page = payload(ctx.cfg, "time", None, ctx.now)
        span = page["span"]
        self.assertEqual([d["date"] for d in span["days"]], ["2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05"])
        self.assertTrue(span["untimed_exercise"])
        self.assertEqual(span["exercise_days"], 2)
        self.assertEqual(span["exercise_known"], 3)
        self.assertEqual(span["known"]["exercise"], 3)
        self.assertAlmostEqual(span["avg"]["exercise"], (45 + 30 + 0) / 3)  # 3-05 is left out, not counted as 0
        self.assertAlmostEqual(sum(h["exercise"] for h in span["by_hour"]), 30 / 3)  # only the timed workout has hours
        self.assertEqual([w["type"] for w in span["workouts"]], ["running"])

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


class WhatChanged(FolderCase):
    """The standout is the biggest clear change against your normal, not the biggest activity."""
    WEEK = date(2026, 10, 5)  # the first shown day of the latest page (today = 12 Oct)

    def test_fun_above_normal_is_named_although_screens_are_the_biggest(self):
        week = self.WEEK
        # four normal weeks (fun 90-130 minutes, work 420-460), then a week with 200 minutes of fun a day
        body, sessions = history(date(2026, 8, 20), date(2026, 10, 11),
                                 fun=lambda k: 200 if date(2026, 8, 20) + timedelta(days=k) >= week else 90 + (k % 5) * 10)
        ctx = self.context(dt(10, 12, 18, 40), body_daily=body, screen_sessions=sessions)
        span = time_page.build(ctx)["span"]
        self.assertEqual(span["from"], "2026-10-05")
        normal = time_page.typical_week(time_page.normal_series(ctx)["fun"], week)
        for d in span["days"]:
            tot = d["totals"]
            self.assertGreater(tot["screen"], max(tot["sleep"] or 0, tot["exercise"] or 0, tot["calendar"] or 0), d["date"])  # screens win every day
            s = d["standout"]
            self.assertEqual((s["key"], s["state"], s["tone"]), ("fun", "high", "bad"), d["date"])
            self.assertAlmostEqual(s["delta"], 200 - s["band"]["median"])
            self.assertGreaterEqual(s["score"], time_page.STANDOUT_MIN, d["date"])
        top = span["standout"]
        self.assertEqual((top["key"], top["state"], top["tone"], top["clear"]), ("fun", "high", "bad", True))
        self.assertEqual(top["band"], normal)  # your usual 7-day averages before the first shown day
        self.assertAlmostEqual(top["value"], 200)
        self.assertAlmostEqual(top["delta"], 200 - normal["median"])
        self.assertEqual(span["changes"][0], top)
        self.assertNotIn("screen", [c["key"] for c in span["changes"]])  # the total is never a candidate
        self.assertEqual(span["metrics"]["screen"]["state"], "high")       # it is still shown against its normal
        self.assertNotIn("top", span)
        self.assertNotIn("top", span["days"][0])

    def test_a_usual_week_has_no_standout(self):
        body, sessions = history(date(2026, 8, 20), date(2026, 10, 11), fun=lambda k: 110, work=lambda k: 440)
        ctx = self.context(dt(10, 12, 18, 40), body_daily=body, screen_sessions=sessions)
        span = time_page.build(ctx)["span"]
        self.assertIsNone(span["standout"])
        self.assertTrue(all(c["score"] == 0 for c in span["changes"]))
        self.assertEqual({c["key"]: c["state"] for c in span["changes"]},
                         {"fun": "normal", "focus": "normal", "communication": "normal", "sleep": "normal",
                          "exercise": "normal", "calendar": None})  # no calendar file: not compared
        self.assertEqual(span["compared"], 5)
        for d in span["days"]:
            self.assertIsNone(d["standout"], d["date"])
            # the last day's evening belongs to tonight's sleep, not recorded yet: sleep is not compared
            self.assertEqual(d["compared"], 4 if d["date"] == "2026-10-11" else 5, d["date"])

    def test_a_varied_usual_week_stays_quiet(self):
        # the same random habits every day: each day lands outside the middle half of something about
        # half the time, but almost never one band width outside it
        import random
        quiet_days = days = quiet_spans = spans = 0
        for seed in range(6):
            rng = random.Random(seed)
            fun = [rng.randint(100, 200) for _ in range(80)]
            work = [rng.randint(240, 420) for _ in range(80)]
            body, sessions = history(date(2026, 7, 25), date(2026, 10, 11), fun=lambda k: fun[k], work=lambda k: work[k])
            ctx = self.context(dt(10, 12, 18, 40), body_daily=body, screen_sessions=sessions)
            page = time_page.build(ctx)
            for _ in range(5):
                span = page["span"]
                spans += 1
                quiet_spans += span["standout"] is None
                for d in span["days"]:
                    days += 1
                    quiet_days += d["standout"] is None
                    if d["standout"]:
                        self.assertGreaterEqual(abs(d["standout"]["delta"]), time_page.DAY_MIN_WIDTH)
                page = time_page.build(ctx, page["prev"])
            shutil.rmtree(self.tmp / "data")
        # (with "anything outside the middle half" nearly every day and every week would name something)
        self.assertGreaterEqual(quiet_days / days, 0.85, (quiet_days, days))
        self.assertGreaterEqual(quiet_spans / spans, 2 / 3, (quiet_spans, spans))

    def test_a_week_without_exercise_reads_low(self):
        # three 50-minute workouts a week, then none at all: the 7-day average falls from about 21 minutes
        # a day to 0. Single days are 0 on four days of every week, so a band of single days would call it
        # normal; the band of 7-day averages does not.
        body, sessions = history(date(2026, 8, 20), date(2026, 10, 11), fun=lambda k: 110, work=lambda k: 440)
        workouts = weekdays_from(date(2026, 8, 20), self.WEEK - timedelta(days=1), (0, 2, 4), lambda d: {
            "start": at(d, 18), "end": at(d, 18, 50), "type": "running", "source": "Apple Watch"})
        ctx = self.context(dt(10, 12, 18, 40), body_daily=body, screen_sessions=sessions, workouts=workouts)
        span = time_page.build(ctx)["span"]
        ex = span["metrics"]["exercise"]
        self.assertEqual(span["known"]["exercise"], 7)
        self.assertEqual(ex["value"], 0)
        self.assertAlmostEqual(ex["band"]["median"], 150 / 7)
        self.assertEqual((ex["state"], ex["tone"], ex["clear"]), ("low", "bad", True))
        self.assertAlmostEqual(ex["delta"], -150 / 7)
        self.assertEqual(span["standout"]["key"], "exercise")
        # a band of single days has its bottom at 0, so 0 would sit inside it
        self.assertEqual(stats.typical(time_page.normal_series(ctx)["exercise"], self.WEEK)["q1"], 0)

    def test_a_week_without_classes_reads_low(self):
        body, sessions = history(date(2026, 8, 20), date(2026, 10, 11), fun=lambda k: 110, work=lambda k: 440)
        events = weekdays_from(date(2026, 8, 20), self.WEEK - timedelta(days=1), range(5), lambda d: {
            "start": at(d, 10), "end": at(d, 12), "title": "Lecture", "kind": "class"})
        ctx = self.context(dt(10, 12, 18, 40), body_daily=body, screen_sessions=sessions, events=events)
        span = time_page.build(ctx)["span"]
        cal = span["metrics"]["calendar"]
        self.assertEqual(span["known"]["calendar"], 7)  # the calendar file exists, the week is just empty
        self.assertEqual((cal["value"], cal["state"], cal["tone"], cal["clear"]), (0, "low", "neutral", True))
        self.assertAlmostEqual(cal["delta"], -600 / 7)
        self.assertEqual(span["standout"]["key"], "calendar")

    def test_a_day_without_screen_time_never_makes_fun_or_focus_the_standout(self):
        gap = {date(2026, 9, 14) + timedelta(days=k) for k in range(14)}  # Screen Time off for two weeks
        body, sessions = history(date(2026, 8, 1), date(2026, 10, 11), skip=gap)
        ctx = self.context(dt(10, 12, 18, 40), body_daily=body, screen_sessions=sessions)
        series = time_page.normal_series(ctx)
        self.assertFalse(gap & set(series["fun"]))  # the gap is not two weeks of zero fun
        self.assertFalse(gap & set(series["focus"]))
        # the week inside the gap: fun and focus are unknown, so they are neither standout nor compared
        p = time_page.build(ctx, "2026-09-27")
        for d in p["span"]["days"]:
            self.assertIsNone(d["totals"]["fun"], d["date"])
            if d["standout"]:
                self.assertNotIn(d["standout"]["key"], ("fun", "focus", "communication"), d["date"])
        for c in p["span"]["changes"]:
            if c["key"] in ("fun", "focus", "communication"):
                self.assertIsNone(c["value"])
                self.assertIsNone(c["state"])
                self.assertEqual(c["score"], 0)
        # back on screens with the usual habits: the normal skips the gap, so nothing reads as a jump
        # (with the gap counted as 0 the normal would sink and the usual 110 minutes of fun would look high)
        span = time_page.build(ctx)["span"]
        for key in ("fun", "focus"):
            m = span["metrics"][key]
            self.assertFalse(m["clear"], key)
            self.assertLess(abs(m["delta"]), 10, key)
        # 7-day averages with at least 4 days of screen time: 10 before the gap, 4 after it
        self.assertEqual(span["metrics"]["fun"]["band"]["days"], 14)
        self.assertIsNone(span["standout"])

    def test_tone_follows_the_better_direction(self):
        band = {"q1": 100.0, "median": 120.0, "q3": 140.0, "days": 20}
        tones = {(key, value): time_page.compare(key, value, band, 15)["tone"]
                 for key in time_page.CANDIDATES for value in (60.0, 120.0, 200.0)}
        self.assertEqual(tones[("fun", 200.0)], "bad")
        self.assertEqual(tones[("fun", 60.0)], "good")
        for key in ("focus", "exercise", "sleep"):
            self.assertEqual(tones[(key, 200.0)], "good", key)
            self.assertEqual(tones[(key, 60.0)], "bad", key)
        for key in ("communication", "calendar"):
            self.assertEqual({tones[(key, 60.0)], tones[(key, 200.0)]}, {"neutral"}, key)
        self.assertEqual({tones[(k, 120.0)] for k in time_page.CANDIDATES}, {"neutral"})  # within normal

    def test_score_is_distance_outside_in_band_widths(self):
        band = {"q1": 100.0, "median": 120.0, "q3": 140.0, "days": 20}
        self.assertEqual(time_page.score(120, band, 15), 0)
        self.assertEqual(time_page.score(140, band, 15), 0)                 # the edge is still normal
        self.assertAlmostEqual(time_page.score(180, band, 15), 40 / 40)
        self.assertAlmostEqual(time_page.score(80, band, 15), 20 / 40)
        narrow = {"q1": 10.0, "median": 12.0, "q3": 14.0, "days": 20}
        self.assertAlmostEqual(time_page.score(29, narrow, 15), 15 / 15)    # at least 15 minutes wide (7-day averages)
        self.assertAlmostEqual(time_page.score(44, narrow, 30), 30 / 30)    # at least 30 minutes wide (single days)
        steady = {"q1": 470.0, "median": 480.0, "q3": 490.0, "days": 20}
        self.assertAlmostEqual(time_page.score(538, steady, 30), 48 / 48)   # or a tenth of the usual value, if larger
        self.assertEqual(time_page.score(None, band, 15), 0)
        self.assertEqual(time_page.score(500, None, 15), 0)

    def test_values_are_compared_in_whole_minutes(self):
        band = {"q1": 100.2, "median": 120.0, "q3": 475.5, "days": 20}
        on_edge = time_page.compare("sleep", 475.57, band, 30)  # prints as the top of the normal
        self.assertEqual((on_edge["state"], on_edge["score"], on_edge["clear"]), ("normal", 0, False))
        self.assertEqual(time_page.compare("sleep", 476.6, band, 30)["state"], "high")

    def test_a_change_must_be_clearly_outside(self):
        band = {"q1": 100.0, "median": 120.0, "q3": 140.0, "days": 20}
        just = time_page.compare("fun", 170.0, band, 15)        # 30 minutes past the edge of a 40-minute band
        self.assertEqual((just["state"], just["clear"]), ("high", False))
        self.assertIsNone(time_page.standout([just]))
        clear = time_page.compare("fun", 180.0, band, 15)       # one band width past it
        self.assertTrue(clear["clear"])
        self.assertEqual(time_page.standout([just, clear]), clear)
        # a single day: communication 28 minutes above an 18-minute band is not a change (the band counts
        # as 30 minutes wide), entertainment 130 minutes above a 110-minute band is
        comms = time_page.compare("communication", 58.0, {"q1": 12.0, "median": 18.0, "q3": 30.0}, time_page.DAY_MIN_WIDTH)
        fun = time_page.compare("fun", 387.0, {"q1": 146.0, "median": 189.0, "q3": 257.0}, time_page.DAY_MIN_WIDTH)
        self.assertEqual((comms["state"], comms["clear"]), ("high", False))
        self.assertEqual(time_page.standout([comms, fun])["key"], "fun")

    def test_the_biggest_clear_change_in_minutes_is_named(self):
        # communication is further outside in band widths, but focused work moved far more minutes:
        # the sentence names focused work, so its minutes are the biggest number on the page
        comms = time_page.compare("communication", 60.0, {"q1": 10.0, "median": 15.0, "q3": 20.0}, 15)
        focus = time_page.compare("focus", 180.0, {"q1": 300.0, "median": 340.0, "q3": 380.0}, 15)
        self.assertGreater(comms["score"], focus["score"])
        self.assertTrue(comms["clear"] and focus["clear"])
        ranked = time_page.ranked([comms, focus])
        self.assertEqual([c["key"] for c in ranked], ["focus", "communication"])
        self.assertEqual(time_page.standout(ranked)["key"], "focus")
        self.assertAlmostEqual(time_page.standout(ranked)["delta"], -160)

    def test_ties_follow_the_candidate_order(self):
        band = {"q1": 100.0, "median": 120.0, "q3": 140.0, "days": 20}
        changes = [time_page.compare(k, 180.0, band, 15) for k in reversed(time_page.CANDIDATES)]
        self.assertEqual(time_page.standout(changes)["key"], "fun")
        changes = [time_page.compare("sleep", 180.0, band, 15), time_page.compare("exercise", 180.0, band, 15),
                   time_page.compare("fun", 130.0, band, 15)]
        self.assertEqual(time_page.standout(changes)["key"], "exercise")
        self.assertIsNone(time_page.standout([time_page.compare("fun", 130.0, band, 15)]))
        self.assertEqual(time_page.CANDIDATES, ("fun", "focus", "communication", "exercise", "calendar", "sleep"))


class DemoTimePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="dayring-time-demo-"))
        try:
            cls.cfg = config.load(demo.generate(cls.tmp, TODAY, NOW))
        except config.ConfigError:  # Python 3.9/3.10 without tomli
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise unittest.SkipTest("needs Python 3.11+ or tomli to read the demo dayring.toml")
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
        for v in walk(p):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                self.assertGreaterEqual(v, 0, label)
        span = p["span"]
        dates = [date.fromisoformat(d["date"]) for d in span["days"]]
        self.assertEqual(span["n"], 7, label)
        self.assertEqual(len(dates), 7, label)
        self.assertEqual(dates, sorted(dates), label)
        self.assertTrue(all(d < TODAY for d in dates), label)  # today is not over, so never in the span
        self.assertEqual((dates[-1] - dates[0]).days, 6, label)  # the demo records every day: 7 whole days in a row
        self.assertEqual(span["from"], dates[0].isoformat())
        self.assertEqual(span["to"], dates[-1].isoformat())
        self.assertEqual(p["day"], span["to"])

        for d in span["days"]:
            tot, length = d["totals"], d["minutes_in_day"]
            self.assertIn(length, (1380, 1440, 1500), d["date"])
            lanes = [tot[a] for a in ACTIVITIES if tot[a] is not None]
            for key, value in tot.items():
                if value is not None:
                    self.assertLessEqual(value, length, (d["date"], key))
            self.assertIsNotNone(tot["screen"], d["date"])  # the demo has screen time every day
            self.assertAlmostEqual(tot["screen"], sum(tot[k] for k in SCREEN_PARTS), msg=d["date"])
            if tot["not_recorded"] is not None:
                self.assertIsNotNone(tot["sleep"], d["date"])
                # recorded = length - not_recorded lies between the biggest lane and the sum of the lanes
                recorded = length - tot["not_recorded"]
                self.assertGreaterEqual(recorded + 1e-9, max(lanes), d["date"])
                self.assertLessEqual(recorded, sum(lanes) + 1e-9, d["date"])
            s = d["standout"]
            self.assertNotIn("top", d)
            if s is not None:  # what changed that day, against the 28 days before it
                self.assertIn(s["key"], time_page.CANDIDATES, d["date"])
                self.assertEqual(s["value"], tot[s["key"]], d["date"])
                self.assertIn(s["state"], ("high", "low"), d["date"])
                self.assertLessEqual(s["band"]["days"], 28)
                self.assertAlmostEqual(s["delta"], s["value"] - s["band"]["median"], msg=d["date"])
                self.assertEqual(s["tone"], stats.tone(s["state"], time_page.BETTER[s["key"]]))
                self.assertGreaterEqual(s["score"], time_page.STANDOUT_MIN, d["date"])  # clearly outside, not a wobble

        avg = span["avg"]
        for key in avg:
            values = [d["totals"][key] for d in span["days"] if d["totals"][key] is not None]
            self.assertEqual(span["known"][key], len(values), (label, key))
            if values:  # each average is over the days that have that record, never padded with zeros
                self.assertAlmostEqual(avg[key], sum(values) / len(values), msg=(label, key))
            else:
                self.assertIsNone(avg[key], (label, key))
        self.assertAlmostEqual(avg["screen"], sum(avg[k] for k in SCREEN_PARTS), msg=label)

        # what changed: every candidate once, the clear changes first (biggest in minutes first), then the
        # rest (furthest outside first); the standout is the first clear one, the screen total never one
        changes = span["changes"]
        self.assertEqual(sorted(c["key"] for c in changes), sorted(time_page.CANDIDATES), label)
        clear = [c for c in changes if c["clear"]]
        self.assertEqual(changes[:len(clear)], clear, label)
        self.assertEqual([abs(c["delta"]) for c in clear], sorted((abs(c["delta"]) for c in clear), reverse=True), label)
        rest = [c["score"] for c in changes[len(clear):]]
        self.assertEqual(rest, sorted(rest, reverse=True), label)
        for c in changes:
            self.assertEqual(c["value"], avg[c["key"]], (label, c["key"]))
            self.assertEqual(c, span["metrics"][c["key"]])
            if c["state"] in (None, "normal"):
                self.assertEqual(c["score"], 0, (label, c["key"]))
            else:
                self.assertGreater(c["score"], 0, (label, c["key"]))
            self.assertEqual(c["clear"], c["score"] >= time_page.STANDOUT_MIN, (label, c["key"]))
        if span["standout"] is None:
            self.assertEqual(clear, [], label)
        else:
            self.assertEqual(span["standout"], changes[0], label)
            self.assertTrue(span["standout"]["clear"], label)
        self.assertNotIn("top", span)
        self.assertNotIn("before", p)  # one baseline for the whole page: no "vs the 7 days before"
        screen = span["metrics"]["screen"]  # the total keeps a tile, compared once its normal exists
        self.assertIn(screen["state"], ("high", "low", "normal") if screen["band"] else (None,), label)

        # the hour chart adds up to the per-day numbers
        self.assertEqual(len(span["by_hour"]), 24)
        for key in HOUR_KEYS:
            self.assertAlmostEqual(sum(h[key] for h in span["by_hour"]), avg[key], msg=(label, key))
        if not span["untimed_exercise"]:
            self.assertAlmostEqual(sum(h["exercise"] for h in span["by_hour"]), avg["exercise"], msg=label)
        for h in span["by_hour"]:
            for key in ("sleep", "exercise", "calendar"):
                self.assertLessEqual(h[key], 60 + 1e-9, label)
            self.assertLessEqual(sum(h[k] for k in SCREEN_PARTS), 60 + 1e-9, label)

        # the workouts list is the exercise lane (the demo's workouts never overlap or cross midnight)
        starts = [w["start"] for w in span["workouts"]]
        self.assertEqual(starts, sorted(starts))
        for w in span["workouts"]:
            self.assertGreater(w["minutes"], 0)
            self.assertTrue(span["from"] <= w["start"][:10] <= span["to"], w)
        if not span["untimed_exercise"]:
            self.assertAlmostEqual(sum(w["minutes"] for w in span["workouts"]),
                                   sum(d["totals"]["exercise"] or 0 for d in span["days"]), msg=label)
        self.assertEqual(span["exercise_days"], sum(1 for d in span["days"] if (d["totals"]["exercise"] or 0) > 0))
        self.assertEqual(span["exercise_known"], sum(1 for d in span["days"] if d["totals"]["exercise"] is not None))

        # 30 days of history ending on the shown day; the 7 shown days are shaded
        hist = p["history"]
        self.assertEqual(len(hist), 30)
        hd = [date.fromisoformat(h["date"]) for h in hist]
        self.assertEqual(hd[-1], dates[-1])
        self.assertTrue(all((b - a).days == 1 for a, b in zip(hd, hd[1:])))
        self.assertEqual({h["date"] for h in hist if h["in_span"]}, {d.isoformat() for d in dates})
        by_date = {d["date"]: d["totals"] for d in span["days"]}
        for h in hist:
            if h["in_span"]:
                self.assertEqual(h["totals"], by_date[h["date"]])
        self.assertEqual(span["stale"], [], label)  # every demo record runs up to yesterday

    def test_latest_page_invariants(self):
        p = self.latest
        self.check_invariants(p)
        self.assertEqual(p["day"], (TODAY - timedelta(days=1)).isoformat())
        self.assertEqual(p["newest"], p["day"])
        self.assertIsNone(p["next"])  # nothing later than yesterday
        self.assertEqual(p["page"], "time")

    def test_missing_night_is_left_out_not_zero(self):
        # the demo watch stayed on the charger the night before 5 Oct: that day and the evening before it
        # have no full sleep record, so they show nothing for sleep and are left out of its average
        p = self.page("2026-10-11")
        days = {d["date"]: d["totals"] for d in p["span"]["days"]}
        self.assertIsNone(days["2026-10-05"]["sleep"])
        self.assertIsNone(days["2026-10-05"]["not_recorded"])
        known = [t["sleep"] for t in days.values() if t["sleep"] is not None]
        self.assertEqual(p["span"]["known"]["sleep"], 6)
        self.assertAlmostEqual(p["span"]["avg"]["sleep"], sum(known) / 6)
        self.assertGreater(p["span"]["avg"]["sleep"], 7 * 60)  # not dragged towards 6h by a zero night
        hist = {h["date"]: h["totals"] for h in p["history"]}
        self.assertIsNone(hist["2026-10-05"]["sleep"])  # drawn as × in the 30-day lanes

    def test_clock_change_day_is_23_hours(self):
        p = self.page("2026-10-04")
        days = {d["date"]: d for d in p["span"]["days"]}
        self.assertEqual(days["2026-10-04"]["minutes_in_day"], 1380)
        self.assertEqual(days["2026-10-03"]["minutes_in_day"], 1440)

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

    def test_demo_never_names_the_screen_total(self):
        # screens are the biggest waking activity on every demo day; the page still names something else
        for param in (None, "2026-10-04", "2026-09-27"):
            p = self.page(param)
            for d in p["span"]["days"]:
                tot = d["totals"]
                self.assertGreater(tot["screen"], max(tot["exercise"] or 0, tot["calendar"] or 0), d["date"])
                if d["standout"]:
                    self.assertNotEqual(d["standout"]["key"], "screen")

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
        self.tmp = Path(tempfile.mkdtemp(prefix="dayring-time-ah-"))
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
        text = (ROOT / "dayring" / "web" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertRegex(text, r'const ALIAS\s*=\s*\{[^}]*\battention\s*:\s*"time"')
        self.assertIn("ALIAS[raw]", text)  # route() resolves the alias before picking the page
        nav = re.search(r"const NAV\s*=\s*\[([^\]]*)\]", text)
        self.assertIsNotNone(nav)
        self.assertIn('"time"', nav.group(1))
        self.assertNotIn('"attention"', nav.group(1))

    def test_no_leftovers_of_the_biggest_activity_and_the_week_before(self):
        i18n = (ROOT / "dayring" / "web" / "js" / "i18n.js").read_text(encoding="utf-8")
        for key in ("time.top_line", "time.top_days", "time.no_top", "time.vs", "time.before", "time.same", "act.screen_lower"):
            self.assertNotIn(f'"{key}"', i18n, key)
        page = (ROOT / "dayring" / "web" / "js" / "pages" / "time.js").read_text(encoding="utf-8")
        for code in ("S.top", "p.before", "top_counts"):
            self.assertNotIn(code, page, code)
        icons = (ROOT / "dayring" / "web" / "js" / "icons.js").read_text(encoding="utf-8")
        for key in time_page.CANDIDATES + ("check", "up", "down"):
            self.assertRegex(icons, rf"\b{key}: '<", key)
        for key in time_page.CANDIDATES:
            self.assertEqual(i18n.count(f'"chg.{key}"'), 2, key)  # English and Chinese
            self.assertEqual(i18n.count(f'"chg.short.{key}"'), 2, key)

    def test_time_page_is_registered_and_named(self):
        self.assertIn("time", PAGES)
        self.assertNotIn("attention", PAGES)
        i18n = (ROOT / "dayring" / "web" / "js" / "i18n.js").read_text(encoding="utf-8")
        self.assertEqual(i18n.count('"nav.time"'), 2)  # English and Chinese
        for page in (ROOT / "dayring" / "web" / "js").rglob("*.js"):
            self.assertNotIn('href="#attention', page.read_text(encoding="utf-8"), page.name)


if __name__ == "__main__":
    unittest.main()
