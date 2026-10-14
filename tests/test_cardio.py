"""Cardio fitness (VO2 max) on the Weight & fitness page, and Tomorrow will be better on Follow-up.

Rules under test (healthaio/modules/body.py cardio(), healthaio/modules/followup.py):
- the level is the median of the last 30 days' estimates; it is set against the median of those 75 to 120 days back
  (at least 2), and a change under 1 mL/kg/min reads as about the same; without data there is no level
- Today has a cardio line; Data sources has a VO2 max stream from the watch
- Follow-up carries what has helped the next day (it used to be on the Weekly review page)
"""
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from healthaio import config, demo
from healthaio.config import Config
from healthaio.context import Context
from healthaio.modules import body
from healthaio.server import payload
from healthaio.store import write_table

TODAY = date(2026, 10, 12)
NOW = datetime(2026, 10, 12, 18, 40)


class Cardio(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-cardio-"))
        self.cfg = Config(root=self.tmp, data_dir=self.tmp / "data", timezone="Australia/Melbourne")
        self.cfg.data_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def level(self, estimates):
        write_table(self.cfg.data_dir, "body_daily", [{"date": TODAY - timedelta(days=k), "vo2max": v} for k, v in estimates])
        return body.cardio(Context(self.cfg, now=NOW), TODAY)

    def test_the_level_against_three_months_ago(self):
        c = self.level([(2, 44.0), (9, 43.0), (20, 45.0), (80, 42.0), (100, 41.5), (110, 42.5)])
        L = c["latest"]
        self.assertEqual((L["level"], L["n"], L["then"]), (44.0, 3, 42.0))
        self.assertEqual(L["state"], "up")
        self.assertEqual(len(c["points"]), 6)

    def test_a_small_change_is_about_the_same(self):
        self.assertEqual(self.level([(2, 42.5), (80, 42.0), (100, 41.8)])["latest"]["state"], "steady")
        self.assertEqual(self.level([(2, 40.5), (80, 42.0), (100, 41.8)])["latest"]["state"], "down")

    def test_too_few_earlier_estimates_compare_nothing(self):
        L = self.level([(2, 44.0), (90, 41.0)])["latest"]
        self.assertIsNone(L["then"])
        self.assertIsNone(L["state"])

    def test_no_estimates_no_level(self):
        write_table(self.cfg.data_dir, "body_daily", [{"date": TODAY, "resting_hr": 60}])
        self.assertIsNone(body.cardio(Context(self.cfg, now=NOW), TODAY)["latest"])


class Demo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="healthaio-cardio-demo-"))
        try:
            cls.cfg = config.load(demo.generate(cls.tmp, TODAY, NOW))
        except config.ConfigError:
            raise unittest.SkipTest("needs Python 3.11+ or tomli")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_every_page_has_it(self):
        self.assertIsNotNone(payload(self.cfg, "body", None, NOW)["cardio"]["latest"])
        self.assertIsNotNone(payload(self.cfg, "today", None, NOW)["summary"]["cardio"])
        streams = {s["key"]: s for s in payload(self.cfg, "data", None, NOW)["streams"]}
        self.assertEqual(streams["vo2max"]["device"], "watch")

    def test_follow_up_says_what_helps_the_next_day(self):
        effects = payload(self.cfg, "followup", None, NOW)["effects"]
        self.assertTrue(effects["outcomes"])
        self.assertEqual(effects, payload(self.cfg, "today", None, NOW)["effects"])  # the Today line agrees with it
