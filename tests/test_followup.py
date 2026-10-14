"""Following advice up: the daytime screen item on Today, and the Follow-up page.

Rules under test (healthaio/modules/actions.py, followup.py):
- daytime screens get an item when entertainment & social is over the plan, or over your normal when there is no
  plan (the Drain page's judgement); the cap is the plan, or your usual day rounded to half hours
- a past day's advice is rebuilt with the Today page's rules and checked against the data afterwards; no record is
  not a miss; training advice is listed, not checked
- advice missed on 3 of its last 5 times gets other ways, and their numbers agree with each other
- every way and fact the server can name has words in English and Chinese
"""
import re
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from healthaio import config, demo
from healthaio.config import Config
from healthaio.context import Context
from healthaio.modules import actions, followup, static_params, today
from healthaio.server import payload
from healthaio.store import write_table

TODAY = date(2026, 10, 12)
NOW = datetime(2026, 10, 12, 18, 40)
WEB = Path(__file__).resolve().parents[1] / "healthaio" / "web" / "js"


def at(day, hh, mm=0):
    return datetime.combine(day, datetime.min.time()).replace(hour=hh, minute=mm)


def fun(day, hours):
    """``hours`` of entertainment in the afternoon of ``day``."""
    start = at(day, 13)
    return {"start": start, "end": start + timedelta(hours=hours), "device": "phone", "app": "Video", "category": "entertainment"}


class Folder(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-followup-"))
        self.cfg = Config(root=self.tmp, data_dir=self.tmp, timezone="Australia/Melbourne")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ctx(self):
        return Context(self.cfg, now=NOW)

    def advice(self, drain):
        ctx = self.ctx()
        return actions.build(ctx, TODAY, today.recovery(ctx, TODAY), drain)


class ScreenItem(Folder):
    def test_over_the_plan_caps_today_at_the_plan(self):
        self.cfg.screen.entertainment_max_hours = 2
        write_table(self.tmp, "screen_sessions", [fun(TODAY - timedelta(days=k), 3) for k in range(1, 8)])
        out = self.advice({"worse": [], "plan_off": [{"key": "fun", "over": 60}]})
        item = next(x for x in out["items"] if x["domain"] == "screen")
        self.assertEqual((item["key"], item["params"]), ("fun_cap", {"hours": 2, "source": "plan"}))
        self.assertAlmostEqual(item["why"]["avg"], 180)

    def test_within_the_plan_says_nothing_even_above_your_normal(self):
        self.cfg.screen.entertainment_max_hours = 4
        write_table(self.tmp, "screen_sessions", [fun(TODAY - timedelta(days=k), 3) for k in range(1, 8)])
        out = self.advice({"worse": ["fun"], "plan_off": []})
        self.assertFalse([x for x in out["items"] if x["domain"] == "screen"])

    def test_without_a_plan_the_cap_is_your_usual_day(self):
        # four weeks of about an hour and a quarter, then a week of three hours
        rows = [fun(TODAY - timedelta(days=k), 3) for k in range(1, 8)]
        rows += [fun(TODAY - timedelta(days=k), 1.25) for k in range(8, 36)]
        write_table(self.tmp, "screen_sessions", rows)
        out = self.advice({"worse": ["fun"], "plan_off": []})
        item = next(x for x in out["items"] if x["domain"] == "screen")
        self.assertEqual(item["params"], {"hours": 1.0, "source": "normal"})  # 75 min to the nearest half hour

    def test_too_few_screen_days_say_nothing(self):
        self.cfg.screen.entertainment_max_hours = 2
        write_table(self.tmp, "screen_sessions", [fun(TODAY - timedelta(days=k), 3) for k in range(1, 3)])
        self.assertTrue(self.advice({"worse": [], "plan_off": [{"key": "fun", "over": 60}]})["steady"])


class Check(Folder):
    def test_asleep_by_allows_fifteen_minutes_and_no_record_is_not_a_miss(self):
        d = TODAY - timedelta(days=3)
        write_table(self.tmp, "body_daily", [
            {"date": d + timedelta(days=1), "sleep_start": at(d + timedelta(days=1), 0, 40), "sleep_end": at(d + timedelta(days=1), 8)},
            {"date": d + timedelta(days=2), "sleep_start": at(d + timedelta(days=2), 1, 10), "sleep_end": at(d + timedelta(days=2), 9)}])
        item = lambda day: {"key": "asleep_by", "params": {"clock": at(day + timedelta(days=1), 0, 30).isoformat(timespec="minutes")}}
        ctx = self.ctx()
        ok = followup.check(ctx, item(d), d, {})
        self.assertEqual((ok["met"], ok["fact"]["late_min"]), (True, 10))
        late = followup.check(ctx, item(d + timedelta(days=1)), d + timedelta(days=1), {})
        self.assertEqual((late["met"], late["fact"]["late_min"]), (False, 40))
        none = followup.check(ctx, item(d + timedelta(days=2)), d + timedelta(days=2), {})
        self.assertEqual((none["checked"], none["met"], none["fact"]), (True, None, None))

    def test_fun_cap_counts_the_whole_day(self):
        d = TODAY - timedelta(days=2)
        write_table(self.tmp, "screen_sessions", [fun(d, 4), fun(d + timedelta(days=1), 1)])
        ctx = self.ctx()
        out = followup.check(ctx, {"key": "fun_cap", "params": {"hours": 3}}, d, {})
        self.assertEqual((out["met"], out["fact"]["minutes"]), (False, 240))
        self.assertTrue(followup.check(ctx, {"key": "fun_cap", "params": {"hours": 3}}, d + timedelta(days=1), {})["met"])

    def test_training_is_listed_but_not_checked(self):
        for key in ("ease", "deload", "move", "strength"):
            self.assertEqual(followup.check(self.ctx(), {"key": key, "params": {}}, TODAY - timedelta(days=1), {}),
                             {"checked": False, "met": None, "fact": None}, key)


class Ways(unittest.TestCase):
    def test_a_smaller_sleep_step_moves_the_phone_time_with_it(self):
        given = [{"params": {"clock": "2026-10-10T00:30"}, "fact": {"asleep": f"2026-10-{d:02d}T02:30"}} for d in (8, 9, 10)]
        ways = {w["kind"]: w["params"] for w in followup.ways("asleep_by", given, {"phone_away": "2026-10-12T00:00"})}
        self.assertEqual(ways["smaller"], {"clock": "01:30"})  # halfway from 02:30 to 00:30
        self.assertEqual(ways["setting"], {"clock": "01:00"})  # Downtime 30 minutes before the smaller step
        self.assertEqual(ways["if_then"], {"clock": "01:00"})

    def test_no_smaller_step_when_halfway_is_the_target(self):
        given = [{"params": {"clock": "2026-10-10T00:30"}, "fact": {"asleep": "2026-10-11T00:40"}}]
        ways = followup.ways("asleep_by", given, {"phone_away": "2026-10-12T00:00"})
        self.assertNotIn("smaller", [w["kind"] for w in ways])
        self.assertEqual(ways[0], {"kind": "setting", "params": {"clock": "00:00"}})

    def test_a_smaller_screen_step_is_also_the_app_limit(self):
        given = [{"params": {"hours": 3, "source": "plan"}, "fact": {"minutes": 300}} for _ in range(3)]
        ways = {w["kind"]: w["params"] for w in followup.ways("fun_cap", given, None)}
        self.assertEqual(ways["smaller"], {"hours": 4.0})
        self.assertEqual(ways["setting"], {"hours": 4.0})

    def test_late_meal_without_a_clock_falls_back_on_hours(self):
        given = [{"params": {"clock": None, "hours": 3}, "fact": {"last": "2026-10-10T22:30", "gap_h": 1}}]
        self.assertEqual(followup.ways("late_meal", given, None), [{"kind": "if_then", "params": {"clock": None, "hours": 3}}])


class Words(unittest.TestCase):
    def test_every_way_and_fact_has_words_in_both_languages(self):
        i18n = (WEB / "i18n.js").read_text(encoding="utf-8")
        page = (WEB / "pages" / "followup.js").read_text(encoding="utf-8")
        source = (Path(followup.__file__)).read_text(encoding="utf-8")
        kinds = set(re.findall(r'"kind": "(\w+)"', source))
        self.assertEqual(kinds, {"smaller", "setting", "place", "if_then"})
        keys = [k for k in followup.CHECKED]
        ways = {(kind, key) for key in keys for kind in kinds if f'fu.way.{kind}.{key}"' in i18n}
        for kind, key in ways:
            self.assertEqual(i18n.count(f'"fu.way.{kind}.{key}"'), 2, (kind, key))
        # each key has at least an if-then plan, and no way is named only in one language
        for key in keys:
            self.assertIn(("if_then", key), ways, key)
        used = set(re.findall(r't\("((?:fu|todo)\.[\w.]+)"', page)) | {f"fu.kind.{k}" for k in kinds}
        used |= {f"fu.name.{k}" for k in actions.KEYS}
        used |= {"todo.fun_cap", "todo.short.fun_cap_plan", "todo.short.fun_cap_normal", "todo.domain.screen", "fu.way.if_then.late_meal_h"}
        for key in used:
            self.assertEqual(i18n.count(f'"{key}"'), 2, key)


class Demo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="healthaio-followup-demo-"))
        try:
            cls.cfg = config.load(demo.generate(cls.tmp, TODAY, NOW))
        except config.ConfigError:
            raise unittest.SkipTest("needs Python 3.11+ or tomli to read the demo healthaio.toml")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_a_rebuild_gives_what_the_today_page_said(self):
        ctx = Context(self.cfg, now=NOW)
        self.assertEqual(followup.advice_on(ctx, TODAY), payload(self.cfg, "today", None, NOW)["actions"])

    def test_the_page_checks_yesterday_and_offers_other_ways(self):
        page = payload(self.cfg, "followup", None, NOW)
        self.assertEqual(page["yesterday"]["date"], (TODAY - timedelta(days=1)).isoformat())
        self.assertEqual(len(page["dates"]), followup.DAYS)
        for row in page["rows"]:
            self.assertLessEqual(row["kept"], row["known"])
            self.assertLessEqual(row["known"], row["given"])
            self.assertEqual(bool(row["ways"]), row["stuck"])
        # the demo person is a night owl: the asleep-by advice keeps failing, so it gets other ways
        self.assertIn("asleep_by", page["stuck"])
        self.assertEqual(static_params("followup", Context(self.cfg, now=NOW)), [None])


if __name__ == "__main__":
    unittest.main()
