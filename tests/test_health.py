"""The proactive-health pages: Food, Exercise, Goals, and what the Today page tells you to adjust.

Rules under test (healthaio/modules/food.py, exercise.py, goals.py, actions.py):
- a food day counts only with two main meals; fewer is shown, not averaged; no rows is unknown, never zero
- a meal before 4 am belongs to the day before; the late-meal check is night by night, on logged days only
- the exercise goal falls back to the WHO guideline and says so; kinds of training come from the workout type
- goals count days with a record, so a day without one is never a missed day; unset plans are listed
- at most one adjustment each for training, sleep and food; none without the data to back it
"""
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from healthaio import config, demo
from healthaio.config import Config, FoodPlan
from healthaio.context import Context
from healthaio.modules import actions, exercise, food, goals, today
from healthaio.server import payload
from healthaio.store import write_table

TODAY = date(2026, 10, 12)
NOW = datetime(2026, 10, 12, 18, 40)


def meal(day, hhmm, kind, kcal=600, protein=30):
    hh, mm = map(int, hhmm.split(":"))
    return {"time": datetime.combine(day, datetime.min.time()).replace(hour=hh, minute=mm), "meal": kind,
            "kcal": kcal, "protein_g": protein, "carbs_g": 60, "fat_g": 20, "fiber_g": 6}


class Folder(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-health-"))
        self.cfg = Config(root=self.tmp, data_dir=self.tmp, timezone="Australia/Melbourne")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ctx(self):
        return Context(self.cfg, now=NOW)


class FoodDays(Folder):
    def test_one_main_meal_is_shown_but_not_counted_and_no_rows_is_unknown(self):
        d1, d2 = TODAY - timedelta(days=2), TODAY - timedelta(days=1)
        write_table(self.tmp, "meals", [meal(d1, "12:30", "lunch"), meal(d1, "19:00", "dinner"),
                                        meal(d2, "13:00", "lunch", kcal=400)])
        days = food.food_days(self.ctx(), TODAY)
        self.assertTrue(days[d1]["full"])
        self.assertFalse(days[d2]["full"])  # one meal written down is not a day of eating one meal
        self.assertNotIn(TODAY - timedelta(days=3), days)  # not logged: absent, never a zero-calorie day
        self.assertEqual(days[d1]["kcal"], 1200)

    def test_a_meal_before_4_am_belongs_to_the_evening_before(self):
        d = TODAY - timedelta(days=2)
        write_table(self.tmp, "body_daily", [{"date": d + timedelta(days=1), "sleep_start": datetime.combine(d + timedelta(days=1), datetime.min.time()).replace(hour=1, minute=30),
                                              "sleep_end": datetime.combine(d + timedelta(days=1), datetime.min.time()).replace(hour=9)}])
        write_table(self.tmp, "meals", [meal(d, "12:30", "lunch"), meal(d, "19:00", "dinner"), meal(d + timedelta(days=1), "00:45", "snack", kcal=300)])
        days = food.food_days(self.ctx(), TODAY)
        self.assertEqual(len(days[d]["meals"]), 3)
        self.assertAlmostEqual(days[d]["gap_h"], 0.75)  # the snack at 00:45, asleep at 01:30
        self.assertTrue(days[d]["late"])
        self.assertNotIn(d + timedelta(days=1), days)

    def test_a_date_without_a_time_stays_on_its_day_and_out_of_the_timing(self):
        d = TODAY - timedelta(days=2)
        midnight = datetime.combine(d, datetime.min.time())
        write_table(self.tmp, "meals", [{"time": midnight, "meal": "lunch", "kcal": 700}, {"time": midnight, "meal": "dinner", "kcal": 900}])
        days = food.food_days(self.ctx(), TODAY)
        self.assertTrue(days[d]["full"])
        self.assertIsNone(days[d]["gap_h"])

    def test_protein_target_from_grams_per_kilogram_of_the_latest_weight(self):
        self.cfg.food = FoodPlan(protein_g_per_kg=1.6)
        write_table(self.tmp, "body_daily", [{"date": TODAY - timedelta(days=k), "weight_kg": 80.0} for k in range(5)])
        self.assertAlmostEqual(food.protein_target(self.ctx(), TODAY)["grams"], 128)

    def test_late_meals_are_judged_night_by_night_not_by_their_average(self):
        self.cfg.food = FoodPlan(last_meal_gap_h=3)
        body, meals = [], []
        for k in range(1, 8):
            d = TODAY - timedelta(days=k)
            asleep = datetime.combine(d, datetime.min.time()).replace(hour=23, minute=30)
            body.append({"date": d + timedelta(days=1), "sleep_start": asleep, "sleep_end": asleep + timedelta(hours=8)})
            # two late nights (a 22:30 dinner), five early ones (18:00): the average gap is well over 3 hours
            meals += [meal(d, "12:30", "lunch"), meal(d, "22:30" if k in (1, 2) else "18:00", "dinner")]
        write_table(self.tmp, "body_daily", body)
        write_table(self.tmp, "meals", meals)
        page = food.build(self.ctx())
        gap = next(r for r in page["rows"] if r["key"] == "gap_h")
        self.assertGreater(gap["value"], 3)
        self.assertEqual(gap["plan_state"], "below")
        self.assertEqual(gap["late"], {"days": 2, "known": 7})  # last night's sleep ended this morning: already in
        self.assertIn("gap_h", page["off"])


class Exercise(Folder):
    def test_kind_of_training_from_its_type(self):
        cases = {"strength training": "strength", "functional strength training": "strength", "running": "cardio",
                 "HIIT": "cardio", "walking": "walk", "hiking": "walk", "yoga": "other", "badminton": "other"}
        for text, kind in cases.items():
            self.assertEqual(exercise.kind_of(text), kind, text)

    def test_goal_says_whether_it_is_the_guideline_or_your_plan(self):
        self.assertEqual(exercise.goal(self.cfg), {"weekly_min": 150.0, "strength_days": 2, "source": "guideline"})
        self.cfg.exercise.weekly_min = 200
        self.assertEqual(exercise.goal(self.cfg)["source"], "plan")
        self.assertEqual(exercise.goal(self.cfg)["strength_days"], 2)

    def test_active_minutes_take_the_ring_and_fall_back_on_workouts(self):
        d1, d2 = TODAY - timedelta(days=2), TODAY - timedelta(days=1)
        write_table(self.tmp, "body_daily", [{"date": d1, "exercise_min": 45}])
        start = datetime.combine(d2, datetime.min.time()).replace(hour=18)
        write_table(self.tmp, "workouts", [{"start": start, "end": start + timedelta(minutes=30), "type": "running"}])
        minutes = exercise.active_minutes(self.ctx(), TODAY)
        self.assertEqual(minutes, {d1: 45.0, d2: 30.0})

    def test_what_today_needs_is_the_rest_of_the_week_shared_out(self):
        # Monday 12 Oct: nothing yet this week, 150 minutes over 7 days
        write_table(self.tmp, "body_daily", [{"date": TODAY - timedelta(days=k), "exercise_min": 20} for k in range(1, 8)])
        week = exercise.week_status(self.ctx(), TODAY)
        self.assertEqual(week["days_left"], 7)
        self.assertAlmostEqual(week["need_today_min"], 150 / 7)
        self.assertEqual(week["status"], "on_track")


class Goals(Folder):
    def test_unset_plans_are_listed_with_their_section(self):
        page = goals.build(self.ctx())
        unset = {r["key"]: r["section"] for r in page["rows"] if r["kind"] == "unset"}
        self.assertEqual(unset, {"asleep_in_time": "plan.sleep", "kcal_range": "plan.food", "protein": "plan.food",
                                 "weight_pace": "plan.weight", "focus_min": "plan.screen", "fun_max": "plan.screen"})

    def test_a_day_without_a_record_is_not_a_missed_day(self):
        write_table(self.tmp, "body_daily", [{"date": TODAY - timedelta(days=k), "sleep_min": 480} for k in (0, 1, 3)])
        row = next(r for r in goals.build(self.ctx())["rows"] if r["key"] == "slept_enough")
        self.assertEqual((row["kept"], row["known"]), (3, 3))
        self.assertEqual(len(row["days"]), goals.DAYS)


class Adjustments(Folder):
    def test_an_empty_folder_gets_a_steady_day_not_invented_advice(self):
        rec = today.recovery(self.ctx(), TODAY)
        out = actions.build(self.ctx(), TODAY, rec, {"worse": []})
        self.assertTrue(out["steady"])
        self.assertEqual(out["items"], [])


class Demo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="healthaio-health-demo-"))
        try:
            cls.cfg = config.load(demo.generate(cls.tmp, TODAY, NOW))
        except config.ConfigError:
            raise unittest.SkipTest("needs Python 3.11+ or tomli to read the demo healthaio.toml")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_sam_gets_one_thing_each_for_training_sleep_and_food(self):
        page = payload(self.cfg, "today", None, NOW)
        items = page["actions"]["items"]
        self.assertEqual([x["domain"] for x in items], ["training", "sleep", "food"])
        # recovery below normal with strength planned; a short night; late snacks before deadlines
        self.assertEqual([x["key"] for x in items], ["ease", "asleep_by", "late_meal"])
        self.assertIsNone(payload(self.cfg, "today", (TODAY - timedelta(days=1)).isoformat(), NOW)["actions"])

    def test_an_early_dinner_shows_up_in_the_next_mornings_hrv(self):
        # the demo person's HRV pays for a late snack; the Food page and Today's list must find it
        page = payload(self.cfg, "food", None, NOW)
        self.assertTrue(page["effect"]["hrv"]["detected"])
        self.assertGreater(page["effect"]["hrv"]["diff"], 0)

    def test_new_pages_build_for_every_pre_rendered_day(self):
        for name in ("food", "exercise", "goals"):
            data = payload(self.cfg, name, None, NOW)
            self.assertEqual(data["page"], name)
        self.assertEqual(payload(self.cfg, "exercise", None, NOW)["goal"]["source"], "plan")


if __name__ == "__main__":
    unittest.main()
