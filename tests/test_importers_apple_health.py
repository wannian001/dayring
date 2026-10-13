import csv
import shutil
import tempfile
import unittest
import zipfile
from datetime import date, datetime
from pathlib import Path

from healthaio.config import Config
from healthaio.importers import apple_health
from healthaio.store import Store

FIXTURE = Path(__file__).parent / "fixtures" / "apple_health_export.xml"
TZ = "Australia/Melbourne"


def make_cfg(folder: Path) -> Config:
    return Config(root=folder, data_dir=folder / "data", timezone=TZ)


class AppleHealthReadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = make_cfg(Path(tempfile.gettempdir()))
        rows, cls.summary = apple_health.read_export(FIXTURE, cfg.tz)
        cls.rows = {row["date"]: row for row in rows}

    def test_days(self):
        self.assertEqual(sorted(self.rows), [date(2026, 10, 4), date(2026, 10, 9), date(2026, 10, 10),
                                             date(2026, 10, 11), date(2026, 10, 12)])
        self.assertEqual(self.summary.problems, [])

    def test_sleep_crossing_midnight_prefers_watch(self):
        row = self.rows[date(2026, 10, 11)]
        self.assertAlmostEqual(row["sleep_min"], 450)      # watch stages only, nap not added
        self.assertAlmostEqual(row["in_bed_min"], 510)     # phone in-bed record
        self.assertEqual(row["sleep_start"], datetime(2026, 10, 10, 23, 20))
        self.assertEqual(row["sleep_end"], datetime(2026, 10, 11, 7, 0))

    def test_hk_timezone_wins_over_export_offset(self):
        row = self.rows[date(2026, 10, 4)]
        self.assertAlmostEqual(row["sleep_min"], 450)
        self.assertEqual(row["sleep_start"], datetime(2026, 10, 3, 23, 0))
        self.assertEqual(row["sleep_end"], datetime(2026, 10, 4, 6, 30))
        self.assertAlmostEqual(row["hrv_ms"], 45)
        self.assertNotIn(date(2026, 10, 5), self.rows)

    def test_steps_not_double_counted(self):
        self.assertEqual(self.rows[date(2026, 10, 11)]["steps"], 4950)

    def test_daily_values(self):
        row = self.rows[date(2026, 10, 11)]
        self.assertAlmostEqual(row["hrv_ms"], 50)
        self.assertAlmostEqual(row["resting_hr"], 56)
        self.assertAlmostEqual(row["exercise_min"], 40)
        self.assertAlmostEqual(row["weight_kg"], 164 * 0.45359237)
        self.assertAlmostEqual(self.rows[date(2026, 10, 10)]["weight_kg"], 75.2)

    def test_workouts(self):
        self.assertAlmostEqual(self.rows[date(2026, 10, 11)]["workout_min"], 65)
        self.assertEqual(self.rows[date(2026, 10, 11)]["workout_type"], "strength training")
        self.assertEqual(self.rows[date(2026, 10, 9)]["workout_type"], "walking")
        self.assertEqual(self.rows[date(2026, 10, 10)]["workout_min"], 0)   # rest day
        self.assertIsNone(self.rows[date(2026, 10, 4)]["workout_min"])     # before any workout: unknown

    def test_complete_flag(self):
        self.assertFalse(self.rows[date(2026, 10, 12)]["complete"])
        self.assertEqual(self.rows[date(2026, 10, 12)]["steps"], 500)
        self.assertTrue(self.rows[date(2026, 10, 11)]["complete"])

    def test_workout_type_cleaning(self):
        self.assertEqual(apple_health.clean_workout_type("HKWorkoutActivityTypeTraditionalStrengthTraining"),
                         "strength training")
        self.assertEqual(apple_health.clean_workout_type("HKWorkoutActivityTypeTableTennis"), "table tennis")


class AppleHealthImportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = make_cfg(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_zip_and_merge(self):
        archive = self.tmp / "export.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
            handle.writestr("apple_health_export/export_cda.xml", "<ClinicalDocument/>")
            handle.write(FIXTURE, "apple_health_export/export.xml")
        self.cfg.data_dir.mkdir()
        existing = self.cfg.data_dir / "body_daily.csv"
        existing.write_text("date,weight_kg,waist_cm\n"
                            "2026-09-01,76,82\n"        # not in the export: kept
                            "2026-10-04,76.5,81\n"      # export has no weight that day: kept
                            "2026-10-11,70,80\n"        # export weight wins, waist kept
                            "not-a-date,1,1\n", encoding="utf-8")
        summary = apple_health.import_apple_health(archive, self.cfg)
        self.assertEqual(summary.imported, 5)
        loaded = Store(self.cfg.data_dir).load("body_daily")
        rows = {r["date"]: r for r in loaded.rows}
        self.assertEqual(rows[date(2026, 9, 1)]["weight_kg"], 76)
        self.assertEqual(rows[date(2026, 10, 4)]["weight_kg"], 76.5)
        self.assertAlmostEqual(rows[date(2026, 10, 4)]["sleep_min"], 450)
        self.assertAlmostEqual(rows[date(2026, 10, 11)]["weight_kg"], 74.39)
        self.assertEqual(rows[date(2026, 10, 11)]["waist_cm"], 80)
        self.assertEqual(rows[date(2026, 10, 11)]["steps"], 4950)
        self.assertEqual(len(loaded.problems), 1)  # the broken line is kept for the user to fix
        with existing.open(encoding="utf-8") as handle:
            self.assertEqual(list(csv.reader(handle))[-1][0], "not-a-date")

    def test_missing_file(self):
        with self.assertRaises(apple_health.HealthExportError):
            apple_health.read_export(self.tmp / "nope.zip", self.cfg.tz)

    def test_zip_without_export(self):
        archive = self.tmp / "other.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("notes.txt", "hello")
        with self.assertRaises(apple_health.HealthExportError):
            apple_health.read_export(archive, self.cfg.tz)


class TimeParsingTest(unittest.TestCase):
    def test_parse_time(self):
        moment = apple_health.parse_time("2026-10-12 07:50:00 +1100")
        self.assertEqual(moment.utcoffset().total_seconds(), 11 * 3600)
        self.assertEqual(moment.hour, 7)
        self.assertEqual(apple_health.parse_time("2026-10-12 07:50:00 -0230").utcoffset().total_seconds(),
                         -(2 * 3600 + 30 * 60))
        self.assertIsNone(apple_health.parse_time("garbage"))


if __name__ == "__main__":
    unittest.main()
