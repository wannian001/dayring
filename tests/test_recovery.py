"""Recovery: workout effort from Apple Health, the training load built from it, soreness check-ins, and the page.

Rules under test (healthaio/importers/apple_health.py, healthaio/soreness.py, healthaio/modules/recovery.py,
healthaio/modules/actions.py):
- a workout's effort is your own rating when there is one, else the watch's estimate; an effort sample belongs to the
  workout it starts within two minutes of, or covers for at least half; a phone package carries it the same way
- load = effort x minutes per day; the last 7 days against the weekly average of the 28 before; minutes without an
  effort are left out and counted, and with under half of the minutes rated the load says it is unsure
- a check-in replaces that morning's rows only; nothing tapped writes "none"; a day without rows is unknown
- only this app's own page may save a check-in
- a region clearly or very sore this morning, with training planned, gives "spare the sore parts"
"""
import json
import re
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path

from healthaio import capture, config, demo, soreness
from healthaio.config import Config
from healthaio.context import Context
from healthaio.importers import apple_health
from healthaio.modules import actions, followup, recovery, today
from healthaio.server import make_handler, payload
from healthaio.store import Store, write_table

TZ = "Australia/Melbourne"
TODAY = date(2026, 10, 12)
NOW = datetime(2026, 10, 12, 18, 40)
HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n<HealthData locale="en_AU">\n <ExportDate value="2026-10-12 14:30:00 +1100"/>\n'
WEB = Path(__file__).resolve().parents[1] / "healthaio" / "web"


def workout(kind, start, end, minutes):
    return (f' <Workout workoutActivityType="HKWorkoutActivityType{kind}" duration="{minutes}" durationUnit="min" '
            f'sourceName="Apple Watch" startDate="{start}" endDate="{end}"/>\n')


def effort(start, end, value, rated=True, source="Apple Watch"):
    kind = apple_health.EFFORT_RATED if rated else apple_health.EFFORT_ESTIMATED
    return (f' <Record type="{kind}" sourceName="{source}" unit="appleEffortScore" '
            f'startDate="{start}" endDate="{end}" value="{value}"/>\n')


class Folder(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-recovery-"))
        self.cfg = Config(root=self.tmp, data_dir=self.tmp / "data", timezone=TZ)
        self.cfg.data_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ctx(self):
        return Context(self.cfg, now=NOW)

    def workouts(self):
        loaded = Store(self.cfg.data_dir).load("workouts")
        self.assertEqual(loaded.problems, [])
        return loaded.rows


class Effort(Folder):
    def run_import(self, body):
        path = self.tmp / "export.xml"
        path.write_text(HEAD + body + "</HealthData>\n", encoding="utf-8")
        return apple_health.import_apple_health(path, self.cfg)

    def test_your_rating_wins_over_the_watch_estimate(self):
        a, b = "2026-10-10 17:00:00 +1100", "2026-10-10 17:50:00 +1100"
        self.run_import(workout("TraditionalStrengthTraining", a, b, 50) + effort(a, b, 5, rated=False) + effort(a, b, 7))
        (row,) = self.workouts()
        self.assertEqual((row["effort"], row["effort_source"]), (7, "rated"))

    def test_the_estimate_fills_in_and_a_far_sample_does_not_match(self):
        a, b = "2026-10-10 07:00:00 +1100", "2026-10-10 07:30:00 +1100"
        c, d = "2026-10-11 07:00:00 +1100", "2026-10-11 07:30:00 +1100"
        self.run_import(workout("Running", a, b, 30) + effort(a, b, 4, rated=False)
                        + workout("Running", c, d, 30) + effort("2026-10-11 09:00:00 +1100", "2026-10-11 09:10:00 +1100", 9))
        first, second = sorted(self.workouts(), key=lambda r: r["start"])
        self.assertEqual((first["effort"], first["effort_source"]), (4, "estimated"))
        self.assertIsNone(second["effort"])  # an hour and a half later: another workout's, or nobody's

    def test_a_package_from_the_phone_carries_effort_too(self):
        data = json.loads((Path(__file__).parent / "fixtures" / "capture" / "health_3days.json").read_text())
        run = data["workouts"][0]
        data["package_id"] = "ios-effort-1"
        data["records"].append({"type": apple_health.EFFORT_RATED, "sourceName": "Apple Watch", "device": "Watch",
                                "unit": "appleEffortScore", "startDate": run["startDate"], "endDate": run["endDate"], "value": "6"})
        status, receipt = capture.receive(self.cfg, json.dumps(data).encode(), {"id": "d_1"})
        self.assertEqual((status, receipt["status"]), (200, "projected"))
        self.assertTrue(any(r["effort"] == 6 and r["effort_source"] == "rated" for r in self.workouts()))


class Load(Folder):
    def rows(self, days, effort_of=lambda k: 6, minutes=50):
        out = []
        for k in range(days):
            d = TODAY - timedelta(days=k)
            if k % 2 == 0:
                start = datetime.combine(d, datetime.min.time()).replace(hour=17)
                e = effort_of(k)
                out.append({"start": start, "end": start + timedelta(minutes=minutes), "type": "running",
                            "effort": e, "effort_source": "rated" if e else None})
        return out

    def test_the_week_against_the_four_before(self):
        rows = self.rows(40, effort_of=lambda k: 9 if k < 7 else 5)
        write_table(self.cfg.data_dir, "workouts", rows)
        L = recovery.load_summary(recovery.daily_load(self.ctx(), TODAY), TODAY)
        self.assertEqual(L["acute"], 4 * 9 * 50)  # days 0, 2, 4, 6
        self.assertAlmostEqual(L["chronic"], 14 * 5 * 50 / 4)  # days 8..34, every other day
        self.assertEqual(L["state"], "high")
        self.assertAlmostEqual(L["ratio"], 1800 / 875)

    def test_too_few_ratings_says_so(self):
        write_table(self.cfg.data_dir, "workouts", self.rows(40, effort_of=lambda k: 6 if k % 6 == 0 else None))
        L = recovery.load_summary(recovery.daily_load(self.ctx(), TODAY), TODAY)
        self.assertEqual(L["state"], "few_ratings")
        self.assertGreater(L["unrated_min"], 0)

    def test_without_a_workout_record_there_is_no_load(self):
        page = payload(self.cfg, "recovery", None, NOW)
        self.assertEqual(page["load"]["state"], "none")
        self.assertTrue(all(d["load"] is None for d in page["load_days"]))


class Soreness(Folder):
    def rows(self):
        return [(r["date"].isoformat(), r["region"], r["level"]) for r in Store(self.cfg.data_dir).rows("soreness")]

    def test_a_check_in_replaces_that_morning_only(self):
        soreness.save(self.cfg, date(2026, 10, 11), {"torso": 2})
        soreness.save(self.cfg, date(2026, 10, 12), {"left_calf": 1, "pelvis": 3})
        soreness.save(self.cfg, date(2026, 10, 12), {"right_calf": 2})
        self.assertEqual(self.rows(), [("2026-10-11", "torso", 2), ("2026-10-12", "right_calf", 2)])

    def test_nothing_tapped_is_a_morning_with_nothing_sore(self):
        soreness.save(self.cfg, date(2026, 10, 12), {})
        self.assertEqual(self.rows(), [("2026-10-12", "none", 0)])
        log = recovery.soreness_log(self.ctx())
        self.assertEqual(log, {date(2026, 10, 12): {}})
        self.assertNotIn(date(2026, 10, 11), log)  # not checked: unknown

    def test_bad_check_ins_are_refused(self):
        for levels in ({"thigh": 1}, {"torso": 4}, {"torso": True}, ["torso"]):
            with self.assertRaises(soreness.SorenessError, msg=levels):
                soreness.check(levels)
        with self.assertRaises(soreness.SorenessError):
            soreness.from_browser(self.cfg, {"date": "2026-10-13", "levels": {}}, NOW)  # tomorrow
        self.assertEqual(soreness.check({"torso": 0, "head": None, "left_calf": 2}), {"left_calf": 2})

    def test_a_hand_written_row_that_does_not_parse_survives(self):
        (self.cfg.data_dir / "soreness.csv").write_text("date,region,level\n2026-10-01,knee,2\n2026-10-12,torso,1\n")
        soreness.save(self.cfg, date(2026, 10, 12), {"head": 1})
        text = (self.cfg.data_dir / "soreness.csv").read_text()
        self.assertIn("2026-10-01,knee,2", text)
        self.assertNotIn("torso", text)

    def test_spare_the_sore_parts_when_training_is_planned(self):
        self.cfg.training = {"mon": "Gym 50 min"}
        soreness.save(self.cfg, TODAY, {"left_calf": 2, "torso": 1})
        ctx = self.ctx()
        out = actions.build(ctx, TODAY, today.recovery(ctx, TODAY), {"worse": []})
        item = next(x for x in out["items"] if x["domain"] == "training")
        self.assertEqual((item["key"], item["params"]["regions"]), ("spare", ["left_calf"]))  # only clearly or very sore
        self.assertFalse(followup.check(ctx, item, TODAY, {})["checked"])  # training advice is not checked


class Endpoint(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-sore-"))
        try:
            self.cfg = config.load(demo.generate(self.tmp, TODAY, NOW))
        except config.ConfigError:
            raise unittest.SkipTest("needs Python 3.11+ or tomli")
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.cfg, lambda: NOW))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def post(self, body, origin="same"):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = f"http://127.0.0.1:{self.port}" if origin == "same" else origin
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/soreness", data=json.dumps(body).encode(),
                                         headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    def test_the_page_saves_and_recovery_shows_it(self):
        status, out = self.post({"date": TODAY.isoformat(), "levels": {"pelvis": 3}})
        self.assertEqual((status, out["ok"]), (200, True))
        page = payload(self.cfg, "recovery", None, NOW)
        self.assertEqual((page["soreness"]["today"], page["soreness"]["levels"]), (True, {"pelvis": 3}))

    def test_only_this_apps_own_page_may_write(self):
        before = (self.cfg.data_dir / "soreness.csv").read_text()
        for origin in ("http://evil.example", None):
            self.assertEqual(self.post({"date": TODAY.isoformat(), "levels": {"head": 1}}, origin=origin)[0], 403)
        self.assertEqual(self.post({"date": TODAY.isoformat(), "levels": {"knee": 1}})[0], 400)
        self.assertEqual((self.cfg.data_dir / "soreness.csv").read_text(), before)


class Demo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="healthaio-recovery-demo-"))
        try:
            cls.cfg = config.load(demo.generate(cls.tmp, TODAY, NOW))
        except config.ConfigError:
            raise unittest.SkipTest("needs Python 3.11+ or tomli")
        cls.page = payload(cls.cfg, "recovery", None, NOW)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_page_agrees_with_today(self):
        p = self.page
        json.dumps(p)
        self.assertEqual(p["recovery"], payload(self.cfg, "today", None, NOW)["recovery"])
        self.assertEqual(len(p["load_days"]), recovery.CHART_DAYS)
        self.assertEqual(p["load_days"][-1]["date"], TODAY.isoformat())
        self.assertEqual(len(p["response"]["rows"]), len(recovery.OUTCOMES))
        for row in p["response"]["rows"]:
            if row["status"] == "ok":
                self.assertEqual(row["detected"], row["p_adjusted"] < 0.05)

    def test_the_demo_rates_most_workouts_and_checks_in(self):
        rows = Store(self.cfg.data_dir).rows("workouts")
        rated = [r for r in rows if r["effort"] is not None]
        self.assertGreater(len(rated) / len(rows), 0.8)
        self.assertGreater(self.page["load"]["rated_share"], 0.8)
        self.assertGreater(self.page["soreness"]["checked"], 5)
        self.assertEqual({r["key"] for r in self.page["soreness"]["regions"]}, set(recovery.SORE_REGIONS))

    def test_words_and_figure_files_exist(self):
        i18n = (WEB / "js" / "i18n.js").read_text(encoding="utf-8")
        page = (WEB / "js" / "pages" / "recovery.js").read_text(encoding="utf-8")
        used = set(re.findall(r't\("((?:rec|sore)\.[\w.]+)"', page))
        used |= {f"sore.region.{r}" for r in recovery.SORE_REGIONS} | {f"sore.level.{k}" for k in range(4)}
        used |= {f"rec.out.{o}" for o in recovery.OUTCOMES} | {f"rec.out.{o}.{d}" for o in recovery.OUTCOMES for d in ("up", "down")}
        used |= {f"rec.load.{s}" for s in ("high", "low", "steady", "none", "unknown", "few_ratings")}
        used |= {"nav.recovery", "todo.spare", "todo.short.spare", "fu.name.spare"}
        for key in used:
            self.assertEqual(i18n.count(f'"{key}"'), 2, key)
        for sex in ("male", "female"):
            self.assertTrue((WEB / "img" / f"body-{sex}-reference.png").is_file())
            for region in recovery.SORE_REGIONS:
                self.assertTrue((WEB / "img" / f"body-mask-{sex}-{region}.png").is_file(), (sex, region))

    def test_the_figure_follows_the_setting(self):
        self.assertEqual(self.page["figure"], "male")
        path = self.tmp / "healthaio.toml"
        text = path.read_text()
        path.write_text(text.replace("[healthaio]\n", '[healthaio]\nfigure = "female"\n', 1))
        try:
            self.assertEqual(config.load(path).figure, "female")
            path.write_text(text.replace("[healthaio]\n", '[healthaio]\nfigure = "robot"\n', 1))
            with self.assertRaises(config.ConfigError):
                config.load(path)
        finally:
            path.write_text(text)


if __name__ == "__main__":
    unittest.main()
