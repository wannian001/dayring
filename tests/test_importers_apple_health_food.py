"""meals.csv and the energy columns from Apple Health: dietary records grouped into meals, one app per meal, units,
the meal from metadata or the clock, active and resting energy without double counting, workout heart rate, and
re-imports that keep meals typed by hand."""
import shutil
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from healthaio.config import Config
from healthaio.importers import apple_health
from healthaio.store import Store, write_table

TZ = "Australia/Melbourne"
HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n<HealthData locale="en_AU">\n <ExportDate value="2026-10-12 21:00:00 +1100"/>\n'
FOOD = "HKQuantityTypeIdentifierDietary"


def record(kind, start, value, unit, source="Food log", meta=None, end=None):
    inner = "".join(f'<MetadataEntry key="{k}" value="{v}"/>' for k, v in (meta or {}).items())
    return (f' <Record type="{kind}" sourceName="{source}" unit="{unit}" startDate="{start}" endDate="{end or start}" '
            f'value="{value}">{inner}</Record>\n')


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="healthaio-ahf-"))
        self.cfg = Config(root=self.tmp, data_dir=self.tmp / "data", timezone=TZ)
        self.cfg.data_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_import(self, body):
        path = self.tmp / "export.xml"
        path.write_text(HEAD + body + "</HealthData>\n", encoding="utf-8")
        return apple_health.import_apple_health(path, self.cfg)

    def meals(self):
        loaded = Store(self.cfg.data_dir).load("meals")
        self.assertEqual(loaded.problems, [])
        return loaded.rows


class Meals(Case):
    def test_records_of_one_minute_are_one_meal(self):
        at = "2026-10-11 12:40:00 +1100"
        summary = self.run_import(
            record(f"{FOOD}EnergyConsumed", at, 2510, "kJ", meta={"HKFoodType": "Chicken rice bowl"})
            + record(f"{FOOD}Protein", at, 38, "g") + record(f"{FOOD}Carbohydrates", at, 70, "g")
            + record(f"{FOOD}FatTotal", at, 15000, "mg") + record(f"{FOOD}Fiber", at, 6, "g"))
        self.assertEqual(summary.problems, [])
        [meal] = self.meals()
        self.assertEqual(meal["time"], datetime(2026, 10, 11, 12, 40))
        self.assertEqual(meal["meal"], "lunch")  # no metadata: from the clock
        self.assertEqual(meal["title"], "Chicken rice bowl")
        self.assertAlmostEqual(meal["kcal"], 600, places=0)  # kJ -> kcal
        self.assertEqual((meal["protein_g"], meal["carbs_g"], meal["fat_g"], meal["fiber_g"]), (38, 70, 15, 6))  # mg -> g
        self.assertTrue(any("1 meals" in n for n in summary.notes), summary.notes)

    def test_two_apps_writing_the_same_meal_count_once(self):
        at = "2026-10-11 19:05:00 +1100"
        self.run_import(record(f"{FOOD}EnergyConsumed", at, 700, "kcal", source="App A")
                        + record(f"{FOOD}EnergyConsumed", at, 650, "kcal", source="App B"))
        [meal] = self.meals()
        self.assertEqual((meal["kcal"], meal["source"], meal["meal"]), (700, "App A", "dinner"))

    def test_metadata_names_the_meal_and_the_clock_fills_in(self):
        self.run_import(record(f"{FOOD}EnergyConsumed", "2026-10-11 16:00:00 +1100", 300, "kcal", meta={"meal": "Lunch"})
                        + record(f"{FOOD}EnergyConsumed", "2026-10-11 08:10:00 +1100", 350, "kcal")
                        + record(f"{FOOD}EnergyConsumed", "2026-10-11 23:30:00 +1100", 250, "kcal"))
        got = {(m["time"].hour, m["meal"]) for m in self.meals()}
        self.assertEqual(got, {(16, "lunch"), (8, "breakfast"), (23, "snack")})

    def test_reimport_keeps_a_meal_typed_by_hand(self):
        write_table(self.cfg.data_dir, "meals", [
            {"time": datetime(2026, 10, 10, 13, 0), "meal": "lunch", "title": "Typed", "kcal": 500, "source": None},
            {"time": datetime(2026, 10, 11, 12, 0), "meal": "lunch", "title": "Old copy", "kcal": 400, "source": "Food log"},
        ])
        self.run_import(record(f"{FOOD}EnergyConsumed", "2026-10-11 09:00:00 +1100", 300, "kcal")
                        + record(f"{FOOD}EnergyConsumed", "2026-10-11 19:00:00 +1100", 600, "kcal"))
        titles = sorted((m["title"] or "", m["kcal"]) for m in self.meals())
        # the hand-typed row stays; the food app's old row inside the export's range is replaced by the export
        self.assertEqual(titles, [("", 300), ("", 600), ("Typed", 500)])


class Energy(Case):
    def test_active_and_resting_energy_by_day_without_double_counting(self):
        watch = "Sam's Apple Watch"
        body = (record("HKQuantityTypeIdentifierActiveEnergyBurned", "2026-10-11 10:00:00 +1100", 300, "kcal", source=watch,
                       end="2026-10-11 11:00:00 +1100")
                + record("HKQuantityTypeIdentifierActiveEnergyBurned", "2026-10-11 10:00:00 +1100", 280, "kcal", source="Sam's iPhone",
                         end="2026-10-11 11:00:00 +1100")
                + record("HKQuantityTypeIdentifierActiveEnergyBurned", "2026-10-11 15:00:00 +1100", 418.4, "kJ", source=watch,
                         end="2026-10-11 15:30:00 +1100")
                + record("HKQuantityTypeIdentifierBasalEnergyBurned", "2026-10-11 00:00:00 +1100", 1650, "kcal", source=watch,
                         end="2026-10-11 23:59:00 +1100"))
        self.run_import(body)
        row = Store(self.cfg.data_dir).by_date("body_daily")[date(2026, 10, 11)]
        self.assertEqual(row["active_kcal"], 400)  # the phone's copy of the same hour is not added; kJ -> kcal
        self.assertEqual(row["basal_kcal"], 1650)

    def test_workout_average_heart_rate(self):
        stats = '<WorkoutStatistics type="HKQuantityTypeIdentifierHeartRate" average="131.6" minimum="90" maximum="160" unit="count/min"/>'
        self.run_import(' <Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="30" durationUnit="min" '
                        'sourceName="Sam\'s Apple Watch" startDate="2026-10-11 18:00:00 +1100" endDate="2026-10-11 18:30:00 +1100">'
                        f'{stats}</Workout>\n')
        [w] = Store(self.cfg.data_dir).rows("workouts")
        self.assertEqual(w["avg_hr"], 132)


if __name__ == "__main__":
    unittest.main()
