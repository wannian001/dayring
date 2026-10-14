"""Load (#load): what each week asks of the body (training load) and of the mind (classes and work, the share of grade
due), the 8 weeks behind and the 4 ahead, each against your usual weeks.

Rules under test (healthaio/modules/load.py):
- weeks run Monday to Sunday; this week counts what is done plus what is still planned
- usual = the middle half of the 8 full weeks before this one, from at least 4
- a week ahead is never judged on training (a plan is not a load); it is flagged to plan lighter when classes or
  deadlines are heavier than usual and the plan still holds the usual number of sessions
- body and mind are "stacked" when training and the mind's side are both heavier than usual
- nothing is added into one number
"""
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from healthaio import config, demo
from healthaio.config import Config
from healthaio.context import Context
from healthaio.modules import load
from healthaio.server import payload
from healthaio.store import write_table

TZ = "Australia/Melbourne"
TODAY = date(2026, 10, 14)  # a Wednesday
NOW = datetime(2026, 10, 14, 18, 40)
MONDAY = TODAY - timedelta(days=TODAY.weekday())


class Folder(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-load-"))
        self.cfg = Config(root=self.tmp, data_dir=self.tmp / "data", timezone=TZ)
        self.cfg.data_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self):
        return load.build(Context(self.cfg, now=NOW))

    def write(self, heavy_week=None, deadline_weeks=(), lecture_hours=3):
        """Ten weeks of three runs a week (effort 5, 40 min), a 3-hour lecture block on Mondays and Thursdays, and a
        10% assignment in the weeks given (week offsets from this one)."""
        workouts, events, deadlines = [], [], []
        for w in range(-9, 5):
            ws = MONDAY + timedelta(days=7 * w)
            for k in (0, 2, 4):
                d = ws + timedelta(days=k)
                if d < TODAY - timedelta(days=0) or (d == TODAY):
                    effort = 9 if w == heavy_week else 5
                    start = datetime.combine(d, datetime.min.time()).replace(hour=7)
                    if d < TODAY:
                        workouts.append({"start": start, "end": start + timedelta(minutes=40), "type": "running", "effort": effort, "effort_source": "rated"})
            for k in (0, 3):
                start = datetime.combine(ws + timedelta(days=k), datetime.min.time()).replace(hour=10)
                events.append({"start": start, "end": start + timedelta(hours=lecture_hours * (3 if w == heavy_week else 1)), "title": "Lecture", "kind": "class"})
            if w in deadline_weeks:
                deadlines.append({"due": datetime.combine(ws + timedelta(days=4), datetime.min.time()).replace(hour=23, minute=59),
                                  "title": f"Assignment {w}", "weight_pct": 30, "status": "todo"})
        write_table(self.cfg.data_dir, "workouts", workouts)
        write_table(self.cfg.data_dir, "events", events)
        write_table(self.cfg.data_dir, "deadlines", deadlines)


class Weeks(Folder):
    def test_thirteen_weeks_and_this_one_in_the_middle(self):
        self.write()
        p = self.build()
        self.assertEqual(len(p["weeks"]), load.PAST_WEEKS + 1 + load.AHEAD_WEEKS)
        self.assertEqual(p["this_week"]["start"], MONDAY.isoformat())
        self.assertEqual([w["when"] for w in p["weeks"]].count("now"), 1)
        past = p["weeks"][0]
        self.assertEqual(past["training"], 3 * 5 * 40)
        self.assertEqual(past["calendar"], 6)
        self.assertEqual(past["state"], {"training": "normal", "calendar": "normal", "deadlines": "normal"})

    def test_a_heavy_past_week_reads_stacked_when_the_mind_is_loaded_too(self):
        self.write(heavy_week=-2)
        week = next(w for w in self.build()["weeks"] if w["start"] == (MONDAY - timedelta(days=14)).isoformat())
        self.assertEqual((week["state"]["training"], week["state"]["calendar"]), ("high", "high"))
        self.assertTrue(week["stacked"])

    def test_a_week_ahead_is_not_judged_on_training_but_flagged_to_plan_lighter(self):
        self.cfg.training = {"mon": "Run 40 min", "wed": "Run 40 min", "fri": "Run 40 min"}
        self.write(deadline_weeks=(2,))
        p = self.build()
        ahead = {w["start"]: w for w in p["weeks"] if w["when"] == "ahead"}
        heavy = ahead[(MONDAY + timedelta(days=14)).isoformat()]
        self.assertIsNone(heavy["state"]["training"])
        self.assertEqual(heavy["state"]["deadlines"], "high")
        self.assertTrue(heavy["plan_lighter"])
        self.assertEqual(heavy["planned_sessions"], 3)
        quiet = ahead[(MONDAY + timedelta(days=7)).isoformat()]
        self.assertFalse(quiet["plan_lighter"])
        self.assertEqual(p["heaviest"]["start"], heavy["start"])

    def test_this_week_is_done_plus_planned(self):
        self.cfg.training = {"mon": "Run 40 min", "wed": "Run 40 min", "fri": "Run 40 min"}
        self.write()
        now = self.build()["this_week"]
        self.assertEqual(now["training"], 5 * 40)  # Monday's run; today's is not on record yet
        self.assertEqual(now["planned_sessions"], 1)  # Friday
        self.assertEqual(now["planned"], 200)

    def test_too_few_weeks_have_no_usual(self):
        self.write()
        write_table(self.cfg.data_dir, "events", [])
        p = self.build()
        self.assertEqual(p["bands"]["calendar"], {"q1": 0, "median": 0, "q3": 0, "weeks": 8})  # an empty calendar is 0 hours
        write_table(self.cfg.data_dir, "workouts", [])
        self.assertIsNone(self.build()["bands"]["training"])


class Demo(unittest.TestCase):
    def test_the_demo_page_builds(self):
        tmp = Path(tempfile.mkdtemp(prefix="healthaio-load-demo-"))
        try:
            try:
                cfg = config.load(demo.generate(tmp, TODAY, NOW))
            except config.ConfigError:
                raise unittest.SkipTest("needs Python 3.11+ or tomli")
            p = payload(cfg, "load", None, NOW)
            self.assertEqual(p["this_week"]["start"], MONDAY.isoformat())
            self.assertIsNotNone(p["bands"]["training"])
            self.assertTrue(any(w["deadlines"] for w in p["weeks"]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
