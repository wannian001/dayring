"""Goals set on the Goals page (and proposed by an assistant): the log, the Goals page, the one write endpoint, the CLI."""
import contextlib
import io
import json
import re
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

from healthaio import config, demo, goal_log
from healthaio.__main__ import main
from healthaio.server import make_handler, payload

TODAY = date(2026, 10, 12)
NOW = datetime(2026, 10, 12, 18, 40)
WEB = Path(__file__).resolve().parents[1] / "healthaio" / "web"


class Demo(unittest.TestCase):
    """A fresh demo folder per test: each one writes to its goals.jsonl."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-test-"))
        try:
            self.cfg = config.load(demo.generate(self.tmp, TODAY, NOW))
        except config.ConfigError:
            raise unittest.SkipTest("needs Python 3.11+ or tomli")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def goals(self):
        return payload(self.cfg, "goals", None, NOW)

    def row(self, key):
        return next(r for r in self.goals()["rows"] if r["key"] == key)


class Log(Demo):
    def test_a_goal_set_here_is_laid_over_the_file_and_null_takes_it_back(self):
        goal_log.append(self.cfg, "set", changes={"food.kcal_max": 2200, "sleep.target_hours": 7.5}, now=NOW)
        applied = goal_log.apply(self.cfg)
        self.assertEqual((applied.food.kcal_max, applied.sleep.target_hours), (2200, 7.5))
        self.assertEqual(self.cfg.food.kcal_max, 2300)  # the loaded file is not touched
        self.assertIn("kcal_max = 2300", (self.tmp / "healthaio.toml").read_text())
        goal_log.append(self.cfg, "set", changes={"food.kcal_max": None}, now=NOW)
        self.assertEqual(goal_log.apply(self.cfg).food.kcal_max, 2300)
        lines = (self.tmp / goal_log.FILENAME).read_text().splitlines()
        self.assertEqual(len(lines), 3)  # the demo's proposal, then both changes: append only

    def test_a_proposal_changes_nothing_until_accepted(self):
        entry = goal_log.append(self.cfg, "propose", "assistant", changes={"exercise.weekly_min": 180}, note="why", now=NOW)
        self.assertEqual(goal_log.apply(self.cfg).exercise.weekly_min, 150)
        self.assertIn(entry["id"], [p["id"] for p in goal_log.apply(self.cfg).goals_proposed])
        goal_log.append(self.cfg, "accept", ref=entry["id"], now=NOW)
        applied = goal_log.apply(self.cfg)
        self.assertEqual(applied.exercise.weekly_min, 180)
        self.assertTrue(applied.goals_set["exercise.weekly_min"]["accepted"])
        self.assertNotIn(entry["id"], [p["id"] for p in applied.goals_proposed])
        with self.assertRaises(goal_log.GoalError):
            goal_log.append(self.cfg, "decline", ref=entry["id"])  # already answered

    def test_a_declined_proposal_is_gone_and_changed_nothing(self):
        goal_log.append(self.cfg, "decline", ref="5a3e0c1d", now=NOW)  # the demo's own proposal
        applied = goal_log.apply(self.cfg)
        self.assertEqual(applied.goals_proposed, [])
        self.assertEqual(applied.screen.entertainment_max_hours, 3)

    def test_values_that_make_no_sense_are_refused(self):
        for changes in ({"food.kcal_maximum": 2000}, {"sleep.target_hours": 20}, {"sleep.bedtime": "25:00"},
                        {"exercise.strength_days": 2.5}, {"food.kcal_max": "2000"}, {"food.kcal_min": 2500},
                        {"weight.target_kg": 90}, {}):
            with self.assertRaises(goal_log.GoalError, msg=changes):
                goal_log.append(self.cfg, "set", changes=changes)
        self.assertEqual(len(goal_log.read(self.cfg)), 1)  # nothing written but the demo's proposal

    def test_protein_per_kg_set_here_replaces_a_fixed_amount_in_the_file(self):
        self.cfg.food.protein_g = 120
        goal_log.append(self.cfg, "set", changes={"food.protein_g_per_kg": 1.8}, now=NOW)
        food = goal_log.apply(self.cfg).food
        self.assertEqual((food.protein_g, food.protein_g_per_kg), (None, 1.8))

    def test_a_weight_plan_can_start_here_from_the_latest_weight(self):
        self.cfg.weight = None
        goal_log.append(self.cfg, "set", changes={"weight.target_kg": 70}, now=NOW)
        weight = goal_log.apply(self.cfg).weight
        self.assertEqual(weight.target_kg, 70)
        self.assertLess(70, weight.start_kg)
        self.assertLessEqual(weight.start_date, TODAY)

    def test_unreadable_lines_are_skipped(self):
        with (self.tmp / goal_log.FILENAME).open("a") as out:
            out.write("not json\n[1, 2]\n{\"op\": \"explode\"}\n")
        goal_log.append(self.cfg, "set", changes={"screen.work_min_hours": 5}, now=NOW)
        self.assertEqual(goal_log.apply(self.cfg).screen.work_min_hours, 5)


class GoalsPage(Demo):
    def test_each_goal_names_the_fields_that_set_it(self):
        self.assertEqual([f["field"] for f in self.row("kcal_range")["edit"]], ["food.kcal_min", "food.kcal_max"])
        self.assertEqual(self.row("weekly_min")["edit"][0]["value"], 150)
        self.assertEqual(self.row("calm_last_hour")["edit"], [])  # a built-in rule
        self.assertEqual(self.row("asleep_in_time")["edit"], [])  # the demo's alarm ladder moves it
        for r in self.goals()["rows"]:
            for f in r["edit"]:
                self.assertIn(f["field"], goal_log.FIELDS)

    def test_a_goal_set_here_is_marked_and_used(self):
        goal_log.append(self.cfg, "set", changes={"screen.entertainment_max_hours": 2}, now=NOW)
        row = self.row("fun_max")
        self.assertEqual(row["target"], {"hours": 2})
        self.assertEqual(row["set_here"]["by"], "you")
        self.assertFalse(row["set_here"]["accepted"])
        self.assertNotIn("set_here", self.row("focus_min"))

    def test_the_demo_has_one_proposal_waiting(self):
        (proposal,) = self.goals()["proposals"]
        self.assertEqual(proposal["by"], "assistant")
        self.assertEqual(proposal["changes"][0]["field"], "screen.entertainment_max_hours")
        self.assertEqual((proposal["changes"][0]["value"], proposal["changes"][0]["to"]), (3, 2.5))
        self.assertEqual(set(proposal["note"]), {"en", "zh"})


class Endpoint(Demo):
    def setUp(self):
        super().setUp()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.cfg, lambda: NOW))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        super().tearDown()

    def post(self, body, origin="same", kind="application/json", path="/api/goals"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        headers = {"Content-Type": kind}
        if origin:
            headers["Origin"] = f"http://127.0.0.1:{self.port}" if origin == "same" else origin
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    def test_the_app_can_set_a_goal_and_every_page_sees_it(self):
        status, out = self.post({"op": "set", "changes": {"food.kcal_max": 2100}})
        self.assertEqual((status, out["ok"]), (200, True))
        goals = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/goals", timeout=10).read())
        row = next(r for r in goals["rows"] if r["key"] == "kcal_range")
        self.assertEqual(row["target"]["high"], 2100)
        self.assertEqual(row["set_here"]["by"], "you")

    def test_the_app_can_answer_a_proposal(self):
        self.assertEqual(self.post({"op": "accept", "id": "5a3e0c1d"})[0], 200)
        self.assertEqual(goal_log.apply(self.cfg).screen.entertainment_max_hours, 2.5)

    def test_only_this_apps_own_page_may_write(self):
        before = (self.tmp / goal_log.FILENAME).read_text()
        set_kcal = {"op": "set", "changes": {"food.kcal_max": 2100}}
        self.assertEqual(self.post(set_kcal, origin=None)[0], 403)
        self.assertEqual(self.post(set_kcal, origin="https://example.com")[0], 403)
        self.assertEqual(self.post(set_kcal, kind="text/plain")[0], 403)  # a form or a no-cors fetch from elsewhere
        self.assertEqual(self.post(set_kcal, path="/api/today")[0], 404)
        self.assertEqual(self.post({"op": "propose", "changes": {"food.kcal_max": 2100}})[0], 400)  # assistants use the CLI
        self.assertEqual(self.post({"op": "set", "changes": {"food.kcal_max": 99999}})[0], 400)
        self.assertEqual(self.post(b"{not json")[0], 400)
        self.assertEqual((self.tmp / goal_log.FILENAME).read_text(), before)


class CommandLine(Demo):
    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = main(["--config", str(self.tmp / "healthaio.toml"), "goal", *args])
        return code, out.getvalue()

    def test_an_assistant_proposes_and_you_accept(self):
        code, out = self.run_cli("propose", "exercise.weekly_min", "200", "sleep.bedtime", "23:15", "--note", "why", "--by", "claude")
        self.assertEqual(code, 0)
        entry = json.loads(out)
        self.assertEqual((entry["by"], entry["changes"]), ("claude", {"exercise.weekly_min": 200, "sleep.bedtime": "23:15"}))
        code, out = self.run_cli("list", "--json")
        self.assertIn(entry["id"], [p["id"] for p in json.loads(out)["proposals"]])
        self.assertEqual(self.run_cli("accept", entry["id"])[0], 0)
        self.assertEqual(goal_log.apply(self.cfg).exercise.weekly_min, 200)
        self.assertEqual(self.run_cli("set", "food.kcal_max", "lots")[0], 2)
        self.assertEqual(self.run_cli("set", "food.kcal_max")[0], 2)  # a field without its value


class Web(unittest.TestCase):
    def test_every_field_and_short_name_has_words_in_both_languages(self):
        i18n = (WEB / "js" / "i18n.js").read_text(encoding="utf-8")
        for name in goal_log.FIELDS:
            self.assertEqual(i18n.count(f'"goals.f.{name}"'), 2, name)
            unit = goal_log.FIELDS[name].get("unit")
            if unit:
                self.assertEqual(i18n.count(f'"goals.u.{unit}"'), 2, unit)
        app = (WEB / "js" / "app.js").read_text(encoding="utf-8")
        for item in re.findall(r'"(\w+)"', re.search(r"const NAV\s*=\s*\[([^\]]*)\]", app).group(1)):
            self.assertEqual(i18n.count(f'"nav.short.{item}"'), 2, item)

    def test_the_static_demo_shows_the_form_but_never_posts(self):
        goals = (WEB / "js" / "pages" / "goals.js").read_text(encoding="utf-8")
        self.assertIn("if (isStatic) return;", goals)
        self.assertIn('"goals.static"', goals)


if __name__ == "__main__":
    unittest.main()
